"""FilingLens Streamlit application."""

from __future__ import annotations

import logging
from pathlib import Path
import sys


# Keep the source-layout application launchable even if macOS marks the
# editable-install .pth file as hidden and Python skips it after a restart.
PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

import pandas as pd
import streamlit as st

from filinglens.analytics.anomalies import detect_anomalies
from filinglens.analytics.normalize import financials_wide, statement_table
from filinglens.analytics.ratios import calculate_ratios
from filinglens.config import Settings
from filinglens.documents.chunking import chunk_sections
from filinglens.documents.parser import clean_filing_html
from filinglens.documents.retrieval import LocalRetriever
from filinglens.documents.sections import extract_sections
from filinglens.llm.analyst_brief import generate_analyst_brief
from filinglens.llm.base import LLMProvider, LocalLLMError
from filinglens.llm.grounded_qa import ask_filing
from filinglens.llm.lmstudio import LMStudioProvider
from filinglens.llm.ollama import OllamaProvider
from filinglens.reporting.export import markdown_to_html
from filinglens.sec.client import SECClient, SECClientError
from filinglens.sec.companies import CompanyDirectory
from filinglens.sec.insiders import fetch_insider_activity
from filinglens.sec.submissions import latest_filing
from filinglens.sec.xbrl import select_annual_facts
from filinglens.ui.charts import financial_trend_chart, ratio_trend_chart
from filinglens.ui.components import (
    ANOMALY_COLOR_MODES,
    anomaly_display_table,
    anomaly_summary_text,
    format_ratio_table,
    human_currency,
    synchronize_filing_session,
    verified_metrics_text,
)


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
st.set_page_config(page_title="FilingLens", page_icon="🔎", layout="wide")


@st.cache_data(ttl=86_400, show_spinner=False)
def load_company(ticker: str, refresh_nonce: int = 0) -> dict[str, object]:
    refresh = refresh_nonce > 0
    settings = Settings.from_env()
    settings.validate_sec()
    settings.ensure_directories()
    with SECClient(
        settings.sec_user_agent,
        settings.cache_dir,
        min_interval=settings.request_interval_seconds,
        timeout=settings.request_timeout_seconds,
    ) as client:
        company = CompanyDirectory(client).lookup(ticker, refresh=refresh)
        submissions = client.submissions(company.cik, refresh=refresh)
        facts = select_annual_facts(
            client.company_facts(company.cik, refresh=refresh), company.ticker
        )
    return {"company": company, "submissions": submissions, "facts": facts}


@st.cache_data(ttl=86_400, show_spinner=False)
def load_filing_text(source_url: str, refresh_nonce: int = 0) -> str:
    settings = Settings.from_env()
    with SECClient(settings.sec_user_agent, settings.cache_dir) as client:
        return client.filing_document(source_url, refresh=refresh_nonce > 0)


@st.cache_data(ttl=3_600, show_spinner=False)
def load_insider_activity(
    cik: str, max_filings: int, refresh_nonce: int = 0
) -> dict[str, object]:
    settings = Settings.from_env()
    settings.validate_sec()
    settings.ensure_directories()
    refresh = refresh_nonce > 0
    with SECClient(
        settings.sec_user_agent,
        settings.cache_dir,
        min_interval=settings.request_interval_seconds,
        timeout=settings.request_timeout_seconds,
    ) as client:
        submissions = client.submissions(cik, refresh=refresh)
        result = fetch_insider_activity(
            client,
            submissions,
            max_filings=max_filings,
            refresh=refresh,
        )
    return {
        "transactions": [transaction.as_record() for transaction in result.transactions],
        "filings_reviewed": result.filings_reviewed,
        "failures": list(result.failures),
    }


def build_retriever(company: object, filing: object, html: str) -> tuple[LocalRetriever, dict[str, str]]:
    text = clean_filing_html(html)
    sections = extract_sections(text)
    chunks = chunk_sections(
        sections,
        company=company.name,
        ticker=company.ticker,
        filing_form=filing.form,
        filing_date=filing.filing_date,
        accession_number=filing.accession_number,
        source_url=filing.source_url,
    )
    return LocalRetriever(chunks), sections


