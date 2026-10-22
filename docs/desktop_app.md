# FilingLens Desktop User Guide

The Mac app opens FilingLens as a normal application. Use it to review SEC financial statements, read filings, investigate unusual movements and insider transactions, and ask optional AI questions that cite filing passages. The numbers come from SEC data and Python calculations; the AI model does not create the financial values. This is educational software, not investment advice.

## Download and open the Mac app

The current DMG and ZIP are for **Apple Silicon (M-series) Macs running macOS 14 or newer**. It has an ad hoc code signature and has **not** been notarized by Apple. Mac users therefore need to approve this specific download manually. It does not require an Apple Developer account, Terminal, Python, Node, or Rust on the user's Mac.

1. From the [FilingLens GitHub Releases page](https://github.com/asapino308/FilingLens/releases), download `FilingLens-0.3.0-macOS-arm64.dmg` under **Assets**. Do not download a copy from an unrelated site.
2. Open the DMG and drag **FilingLens.app** onto the **Applications** shortcut. Quit any older FilingLens app first and confirm **Replace** if updating. Eject the disk image after copying.
3. Open **FilingLens.app** from Applications. Because Apple has not notarized this build, macOS may say it **cannot check the app for malicious software** or **cannot verify the developer**. Dismiss that alert without moving the app to Trash.
4. Open **Apple menu > System Settings > Privacy & Security**. Scroll to **Security** and find the blocked FilingLens app. Depending on your macOS version, click **Open** or **Open Anyway**, then confirm the follow-up **Open Anyway/Open** prompt. Enter your Mac login password if asked. Apple says **Open Anyway** is available for about one hour after the first blocked launch; if it is missing, try opening FilingLens again and return to this screen.
5. Wait a few seconds for the window and bundled local service. No browser address or command is needed.

Only use **Open Anyway** if you trust the download from this repository's release page. If macOS says the app **contains malware**, **is damaged**, or its contents **have been modified**, stop and report the issue instead of overriding the warning. Apple's [guide to opening an unverified app](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unknown-developer-mh40616/mac) explains the controls, and its [app safety guidance](https://support.apple.com/102445) explains what the warnings mean.

The ZIP remains available as an alternative: unzip it and move **FilingLens.app** into Applications. The DMG contains the same verified app; it does not install a background service or remove the first-launch approval requirement.

FilingLens needs network access to download public SEC filings and to discover models from configured cloud providers; generation sends research only to the selected provider. Normal research does not require Full Disk Access or access to your documents. If macOS asks for Keychain access while you save a cloud AI key, confirm that you initiated the save in FilingLens before allowing it. The original `Launch FilingLens.command` remains available for people building the Streamlit source interface.

On the first packaged launch, FilingLens opens Settings so you can enter your own SEC contact. The download has no saved research or AI key. After use, your SEC cache and service settings remain under `~/Library/Application Support/FilingLens`, and optional cloud AI keys remain in your macOS Keychain. The app does not import settings or cache from a source checkout. Reinstalling on the same Mac account preserves data saved by earlier use; it is not a data-reset operation.

## Start with a company

Use the search field at the upper left to enter a ticker or company name. Select a suggestion, or enter a ticker and press Return. The current ticker appears at the top right. **Historical periods** changes the annual comparison window from three to ten years. The refresh button beside the ticker checks the SEC again for the selected company; otherwise FilingLens reuses its local cache. Source notes show when the Company Facts cache was updated.

Enter a name and monitored contact email in **SEC User-Agent** on first launch, for example `FilingLens/1.0 Researcher name@example.com`, then save. The SEC public-data APIs do not require an API key; they ask automated clients to identify themselves in a request header. The contact address is sent to SEC.gov and is not displayed to other app users. FilingLens limits request speed and caches responses on your Mac.

## What each workspace area does

### Overview

The four headline figures show the latest available annual revenue, operating income, net income, and free cash flow. Changes compare with the preceding reported year. A separate **Latest quarterly filing** card shows three-month figures from the most recent 10-Q when reliably mapped. Ratio, signal, and filing cards lead to detail. **Ask about this company** lets you choose the latest 10-K or 10-Q; answers use the selected filing plus clearly labeled verified metrics. **Inspect value provenance** lists reported annual XBRL concepts and filing dates.

**Your research approach** lets you choose **Explore**, **Evaluate**, or **Follow**. It changes the starting steps and suggested filing questions, while the underlying SEC facts and answers stay the same. The choice is saved on this Mac. **Save company** adds the current company to the sidebar for quick access; saved companies are a research list, not a portfolio.

**Since your last check** compares the current loaded SEC data with the last snapshot this Mac saw for that company. It highlights a new annual or quarterly filing and changes in the four headline annual figures, each with a source link. The first visit creates the starting snapshot. This comparison is limited to the data currently loaded; use the refresh button to check the SEC for newer records. It does not monitor filings in the background or assess investment merit.

### Financials

Switch between **Annual history** and **Latest 10-Q**. Annual history retains the Income statement, Balance sheet, Cash flow, and Ratios & growth views. Click an annual account row for its trend, available calculation components, and source concept. Hover over or focus a year in the trend to see its exact value. At the bottom of Annual history, **Graph your financials** lets you compare up to five accounts for the same company. Choose dollar values, percentages, or multiples, then select the accounts; hovering over a year shows all selected values together. Missing years are left blank. The latest-quarter view separates three-month income values, quarter-end balances, and fiscal year-to-date cash-flow values. It displays each mapped US-GAAP concept and period; it does not mix these values into annual charts. An em dash means no reliable value was available; it is not zero.

**What makes up the numbers?** adds a filing-specific revenue-to-profit breakdown. Choose the latest 10-Q or 10-K, then **Brief view** for a plain-English explanation and the main revenue categories, or **Deep dive** for the reported income lines, nonoverlapping operating-expense detail, revenue splits, periods, and XBRL concepts. Product, business-segment, and geographic revenue are alternative views of the same total. A split appears only when its inline-XBRL categories reconcile to the filing's reported revenue. Some companies do not disclose a breakdown that can be verified this way.

### Time machine

Open **Time machine** in the sidebar to see how annual values were reported in different filings. **All years** puts multiple reporting years together; choose a year or use the arrow controls to focus on one. Year labels refer to the calendar year in which the reporting period ends; exact dates remain visible. Filter by account or show changed values only, then select a row to explore its reporting trail.

The version buttons and slider move between different reported values for the same exact period and US-GAAP concept. Repeated unchanged values are grouped. Each version shows its exact amount, filing date, accession, and SEC source; the final observation date also links to its source. A value that changed and later returned to its original amount still has a revision trail. The calculation cards show the resulting effects on free cash flow, selected growth rates, and margins when the necessary comparable inputs exist.

“First available” means the earliest eligible observation retained in today's SEC Company Facts data for the selected concept, not necessarily the original report. The first and latest inputs can have different filing dates. This is not a complete historical as-of database or a backtesting dataset. A reported-value change alone does not establish an accounting error or restatement. Different periods and concepts are not compared as revisions; ambiguous conflicting observations are omitted. The view works without AI.

### Quarterly history and TTM

In **Financials**, select **Quarterly history & TTM**. Choose performance, cash flow, or balance sheet, change the chart account, and choose the number of recent quarters to display. Hover over or focus a chart bar to inspect its value. The table lists newest quarters first; **Inspect sources** reveals the exact values, periods, concepts, and filings behind each amount.

Income and cash-flow values cover standalone quarters. Where only cumulative cash flow is reported, FilingLens subtracts the preceding YTD observation with the same fiscal start and concept. A fourth quarter may be calculated from annual less nine-month values. Such cells are marked **YTD difference**, with both operands retained. Balance sheets remain point-in-time. TTM totals sum four contiguous quarters with matching reporting boundaries; missing inputs remain unavailable. Later comparative disclosures can revise the inputs, and the operand filing dates remain visible. The separate **Latest 10-Q** view retains the filing's original three-month/YTD distinction.

### Compare peers

Open **Compare peers** in the sidebar. Add two to four tickers, including names from your saved companies, then select **Compare companies**. FilingLens initially chooses the latest annual reporting end-year shared by the successfully loaded companies. Use the year selector to move to an earlier shared year. A failed company remains visible as a warning, and at least two loaded companies are required to display a comparison.

The table compares revenue, growth, operating/net/FCF margins, free cash flow, current ratio, and mapped long-term debt divided by assets. Each column shows the company's exact fiscal period; a shared end-year does not mean identical reporting dates. Margins require exactly matched duration inputs, and growth requires a comparable adjacent prior annual period using the same concept. Missing values stay unavailable. Every calculated cell exposes its source operands. There are no market-price valuation multiples or investment rankings.

Workspace, topic, and Time Machine year changes use short transitions. System reduced-motion preferences disable animation and smooth scrolling.

### Filings and research

Choose the latest **10-K** or **10-Q** above **Read filing** and **Ask the filing**. Read filing loads the selected document's sections; Ask the filing answers from that document's numbered passages. **Analyst brief** brings together both filings when available, with a latest-quarter section and source labels identifying each filing. It keeps annual movement screens and quarterly figures distinct. The brief aims for short, plain-English sections that explain the most useful figures; its output allowance is 4,000 tokens so a complete brief has room to finish. Generate a new brief after updating the app to see this format. Download the resulting Markdown if useful. The document shelf links to official SEC filings.

### Signals

**Anomaly analysis** screens annual changes by severity and direction. It starts with raw numerical increases and decreases; an optional color view shows a simple directional impact heuristic. **Insider activity** loads recent Forms 4 and filters purchases, sales, and other transactions; each row links to its SEC filing.

Open the arrow beside an annual movement to start an **evidence trail**. Inspect the prior and current values, expand their exact calculation inputs and SEC sources, and compare up to three related movements. The previous available observation is shown explicitly; a missing-year gap is flagged rather than presented as a consecutive-year comparison.

Choose **Find filing passages** to read annual documents tied to the selected source facts. This runs locally without an AI model. Passages are lexical research leads, not verified explanations. Historical values may come from later comparative or revised filings; every source retains its reporting period and filing date. If the matching document or a relevant passage is unavailable, FilingLens keeps the numerical evidence and shows the limitation instead of substituting an unrelated latest report.

Under **Your interpretation**, add your own hypothesis, attach source evidence, and record your judgment as **Unresolved**, **Supported**, or **Contradicted**. These are your assessments. Hypotheses, notes, and attached evidence snapshots are saved locally for the exact source observations. Reopening the same investigation restores them; revised source inputs create a separate investigation. Clearing app website data removes these local reviews. **Export investigation** saves the figures, retrieved passages, hypotheses, judgments, attached evidence, and limitations as Markdown. The Mac app writes a uniquely named file in its local export folder, displays the exact path, and offers **Show export folder**; browser development sessions use a normal download. If local saving fails, an explicit warning directs you to export before leaving.

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

SEC files are public and downloaded from SEC.gov. The Mac app listens only on your computer and uses a private session token between its window and local service. It stores SEC cache and service settings under `Library/Application Support/FilingLens`; cloud keys go to macOS Keychain. Nothing from an existing Streamlit checkout is copied into a new Mac installation. FilingLens does not provide real-time prices or personalized investment advice.

## Storage and provider discovery

SEC cache and service settings are stored under `~/Library/Application Support/FilingLens`. Saved research approaches and investigation reviews use the app webview’s local storage. Markdown investigations are written under `~/Library/Application Support/com.filinglens.desktop/exports`. Saved cloud keys use macOS Keychain; trusted process environment settings can also provide a key. Configured cloud providers may receive authenticated model-discovery requests at startup or when availability is refreshed. Questions and filing evidence are sent only when you request generation using that provider. Local provider addresses default to loopback and can be overridden by trusted environment settings.

## Build a disk image

Release maintainers can run `./scripts/package_dmg_macos.sh /path/to/FilingLens.app release` on macOS with `uv` installed. The helper verifies the existing app signature, uses pinned dmgbuild 1.6.7 for a read-only image with an Applications shortcut, and verifies the image checksum. It packages the existing app without changing its code signature. The clean release helper creates both ZIP and DMG when uv is available. Signing and Apple notarization remain separate steps.
