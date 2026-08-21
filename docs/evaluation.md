# AI evaluation

## Scope

FilingLens includes 20 reusable questions:

- direct filing retrieval
- MD&A reasoning
- risk-factor synthesis
- financial-change explanation
- verified-metric interpretation
- deliberately unsupported information

The dataset lives in `src/filinglens/evaluation/qa_eval.py`. It is a compact engineering evaluation, not a claim of model-wide accuracy.

## Measures

- **Retrieval relevance:** inspect whether a relevant filing section appears in top-k.
- **Citation compliance:** detect `[Source N]` markers and verify they refer to supplied chunks.
- **Unsupported handling:** detect explicit insufficient-evidence language.
- **Numerical consistency:** compare values in the response with the exact serialized Python metrics.
- **Operational performance:** retain model ID, latency, output length, and local token statistics where the endpoint supplies them.

No separate LLM is used as the sole judge. Human review of the linked filing remains required.

## Verified live smoke tests — 2026-08-20

### Data and retrieval

AAPL and MSFT were loaded from the official SEC ticker directory, submissions endpoint, Company Facts endpoint, and their latest available 10-K archive documents. Each produced five consecutive annual periods, statements, 15 ratio/growth series, anomaly records, section-aware chunks, and MD&A-oriented top results for a revenue/margin query. A cache-only replay with a transport that would fail on any network request also succeeded.

### Local model

LM Studio at `http://127.0.0.1:1234/v1` exposed the intended model as `google/gemma-4-12b`. After the XBRL comparative-period regression fix, a live AAPL question preserved the verified FY2025 revenue value of `$416.16B` and answered net-sales drivers with four retrieved sources and `[Source N]` citations in 98.38 seconds. A deliberately unsupported question about a private CEO/board conversation stated that the filing evidence did not contain that information and was insufficient.

The initial analyst-brief run exposed an important failure: the model used output tokens for hidden reasoning and stopped after three headings. The production path was changed to LM Studio's native local chat endpoint with reasoning off and five evidence chunks. The final corrected-metrics rerun completed all eight required headings, included 14 source markers, ended with the responsible-use disclaimer, used zero reasoning tokens, and generated 1,165 output tokens at approximately 7.66 tokens/second in 177.5 seconds.

### Automated tests

The final suite contains 104 passing tests with 85% package coverage. It covers SEC headers, request throttling, cache behavior, retries, ticker normalization, submissions, annual fact filtering, duplicate/restatement handling, comparative-period labeling, debt mapping, statements, ratios, zero denominators, negative equity, anomaly thresholds, parsing, section fallback, chunk metadata, retrieval ranking, LM Studio and Ollama discovery/generation/offline behavior, prompt isolation, exports, and evaluation helpers.

Ollama compatibility is validated with mocked native `/api/tags` and `/api/chat` responses, including model filtering, explicit reasoning control, token statistics, invalid configuration, timeout handling, and offline behavior. The live performance figures below remain LM Studio-specific and are not presented as an Ollama benchmark.

## Honest limitations

- Only two issuers were used in the live end-to-end smoke test.
- The full 20-question set has not been run and manually labeled for every model.
- One supported and one unsupported question were manually inspected with the current Gemma model.
- Citation markers were present, but automated semantic entailment is not implemented.
- Local model latency ranged from about 98 seconds for grounded Q&A to 178 seconds for the completion-safe analyst brief on the tested hardware.
- Model behavior may change with provider version, model, quantization, context size, and hardware.

## Reproducing a benchmark

Load a filing and construct `LocalRetriever`, then call `run_benchmark` with one or more discovered model IDs and a subset of `EVALUATION_QUESTIONS`. Save genuine returned records; do not pre-populate scores for runs that did not happen. Review unsupported answers and every citation manually before reporting aggregate results.
