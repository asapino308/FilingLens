# Resume and interview summary

## One-line description

FilingLens is a local-first Python application that joins official SEC/XBRL data, deterministic financial analytics, statistical unusual-change screening, transparent filing retrieval, and source-grounded generation through LM Studio or Ollama.

## Conservative resume bullets

- Developed a modular Python and Streamlit application that retrieves cached SEC submissions, Company Facts, and 10-K documents; normalizes traceable annual financial data; and calculates historical statements, ratios, free cash flow, and robust unusual-change flags.
- Implemented local TF-IDF filing retrieval and provider-agnostic Q&A/report generation through LM Studio or Ollama, with visible SEC sources, verified Python metrics, graceful offline behavior, and 104 automated tests at 85% package coverage.

## Technology stack

Python 3.11+, pandas, NumPy, SciPy, scikit-learn, HTTPX, Beautiful Soup, lxml, Streamlit, Plotly, pytest, SEC EDGAR/XBRL, LM Studio, and Ollama.

## Technical skills demonstrated

API client design, responsible rate limiting, caching, retries, accounting-data normalization, XBRL concept mapping, pandas analysis, ratio design, robust statistics, HTML parsing, information retrieval, prompt-injection boundaries, provider abstraction, local inference, UI development, mocked testing, integration testing, and technical documentation.

## 30-second interview explanation

“FilingLens analyzes public companies from official SEC data without a paid financial or LLM API. I built a deterministic layer that maps annual XBRL facts and calculates ratios and anomaly screens, then a separate local retrieval layer that finds relevant 10-K passages. A local model receives only those passages plus verified Python metrics, so it explains the numbers rather than inventing them. The UI exposes provenance and citations, and still works when the model is offline.”

## Two-minute interview explanation

“I wanted a project that combined my finance/accounting background with data engineering and responsible AI. A ticker first resolves to a CIK from the SEC directory. A responsible HTTP client adds the SEC User-Agent, throttles requests, retries failures, and caches responses. Company Facts vary across issuers, so I created prioritized concept candidates and conservative annual filters while retaining accession, period, filing, unit, and concept provenance.

“The long data becomes pandas statement tables. Python—not the LLM—calculates growth, margins, ROA, ROE, liquidity, leverage, free cash flow, and two unusual-change methods. The second method uses median absolute deviation because a normal z-score is unstable with a short series and an outlier.

“For narrative analysis, I clean SEC inline-XBRL HTML, detect filing sections with fallback behavior, make overlapping chunks, and rank them with local TF-IDF. A provider abstraction discovers the exact model from LM Studio or Ollama. The prompt treats filing text as untrusted evidence, injects verified metrics, and requires source markers and explicit insufficiency. I tested AAPL and MSFT live, tested no-network cache replay and no-model behavior, and built 104 automated tests with 85% package coverage. The key limitation is issuer-specific XBRL complexity and local-model latency.”

## Important design decisions

- Separate data, analytics, and language trust layers.
- Prefer transparent TF-IDF over an early vector database.
- Group Company Facts by the observation period end rather than the containing filing's `fy`.
- Preserve missing values instead of guessing tag equivalence.
- Use MAD change scores and responsible “unusual change” terminology.
- Keep every runtime model call on the selected local provider's loopback server.
- Disable reasoning for the long brief so all required visible sections complete.

## Biggest technical challenges

1. SEC comparative facts repeat across later filings and can carry the later filing's fiscal-year metadata.
2. US-GAAP concepts vary across companies and debt components are not interchangeable.
3. Filing headings and inline-XBRL markup vary enough to require fallback parsing.
4. Short annual histories make statistical claims easy to overstate.
5. A local reasoning model can consume the output budget before completing a structured report.

## Known limitations

Issuer extensions and fiscal calendars need more reconciliation; retrieval is lexical; section detection is heuristic; five-year anomaly statistics are weak; generated claims still require source review; and local inference is slow on the tested model/hardware combination.

## Likely interviewer questions and factual answers

### Why not let the model calculate ratios?

Because deterministic Python calculations are reproducible, testable, and traceable. The model only receives labeled results for explanation.

### Why MAD instead of a standard z-score?

A single extreme change can shift the mean and standard deviation in a five-year series. Median and MAD resist that influence, although the short sample still limits confidence.

### How do you prevent prompt injection from a filing?

Filing passages are placed only in a labeled evidence block. The separate system prompt explicitly says document text is untrusted and cannot supply instructions.

### How do you know a citation is real?

The application controls the source list and renders metadata from retrieved chunks. The model may reference only those numbered chunks. Users can expand the exact passage and open the SEC URL.

### What did you test live?

AAPL and MSFT SEC/XBRL/filing pipelines, cache-only replay, current Gemma model discovery, supported and unsupported filing Q&A, the full analyst-brief heading set, and Streamlit startup. Automated behavior is covered by 104 tests with 85% package coverage.

### What would you improve first?

Build an issuer-aware fiscal-calendar and fact-reconciliation layer, then add manually labeled retrieval/evidence expectations for the full evaluation set.
