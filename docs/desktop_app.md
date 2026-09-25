# FilingLens Desktop User Guide

The Mac app opens FilingLens as a normal application. Use it to review SEC financial statements, read filings, investigate unusual movements and insider transactions, and ask optional AI questions that cite filing passages. The numbers come from SEC data and Python calculations; the AI model does not create the financial values. This is educational software, not investment advice.

## Open the app

1. In Finder, open **Applications** in your home folder and double-click **FilingLens.app**.
2. Developers can find a local build under `desktop/src-tauri/target/release/bundle/macos`.
3. Allow a little time on the first launch while the bundled local service starts. You do not need to run a command or visit a local web address.

Developer builds may be unsigned. A public release must be code signed and notarized before distribution. The original `Launch FilingLens.command` still starts the Streamlit source interface if you need it.

On the first packaged launch, FilingLens opens Settings so you can enter your own SEC contact. The download has no saved research or AI key. After use, your SEC cache and preferences remain under `Library/Application Support/FilingLens`, and optional cloud AI keys remain in your macOS Keychain. The app does not import settings or cache from a source checkout.

## Start with a company

Use the search field at the upper left to enter a ticker or company name. Select a suggestion, or enter a ticker and press Return. The current ticker appears at the top right. **Historical periods** changes the annual comparison window from three to ten years. The refresh button beside the ticker checks the SEC again for the selected company; otherwise FilingLens reuses its local cache. Source notes show when the Company Facts cache was updated.

Enter a name and contact email in **SEC User-Agent** on first launch, then save. The SEC public-data APIs do not require an API key; they ask automated clients to identify themselves in a request header. The contact address is sent to SEC.gov and is not displayed to other app users.

## What each workspace area does

### Overview

The four headline figures show the latest available annual revenue, operating income, net income, and free cash flow. Changes compare with the preceding reported year. A separate **Latest quarterly filing** card shows three-month figures from the most recent 10-Q when reliably mapped. Ratio, signal, and filing cards lead to detail. **Ask about this company** lets you choose the latest 10-K or 10-Q; answers use the selected filing plus clearly labeled verified metrics. **Inspect value provenance** lists reported annual XBRL concepts and filing dates.

**Your research approach** lets you choose **Explore**, **Evaluate**, or **Follow**. It changes the starting steps and suggested filing questions, while the underlying SEC facts and answers stay the same. The choice is saved on this Mac. **Save company** adds the current company to the sidebar for quick access; saved companies are a research list, not a portfolio.

**Since your last check** compares the current loaded SEC data with the last snapshot this Mac saw for that company. It highlights a new annual or quarterly filing and changes in the four headline annual figures, each with a source link. The first visit creates the starting snapshot. This comparison is limited to the data currently loaded; use the refresh button to check the SEC for newer records. It does not monitor filings in the background or assess investment merit.

### Financials

Switch between **Annual history** and **Latest 10-Q**. Annual history retains the Income statement, Balance sheet, Cash flow, and Ratios & growth views. Click an annual account row for its trend, available calculation components, and source concept. The latest-quarter view separates three-month income values, quarter-end balances, and fiscal year-to-date cash-flow values. It displays each mapped US-GAAP concept and period; it does not mix these values into annual charts. An em dash means no reliable value was available; it is not zero.

**What makes up the numbers?** adds a filing-specific revenue-to-profit breakdown. Choose the latest 10-Q or 10-K, then **Brief view** for a plain-English explanation and the main revenue categories, or **Deep dive** for the reported income lines, nonoverlapping operating-expense detail, revenue splits, periods, and XBRL concepts. Product, business-segment, and geographic revenue are alternative views of the same total. A split appears only when its inline-XBRL categories reconcile to the filing's reported revenue. Some companies do not disclose a breakdown that can be verified this way.

### Filings and research

Choose the latest **10-K** or **10-Q** above **Read filing** and **Ask the filing**. Read filing loads the selected document's sections; Ask the filing answers from that document's numbered passages. **Analyst brief** brings together both filings when available, with a latest-quarter section and source labels identifying each filing. It keeps annual movement screens and quarterly figures distinct. The brief aims for short, plain-English sections that explain the most useful figures; its output allowance is 4,000 tokens so a complete brief has room to finish. Generate a new brief after updating the app to see this format. Download the resulting Markdown if useful. The document shelf links to official SEC filings.

