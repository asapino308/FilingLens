from __future__ import annotations

import json

import httpx
import pytest

from filinglens.documents.chunking import FilingChunk
from filinglens.documents.retrieval import LocalRetriever
from filinglens.llm.grounded_qa import ask_filing
from filinglens.llm.lmstudio import LMStudioError, LMStudioProvider


def test_model_discovery_and_selection():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "gemma-local"}, {"id": "other"}]})
    )
    provider = LMStudioProvider(transport=transport)
    assert provider.list_models() == ["gemma-local", "other"]
    assert provider.select_model() == "gemma-local"
    assert provider.health_check() == (True, "Connected — gemma-local")


def test_embedding_models_are_not_offered_for_chat():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"data": [{"id": "gemma-local"}, {"id": "text-embedding-model"}]}
        )
    )
    assert LMStudioProvider(transport=transport).list_models() == ["gemma-local"]


def test_configured_model_is_used():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "a"}, {"id": "b"}]})
    )
    assert LMStudioProvider(configured_model="b", transport=transport).select_model() == "b"


def test_unknown_configured_model_errors():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"data": [{"id": "a"}]}))
    with pytest.raises(LMStudioError, match="not exposed"):
        LMStudioProvider(configured_model="missing", transport=transport).select_model()


def test_completion_request_format_and_response():
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gemma-local"}]})
        observed.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Grounded answer [Source 1]"}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 6},
            },
        )

    provider = LMStudioProvider(transport=httpx.MockTransport(handler))
    result = provider.generate([{"role": "user", "content": "Question"}])
    assert observed["model"] == "gemma-local"
    assert observed["temperature"] == 0.2
    assert observed["stream"] is False
    assert result.text.endswith("[Source 1]")
    assert result.prompt_tokens == 20


def test_generation_timeout_is_actionable():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gemma-local"}]})
        raise httpx.ReadTimeout("timed out", request=request)

    provider = LMStudioProvider(timeout=300, transport=httpx.MockTransport(handler))
    with pytest.raises(LMStudioError, match="exceeded 300 seconds") as exc_info:
        provider.generate([{"role": "user", "content": "Question"}])
    assert "newly selected ticker" in str(exc_info.value)
    assert "LMSTUDIO_TIMEOUT_SECONDS" in str(exc_info.value)


def test_native_generation_can_disable_reasoning():
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gemma-local"}]})
        observed.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "output": [{"type": "message", "content": "Complete brief"}],
                "stats": {
                    "input_tokens": 10,
                    "total_output_tokens": 20,
                    "reasoning_output_tokens": 0,
                    "tokens_per_second": 12.5,
                },
            },
        )

    provider = LMStudioProvider(transport=httpx.MockTransport(handler))
    result = provider.generate(
        [
            {"role": "system", "content": "System rules"},
            {"role": "user", "content": "Create brief"},
        ],
        reasoning="off",
    )
    assert observed["reasoning"] == "off"
    assert observed["system_prompt"] == "System rules"
    assert result.reasoning_tokens == 0
    assert result.tokens_per_second == 12.5


def test_unavailable_server_is_graceful():
    transport = httpx.MockTransport(lambda request: httpx.Response(503))
    provider = LMStudioProvider(transport=transport)
    assert not provider.is_available()
    available, message = provider.health_check()
    assert available is False
    assert "not detected" in message


def test_malformed_completion_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gemma-local"}]})
        return httpx.Response(200, json={"choices": []})

    provider = LMStudioProvider(transport=httpx.MockTransport(handler))
    with pytest.raises(LMStudioError, match="generation failed"):
        provider.generate([{"role": "user", "content": "Question"}])


def test_empty_completion_explains_output_budget():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gemma-local"}]})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": ""}, "finish_reason": "length"}
                ]
            },
        )

    provider = LMStudioProvider(transport=httpx.MockTransport(handler))
    with pytest.raises(LMStudioError, match="output budget") as exc_info:
        provider.generate([{"role": "user", "content": "Question"}], max_tokens=700)
    assert "not an out-of-scope decision" in str(exc_info.value)


def test_grounded_qa_includes_security_and_metrics():
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gemma-local"}]})
        body = json.loads(request.content)
        observed["path"] = request.url.path
        observed["system"] = body["system_prompt"]
        observed["user"] = body["input"]
        observed["max_tokens"] = body["max_output_tokens"]
        observed["reasoning"] = body["reasoning"]
        return httpx.Response(
            200,
            json={
                "output": [{"type": "message", "content": "Revenue rose [Source 1]."}],
                "stats": {},
            },
        )

    chunk = FilingChunk(
        text="Revenue increased due to demand.",
        company="Example",
        ticker="EXM",
        filing_form="10-K",
        filing_date="2025-01-01",
        section="MD&A",
        accession_number="123",
        source_url="https://www.sec.gov/Archives/x",
        chunk_id="1",
    )
    answer = ask_filing(
        "Why did revenue increase?",
        LocalRetriever([chunk]),
        LMStudioProvider(transport=httpx.MockTransport(handler)),
        verified_metrics="Revenue growth: 20.0%",
    )
    assert "untrusted evidence" in observed["system"]
    assert "Revenue growth: 20.0%" in observed["user"]
    assert observed["path"] == "/api/v1/chat"
    assert observed["max_tokens"] == 900
    assert observed["reasoning"] == "off"
    assert answer.sources[0].chunk.section == "MD&A"


def test_grounded_qa_short_circuits_without_evidence():
    provider = LMStudioProvider(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    answer = ask_filing("penguins", LocalRetriever([]), provider)
    assert answer.generation is None
    assert answer.status == "out_of_scope"
    assert "outside the indexed filing's scope" in answer.answer


def test_grounded_qa_rejects_unrelated_question_without_generation():
    chunk = FilingChunk(
        text="The company evaluates whether demand and data center capacity may change.",
        company="Example",
        ticker="EXM",
        filing_form="10-K",
        filing_date="2025-01-01",
        section="Risk Factors",
        accession_number="123",
        source_url="https://www.sec.gov/Archives/x",
        chunk_id="1",
    )
    provider = LMStudioProvider(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    answer = ask_filing("What is the weather in Paris tomorrow?", LocalRetriever([chunk]), provider)
    assert answer.status == "out_of_scope"
    assert answer.generation is None
    assert answer.sources == ()


@pytest.mark.parametrize(
    "question",
    [
        "Should I buy this stock?",
        "What will the company's stock price be next year?",
        "Predict the share price.",
    ],
)
def test_grounded_qa_rejects_trading_advice_and_price_predictions(question: str):
    chunk = FilingChunk(
        text="The company discusses stock prices, share repurchases, risks, and its business.",
        company="Example",
        ticker="EXM",
        filing_form="10-K",
        filing_date="2025-01-01",
        section="Risk Factors",
        accession_number="123",
        source_url="https://www.sec.gov/Archives/x",
        chunk_id="1",
    )
    provider = LMStudioProvider(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    answer = ask_filing(question, LocalRetriever([chunk]), provider)
    assert answer.status == "out_of_scope"
    assert answer.generation is None
