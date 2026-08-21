# FilingLens Project Report

**Project:** FilingLens — Local AI-Powered SEC Filing Intelligence and Financial Anomaly Analysis  
**Implementation status:** Core application complete and operational  
**Validation date:** August 21, 2026  
**Intended audience:** Project owner, reviewers, instructors, recruiters, and technical collaborators

## Executive summary

FilingLens is a local-first financial-analysis application for U.S. public companies. It retrieves official SEC EDGAR data, normalizes annual XBRL financial facts, calculates financial metrics in Python, detects unusual changes, parses SEC filings, retrieves relevant filing passages, and uses a locally hosted LM Studio or Ollama model for source-grounded questions and analyst briefs.

The main design goal was reliability and traceability. FilingLens therefore separates three responsibilities:

1. **SEC data supplies the evidence.**
2. **Python performs authoritative calculations.**
3. **The local language model interprets supplied calculations and filing passages.**

The model is never treated as the authoritative source for revenue, margins, ratios, free cash flow, or anomaly scores. Every selected SEC fact retains its source metadata, and every qualitative AI answer exposes the filing passages supplied to the model.

## Work completed

### Project foundation

The repository was created with:

- support for Python 3.11 and newer;
- modular source code under `src/filinglens/`;
- dependency and build configuration in `pyproject.toml`;
- a local `.env` configuration file;
- a safe public `.env.example`;
- a `.gitignore` covering private configuration, caches, build files, and local artifacts;
- an MIT license;
- a complete Streamlit entry point in `app.py`;
- a macOS setup helper, environment diagnostic, automated GitHub test workflow, and dependency-update configuration.

The private SEC contact value exists only in the ignored local `.env`. It does not appear in the README, public documentation, source code, tests, screenshots, or publication candidate.

### SEC integration

FilingLens uses official SEC resources for:

- ticker-to-CIK lookup;
- company identity;
- recent filing metadata;
- structured Company Facts/XBRL data;
- 10-K and 10-Q filing documents.

The SEC client implements:

- a required identifiable User-Agent;
- approximately 0.4 seconds between requests, or about 2.5 requests per second;
- persistent URL-based caching;
- configurable timeouts;
- transient-failure retries;
- exponential backoff;
- JSON and empty-response validation;
- descriptive errors;
- restriction of filing downloads to the official SEC Archives host.

The cache was tested by replaying AAPL and MSFT data through a transport configured to fail if a network request occurred. The replay succeeded, confirming that unchanged Streamlit runs can reuse the local cache.

### XBRL normalization

Candidate US-GAAP mappings were implemented for:

- revenue;
- cost of revenue;
- gross profit;
- operating income;
- net income;
- cash and cash equivalents;
- current assets;
- total assets;
- current liabilities;
- total liabilities;
- stockholders' equity;
- long-term debt;
- operating cash flow;
- capital expenditures.

The selector distinguishes instant values from duration values, accepts full-year 10-K/10-K/A facts, and filters duration facts to approximately 300–450 days. It prefers explicit higher-priority concepts and then the latest-filed duplicate for the same reporting period.

An important live-data issue was found and fixed during validation. The SEC `fy` field can describe the later filing containing a comparative fact rather than the historical period represented by that fact. FilingLens now groups annual observations using the fact's actual period end. A second regression fix prevents the current portion of long-term debt from being selected as total long-term debt.

Every normalized fact preserves:

- ticker;
- company name;
- CIK;
- filing form;
- accession number;
- filing date;
- annual period label;
- fiscal period;
- period start and end;
- normalized metric;
- value and unit;
- selected XBRL concept.

### Deterministic financial analytics

The normalized facts are converted into annual pandas tables. FilingLens calculates, where inputs permit:

#### Growth

- revenue growth;
- operating income growth;
- net income growth;
- operating cash flow growth;
- free cash flow growth.

#### Profitability

- gross margin;
- operating margin;
- net margin;
- return on assets;
- return on equity.

#### Liquidity and leverage

- current ratio;
- debt to assets;
- debt to equity.

#### Cash flow

- operating cash flow margin;
- free cash flow;
- free cash flow margin.

Free cash flow is calculated as operating cash flow minus capital expenditures. Return on assets and return on equity use average beginning-and-ending balances. Zero denominators and missing inputs remain unavailable instead of becoming infinite or fabricated values.

### Unusual-change analysis

FilingLens implements two complementary methods. The feature is deliberately described as unusual-change or anomaly analysis—not fraud detection.