def provider_states(
    settings: Settings,
) -> dict[str, tuple[LLMProvider, list[str], str, str]]:
    candidates: dict[str, tuple[LLMProvider, str, str]] = {
        "LM Studio": (
            LMStudioProvider(
                settings.lmstudio_base_url,
                settings.lmstudio_model,
                settings.lmstudio_api_key,
                timeout=settings.lmstudio_timeout_seconds,
            ),
            settings.lmstudio_model,
            settings.lmstudio_base_url,
        ),
        "Ollama": (
            OllamaProvider(
                settings.ollama_base_url,
                settings.ollama_model,
                timeout=settings.ollama_timeout_seconds,
            ),
            settings.ollama_model,
            settings.ollama_base_url,
        ),
    }
    if settings.local_llm_provider == "lmstudio":
        candidates = {"LM Studio": candidates["LM Studio"]}
    elif settings.local_llm_provider == "ollama":
        candidates = {"Ollama": candidates["Ollama"]}

    states: dict[str, tuple[LLMProvider, list[str], str, str]] = {}
    for name, (provider, configured_model, endpoint) in candidates.items():
        try:
            models = provider.list_models()
            status = f"Connected - {len(models)} model(s)"
        except LocalLLMError:
            models = []
            status = f"{name} was not detected at {endpoint}."
        states[name] = (provider, models, status, configured_model)
    return states


settings = Settings.from_env()
st.title("FilingLens")
st.caption("Local SEC filing intelligence · Deterministic financial analytics · Educational use only")

with st.sidebar:
    st.header("Company")
    ticker = st.text_input("Ticker", value="AAPL", max_chars=10).strip().upper()
    years_to_show = st.slider("Historical periods", min_value=3, max_value=10, value=5)
    if "refresh_nonce" not in st.session_state:
        st.session_state.refresh_nonce = 0
    if st.button("Refresh SEC cache"):
        st.session_state.refresh_nonce += 1
        st.cache_data.clear()
    st.divider()
    st.header("Local AI")
    local_states = provider_states(settings)
    available_providers = [name for name, state in local_states.items() if state[1]]
    if available_providers:
        provider_name = st.selectbox("Local AI provider", available_providers)
        provider, models, llm_status, configured_model = local_states[provider_name]
        default_model = configured_model if configured_model in models else models[0]
        model = st.selectbox("Local model", models, index=models.index(default_model))
        st.success(f"{provider_name}: {llm_status}")
    else:
        provider_name = None
        provider = next(iter(local_states.values()))[0]
        models = []
        model = None
        llm_status = "No configured local AI service was detected."
        st.warning(llm_status)
        st.caption(
            "Start LM Studio or Ollama and make a chat model available. Deterministic features "
            "remain available."
        )

if not ticker:
    st.info("Enter a ticker to begin.")
    st.stop()

try:
    with st.spinner(f"Loading official SEC data for {ticker}…"):
        bundle = load_company(ticker, st.session_state.refresh_nonce)
except (SECClientError, ValueError) as exc:
    st.error(str(exc))
    st.stop()

company = bundle["company"]
submissions = bundle["submissions"]
facts = bundle["facts"]
financials = financials_wide(facts).tail(years_to_show)
ratios = calculate_ratios(financials)
anomalies = detect_anomalies(pd.concat([financials, ratios], axis=1))
latest_10k = latest_filing(submissions, "10-K")
latest_10q = latest_filing(submissions, "10-Q")
active_filing_key = (
    f"{company.ticker}:{latest_10k.accession_number}" if latest_10k else f"{company.ticker}:no-10k"
)
synchronize_filing_session(st.session_state, active_filing_key)
metrics_context = verified_metrics_text(financials, ratios)

tabs = st.tabs(
    [
        "Overview",
        "Financial Trends",
        "Anomaly Analysis",
        "Insider Activity",
        "Ask the Filing",
        "Analyst Brief",
        "Methodology",
    ]
)

