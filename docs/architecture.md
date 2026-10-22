# FilingLens architecture

## Design objective

FilingLens combines structured accounting data and narrative filings without allowing a generative model to become the source of record. Data acquisition, numerical analysis, retrieval, and language generation are separate modules connected by explicit data structures.

The new desktop interface lives in `desktop/`. Its React front end calls `filinglens.desktop.api`, a token-protected FastAPI service bound to `127.0.0.1`. Tauri starts a bundled Python sidecar and shuts it down when the app exits. The existing Streamlit `app.py` remains an alternate interface over the same calculation modules.

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
  → selected provider (LM Studio, local Ollama, Ollama Cloud, OpenAI, or Anthropic)
  → answer / analyst brief + visible sources
```

## Trust boundaries

### Data layer

`filinglens.sec` talks only to official SEC hosts. `SECClient` supplies the configured User-Agent, spaces requests at 0.4 seconds, retries transient HTTP failures, validates basic response structure, and writes URL-keyed cache files. `companies.py` resolves tickers. `submissions.py` produces archive URLs. `xbrl.py` maps and normalizes annual facts with provenance.

Filing text is untrusted external input. It never becomes a system message or application instruction.

### Analytics layer

`filinglens.analytics` pivots long facts, derives free cash flow, calculates ratios, and produces economic and robust statistical flags. Divide-by-zero and missing inputs remain `NaN`. These outputs are authoritative within FilingLens; the LLM is not asked to recalculate them.

### Language layer

`filinglens.documents` cleans, sections, chunks, and ranks filing text locally. `filinglens.llm` exposes a common contract for LM Studio, local Ollama, Ollama Cloud, OpenAI, and Anthropic. `grounded_qa.py` combines only top-ranked evidence and verified metrics. The system prompt rejects document instructions, unsupported claims, invented citations, and personalized investment advice. Local providers default to loopback; trusted environment settings can override their addresses; selecting a cloud provider sends the bounded prompt to its authenticated API.

## Module responsibilities

| Module | Responsibility |
|---|---|
| `config.py` | Environment, provider, credential, and cache configuration |
| `sec/client.py` | Headers, throttling, retries, caching, validation |
| `sec/companies.py` | Ticker normalization and CIK resolution |
| `sec/submissions.py` | Filing metadata and official archive URLs |
| `sec/xbrl.py` | Concept candidates, annual selection, provenance |
| `analytics/normalize.py` | Long-to-wide financial structures and FCF |
| `analytics/ratios.py` | Authoritative ratios and growth |
| `analytics/anomalies.py` | Economic and MAD-based unusual-change screens |
| `analytics/evidence.py` | Exact annual comparison context, recursive calculation inputs, source receipts, and versioned evidence-trail identity |
| `documents/*` | Parsing, sectioning, chunking, TF-IDF retrieval |
| `llm/base.py` | Replaceable provider contract |
| `llm/lmstudio.py` | Discovery, health, local generation, offline errors |
| `llm/ollama.py` | Native local/cloud Ollama discovery, authentication, generation, statistics, errors |
| `llm/grounded_qa.py` | Evidence and metric grounded questions |
| `llm/analyst_brief.py` | Required-section local synthesis |
| `evaluation/*` | Reusable questions and benchmark records |
| `reporting/export.py` | Safe Markdown-to-HTML export |
| `app.py` | Streamlit orchestration and user-facing errors |
| `desktop/src` | React company workspace, statements, filings, signals, and settings |
| `desktop/src/EvidenceTrail.tsx` | Accessible anomaly investigation dialog, filing leads, user judgments, evidence attachments, and Markdown export |
| `desktop/src/evidenceReviews.ts` | Versioned local review persistence isolated by exact source context |
| `desktop/src-tauri` | Mac window, private sidecar launch, and native external links |
| `filinglens/desktop/service.py` | Shared desktop research data and AI orchestration |
| `filinglens/desktop/api.py` | Local JSON API and request validation |

## Caching and performance

The on-disk SEC cache survives Streamlit reruns and is ignored by Git. Streamlit additionally caches company bundles and filing documents for 24 hours. Retrieval indexes live in session state and are scoped to both ticker and filing accession; switching companies clears the prior index and generated brief. The app does not automatically download filing documents until the user asks to index one.

## Failure modes

- SEC failures produce `SECClientError` with the failing resource.
- Missing concepts remain absent rather than synthesized.
- Unusual filing markup falls back to full-text chunking.
- An empty retrieval result returns an insufficient-evidence response without calling the model.
- Provider discovery or generation errors affect only AI-assisted features.
- Export escapes HTML from model output.

## Anomaly evidence trails

`GET /api/company/{ticker}/evidence?metric=...&period=...` uses the same financial and ratio frames as the annual movement screen. It follows the detector's previous nonmissing observation, explicitly identifies missing-year gaps, and recursively includes source facts for derived metrics. Ratio changes use percentage points or multiples as appropriate. Trail identities include the numerical observations and their provenance, preventing old judgments from being applied silently to revised facts.

The optional `include_passages=true` reads up to three matching annual filings through the shared accession-scoped retriever. Matching prefers the selected observation's source accession, then its exact reporting end date; it never silently substitutes the latest unrelated annual filing. Results are filtered for metric-specific language, management discussion is prioritized, and substantially overlapping chunks are suppressed. Missing documents or retrieval failures leave the numeric trail intact. The bounded search is neither exhaustive disclosure analysis nor citation-entailment verification.

The feature does not invoke any model. User-authored hypotheses, judgments, notes, and attached evidence snapshots live in local website storage, keyed by source-specific trail ID. Storage failures are visible; Markdown export provides a portable copy. The Mac `export_investigation` command writes only a size-bounded Markdown file with a validated basename and unique suffix under the app's own data directory (`exports/`); it accepts no user-supplied destination path and never overwrites a previous export. `show_investigation_exports` opens that fixed folder in Finder. This avoids native webview Blob-download failures. Browser development sessions retain normal downloads. Local reviews are not a server database or a synchronized backup.
