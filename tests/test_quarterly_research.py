"""Latest-quarter filing selection and evidence boundaries."""

from fastapi.testclient import TestClient
import pandas as pd

from filinglens.desktop.api import create_app
from filinglens.desktop.service import ResearchService
from filinglens.documents.chunking import FilingChunk
from filinglens.documents.retrieval import LocalRetriever
from filinglens.llm.base import GenerationResult
from filinglens.sec.companies import Company
from filinglens.sec.submissions import FilingMetadata


def _filing(form: str, accession: str, date: str) -> FilingMetadata:
    return FilingMetadata(form, date, date, accession, "filing.htm", "0000000001")


class RecordingProvider:
    def __init__(self):
        self.prompts: list[str] = []
        self.options: list[dict] = []

    def generate(self, messages, **kwargs):
        self.prompts.append(messages[-1]["content"])
        self.options.append(kwargs)
        return GenerationResult("Grounded answer [Source 1]", "test-model", 0)

    def close(self):
        pass


def _research_service(monkeypatch):
    annual = _filing("10-K", "0000000001-25-000001", "2025-12-31")
    quarter = _filing("10-Q", "0000000001-26-000001", "2026-03-31")
    submissions = {"cik": 1, "filings": {"recent": {
        "form": ["10-Q", "10-K"],
        "filingDate": [quarter.filing_date, annual.filing_date],
        "reportDate": [quarter.report_date, annual.report_date],
        "accessionNumber": [quarter.accession_number, annual.accession_number],
        "primaryDocument": ["filing.htm", "filing.htm"],
    }}}
    bundle = {
        "company": Company("TEST", "Test Company", "0000000001"),
        "submissions": submissions,
        "financials": pd.DataFrame({"revenue": [100.0, 120.0]}, index=[2024, 2025]),
        "ratios": pd.DataFrame(index=[2024, 2025]),
        "anomalies": pd.DataFrame(columns=["severity"]),
        "quarterly_facts": pd.DataFrame([{
            "metric": "revenue", "value": 35.0, "period_start": "2026-01-01",
            "period_end": "2026-03-31", "xbrl_concept": "Revenues",
        }]),
    }
    service = ResearchService()
    provider = RecordingProvider()
    retrievers = {}
    for filing in (annual, quarter):
        chunk = FilingChunk(
            text=f"Revenue in the {filing.form} reflects customer demand and business conditions.",
            company="Test Company", ticker="TEST", filing_form=filing.form,
            filing_date=filing.filing_date, section="Management discussion",
            accession_number=filing.accession_number, source_url=filing.source_url,
            chunk_id=f"{filing.accession_number}-1",
        )
        retrievers[filing.form] = (LocalRetriever([chunk]), {}, filing)
    monkeypatch.setattr(service, "_load", lambda *args, **kwargs: bundle)
    monkeypatch.setattr(service, "_retriever", lambda _bundle, form="10-K": retrievers[form])
    monkeypatch.setattr(service, "_provider", lambda *args: provider)
    return service, provider, annual, quarter


def test_api_forwards_10q_choice_and_rejects_unknown_form(monkeypatch):
    service, _, _, _ = _research_service(monkeypatch)
    client = TestClient(create_app(service=service, token="test-session"))
    headers = {"X-FilingLens-Token": "test-session"}
    filing = client.get("/api/company/TEST/filing?form=10-Q", headers=headers)
    assert filing.status_code == 200
    assert filing.json()["filing"]["form"] == "10-Q"
    answer = client.post("/api/ask", headers=headers, json={
        "ticker": "TEST", "question": "What affected revenue?", "provider": "test",
        "model": "test-model", "filing_form": "10-Q",
    })
    assert answer.status_code == 200
    assert answer.json()["filing"]["form"] == "10-Q"
    assert client.get("/api/company/TEST/filing?form=8-K", headers=headers).status_code == 422


def test_quarterly_answer_uses_10q_evidence_and_labeled_metrics(monkeypatch):
    service, provider, _, quarter = _research_service(monkeypatch)
    answer = service.ask("TEST", "What affected revenue?", "test", "test-model", filing_form="10-Q")
    assert answer["filing"]["accession_number"] == quarter.accession_number
    assert answer["sources"][0]["form"] == "10-Q"
    assert "Latest 10-Q" in provider.prompts[0]
    assert "Revenue (three-month period, end 2026-03-31): $35" in provider.prompts[0]
    assert "Annual XBRL figures" in provider.prompts[0]


def test_brief_cites_both_filings_and_has_quarter_update(monkeypatch):
    service, provider, _, _ = _research_service(monkeypatch)
    brief = service.brief("TEST", "test", "test-model")
    assert [filing["form"] for filing in brief["filings"]] == ["10-K", "10-Q"]
    assert {source["form"] for source in brief["sources"]} == {"10-K", "10-Q"}
    prompt = provider.prompts[0]
    assert "## What Happened in the Latest Quarter" in prompt
    assert "Form: 10-K" in prompt and "Form: 10-Q" in prompt
    assert "Annual periods only" in prompt
    assert "Use no Markdown tables" in prompt
    assert "curious reader with no finance background" in prompt
    assert provider.options[0]["max_tokens"] == 4000
    assert provider.options[0]["reasoning"] == "off"