with tabs[0]:
    st.caption(
        "What this tab does: summarizes the active company, recent SEC filings, selected local "
        "model, headline annual metrics, and the provenance behind each XBRL value."
    )
    st.subheader(f"{company.name} ({company.ticker})")
    cols = st.columns(4)
    cols[0].metric("CIK", company.cik)
    cols[1].metric("Latest 10-K", latest_10k.filing_date if latest_10k else "Unavailable")
    cols[2].metric("Latest 10-Q", latest_10q.filing_date if latest_10q else "Unavailable")
    cols[3].metric("Local model", model or "Offline")
    if not financials.empty:
        latest_year = financials.index[-1]
        headline = st.columns(4)
        for column, metric_name in zip(
            headline, ("revenue", "operating_income", "net_income", "free_cash_flow")
        ):
            column.metric(
                f"{metric_name.replace('_', ' ').title()} FY{latest_year}",
                human_currency(financials.loc[latest_year, metric_name])
                if metric_name in financials
                else "Unavailable",
            )
    else:
        st.warning("No reliable XBRL concept mapping was found for this company.")
    with st.expander("Value provenance"):
        st.dataframe(facts, width="stretch", hide_index=True)

with tabs[1]:
    st.caption(
        "What this tab does: charts Python-calculated financial statements, cash flow, margins, "
        "ratios, and growth across the selected historical periods."
    )
    if financials.empty:
        st.warning("SEC financial data for these metrics was unavailable.")
    else:
        st.plotly_chart(
            financial_trend_chart(
                financials,
                ["revenue", "gross_profit", "operating_income", "net_income"],
                "Income statement trends",
            ),
            width="stretch",
        )
        st.plotly_chart(
            financial_trend_chart(
                financials,
                ["operating_cash_flow", "free_cash_flow", "total_assets", "long_term_debt"],
                "Cash flow and capital trends",
            ),
            width="stretch",
        )
        st.plotly_chart(
            ratio_trend_chart(
                ratios, ["gross_margin", "operating_margin", "net_margin"], "Margin trends"
            ),
            width="stretch",
        )
        for statement in ("Income Statement", "Balance Sheet", "Cash Flow"):
            with st.expander(statement, expanded=statement == "Income Statement"):
                st.dataframe(statement_table(financials, statement), width="stretch")
        with st.expander("Ratios and growth"):
            st.dataframe(format_ratio_table(ratios), width="stretch")

with tabs[2]:
    st.caption(
        "What this tab does: screens year-over-year financial movements using documented economic "
        "thresholds and robust statistical scores so you can decide what to investigate further."
    )
    st.info(
        "This screen identifies unusual financial movements. It is not fraud detection and does not establish misconduct."
    )
    if anomalies.empty:
        st.warning("Insufficient historical observations for change analysis.")
    else:
        severity = st.multiselect(
            "Severity", ["Significant", "Notable", "Normal"], default=["Significant", "Notable"]
        )
        color_mode = st.selectbox(
            "Change coloring",
            ANOMALY_COLOR_MODES,
            help=(
                "Likely financial impact treats increases in costs, expenses, debt, and liabilities "
                "as unfavorable. Raw mode colors every increase green and every decrease red."
            ),
        )
        filtered_anomalies = anomalies[anomalies["severity"].isin(severity)]
        if color_mode == "Likely financial impact":
            st.caption(
                "Green indicates a likely favorable movement and red a likely unfavorable movement. "
                "Costs, expenses, debt, and liabilities are interpreted as lower-is-better; all "
                "other metrics are interpreted as higher-is-better. This directional label is a "
                "screening aid, not an investment conclusion."
            )
        elif color_mode == "Raw increase / decrease":
            st.caption(
                "Green indicates a numerical increase and red a numerical decrease, regardless of "
                "whether that movement is economically favorable."
            )
        if color_mode != "Off":
            st.caption(
                "Color intensity: light below 20% · medium from 20% to 39.9% · deep at 40% or more."
            )
        if color_mode == "Likely financial impact":
            st.caption(
                "Direction rank: 1 is strongly favorable and 6 is strongly unfavorable. Sort the "
                "Direction column ascending for most-to-least favorable or descending for the exact reverse."
            )
        else:
            st.caption(
                "Direction rank: 1 is the strongest gain and 6 is the strongest loss. Sort the "
                "Direction column ascending for gains-first or descending for the exact reverse."
            )
        if not filtered_anomalies.empty:
            detail_frame = filtered_anomalies.reset_index(drop=True)
            selected_detail = st.selectbox(
                "Full explanation",
                range(len(detail_frame)),
                format_func=lambda index: (
                    f"{str(detail_frame.loc[index, 'metric']).replace('_', ' ').title()} · "
                    f"FY{int(detail_frame.loc[index, 'period'])} · "
                    f"{float(detail_frame.loc[index, 'percentage_change']):+.1%}"
                    if pd.notna(detail_frame.loc[index, "percentage_change"])
                    else f"{str(detail_frame.loc[index, 'metric']).replace('_', ' ').title()} · "
                    f"FY{int(detail_frame.loc[index, 'period'])} · change unavailable"
                ),
            )
            selected_row = detail_frame.loc[selected_detail]
            st.info(str(selected_row["explanation"]))
            st.caption(f"Method: {selected_row['method']}")
        st.dataframe(
            anomaly_display_table(filtered_anomalies, color_mode),
            width="stretch",
            hide_index=True,
            height=min(500, 38 + 35 * max(len(filtered_anomalies), 1)),
            column_config={
                "Metric": st.column_config.TextColumn(width="medium"),
                "Direction": st.column_config.TextColumn(width="medium"),
            },
        )
        st.caption(
            "Economic thresholds: Notable ≥20%, Significant ≥40%. Robust change scores use median absolute deviation: Notable ≥2.5, Significant ≥3.5."
        )