### Signals

**Anomaly analysis** screens annual changes by severity and direction. It starts with raw numerical increases and decreases; an optional color view shows a simple directional impact heuristic. **Insider activity** loads recent Forms 4 and filters purchases, sales, and other transactions; each row links to its SEC filing.

### Settings

Save the SEC User-Agent and optional Ollama Cloud, OpenAI, or Anthropic key. Select a provider and an available model. **Check again** refreshes model availability. Cloud keys are saved in macOS Keychain and are never shown after saving.

## Understand the financial and signal displays

FilingLens selects annual observations from mapped SEC US-GAAP concepts. It uses the latest filed duplicate within a concept and keeps the filing date and accession as provenance. Free cash flow is operating cash flow minus capital expenditures. Ratios and growth are calculated in Python from the selected annual values. If a component or comparable prior period is missing, the derived value stays unavailable rather than being estimated.

An anomaly is a screen for an unusual year-over-year movement, not a conclusion about fraud or future returns. Economic thresholds mark changes of at least 20% as notable and 40% as significant. When enough history exists, a median-absolute-deviation score adds a statistical screen. The favorable/unfavorable label assumes lower costs, expenses, debt, and liabilities are generally preferable; company context may change that interpretation. In raw mode, green means an increase and red means a decrease, irrespective of financial merit. Light, medium, and deep shades indicate movement magnitude.

Insider value totals include only non-amended open-market purchase and sale rows with reported value. Grants, exercises, gifts, tax-related transactions, and amendments remain visible in the detail table but do not enter those totals. A sale can reflect taxes, diversification, or a pre-arranged plan. Read the Form 4 footnotes before interpreting a transaction.

## Set up optional AI

Financials, filing links, anomaly screens, and insider data work without AI. For questions or analyst briefs, choose a connected provider and model in **Settings**:

- **LM Studio:** Open LM Studio, load a chat model, and start its local server. FilingLens checks the configured local endpoint.
- **Local Ollama:** Open Ollama and ensure a chat model is installed. FilingLens discovers its available models.
- **Ollama Cloud:** Save an API key in Settings. The app shows currently available cloud models and initially favors models marked for free usage credits. Turn on **Show models that may require paid credits** only if your account supports them.
- **OpenAI or Anthropic:** Save the respective API key in Settings. The app lists available models from that provider; API usage may incur charges.

Ask the Filing is for the company's business, financial performance, liquidity, management discussion, and risks. Clearly unrelated questions, price predictions, and buy or sell requests are declined before model generation. A response may still say evidence is insufficient; inspect its cited passages. The analyst brief searches both the latest 10-K and 10-Q when available and takes longer because it generates a larger document. Cloud mode sends the question, selected filing passages, and verified metrics to the selected cloud provider. Local mode sends those prompts only to your local model service.

## If something does not work

| Message or symptom | What to do |
|---|---|
| No SEC company data | Confirm the ticker and SEC User-Agent in Settings. Use refresh after reconnecting to the internet. Cached companies can still load while offline. |
| Local service did not start | Quit and reopen FilingLens. The original Streamlit launcher remains available while you troubleshoot. |
| AI model unavailable | Start LM Studio or Ollama and load a chat model, then click **Check again** in Settings. Financial research does not require AI. |
| Model timed out or returned an invalid response | Try a smaller or faster model and retry. This is a model-service failure, not proof that the question was out of scope. |
| Ollama Cloud says payment required | Choose a currently free-credit model, check account credits, or switch to a local model. A cloud key alone does not guarantee paid-model access. |
| Filing question declined as out of scope | Ask about information likely to appear in the company's latest 10-K. Market prices and trade recommendations are outside this tool. |
| An account is missing | The selected SEC facts did not support a reliable mapping. FilingLens does not invent a replacement value. |

## Data and privacy

SEC files are public and downloaded from SEC.gov. The Mac app listens only on your computer and uses a private session token between its window and local service. It stores SEC cache and non-secret preferences under `Library/Application Support/FilingLens`; cloud keys go to macOS Keychain. Nothing from an existing Streamlit checkout is copied into a new Mac installation. FilingLens does not provide real-time prices or personalized investment advice.
