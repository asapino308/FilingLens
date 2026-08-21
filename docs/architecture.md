# FilingLens architecture

## Design objective

FilingLens combines structured accounting data and narrative filings without allowing a generative model to become the source of record. Data acquisition, numerical analysis, retrieval, and language generation are separate modules connected by explicit data structures.

## Data flow

```text
Ticker
  → SEC company directory → CIK
  → SEC submissions → filing metadata and archive URLs
  → SEC Company Facts → provenance-rich annual long table
  → pandas wide statements → ratios, trends, anomaly records

Official filing HTML
  → safe visible-text cleanup → section detection → overlapping chunks
  → TF-IDF index → top-k evidence passages

Verified Python metrics + retrieved evidence + user question
  → local provider (LM Studio or Ollama) → answer / analyst brief + visible sources
```

## Trust boundaries

### Data layer

`filinglens.sec` talks only to official SEC hosts. `SECClient` supplies the configured User-Agent, spaces requests at 0.4 seconds, retries transient HTTP failures, validates basic response structure, and writes URL-keyed cache files. `companies.py` resolves tickers. `submissions.py` produces archive URLs. `xbrl.py` maps and normalizes annual facts with provenance.

Filing text is untrusted external input. It never becomes a system message or application instruction.

### Analytics layer

`filinglens.analytics` pivots long facts, derives free cash flow, calculates ratios, and produces economic and robust statistical flags. Divide-by-zero and missing inputs remain `NaN`. These outputs are authoritative within FilingLens; the LLM is not asked to recalculate them.

### Language layer

`filinglens.documents` cleans, sections, chunks, and ranks filing text locally. `filinglens.llm` exposes a common contract with LM Studio and Ollama implementations. `grounded_qa.py` combines only top-ranked evidence and verified metrics. The system prompt rejects document instructions, unsupported claims, invented citations, and personalized investment advice.

## Module responsibilities

| Module | Responsibility |
|---|---|
| `config.py` | Local environment configuration and cache path |
| `sec/client.py` | Headers, throttling, retries, caching, validation |
| `sec/companies.py` | Ticker normalization and CIK resolution |
| `sec/submissions.py` | Filing metadata and official archive URLs |
| `sec/xbrl.py` | Concept candidates, annual selection, provenance |
| `analytics/normalize.py` | Long-to-wide financial structures and FCF |
| `analytics/ratios.py` | Authoritative ratios and growth |
| `analytics/anomalies.py` | Economic and MAD-based unusual-change screens |
| `documents/*` | Parsing, sectioning, chunking, TF-IDF retrieval |
| `llm/base.py` | Replaceable provider contract |
| `llm/lmstudio.py` | Discovery, health, local generation, offline errors |
| `llm/ollama.py` | Native Ollama discovery, generation, statistics, offline errors |
| `llm/grounded_qa.py` | Evidence and metric grounded questions |
| `llm/analyst_brief.py` | Required-section local synthesis |
| `evaluation/*` | Reusable questions and benchmark records |
| `reporting/export.py` | Safe Markdown-to-HTML export |
| `app.py` | Streamlit orchestration and user-facing errors |

## Caching and performance

The on-disk SEC cache survives Streamlit reruns and is ignored by Git. Streamlit additionally caches company bundles and filing documents for 24 hours. Retrieval indexes live in session state and are scoped to both ticker and filing accession; switching companies clears the prior index and generated brief. The app does not automatically download filing documents until the user asks to index one.

## Failure modes

- SEC failures produce `SECClientError` with the failing resource.
- Missing concepts remain absent rather than synthesized.
- Unusual filing markup falls back to full-text chunking.
- An empty retrieval result returns an insufficient-evidence response without calling the model.
- Local-provider discovery or generation errors affect only AI tabs.
- Export escapes HTML from model output.