with tabs[3]:
    st.caption(
        "What this tab does: retrieves recent official SEC Forms 4 and 4/A, separates open-market "
        "purchases and sales from grants, option exercises, gifts, and tax-related transactions, "
        "and preserves a direct link to every source filing."
    )
    st.info(
        "Insider filings are research signals, not trade recommendations. A sale may reflect taxes, "
        "diversification, compensation, or a pre-arranged 10b5-1 plan; a purchase does not guarantee "
        "future performance. Review the filing footnotes before drawing conclusions."
    )
    max_insider_filings = st.slider(
        "Recent Form 4 filings to review",
        min_value=5,
        max_value=50,
        value=20,
        step=5,
        help="Each filing is downloaded once from SEC.gov and then cached locally.",
    )
    insider_key = f"{company.ticker}:{max_insider_filings}:{st.session_state.refresh_nonce}"
    if st.button("Load insider activity", key="load_insider_activity"):
        try:
            with st.spinner("Retrieving and parsing official SEC ownership filings…"):
                st.session_state.insider_activity = load_insider_activity(
                    company.cik,
                    max_insider_filings,
                    st.session_state.refresh_nonce,
                )
                st.session_state.insider_activity_key = insider_key
        except (SECClientError, ValueError) as exc:
            st.error(str(exc))

    activity = (
        st.session_state.get("insider_activity")
        if st.session_state.get("insider_activity_key") == insider_key
        else None
    )
    if activity:
        records = activity["transactions"]
        failures = activity["failures"]
        st.caption(
            f"Reviewed {activity['filings_reviewed']} filing(s); found {len(records)} transaction row(s)."
        )
        if failures:
            st.warning(
                f"{len(failures)} filing(s) could not be parsed. Available transactions are shown below."
            )
        if not records:
            st.warning("No transaction rows were found in the selected recent Form 4 filings.")
        else:
            insider_frame = pd.DataFrame(records)
            unamended = insider_frame[insider_frame["form"] == "4"]
            open_market = unamended[unamended["transaction_code"].isin(["P", "S"])]
            purchases = open_market[open_market["transaction_code"] == "P"]
            sales = open_market[open_market["transaction_code"] == "S"]
            purchase_value = purchases["transaction_value"].sum(min_count=1)
            sale_value = sales["transaction_value"].sum(min_count=1)
            purchase_value = 0.0 if pd.isna(purchase_value) else float(purchase_value)
            sale_value = 0.0 if pd.isna(sale_value) else float(sale_value)
            summary_columns = st.columns(4)
            summary_columns[0].metric("Open-market purchases", human_currency(purchase_value))
            summary_columns[1].metric("Open-market sales", human_currency(sale_value))
            summary_columns[2].metric(
                "Net open-market value", human_currency(purchase_value - sale_value)
            )
            summary_columns[3].metric(
                "Reporting insiders", int(insider_frame["insider_name"].nunique())
            )
            st.caption(
                "Value totals include only non-amended P (purchase) and S (sale) rows with both "
                "shares and price reported. Form 4/A amendments remain visible but are excluded from totals."
            )

            categories = {
                "Open-market purchases": {"P"},
                "Open-market sales": {"S"},
                "Awards, exercises, gifts, taxes, and other": set(
                    insider_frame["transaction_code"].unique()
                )
                - {"P", "S"},
            }
            selected_categories = st.multiselect(
                "Transaction categories",
                list(categories),
                default=list(categories),
            )
            selected_codes: set[str] = set()
            for category in selected_categories:
                selected_codes.update(categories[category])
            displayed = insider_frame[
                insider_frame["transaction_code"].isin(selected_codes)
            ].copy()
            displayed["10b5-1 plan"] = displayed["plan_10b5_1"].map(
                {True: "Yes", False: "No/not indicated"}
            )
            displayed["Derivative"] = displayed["derivative"].map(
                {True: "Yes", False: "No"}
            )
            displayed = displayed.rename(
                columns={
                    "transaction_date": "Transaction date",
                    "filing_date": "Filed",
                    "insider_name": "Insider",
                    "insider_role": "Role",
                    "transaction_code": "Code",
                    "transaction_type": "Transaction type",
                    "acquired_disposed": "Acquired/disposed",
                    "shares": "Shares",
                    "price_per_share": "Price/share",
                    "transaction_value": "Estimated value",
                    "shares_owned_after": "Owned after",
                    "ownership_nature": "Ownership",
                    "security_title": "Security",
                    "source_url": "SEC filing",
                }
            )
            table_columns = [
                "Transaction date",
                "Filed",
                "Insider",
                "Role",
                "Code",
                "Transaction type",
                "Acquired/disposed",
                "Shares",
                "Price/share",
                "Estimated value",
                "Owned after",
                "Ownership",
                "10b5-1 plan",
                "Derivative",
                "form",
                "Security",
                "SEC filing",
            ]
            st.dataframe(
                displayed[table_columns],
                width="stretch",
                hide_index=True,
                column_config={
                    "Shares": st.column_config.NumberColumn(format="compact"),
                    "Price/share": st.column_config.NumberColumn(format="dollar"),
                    "Estimated value": st.column_config.NumberColumn(format="dollar"),
                    "Owned after": st.column_config.NumberColumn(format="compact"),
                    "SEC filing": st.column_config.LinkColumn(display_text="Open filing"),
                },
            )
            st.download_button(
                "Download insider transactions CSV",
                insider_frame.to_csv(index=False),
                f"{company.ticker}_insider_activity.csv",
                mime="text/csv",
            )
    else:
        st.caption(
            "Click Load insider activity to retrieve the selected number of recent ownership filings."
        )