1. **Year-over-year economic change** calculates prior value, current value, absolute change, and percentage change. A 20% movement is classified as Notable and a 40% movement as Significant.
2. **MAD robust z-score** applies the median absolute deviation method to the annual percentage-change series. Absolute scores of 2.5 and 3.5 correspond to Notable and Significant. At least four valid annual changes are required.

MAD was chosen because a mean and standard deviation can be distorted by a single large outlier in a short annual series. The resulting flags are screening signals that require accounting and business context.

The anomaly interface presents a compact, unit-aware table and a separate full-explanation selector so long text is never clipped. Users can disable coloring, color raw increases and decreases, or use a likely-impact mode that treats increases in costs, expenses, debt, and liabilities as unfavorable. Light, medium, and deep green/red shades correspond to movements below 20%, from 20% through 39.9%, and at least 40%, respectively. Direction labels carry a stable 1-to-6 semantic rank so browser-side column sorting runs from strongly favorable through strongly unfavorable, with descending sort applying the exact reverse. These colors and rankings are screening aids rather than investment conclusions.

### Filing document system

Official SEC filing HTML is:

1. downloaded through the cached SEC client;
2. cleaned of scripts, styles, navigation, repeated adjacent lines, and non-visible content;
3. divided using recognized 10-K and 10-Q section headings;
4. preserved as full cleaned text when section recognition fails;
5. split into approximately 450-word chunks with 60-word overlap;
6. deduplicated;
7. labeled with filing and source metadata.

Supported section patterns include Business, Risk Factors, Management's Discussion and Analysis, Financial Statements, and corresponding 10-Q sections.

### Local retrieval

A transparent local TF-IDF and cosine-similarity pipeline was implemented with scikit-learn. It uses English stop words, unigrams, and bigrams. A question is cleaned, vectorized, scored against filing chunks, and returned with the highest-ranking evidence.

Every result retains:

- relevance score;
- company and ticker;
- filing form and date;
- filing section;
- accession number;
- official source URL;
- exact retrieved passage.

Empty or lexically unmatched questions return no evidence rather than an arbitrary passage.

### Local model integration

FilingLens uses a provider abstraction for LM Studio and Ollama instead of hard-coding a service or model ID. Automatic mode checks LM Studio first and then Ollama; users can force either provider in `.env`. The tested LM Studio server exposed the intended model as:

`google/gemma-4-12b`

Both providers support:

- availability checks;
- model discovery;
- configured-model validation;
- automatic first-model selection;
- chat completion requests;
- temperature and output limits;
- latency and token metadata where available;
- clear offline and invalid-response errors.

Likely embedding models are removed from the chat-model selector. Filing Q&A and the longer analyst brief use each provider's local native chat endpoint with reasoning disabled so the output budget is reserved for visible answers. Filing Q&A also performs a deterministic scope preflight so clearly unrelated questions and requests for price predictions or buy/sell advice do not consume model resources.

### Grounded filing Q&A

The Ask the Filing feature combines:

- the user's question;
- top-ranked filing chunks;
- verified Python metrics;
- a security-focused system prompt;
- the selected local model.

Before generation, a conservative local scope check rejects clearly unrelated topics and unsupported trading-advice or price-prediction requests. Filing-related questions continue to retrieval and local generation; low-confidence answers must state when the supplied evidence is insufficient.

The system prompt requires the model to:

- use only supplied evidence and verified metrics;
- treat filing text as untrusted evidence, not instructions;
- preserve supplied numerical values;
- distinguish Python calculations from management commentary;
- avoid invented citations and unsupported claims;
- state when evidence is insufficient;
- avoid personalized investment advice and unsupported misconduct claims.

Answers expose numbered evidence passages and official SEC links.

### Analyst brief and exports

The local analyst brief contains:

- Company Overview;
- Financial Trend Summary;
- Key Year-over-Year Changes;
- Anomaly Flags;
- Management Commentary;
- Major Risk Factors;
- Liquidity / Capital Structure;
- Questions for Further Research.

The brief can be downloaded as Markdown or as a standalone, safely escaped HTML document.

### Streamlit application

The completed interface includes:

- Overview;
- Financial Trends;
- Anomaly Analysis;
- Insider Activity;
- Ask the Filing;
- Analyst Brief;
- Methodology.

Streamlit data caching prevents repeated rebuilding of unchanged company and filing data. Retrieval indexes and generated reports are retained in session state during the active browser session.

### Evaluation and testing

The automated suite contains **104 passing tests and zero failures**, with **85% package coverage**. Coverage includes:

