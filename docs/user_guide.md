# FilingLens User Guide

This guide documents the original Streamlit interface. For the new Mac app that opens without Terminal, use the [FilingLens desktop user guide](desktop_app.md). The Streamlit version remains available during the desktop rollout.

> **Responsible-use notice:** FilingLens is educational financial-analysis software. It is not investment advice, an audit opinion, or a fraud-detection system.

## 1. What FilingLens does

FilingLens helps users investigate U.S. public companies through two kinds of official SEC information:

- **Structured XBRL facts** used for financial statements, ratios, growth, and unusual-change analysis.
- **Filing documents** used for management commentary, risks, business descriptions, and source-grounded questions.

Python calculates the numerical results. LM Studio, local Ollama, Ollama Cloud, OpenAI, or Anthropic can explain those results and relevant filing passages, but the model is not the source of the calculations.

## 2. Requirements

The documented quick-start path requires:

- a Mac running macOS 14 or newer (Apple Silicon recommended);
- Python 3.11 or newer;
- an internet connection for package installation and first-time SEC downloads;
- an identifiable SEC automated-access User-Agent;
- A local LM Studio or Ollama model, or an Ollama Cloud, OpenAI, or Anthropic API key, only if you want AI questions and analyst briefs.

LM Studio requires Apple Silicon and officially recommends 16 GB or more RAM. Ollama also supports Intel Macs in CPU-only mode, although generation will be slower. The tested Gemma 4 12B MLX 5-bit model is approximately 7.7 GB before context/KV-cache overhead, so 16 GB is a practical minimum and 24 GB is more comfortable. Smaller models are appropriate for lower-memory systems. Linux and Windows may also work, but this guide focuses on macOS.

You do **not** need a paid financial-data API. AI is optional; Ollama Cloud may use free allowance or paid plan credits depending on the account.

## 3. Installation

Check Python first:

```bash
python3 --version
```