with tabs[4]:
    st.caption(
        "What this tab does: indexes this company's latest 10-K, retrieves the passages most "
        "relevant to your question, and asks the selected local model to answer using only those "
        "passages and verified FilingLens metrics. Clearly unrelated questions and requests for "
        "price predictions or buy/sell advice are stopped before model generation. Load a new "
        "index after changing tickers."
    )
    if latest_10k is None:
        st.warning("No recent 10-K filing is available.")
    else:
        st.caption(f"Evidence source: {latest_10k.form} filed {latest_10k.filing_date}")
        retrieval_is_current = (
            "retrieval" in st.session_state
            and st.session_state.get("retrieval_accession") == latest_10k.accession_number
            and st.session_state.get("retrieval_ticker") == company.ticker
        )
        if not retrieval_is_current:
            if st.button("Load and index latest 10-K", key="load_10k"):
                with st.spinner("Retrieving, parsing, and indexing the official filing…"):
                    html = load_filing_text(latest_10k.source_url, st.session_state.refresh_nonce)
                    retriever, sections = build_retriever(company, latest_10k, html)
                    st.session_state.retrieval = retriever
                    st.session_state.sections = sections
                    st.session_state.retrieval_accession = latest_10k.accession_number
                    st.session_state.retrieval_ticker = company.ticker
                    st.rerun()
        else:
            retriever = st.session_state.retrieval
            st.success(f"Indexed {len(retriever.chunks)} chunks across {len(st.session_state.sections)} section(s).")
            question = st.text_area("Question", "What factors did management say affected revenue?")
            if st.button("Ask the filing", disabled=not models):
                try:
                    with st.spinner("Generating a source-grounded answer locally…"):
                        answer = ask_filing(
                            question,
                            retriever,
                            provider,
                            verified_metrics=metrics_context,
                            model=model,
                        )
                    if answer.status == "out_of_scope":
                        st.warning(answer.answer)
                    else:
                        st.markdown(answer.answer)
                        st.subheader("Sources")
                        for index, result in enumerate(answer.sources, 1):
                            chunk = result.chunk
                            with st.expander(
                                f"Source {index} · {chunk.section} · relevance {result.score:.3f}"
                            ):
                                st.markdown(
                                    f"[{chunk.filing_form} filed {chunk.filing_date}]({chunk.source_url})"
                                )
                                st.write(chunk.text)
                except LocalLLMError as exc:
                    st.error(str(exc))
            if not models:
                st.warning(llm_status)