- SEC headers, throttling, caching, retries, and validation;
- ticker normalization and company directory parsing;
- filing metadata and official source URLs;
- concept candidates and annual XBRL selection;
- comparative-period and debt-mapping regressions;
- free cash flow, growth, margins, returns, liquidity, and leverage;
- missing values, negative equity, and zero denominators;
- economic and robust anomaly detection;
- HTML cleanup, section fallback, and chunk metadata;
- retrieval ranking and empty-query behavior;
- LM Studio and Ollama discovery, request formatting, native reasoning control, model filtering, and offline behavior;
- grounded prompt isolation and metric injection;
- export escaping and evaluation helpers.

Live SEC smoke tests were completed for AAPL and MSFT. Both produced five annual periods, statements, ratio series, anomaly records, filing sections, and relevant retrieval results.

The final live model checks demonstrated:

- preservation of verified AAPL FY2025 revenue as `$416.16B`;
- four visible sources for a supported net-sales question;
- explicit insufficiency for an unsupported private-conversation question;
- all eight analyst-brief headings;
- 14 source markers;
- zero reasoning tokens in the completion-safe brief;
- approximately 98 seconds for grounded Q&A and 178 seconds for the full brief on the tested hardware.

### Visual and offline validation

The application was opened and inspected in a browser. Overview values, charts, tables, anomaly controls, and filing indexing rendered successfully. No final browser warnings or console errors remained.

No-LLM mode was tested using an unavailable local endpoint. FilingLens displayed an actionable warning while continuing to show SEC data, statements, ratios, charts, anomaly analysis, filing retrieval, and retrieval inspection.

## Repository deliverables

| Deliverable | Purpose |
|---|---|
| `app.py` | Streamlit application |
| `src/filinglens/sec/` | SEC client, ticker directory, submissions, filing retrieval, XBRL |
| `src/filinglens/analytics/` | Statements, ratios, trends, anomaly analysis |
| `src/filinglens/documents/` | HTML parsing, section detection, chunking, retrieval |
| `src/filinglens/llm/` | Provider interface, LM Studio, Ollama, Q&A, analyst brief |
| `src/filinglens/evaluation/` | Evaluation questions and benchmark runner |
| `src/filinglens/reporting/` | HTML export |
| `src/filinglens/ui/` | Chart and formatting helpers |
| `tests/` | Automated test suite |
| `scripts/setup_macos.sh` | Repeatable Mac environment setup |
| `scripts/doctor.py` | Configuration and local-service diagnostic |
| `.github/workflows/tests.yml` | Automated tests on supported Python versions |
| `docs/architecture.md` | Architecture and trust boundaries |
| `docs/methodology.md` | Calculation and selection methodology |
| `docs/evaluation.md` | Genuine test methodology and results |
| `docs/resume_summary.md` | Conservative résumé and interview material |
| `docs/user_guide.md` | End-user installation and usage guide |

## Security and privacy

- Generative runtime traffic stays on the configured LM Studio or Ollama loopback server.
- Filing text and user questions are not sent to a paid cloud LLM API.
- FilingLens contacts SEC.gov only for public filing data.
- Filing text is treated as untrusted content.
- The local `.env`, SEC cache, virtual environment, build artifacts, and local model files are excluded from Git.
- The real SEC contact value was not placed in public repository files.
- Streamlit usage telemetry is disabled in the committed configuration.

## Known limitations

- Issuer-specific and extension XBRL tags can leave some metrics unavailable.
- Period labels currently use the observation end year; non-calendar retail filers may need issuer-aware fiscal calendars.
- The system does not fully reconcile every restatement, dimension, acquisition, segment, or debt component.
- SEC filing section extraction is heuristic.
- TF-IDF is lexical and can miss semantically similar wording.
- Five annual periods provide limited statistical evidence for anomaly classification.
- AI citations show supplied passages but do not prove semantic entailment automatically.
- Local generation latency depends on model size, quantization, context, and hardware.
- The full 20-question dataset has not been manually scored for every available model.

## Recommended next improvement

The highest-value next development phase is an issuer-aware XBRL reconciliation layer. It should map issuer fiscal calendars, distinguish comparable contexts, reconcile total and component debt, identify restated periods, and provide explicit confidence notes for every normalized metric.

## Conclusion

FilingLens meets the core objective of combining official SEC data, deterministic financial analytics, transparent retrieval, and local source-grounded generation. It can be presented truthfully as a serious undergraduate finance, accounting, data-science, information-retrieval, and responsible-AI engineering project. Its strongest design feature is the separation of calculation from interpretation: SEC data flows into tested Python analytics, and the local model receives verified results only for explanation and synthesis.