If it is older than 3.11, install a current build from [python.org](https://www.python.org/downloads/macos/) or use Homebrew. Then:

```bash
git clone https://github.com/asapino308/FilingLens.git
cd FilingLens
./scripts/setup_macos.sh
```

The helper creates `.venv`, installs every runtime dependency declared in `pyproject.toml`, and copies the safe configuration example to `.env` without overwriting an existing file. Developers can include pytest and coverage tools with:

```bash
./scripts/setup_macos.sh --dev
```

For manual installation and lower-level troubleshooting, see [macos_setup.md](macos_setup.md).

## 4. Configuration

If `.env` does not already exist, copy the example:

```bash
cp .env.example .env
```

Open `.env` and configure:

```dotenv
SEC_USER_AGENT=FilingLens/1.0 your-email@example.com
AI_PROVIDER=auto
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
LMSTUDIO_MODEL=
LMSTUDIO_API_KEY=
LMSTUDIO_TIMEOUT_SECONDS=300
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=
OLLAMA_TIMEOUT_SECONDS=300
OLLAMA_API_KEY=
OLLAMA_CLOUD_BASE_URL=https://ollama.com
OLLAMA_CLOUD_MODEL=
OLLAMA_CLOUD_TIMEOUT_SECONDS=300
OPENAI_API_KEY=
OPENAI_MODEL=
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=
```

### What each setting means

| Setting | Meaning |
|---|---|
| `SEC_USER_AGENT` | Identifies your automated SEC client and supplies a contact address. Replace the example email. |
| `AI_PROVIDER` | `auto` checks LM Studio, local Ollama, Ollama Cloud, OpenAI, and Anthropic. Use the corresponding provider ID to force one service. |
| `LMSTUDIO_BASE_URL` | Local LM Studio OpenAI-compatible endpoint. The normal default is `http://127.0.0.1:1234/v1`. |
| `LMSTUDIO_MODEL` | Optional exact model ID. Leave blank to discover models automatically. |
| `LMSTUDIO_API_KEY` | Optional local authentication key. Normally blank when LM Studio authentication is disabled. |
| `LMSTUDIO_TIMEOUT_SECONDS` | Maximum wait for one local generation. Default: 300 seconds. Increase for slower models. |
| `OLLAMA_BASE_URL` | Local Ollama service. The normal default is `http://127.0.0.1:11434`. |
| `OLLAMA_MODEL` | Optional exact installed Ollama tag. Leave blank to discover models automatically. |
| `OLLAMA_TIMEOUT_SECONDS` | Maximum wait for one Ollama generation. Default: 300 seconds. |
| `OLLAMA_API_KEY` | Secret key for direct Ollama Cloud access. Leave blank to disable the cloud provider. |
| `OLLAMA_CLOUD_BASE_URL` | Ollama Cloud host. Default: `https://ollama.com`. |
| `OLLAMA_CLOUD_MODEL` | Optional exact cloud model. Leave blank to discover available models. |
| `OLLAMA_CLOUD_TIMEOUT_SECONDS` | Maximum wait for one Ollama Cloud generation. Default: 300 seconds. |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Optional direct cloud API keys. Leave blank to disable each provider. |
| `OPENAI_MODEL` / `ANTHROPIC_MODEL` | Optional exact model IDs. Leave blank to discover available models. |

The `.env` file is private and ignored by Git. Do not publish it. The SEC contact address is not printed by the doctor, but it is transmitted to SEC.gov in the request header as required by the SEC's automated-access guidance.

## 5. Optional AI setup

You can use all deterministic financial features without an AI provider. To enable Overview Q&A, Ask the Filing, and Analyst Brief, choose one option.

### Option A: LM Studio

1. Install and open [LM Studio](https://lmstudio.ai/download).
2. Download an instruction-tuned chat model. On a 16-24 GB Apple Silicon Mac, Gemma 4 12B MLX 5-bit (approximately 7.7 GB) is a practical starting point.
3. Load it with an initial 16K-32K context rather than the maximum theoretical context.
4. Open LM Studio's Developer area.
5. Start the server on port `1234`.
6. Leave `LMSTUDIO_MODEL` blank unless you need to force a specific exposed model ID.

Verify with `curl http://127.0.0.1:1234/v1/models`. Keep network serving disabled unless you intentionally need LAN access; if you enable it, also enable authentication and restrict the network.

### Option B: Ollama

1. Install [Ollama for macOS](https://ollama.com/download) and open it.
2. On Apple Silicon, run `ollama run gemma4:12b-mlx`. The comparable portable tag is `gemma4:12b`; smaller Macs can use `gemma4:e2b-mlx`.
3. Type `/bye` after the initial chat. The model remains installed.
4. Set `AI_PROVIDER=ollama` if LM Studio may also be running.
5. Verify with `curl http://127.0.0.1:11434/api/tags`.

FilingLens discovers available chat-model IDs instead of guessing a filename. The first generation after changing ticker or filing evidence may be slower because the model cannot reuse the previous prompt cache. FilingLens uses a five-minute default timeout and compact prompt contexts; a smaller model will respond faster.

### Option C: Ollama Cloud API

1. Sign in to Ollama and create a key at [ollama.com/settings/keys](https://ollama.com/settings/keys).
2. In the FilingLens sidebar, expand **Add Ollama Cloud API key**.
3. Paste the key into the hidden field.
4. Choose **Connect for this session** to keep it only in the running browser session, or **Save on this Mac** to store it in the project's ignored `.env` with owner-only permissions.
5. Select **Ollama Cloud** and a discovered model. No restart or Terminal command is required.

Advanced users may still set `OLLAMA_API_KEY` directly in `.env`, set `AI_PROVIDER=ollama_cloud` to force cloud mode, and optionally set an exact `OLLAMA_CLOUD_MODEL`.

The key remains in `.env`, is added to the `Authorization: Bearer` request header, and is never displayed in the interface. When Ollama Cloud is selected, FilingLens sends the question, verified Python metrics, and selected filing passages to Ollama. Usage may consume account credits.

By default, the cloud model selector shows only the models currently covered by Ollama's free usage credits: `gemma4:31b`, `gpt-oss:120b`, `gpt-oss:20b`, `nemotron-3-nano:30b`, `nemotron-3-super`, and `nemotron-3-ultra`. The selection is retained across Streamlit reruns. Enable **Show models that may require paid credits** only after adding credits or upgrading the Ollama account.

## 6. Launching FilingLens

From the project directory:

```bash
.venv/bin/python scripts/doctor.py
.venv/bin/python -m streamlit run app.py
```

Open the displayed local address, normally:

`http://localhost:8501`

To stop FilingLens, return to the terminal and press `Control+C`.

## 7. First-use walkthrough

For a straightforward first session:

1. Enter `AAPL` in the **Ticker** field.
2. Keep **Historical periods** set to `5`.
3. Confirm that Overview shows Apple, its CIK, latest filing dates, and headline metrics.
4. Open **Financial Trends** and inspect the charts and statements.
5. Open **Anomaly Analysis** and review Notable or Significant movements.
6. Open **Ask the Filing**.
7. Click **Load and index latest 10-K**.
8. Enter a question such as “What factors did management say affected revenue?”
9. Click **Ask the filing** and inspect both the answer and each source passage.
10. Open **Analyst Brief** and generate the report if an AI provider is connected.

## 8. Sidebar reference

The sidebar controls the active company, historical window, cache, AI provider, and model.

### Ticker

Enter a U.S. public-company ticker such as:

- `AAPL`
- `MSFT`
- `WMT`
- `KO`
- `JPM`

FilingLens normalizes lowercase input to uppercase and converts dot-class symbols such as `BRK.B` to SEC-style `BRK-B`.

After a ticker is entered, FilingLens uses the SEC company directory to find the company name and zero-padded CIK.

Possible messages:

- **Ticker was not found:** the symbol may be invalid, delisted, foreign-only, or absent from the SEC directory.
- **Enter a valid U.S. ticker symbol:** the input contains unsupported characters or is too long.

### Historical periods

Selects how many recent annual periods are shown in tables, charts, ratios, and anomaly analysis.

- Minimum: 3
- Maximum: 10
- Default: 5

A longer window provides more history but may expose tag changes and non-comparable periods. The robust anomaly method needs at least four valid year-over-year changes, which generally requires five annual observations.

### Refresh SEC cache

Forces FilingLens to bypass both the current Streamlit data cache and the persistent SEC response cache for the active reload.

Use it when:

- a new filing was recently published;
- you suspect a cached response is incomplete;
- you want the latest SEC directory or Company Facts data.

Do not click it repeatedly. Normal reruns should use the cache to avoid unnecessary SEC traffic.

### AI provider and model

Choose among every available provider and model. With `AI_PROVIDER=auto`, FilingLens checks LM Studio, local Ollama, Ollama Cloud, OpenAI, and Anthropic. Set the variable to force one provider. Ollama Cloud appears only when its key authenticates and models are returned.

Changing the model does not change SEC data or Python calculations. It changes only generative explanations.

### AI provider status

Possible states include:

- **Provider: Connected - N model(s):** the service is reachable and chat models were discovered.
- **No configured AI provider exposed an available chat model:** no local service was reachable and Ollama Cloud was not configured or available.
- **No local chat models:** download/load a model in LM Studio or install one with Ollama.
- **Ollama Cloud requires OLLAMA_API_KEY:** expand **Add Ollama Cloud API key** in the sidebar and connect or save the key there.
- **Ollama Cloud did not authorize the selected model:** the account returned HTTP 402. Choose one of the free-credit models shown by default, confirm free usage remains in Ollama Usage settings, or add credits. FilingLens intentionally hides paid models unless **Show models that may require paid credits** is enabled.

When offline, deterministic features continue working and the Overview model value shows **Offline**.

## 9. Overview tab

Overview is the high-level company summary.

### Company heading

Shows the SEC company name and normalized ticker.

### CIK

The Central Index Key is the SEC's unique company identifier. FilingLens displays the normalized ten-digit version.

### Latest 10-K

Shows the filing date of the most recent annual report found in recent SEC submissions.

### Latest 10-Q

Shows the filing date of the most recent quarterly report found in recent SEC submissions.

### AI provider and model

Shows the selected provider and exact LM Studio/Ollama model ID, or **Offline**.

### Headline metrics

The latest available annual period displays:

- **Revenue:** mapped annual sales/revenue fact.
- **Operating Income:** profit from core operations before interest and taxes, based on the selected XBRL concept.
- **Net Income:** annual profit after expenses and taxes.
- **Free Cash Flow:** operating cash flow minus capital expenditures, calculated in Python.

If a reliable mapping is not available, the value appears as **Unavailable**.

Each headline metric also shows its latest year-over-year percentage movement when a valid prior period exists.

### Ratio snapshot

Shows the latest revenue growth, gross margin, operating margin, current ratio, and debt-to-equity value using percentage or multiple units as appropriate.

### Recent SEC filings and flags

Provides direct official links to the latest 10-K and 10-Q, including filing/report dates and accession numbers. The latest-period flag counters summarize Notable and Significant unusual-change records; they are screening signals, not misconduct findings.

### Ask a general company question

Enter a broad but filing-related question about the business, financial performance, liquidity, strategy, or risks. FilingLens automatically indexes the latest 10-K if necessary, retrieves relevant passages, and combines them with verified Python metrics. Answers expose the supporting SEC passages. This area is not connected to live news or market prices.

### Value provenance

Expand this area to inspect the long-form source table.

| Column | Meaning |
|---|---|
| `ticker` | Normalized market ticker |
| `company_name` | SEC entity name |
| `cik` | Ten-digit SEC identifier |
| `form` | Filing form supplying the fact, normally 10-K or 10-K/A |
| `accession_number` | Unique SEC filing accession |
| `filing_date` | Date the supplying filing was submitted |
| `fiscal_year` | Annual label derived from the observation period end |
| `fiscal_period` | SEC fiscal-period label, normally FY |
| `period_start` | Beginning date for duration facts |
| `period_end` | End date of the represented observation |
| `metric` | FilingLens normalized metric name |
| `value` | Raw selected numerical value |
| `unit` | XBRL unit, currently normally USD |
| `xbrl_concept` | Exact selected US-GAAP concept |

Use provenance when a value looks surprising. Confirm the concept, period, filing, and original SEC report before relying on it.

## 10. Financial Trends tab

This tab provides readable multi-year statements and ratios in four subtabs: **Income Statement**, **Balance Sheet**, **Cash Flow**, and **Ratios & Growth**. Each account row includes a compact sparkline, one formatted value per fiscal year, and the latest comparable movement.

Select any main account row to open its detail panel. The panel shows the latest value, prior value, latest change, a larger interactive chart, and any reliable components or calculation inputs available to FilingLens. Use the chart toolbar to zoom, reset the axes, view fullscreen, or download a PNG.

Growth and return series naturally lack a value in their first displayed year because they require a prior-year comparison. FilingLens omits that missing base point from the compact sparkline while retaining the unavailable year as `—` in the table.

### Income Statement

Groups the available annual series into:

- **Revenue and gross profit:** revenue, cost of revenue, and gross profit;
- **Operating and net income:** operating income and net income.

Only reliably mapped accounts are displayed. FilingLens does not manufacture missing line items to resemble a complete statement. Direct accounts such as revenue remain at the reported total when a trustworthy product or segment breakdown is not available from normalized Company Facts. Derived accounts such as gross profit and free cash flow expose their available inputs without adding separate charts for those component rows.

### Balance Sheet

Separates assets from liabilities and equity:

- **Assets:** cash and cash equivalents, current assets, and total assets;
- **Liabilities and equity:** current liabilities, total liabilities, long-term debt, and stockholders' equity.

### Cash Flow

Shows operating cash flow, capital expenditures, and Python-calculated free cash flow. Capital expenditures are displayed as reported by the SEC fact; free cash flow is operating cash flow minus capital expenditures.

### Ratios & Growth

Organizes calculated metrics into four groups:

- **Growth:** revenue, operating income, net income, operating cash flow, and free cash flow growth;
- **Margins:** gross, operating, net, operating cash flow, and free cash flow margins;
- **Returns:** return on assets and return on equity;
- **Liquidity and leverage:** current ratio, debt to assets, and debt to equity.

Percentage metrics show their latest change in percentage points. Current ratio and debt to equity use multiples and show their latest change in `x` units.

### Source and interpretation

All statement values come from the same normalized SEC/XBRL data used elsewhere in FilingLens. Open **Value provenance** on the Overview tab to inspect the exact concept, reporting period, filing date, and accession number behind a surprising account value.

#### Growth fields

Growth is calculated as:

`(current value − prior value) ÷ absolute prior value`

Using the absolute prior value preserves the direction of change after a negative comparison period.

#### Profitability fields

- `gross_margin`
- `operating_margin`
- `net_margin`
- `return_on_assets`
- `return_on_equity`

ROA and ROE use average beginning-and-ending balances. The first displayed period can be blank when the prior balance is not available.

#### Liquidity and leverage fields

- `current_ratio`: current assets ÷ current liabilities
- `debt_to_assets`: long-term debt ÷ total assets
- `debt_to_equity`: long-term debt ÷ stockholders' equity

A negative debt-to-equity result can occur when reported equity is negative. It is mathematically defined but requires careful interpretation.

#### Cash-flow fields

- `operating_cash_flow_margin`
- `free_cash_flow_margin`
- `operating_cash_flow_growth`
- `free_cash_flow_growth`

Blank values normally mean that an input, comparison period, or valid denominator was unavailable.

## 11. Anomaly Analysis tab

This tab screens for unusual financial movements. It does **not** determine fraud, manipulation, misconduct, or deception.

### Severity filter

Choose which records to display:

- **Normal:** below both screening thresholds.
- **Notable:** absolute economic change of at least 20% or robust-score magnitude of at least 2.5.
- **Significant:** absolute economic change of at least 40% or robust-score magnitude of at least 3.5.

The default shows Notable and Significant records.

### Change coloring

Choose one of three display modes:

- **Likely financial impact:** green means likely favorable and red likely unfavorable. Increases in costs, expenses, debt, and liabilities are treated as unfavorable; decreases in those metrics are favorable. Other metrics use higher-is-better as a screening assumption.
- **Raw increase / decrease:** every numerical increase is green and every decrease is red, regardless of economic meaning.
- **Off:** removes directional cell coloring.

Each direction has three shades: light below 20%, medium from 20% through 39.9%, and deep at 40% or more. The direction is a visual research aid, not an investment conclusion; whether a movement is actually favorable depends on its cause and context.

The Direction column includes a stable rank so its header sorts by meaning instead of alphabetically. In likely-impact mode, ascending order is `1 · Strongly favorable`, `2 · Moderately favorable`, `3 · Lightly favorable`, `4 · Lightly unfavorable`, `5 · Moderately unfavorable`, then `6 · Strongly unfavorable`. Clicking the header again applies the exact reverse order. Raw increase/decrease mode uses the same 1-to-6 structure from strongest gain to strongest loss.

### Full explanation

Use the selector above the table to display the complete explanation and detection method for a specific metric and period. This keeps the main grid compact while ensuring that the explanation is not clipped. Currency values, percentages, percentage-point changes, and ratio multiples are formatted in their appropriate units.

### Anomaly table fields

| Field | Meaning |
|---|---|
| `metric` | Financial value or ratio being evaluated |
| `period` | Current annual period |
| `prior_value` | Value in the prior available annual period |
| `current_value` | Value in the current period |
| `absolute_change` | Current value minus prior value |
| `percentage_change` | Absolute change divided by the absolute prior value |
| `anomaly_score` | MAD robust z-score for the change series, when enough history exists |
| `severity` | Normal, Notable, or Significant |
| `method` | Economic change alone or economic change plus MAD robust z-score |
| `explanation` | Plain-language description and responsible-use warning, displayed in full above the grid |

### How to interpret a flag

A flag answers: “Did this annual movement cross the documented screen?” It does not answer why it happened or whether it was good, bad, intentional, or improper.

Recommended follow-up:

1. Open Financial Trends to view the history.
2. Check Value provenance for comparable facts and periods.
3. Ask the filing what management said about the movement.
4. Read the original SEC source.

## 12. Insider Activity tab

This tab retrieves recent official SEC Forms 4 and 4/A for the active company. It provides a Finviz-style insider-transaction workflow without scraping a third-party website.

### Load insider activity

Choose how many recent ownership filings to review, then click **Load insider activity**. SEC responses are cached locally, so unchanged filings do not need to be downloaded again.

The summary shows:

- total value of transaction-code `P` open-market/private purchases;
- total value of transaction-code `S` open-market/private sales;
- purchase value minus sale value;
- number of distinct reporting insiders.

Grants, awards, option exercises, gifts, tax-related dispositions, conversions, and other transaction codes are displayed separately and excluded from the directional purchase/sale totals. Form 4/A amendments remain visible but are excluded from summary totals.

Each transaction retains the insider name and role, dates, transaction code and description, shares, price, estimated value, ownership after the transaction, direct/indirect status, derivative-security indicator, 10b5-1-plan indicator, and direct SEC filing link. A CSV download is available.

Insider activity is not a standalone buy or sell signal. Review the source footnotes because sales may reflect diversification, taxes, compensation, charitable gifts, or pre-arranged plans.

## 13. Ask the Filing tab

This tab retrieves passages from the latest 10-K and optionally asks the selected AI model to answer using those passages.

### Evidence source

Shows the filing form and filing date that will be indexed.

### Load and index latest 10-K

Downloads or loads the cached official filing, cleans it, detects sections, creates overlapping chunks, and builds the local TF-IDF index.

This button must be used before asking questions or generating a brief. After indexing, the app shows:

- number of chunks;
- number of detected sections.

### Question

Enter a filing-related question. Good questions use language likely to appear in the report.

Examples:

- What factors did management say affected revenue?
- Why did operating margin change?
- What does management say about liquidity?
- What were the major business risks?
- What factors affected operating cash flow?
- How does management describe competitive pressure?
- What changed in capital expenditures?

Avoid overly broad questions such as “Tell me everything.” Focused questions produce more relevant evidence.

### Ask the filing

Runs a deterministic scope preflight, ranks the filing chunks, sends the top passages and verified Python metrics to the selected model, and displays the response. Generation disables model reasoning where supported so the output budget is reserved for the visible, cited answer.

Clearly unrelated questions—such as weather or sports questions—and requests for future price predictions or buy/sell recommendations are stopped before model generation. The app labels these requests as outside the indexed filing's scope and suggests filing-related topics. This avoids spending compute or cloud credits on a request that the evidence cannot support.

The button is disabled when no supported chat model is available. You can still inspect deterministic financial data without AI.

### Answer

The model is instructed to use `[Source N]` markers for filing-derived claims. Numerical values supplied under Verified FilingLens Metrics came from Python and should be distinguished from management commentary.

If the evidence is insufficient, the expected response says so. An unsupported answer should not be treated as established just because it sounds plausible.

### Sources

Each expandable source shows:

- source number;
- filing section;
- TF-IDF relevance score;
- filing form and date;
- official SEC hyperlink;
- exact retrieved filing passage.

Always compare important AI claims with the displayed passages. A relevance score measures lexical similarity, not factual correctness.

## 14. Analyst Brief tab

The Analyst Brief combines verified metrics, unusual-change records, and retrieved filing evidence into a structured report.

### Prerequisites

- Load and index the latest 10-K in Ask the Filing.
- Connect a local or cloud AI provider and select an available text model.

If either prerequisite is missing, the tab displays an explanatory message.

### Generate analyst brief

Creates a report with eight sections:

1. Company Overview
2. Financial Trend Summary
3. Key Year-over-Year Changes
4. Anomaly Flags
5. Management Commentary
6. Major Risk Factors
7. Liquidity / Capital Structure
8. Questions for Further Research

Generation time depends on the selected provider. Local models may take several minutes; cloud models are normally faster but may consume plan credits.

### Download Markdown

Downloads the displayed brief as a `.md` file suitable for GitHub, note-taking tools, or further editing.

### Download HTML

Downloads a standalone `.html` report with simple styling. Model text is escaped during export to prevent injected HTML from being executed.

### Reviewing a brief

Before sharing:

1. Confirm all required sections are present.
2. Check numerical statements against Overview and Financial Trends.
3. Match every `[Source N]` claim to an available source passage.
4. Remove or qualify unsupported conclusions.
5. Retain the educational-use disclaimer.

## 15. Methodology tab

This tab gives a concise explanation of:

- the three-layer architecture;
- annual XBRL selection;
- Python calculations;
- unusual-change methods;
- TF-IDF retrieval;
- source-grounded AI explanations;
- privacy and responsible use.

Use it when explaining how a displayed value or AI answer was produced. More detail is available in `docs/methodology.md` and `docs/architecture.md`.

## 16. Common workflows

### Investigate a large revenue change

1. Select the company and five or more periods.
2. Review the income statement chart.
3. Check `revenue_growth` in Ratios and growth.
4. Inspect any revenue anomaly record.
5. Verify the current and prior revenue facts in Value provenance.
6. Ask: “What factors did management say affected revenue?”
7. Open each cited MD&A passage.

### Review liquidity

1. Check cash, current assets, and current liabilities.
2. Review `current_ratio`.
3. Review operating cash flow and free cash flow.
4. Ask: “What does management say about liquidity and capital resources?”
5. Inspect cited credit-facility, debt, or cash-management passages.

### Review risk factors

1. Load the latest 10-K.
2. Ask a focused risk question, such as cybersecurity, competition, regulation, or supply chain.
3. Confirm that the top passages come from Risk Factors or relevant Business/MD&A sections.
4. Read the original SEC filing for complete context.

### Create a portfolio demonstration

1. Analyze two companies with different industries.
2. Capture screenshots that do not expose private settings.
3. Export one reviewed analyst brief.
4. Cite the official SEC filings.
5. Explain the deterministic-versus-generative separation.
6. State the project's limitations honestly.

## 17. Caching and data freshness

FilingLens has two cache layers:

- **Persistent SEC cache:** stored under `data/cache/` and reused between application sessions.
- **Streamlit cache:** keeps company and filing results during application use.

Retrieval indexes and generated briefs are kept in the current browser session state. Changing to another company's filing requires a new index. Closing the browser session can clear session-only results.

Use Refresh SEC cache for newly published filings. Normal use should not repeatedly redownload unchanged data.

## 18. Error and status messages

### SEC_USER_AGENT must identify the application

Your `.env` value is blank or lacks a contact email. Update `SEC_USER_AGENT` and restart Streamlit.

### Ticker was not found

Confirm the ticker and check whether the issuer files with the SEC under another class symbol.

### SEC request failed

Possible causes include internet loss, SEC maintenance, invalid automated-access headers, or a temporary block. Wait before retrying. Do not increase the request rate.

### No reliable XBRL concept mapping was found

The issuer may use an extension concept or a different accounting presentation. Treat the metric as unavailable and inspect the filing directly.

### No configured AI provider exposed an available chat model

Start LM Studio on port `1234` or Ollama on port `11434`, or add `OLLAMA_API_KEY` for Ollama Cloud. Deterministic features remain available.

### The provider exposes no chat models

For LM Studio, load a chat model or enable JIT model loading. For Ollama, install a model with `ollama run gemma4:12b-mlx`. Refresh the browser afterward.

### Configured model is not exposed

The exact `LMSTUDIO_MODEL` value in `.env` does not match the current `/v1/models` result. Clear it for automatic selection or replace it with the current exact ID.

### Question is outside the indexed filing's scope

The app found no adequate filing relationship or detected a request for price predictions or buy/sell advice. Rephrase the question around the company's business, financial performance, liquidity, management discussion, or risk factors. Confirm that the correct ticker's 10-K is indexed.

### The selected model produced no visible answer

This is a model-generation problem, not an out-of-scope decision. FilingLens disables reasoning/thinking for filing Q&A so the output budget is reserved for the answer. If an empty response still occurs, retry once, reduce other local-model workloads, or select another compatible chat model.

### Local model generation exceeded the configured timeout

Changing tickers replaces the filing evidence, so the selected provider may need to process a cold prompt instead of reusing its previous prompt cache. Wait for any earlier generation to finish, then retry. If the model is simply slow, increase the corresponding `LMSTUDIO_TIMEOUT_SECONDS`, `OLLAMA_TIMEOUT_SECONDS`, or `OLLAMA_CLOUD_TIMEOUT_SECONDS` value in `.env` and restart FilingLens, or select a smaller model. If the provider reports a context-window limit, configure at least an 8K context window; FilingLens already limits Q&A evidence and compacts anomaly records before generation.

## 19. Interpreting missing data

Missing values are intentional when FilingLens cannot calculate a result reliably.

Common reasons:

- no mapped XBRL concept;
- missing comparison period;
- non-annual or non-comparable fact;
- zero denominator;
- insufficient observations for a robust score;
- issuer-specific extension or dimension;
- metric not applicable to the company's presentation.

Do not replace an unavailable value with an AI guess.

## 20. Privacy and security

- Local model inference stays at the configured LM Studio or Ollama loopback address.
- When Ollama Cloud is selected, the question, verified metrics, and retrieved SEC filing passages are sent to `https://ollama.com/api` using Bearer authentication.
- The SEC contact email remains in ignored `.env` but is transmitted to SEC.gov in the required User-Agent header.
- Streamlit usage-statistics collection is disabled in `.streamlit/config.toml`.
- Filing text and questions are sent to OpenAI or Anthropic only when that provider is selected. Keys are included only in authenticated requests to the selected service.
- SEC.gov receives the public-data requests and configured User-Agent.
- Filing text is untrusted evidence and is never allowed to override the system prompt.
- Keep `.env` private.
- Do not commit downloaded filings, SEC caches, local model files, tokens, or personal contact values.

## 21. Running the tests

Activate the virtual environment and run:

```bash
.venv/bin/python -m pytest
```

The live SEC, LM Studio, and Ollama checks are separate from the unit tests so routine test runs do not repeatedly contact external services or perform slow local generation.

## 22. Shutting down and restarting

To stop the app, press `Control+C` in the Streamlit terminal.

To restart:

```bash
cd /path/to/FilingLens
.venv/bin/python -m streamlit run app.py
```

Cached SEC data remains available after restart.

## 23. Quick-reference glossary

| Term | Definition |
|---|---|
| CIK | SEC Central Index Key identifying a filer |
| 10-K | Annual report filed with the SEC |
| 10-Q | Quarterly report filed with the SEC |
| XBRL | Structured financial-reporting data and taxonomy |
| Accession number | Unique identifier for an SEC filing submission |
| Company Facts | SEC API containing an issuer's XBRL facts |
| MD&A | Management's Discussion and Analysis |
| Provenance | Metadata showing where a selected value came from |
| Free cash flow | Operating cash flow minus capital expenditures in FilingLens |
| TF-IDF | Local lexical weighting method used to rank filing chunks |
| Cosine similarity | Similarity score between the question and a filing chunk |
| MAD | Median absolute deviation, used for robust anomaly scores |
| Grounding | Restricting model output to supplied evidence and verified metrics |
| LM Studio | Graphical local model server supported for generative features |
| Ollama | Local model server and authenticated cloud API supported for generative features |

## 24. Final user checklist

Before relying on or sharing an analysis:

- [ ] Confirm the correct company and CIK.
- [ ] Confirm the filing and annual periods.
- [ ] Inspect XBRL provenance for important values.
- [ ] Review missing and non-comparable data.
- [ ] Treat anomaly flags as screening signals only.
- [ ] Read the retrieved evidence and original SEC filing.
- [ ] Verify AI numerical statements against Python tables.
- [ ] Confirm citations refer to supplied passages.
- [ ] Retain the educational-use disclaimer.