with tabs[5]:
    st.caption(
        "What this tab does: creates an eight-section educational brief from the active company's "
        "verified metrics, compact anomaly summary, and indexed 10-K evidence. It requires the "
        "current ticker's filing index and a connected local model; larger models can take several minutes."
    )
    retriever = st.session_state.get("retrieval")
    retrieval_is_current = (
        retriever is not None
        and latest_10k is not None
        and st.session_state.get("retrieval_accession") == latest_10k.accession_number
        and st.session_state.get("retrieval_ticker") == company.ticker
    )
    brief_key = f"{active_filing_key}:{years_to_show}:{model or 'offline'}"
    if not retrieval_is_current:
        st.info(
            f"Load and index {company.ticker}'s latest 10-K in Ask the Filing before generating a brief."
        )
    elif not models:
        st.warning(llm_status)
    else:
        if st.button("Generate local analyst brief"):
            flagged = anomalies[anomalies["severity"].isin(["Notable", "Significant"])]
            anomaly_context = anomaly_summary_text(flagged)
            try:
                with st.spinner("Synthesizing verified metrics and filing evidence locally…"):
                    brief = generate_analyst_brief(
                        company.ticker,
                        metrics_context,
                        anomaly_context,
                        retriever,
                        provider,
                        model=model,
                )
                st.session_state.analyst_brief = brief.text
                st.session_state.analyst_brief_key = brief_key
            except LocalLLMError as exc:
                st.error(str(exc))
        brief_text = (
            st.session_state.get("analyst_brief")
            if st.session_state.get("analyst_brief_key") == brief_key
            else None
        )
        if brief_text:
            st.markdown(brief_text)
            st.download_button("Download Markdown", brief_text, f"{ticker}_filinglens_brief.md")
            st.download_button(
                "Download HTML",
                markdown_to_html(brief_text, f"{ticker} FilingLens Brief"),
                f"{ticker}_filinglens_brief.html",
                mime="text/html",
            )

with tabs[6]:
    st.caption(
        "What this tab does: explains FilingLens's data, analytics, retrieval, local-generation, "
        "privacy, and responsible-use methodology."
    )
    st.markdown(
        """
### Three-layer design

1. **Data layer:** official SEC submissions, Company Facts, and filing documents with source provenance.
2. **Analytics layer:** Python calculates financial statements, ratios, changes, free cash flow, and robust anomaly scores.
3. **Language layer:** the selected LM Studio or Ollama model interprets only verified metrics and retrieved filing evidence.

### Selection and anomaly methodology

Annual XBRL observations prefer mapped US-GAAP concepts, full-year 10-K durations, and the latest filed duplicate. Missing or ambiguous mappings remain unavailable. Economic flags use absolute year-over-year percentage changes. Statistical flags use median absolute deviation on the change series, which is less sensitive to a single outlier than an ordinary mean/standard-deviation z-score.

### Retrieval and privacy

Filing HTML is cleaned, divided using recognized filing sections, chunked with overlap, and ranked locally with TF-IDF cosine similarity. Filing text is evidence—not instructions. Generative inference goes only to the selected local LM Studio or Ollama loopback endpoint. FilingLens contacts SEC.gov for public data and does not require a paid API.

**Educational financial-analysis software. Not investment advice.**
"""
    )
