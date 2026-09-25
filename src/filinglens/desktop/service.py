"""Read-only research data and scoped AI orchestration for the desktop UI."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import math
import threading
import time
from typing import Any

import pandas as pd

from filinglens.analytics.anomalies import detect_anomalies
from filinglens.analytics.normalize import financials_wide
from filinglens.analytics.ratios import calculate_ratios
from filinglens.config import Settings
from filinglens.documents.chunking import chunk_sections
from filinglens.documents.parser import clean_filing_html
from filinglens.documents.retrieval import LocalRetriever
from filinglens.documents.sections import extract_sections
from filinglens.llm.analyst_brief import generate_analyst_brief
from filinglens.llm.grounded_qa import ask_filing
from filinglens.llm.lmstudio import LMStudioProvider
from filinglens.llm.cloud import CloudProvider
from filinglens.llm.ollama import OllamaProvider, free_credit_cloud_models
from filinglens.sec.client import SECClient, SECClientError
from filinglens.sec.composition import compose_income, revenue_disaggregations, select_filing_income_facts
from filinglens.sec.companies import CompanyDirectory, normalize_ticker
from filinglens.sec.insiders import fetch_insider_activity
from filinglens.sec.submissions import latest_filing, parse_recent_filings
from filinglens.sec.xbrl import select_annual_facts, select_quarterly_facts
from filinglens.ui.components import (
    LABELS, METRIC_FORMULAS, anomaly_change_presentation,
    anomaly_summary_text, human_currency, metric_component_table,
    metric_display_value, metric_latest_change, period_delta, ratio_display,
    verified_metrics_text,
)

STATEMENT_GROUPS: dict[str, list[tuple[str, list[str]]]] = {
    "income": [
        ("Revenue & gross profit", ["revenue", "cost_of_revenue", "gross_profit"]),
        ("Earnings", ["operating_income", "net_income"]),
    ],
    "balance": [
        ("Assets", ["cash", "current_assets", "total_assets"]),
        ("Liabilities & equity", ["current_liabilities", "total_liabilities", "long_term_debt", "stockholders_equity"]),
    ],
    "cash": [("Cash generation & investment", ["operating_cash_flow", "capital_expenditures", "free_cash_flow"])],
    "ratios": [
        ("Growth", ["revenue_growth", "operating_income_growth", "net_income_growth", "operating_cash_flow_growth", "free_cash_flow_growth"]),
        ("Margins", ["gross_margin", "operating_margin", "net_margin", "operating_cash_flow_margin", "free_cash_flow_margin"]),
        ("Returns", ["return_on_assets", "return_on_equity"]),
        ("Liquidity & leverage", ["current_ratio", "debt_to_assets", "debt_to_equity"]),
    ],
}
FEATURED_METRICS = {"revenue", "operating_income", "net_income", "free_cash_flow", "total_assets", "operating_cash_flow", "gross_margin", "revenue_growth"}


def finite(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


class ResearchService:
    def __init__(self) -> None:
        self._company_cache: dict[tuple[str, int], tuple[float, dict[str, Any]]] = {}
        self._retrieval_cache: dict[str, tuple[LocalRetriever, dict[str, str]]] = {}
        self._composition_cache: dict[str, dict[str, Any]] = {}
        self._directory: dict[str, Any] | None = None
        self._lock = threading.RLock()

    def search(self, query: str) -> list[dict[str, str]]:
        term = query.strip().upper()
        if len(term) < 2:
            return []
        settings = Settings.from_env()
        settings.validate_sec()
        with self._lock:
            directory = self._directory
        if directory is None:
            with SECClient(settings.sec_user_agent, settings.cache_dir,
                           min_interval=settings.request_interval_seconds,
                           timeout=settings.request_timeout_seconds) as client:
                directory = CompanyDirectory(client).all()
            with self._lock:
                self._directory = directory
        ranked = []
        for company in directory.values():
            name = company.name.upper()
            if company.ticker == term:
                rank = 0
            elif company.ticker.startswith(term):
                rank = 1
            elif name.startswith(term):
                rank = 2
            elif term in name:
                rank = 3
            else:
                continue
            ranked.append((rank, len(company.name), company.ticker, company))
        ranked.sort(key=lambda item: (item[0], item[1], item[2]))
        return [asdict(item[3]) for item in ranked[:8]]

    def _load(self, ticker: str, years: int, refresh: bool = False) -> dict[str, Any]:
        ticker = normalize_ticker(ticker)
        if not 3 <= years <= 10:
            raise ValueError("Historical periods must be between 3 and 10.")
        key = (ticker, years)
        with self._lock:
            hit = self._company_cache.get(key)
            if hit and not refresh and time.monotonic() - hit[0] < 3600:
                return hit[1]
        settings = Settings.from_env()
        settings.validate_sec()
        settings.ensure_directories()
        with SECClient(settings.sec_user_agent, settings.cache_dir,
                       min_interval=settings.request_interval_seconds,
                       timeout=settings.request_timeout_seconds) as client:
            company = CompanyDirectory(client).lookup(ticker, refresh=refresh)
            submissions = client.submissions(company.cik, refresh=refresh)
            company_facts = client.company_facts(company.cik, refresh=refresh)
            facts = select_annual_facts(company_facts, ticker)
            quarter = latest_filing(submissions, "10-Q")
            quarterly_facts = (select_quarterly_facts(company_facts, ticker, quarter.accession_number, quarter.report_date)
                               if quarter else pd.DataFrame())
        facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{company.cik}.json"
        cache_file = settings.cache_dir / f"{hashlib.sha256(facts_url.encode()).hexdigest()}.json"
        facts_cached_at = (datetime.fromtimestamp(cache_file.stat().st_mtime, timezone.utc).isoformat()
                           if cache_file.exists() else None)
        financials = financials_wide(facts).tail(years)
        ratios = calculate_ratios(financials)
        anomalies = detect_anomalies(pd.concat([financials, ratios], axis=1))
        bundle = {"company": company, "submissions": submissions, "facts": facts,
                  "quarterly_facts": quarterly_facts,
                  "financials": financials, "ratios": ratios, "anomalies": anomalies,
                  "facts_cached_at": facts_cached_at}
        with self._lock:
            self._company_cache[key] = (time.monotonic(), bundle)
        return bundle

    @staticmethod
    def _filing(record: Any) -> dict[str, str] | None:
        if record is None:
            return None
        return {**asdict(record), "source_url": record.source_url}

    @staticmethod
    def _quarterly_data(facts: pd.DataFrame, filing: Any) -> dict[str, Any] | None:
        if filing is None:
            return None
        definitions = (
            ("Quarter income statement", ("revenue", "cost_of_revenue", "gross_profit", "operating_income", "net_income"), "Three-month period"),
            ("Balance sheet", ("cash", "current_assets", "total_assets", "current_liabilities", "total_liabilities", "long_term_debt", "stockholders_equity"), "As of quarter end"),
            ("Cash flow", ("operating_cash_flow", "capital_expenditures"), "Fiscal year to date"),
        )
        groups = []
        for title, metrics, basis in definitions:
            rows = []
            for metric in metrics:
                match = facts[facts["metric"] == metric] if not facts.empty else pd.DataFrame()
                if match.empty:
                    continue
                fact = match.iloc[0]
                rows.append({"id": metric, "label": LABELS.get(metric, metric),
                             "value": finite(fact["value"]), "display": human_currency(finite(fact["value"])),
                             "period_start": fact["period_start"], "period_end": fact["period_end"],
                             "concept": fact["xbrl_concept"]})
            if rows:
                groups.append({"title": title, "basis": basis, "rows": rows})
        return {"filing": ResearchService._filing(filing), "groups": groups}

    @staticmethod
    def _quarterly_metrics_text(quarterly: dict[str, Any] | None) -> str:
        if not quarterly:
            return "No latest 10-Q is available."
        filing = quarterly["filing"]
        lines = [f"Latest {filing['form']} filed {filing['filing_date']}, report period ended {filing['report_date']}:"]
        for group in quarterly["groups"]:
            for row in group["rows"]:
                lines.append(f"{row['label']} ({group['basis'].lower()}, end {row['period_end']}): {row['display']}")
        if len(lines) == 1:
            lines.append("No confidently matched quarterly US-GAAP values are available.")
        return "\n".join(lines)

    def company(self, ticker: str, years: int = 5, refresh: bool = False) -> dict[str, Any]:
        bundle = self._load(ticker, years, refresh)
        company = bundle["company"]
        financials, ratios, anomalies, facts = (bundle[k] for k in ("financials", "ratios", "anomalies", "facts"))
        latest_year = int(financials.index[-1]) if not financials.empty else None
        k = latest_filing(bundle["submissions"], "10-K")
        q = latest_filing(bundle["submissions"], "10-Q")
        quarterly = self._quarterly_data(bundle.get("quarterly_facts", pd.DataFrame()), q)
        groups: dict[str, list[dict[str, Any]]] = {}
        for statement, definitions in STATEMENT_GROUPS.items():
            source_frame = ratios if statement == "ratios" else financials
            ratio = statement == "ratios"
            sections = []
            for title, metrics in definitions:
                rows = []
                for metric in metrics:
                    if metric not in source_frame.columns:
                        continue
                    series = pd.to_numeric(source_frame[metric], errors="coerce")
                    if not series.notna().any():
                        continue
                    values = [{"year": int(year), "value": finite(value),
                               "display": metric_display_value(metric, value, ratio=ratio)}
                              for year, value in series.items()]
                    available = [(item["year"], item["value"]) for item in values if item["value"] is not None]
                    last_year = available[-1][0] if available else None
                    components = (metric_component_table(financials, metric, last_year).to_dict("records")
                                  if last_year is not None else [])
                    source_fact = facts[(facts["metric"] == metric) & (facts["fiscal_year"] == last_year)] if not ratio and last_year is not None and not facts.empty else pd.DataFrame()
                    provenance = None
                    if not source_fact.empty:
                        fact = source_fact.iloc[-1]
                        provenance = {"concept": str(fact["xbrl_concept"]), "filing_date": str(fact["filing_date"]),
                                      "accession": str(fact["accession_number"])}
                    rows.append({"id": metric, "label": LABELS.get(metric, metric.replace("_", " ").title()),
                                 "values": values, "latest_change": metric_latest_change(source_frame, metric, ratio=ratio),
                                 "ratio": ratio, "featured": metric in FEATURED_METRICS,
                                 "formula": METRIC_FORMULAS.get(metric), "components": components,
                                 "provenance": provenance})
                if rows:
                    sections.append({"title": title, "rows": rows})
            groups[statement] = sections
        latest_flags = anomalies[(anomalies["period"] == latest_year) & anomalies["severity"].isin(["Notable", "Significant"])] if latest_year is not None and not anomalies.empty else pd.DataFrame()
        hero = []
        for metric in ("revenue", "operating_income", "net_income", "free_cash_flow"):
            value = finite(financials.loc[latest_year, metric]) if latest_year is not None and metric in financials else None
            hero.append({"id": metric, "label": LABELS.get(metric, metric), "value": human_currency(value),
                         "change": period_delta(financials, metric)})
        snapshot = []
        for metric in ("revenue_growth", "gross_margin", "operating_margin", "current_ratio", "debt_to_equity"):
            value = finite(ratios.loc[latest_year, metric]) if latest_year is not None and metric in ratios else None
            snapshot.append({"id": metric, "label": LABELS.get(metric, metric), "value": ratio_display(metric, value)})
        result = {
            "company": asdict(company), "latest_year": latest_year,
            "filings": {"annual": self._filing(k), "quarterly": self._filing(q),
                        "recent": [self._filing(item) for item in parse_recent_filings(bundle["submissions"])[:16]]},
            "hero": hero, "ratios": snapshot, "statements": groups,
            "quarterly": quarterly,
            "flags": {"total": len(latest_flags), "significant": int(latest_flags["severity"].eq("Significant").sum()) if not latest_flags.empty else 0,
                      "notable": int(latest_flags["severity"].eq("Notable").sum()) if not latest_flags.empty else 0},
            "anomalies": self._anomaly_records(anomalies),
            "source": {"label": "Official SEC Company Facts", "url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{company.cik}.json",
                       "latest_filing_date": k.filing_date if k else None,
                       "cache_updated_at": bundle.get("facts_cached_at"),
                       "loaded_at": datetime.now(timezone.utc).isoformat()},
        }
        return result

    @staticmethod
    def _anomaly_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
        records = []
        for _, row in frame.iterrows():
            metric = str(row["metric"])
            change = finite(row.get("percentage_change"))
            impact, signed = anomaly_change_presentation(metric, change, "Likely financial impact")
            raw, _ = anomaly_change_presentation(metric, change, "Raw increase / decrease")
            records.append({"metric": metric, "label": LABELS.get(metric, metric.replace("_", " ").title()),
                            "period": int(row["period"]), "prior": finite(row.get("prior_value")),
                            "current": finite(row.get("current_value")), "absolute_change": finite(row.get("absolute_change")),
                            "percentage_change": change, "score": finite(row.get("anomaly_score")),
                            "severity": str(row["severity"]), "method": str(row["method"]),
                            "explanation": str(row["explanation"]), "impact_direction": impact,
                            "raw_direction": raw, "impact_signed": signed})
        return records

    def provenance(self, ticker: str, years: int = 5) -> list[dict[str, Any]]:
        facts = self._load(ticker, years)["facts"]
        return [{key: (None if pd.isna(value) else value) for key, value in row.items()}
                for row in facts.to_dict("records")]

    def composition(self, ticker: str, form: str = "10-Q", years: int = 5) -> dict[str, Any]:
        if form not in {"10-K", "10-Q"}:
            raise ValueError("Choose a 10-K or 10-Q filing.")
        bundle = self._load(ticker, years)
        filing = latest_filing(bundle["submissions"], form)
        if filing is None:
            raise ValueError(f"No recent {form} is available for this company.")
        with self._lock:
            cached = self._composition_cache.get(filing.accession_number)
            if cached is not None:
                return cached
        settings = Settings.from_env()
        with SECClient(settings.sec_user_agent, settings.cache_dir,
                       min_interval=settings.request_interval_seconds,
                       timeout=settings.request_timeout_seconds) as client:
            payload = client.company_facts(bundle["company"].cik)
            facts = select_filing_income_facts(payload, filing.accession_number, filing.report_date, form)
            composition = compose_income(facts)
            revenue = facts.get("revenue")
            splits: list[dict[str, Any]] = []
            split_status = "No revenue breakdown in this filing reconciled to the reported total."
            if revenue:
                try:
                    html = client.filing_document(filing.source_url)
                    splits = revenue_disaggregations(html, revenue["period_start"], revenue["period_end"], revenue["value"])
                    if splits:
                        split_status = "Breakdowns are from this filing's inline XBRL and reconcile to total revenue."
                except SECClientError:
                    split_status = "The SEC filing could not be loaded for a detailed revenue breakdown."
        for item in composition["metrics"].values():
            item["display"] = human_currency(item["value"])
        for group in splits:
            group["total_display"] = human_currency(group["total"])
            for item in group["items"]:
                item["display"] = human_currency(item["value"])
                item["share"] = item["value"] / group["total"]
        result = {"filing": self._filing(filing), "basis": "Fiscal year" if form == "10-K" else "Three months",
                  "period_start": revenue["period_start"] if revenue else None,
                  "period_end": filing.report_date, **composition,
                  "revenue_splits": splits, "split_status": split_status}
        with self._lock:
            self._composition_cache[filing.accession_number] = result
        return result

    def _retriever(self, bundle: dict[str, Any], form: str = "10-K") -> tuple[LocalRetriever, dict[str, str], Any]:
        if form not in {"10-K", "10-Q"}:
            raise ValueError("Choose a 10-K or 10-Q filing.")
        filing = latest_filing(bundle["submissions"], form)
        if filing is None:
            raise ValueError(f"No recent {form} is available for this company.")
        with self._lock:
            cached = self._retrieval_cache.get(filing.accession_number)
            if cached:
                return *cached, filing
        settings = Settings.from_env()
        with SECClient(settings.sec_user_agent, settings.cache_dir,
                       min_interval=settings.request_interval_seconds,
                       timeout=settings.request_timeout_seconds) as client:
            html = client.filing_document(filing.source_url)
        sections = extract_sections(clean_filing_html(html))
        company = bundle["company"]
        chunks = chunk_sections(sections, company=company.name, ticker=company.ticker,
                                filing_form=filing.form, filing_date=filing.filing_date,
                                accession_number=filing.accession_number, source_url=filing.source_url)
        retriever = LocalRetriever(chunks)
        with self._lock:
            self._retrieval_cache[filing.accession_number] = (retriever, sections)
        return retriever, sections, filing

    def filing(self, ticker: str, years: int = 5, form: str = "10-K") -> dict[str, Any]:
        retriever, sections, filing = self._retriever(self._load(ticker, years), form)
        return {"filing": self._filing(filing), "chunk_count": len(retriever.chunks),
                "sections": [{"title": title, "text": text} for title, text in sections.items()]}

    @staticmethod
    def _provider(provider: str, model: str | None = None):
        settings = Settings.from_env()
        if provider == "lmstudio":
            return LMStudioProvider(settings.lmstudio_base_url, model or settings.lmstudio_model,
                                    settings.lmstudio_api_key, timeout=settings.lmstudio_timeout_seconds)
        if provider == "ollama":
            return OllamaProvider(settings.ollama_base_url, model or settings.ollama_model,
                                  timeout=settings.ollama_timeout_seconds)
        if provider == "ollama_cloud":
            from filinglens.desktop.runtime import read_cloud_key
            return OllamaProvider(settings.ollama_cloud_base_url, model or settings.ollama_cloud_model,
                                  api_key=read_cloud_key() or settings.ollama_api_key, cloud=True,
                                  timeout=settings.ollama_cloud_timeout_seconds)
        if provider in {"openai", "anthropic"}:
            from filinglens.desktop.runtime import read_api_key
            key = read_api_key(provider) or getattr(settings, f"{provider}_api_key")
            return CloudProvider(provider, key, model or getattr(settings, f"{provider}_model"))
        raise ValueError("Choose a supported AI provider.")

    def providers(self) -> list[dict[str, Any]]:
        result = []
        for code, label in (("lmstudio", "LM Studio"), ("ollama", "Ollama local"),
                            ("ollama_cloud", "Ollama Cloud"), ("openai", "OpenAI"),
                            ("anthropic", "Anthropic")):
            provider = self._provider(code)
            try:
                models = provider.list_models()
                result.append({"id": code, "label": label, "models": models,
                               "free_models": free_credit_cloud_models(models) if code == "ollama_cloud" else [],
                               "status": "Connected" if models else "No chat models available"})
            except Exception as exc:
                result.append({"id": code, "label": label, "models": [], "free_models": [], "status": str(exc)})
            finally:
                provider.close()
        return result

    def ask(self, ticker: str, question: str, provider_code: str, model: str, years: int = 5,
            filing_form: str = "10-K") -> dict[str, Any]:
        if not question.strip():
            raise ValueError("Enter a question about the company or filing.")
        bundle = self._load(ticker, years)
        retriever, _, filing = self._retriever(bundle, filing_form)
        annual_metrics = verified_metrics_text(bundle["financials"], bundle["ratios"])
        metrics = f"Annual XBRL figures:\n{annual_metrics}"
        if filing_form == "10-Q":
            quarter = self._quarterly_data(bundle.get("quarterly_facts", pd.DataFrame()), filing)
            metrics = f"{self._quarterly_metrics_text(quarter)}\n\n{metrics}"
        provider = self._provider(provider_code, model)
        try:
            answer = ask_filing(question, retriever, provider,
                                verified_metrics=metrics, model=model)
        finally:
            provider.close()
        return {"answer": answer.answer, "status": answer.status, "filing": self._filing(filing),
                "sources": [{"section": hit.chunk.section, "text": hit.chunk.text,
                             "url": hit.chunk.source_url, "form": hit.chunk.filing_form,
                             "score": hit.score,
                             "chunk_id": hit.chunk.chunk_id} for hit in answer.sources]}

    def brief(self, ticker: str, provider_code: str, model: str, years: int = 5) -> dict[str, Any]:
        bundle = self._load(ticker, years)
        available = [form for form in ("10-K", "10-Q") if latest_filing(bundle["submissions"], form)]
        if not available:
            raise ValueError("No recent 10-K or 10-Q is available for this company.")
        retrievers = [self._retriever(bundle, form) for form in available]
        query = "business overview revenue margin liquidity debt cash flow major risk factors management discussion"
        evidence = [hit for retriever, _, _ in retrievers for hit in retriever.search(query, top_k=4)]
        filing = retrievers[0][2]
        anomalies = bundle["anomalies"]
        flagged = anomalies[anomalies["severity"].isin(["Notable", "Significant"])]
        annual_metrics = verified_metrics_text(bundle["financials"], bundle["ratios"])
        metrics = f"Annual XBRL figures:\n{annual_metrics}"
        if "10-Q" in available:
            quarter = self._quarterly_data(bundle.get("quarterly_facts", pd.DataFrame()), latest_filing(bundle["submissions"], "10-Q"))
            metrics = f"{self._quarterly_metrics_text(quarter)}\n\n{metrics}"
        provider = self._provider(provider_code, model)
        try:
            generated = generate_analyst_brief(bundle["company"].ticker,
                                               metrics,
                                               f"Annual periods only:\n{anomaly_summary_text(flagged)}",
                                               retrievers[0][0], provider, model=model,
                                               evidence=evidence, include_quarterly="10-Q" in available)
        finally:
            provider.close()
        return {"text": generated.text, "filing": self._filing(filing),
                "filings": [self._filing(item[2]) for item in retrievers],
                "sources": [{"section": hit.chunk.section, "text": hit.chunk.text,
                             "url": hit.chunk.source_url, "form": hit.chunk.filing_form,
                             "chunk_id": hit.chunk.chunk_id} for hit in evidence]}

    def insiders(self, ticker: str, max_filings: int = 20) -> dict[str, Any]:
        if not 5 <= max_filings <= 50:
            raise ValueError("Choose between 5 and 50 ownership filings.")
        bundle = self._load(ticker, 5)
        settings = Settings.from_env()
        with SECClient(settings.sec_user_agent, settings.cache_dir,
                       min_interval=settings.request_interval_seconds,
                       timeout=settings.request_timeout_seconds) as client:
            result = fetch_insider_activity(client, bundle["submissions"], max_filings=max_filings)
        transactions = [transaction.as_record() for transaction in result.transactions]
        unamended = [row for row in transactions if row["form"] == "4" and row["transaction_code"] in {"P", "S"}]
        purchases = sum(finite(row.get("transaction_value")) or 0 for row in unamended if row["transaction_code"] == "P")
        sales = sum(finite(row.get("transaction_value")) or 0 for row in unamended if row["transaction_code"] == "S")
        return {"transactions": transactions, "filings_reviewed": result.filings_reviewed,
                "failures": list(result.failures), "summary": {"purchases": purchases, "sales": sales,
                "net": purchases - sales, "insiders": len({row["insider_name"] for row in transactions})}}
