"""FilingLens Streamlit application."""

from __future__ import annotations

import logging
from pathlib import Path
import sys


# Keep the source-layout application launchable even if macOS marks the
# editable-install .pth file as hidden and Python skips it after a restart.
PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

import pandas as pd
import streamlit as st

from filinglens.analytics.anomalies import detect_anomalies
from filinglens.analytics.normalize import financials_wide
from filinglens.analytics.ratios import calculate_ratios
from filinglens.config import PROJECT_ROOT, Settings, save_env_value
from filinglens.documents.chunking import chunk_sections
from filinglens.documents.parser import clean_filing_html
from filinglens.documents.retrieval import LocalRetriever
from filinglens.documents.sections import extract_sections
from filinglens.llm.analyst_brief import generate_analyst_brief
from filinglens.llm.base import LLMProvider, LocalLLMError
from filinglens.llm.grounded_qa import ask_filing
from filinglens.llm.lmstudio import LMStudioProvider
from filinglens.llm.cloud import CloudProvider
from filinglens.llm.ollama import OllamaProvider, free_credit_cloud_models
from filinglens.reporting.export import markdown_to_html
from filinglens.sec.client import SECClient, SECClientError
from filinglens.sec.csv_export import safe_csv
from filinglens.sec.companies import CompanyDirectory
from filinglens.sec.insiders import fetch_insider_activity
from filinglens.sec.submissions import latest_filing
from filinglens.sec.xbrl import select_annual_facts
from filinglens.ui.charts import account_trend_chart
from filinglens.ui.components import (
    ANOMALY_COLOR_MODES,
    LABELS,
    METRIC_FORMULAS,
    anomaly_display_table,
    anomaly_summary_text,
    human_currency,
    metric_component_table,
    metric_display_value,
    metric_latest_change,
    metric_trend_table,
    period_delta,
    ratio_display,
    synchronize_filing_session,
    verified_metrics_text,
)


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
st.set_page_config(page_title="FilingLens", page_icon="🔎", layout="wide")


@st.cache_data(ttl=86_400, show_spinner=False)
def load_company(ticker: str, refresh_nonce: int = 0) -> dict[str, object]:
    refresh = refresh_nonce > 0
    settings = Settings.from_env()
    settings.validate_sec()
    settings.ensure_directories()
    with SECClient(
        settings.sec_user_agent,
        settings.cache_dir,
        min_interval=settings.request_interval_seconds,
        timeout=settings.request_timeout_seconds,
    ) as client:
        company = CompanyDirectory(client).lookup(ticker, refresh=refresh)
        submissions = client.submissions(company.cik, refresh=refresh)
        facts = select_annual_facts(
            client.company_facts(company.cik, refresh=refresh), company.ticker
        )
    return {"company": company, "submissions": submissions, "facts": facts}


@st.cache_data(ttl=86_400, show_spinner=False)
def load_filing_text(source_url: str, refresh_nonce: int = 0) -> str:
    settings = Settings.from_env()
    with SECClient(settings.sec_user_agent, settings.cache_dir) as client:
        return client.filing_document(source_url, refresh=refresh_nonce > 0)


@st.cache_data(ttl=3_600, show_spinner=False)
def load_insider_activity(
    cik: str, max_filings: int, refresh_nonce: int = 0
) -> dict[str, object]:
    settings = Settings.from_env()
    settings.validate_sec()
    settings.ensure_directories()
    refresh = refresh_nonce > 0
    with SECClient(
        settings.sec_user_agent,
        settings.cache_dir,
        min_interval=settings.request_interval_seconds,
        timeout=settings.request_timeout_seconds,
    ) as client:
        submissions = client.submissions(cik, refresh=refresh)
        result = fetch_insider_activity(
            client,
            submissions,
            max_filings=max_filings,
            refresh=refresh,
        )
    return {
        "transactions": [transaction.as_record() for transaction in result.transactions],
        "filings_reviewed": result.filings_reviewed,
        "failures": list(result.failures),
    }


def build_retriever(company: object, filing: object, html: str) -> tuple[LocalRetriever, dict[str, str]]:
    text = clean_filing_html(html)
    sections = extract_sections(text)
    chunks = chunk_sections(
        sections,
        company=company.name,
        ticker=company.ticker,
        filing_form=filing.form,
        filing_date=filing.filing_date,
        accession_number=filing.accession_number,
        source_url=filing.source_url,
    )
    return LocalRetriever(chunks), sections


def get_or_build_retriever(
    company: object, filing: object, refresh_nonce: int
) -> LocalRetriever:
    """Reuse the current filing index or build it once for any AI feature."""
    is_current = (
        st.session_state.get("retrieval_accession") == filing.accession_number
        and st.session_state.get("retrieval_ticker") == company.ticker
        and st.session_state.get("retrieval") is not None
    )
    if is_current:
        return st.session_state.retrieval

    html = load_filing_text(filing.source_url, refresh_nonce)
    retriever, sections = build_retriever(company, filing, html)
    st.session_state.retrieval = retriever
    st.session_state.sections = sections
    st.session_state.retrieval_accession = filing.accession_number
    st.session_state.retrieval_ticker = company.ticker
    return retriever


def provider_states(
    settings: Settings,
    ollama_cloud_api_key: str = "",
    openai_api_key: str = "",
    anthropic_api_key: str = "",
) -> dict[str, tuple[LLMProvider, list[str], str, str]]:
    candidates: dict[str, tuple[LLMProvider, str, str]] = {
        "LM Studio (local)": (
            LMStudioProvider(
                settings.lmstudio_base_url,
                settings.lmstudio_model,
                settings.lmstudio_api_key,
                timeout=settings.lmstudio_timeout_seconds,
            ),
            settings.lmstudio_model,
            settings.lmstudio_base_url,
        ),
        "Ollama (local)": (
            OllamaProvider(
                settings.ollama_base_url,
                settings.ollama_model,
                timeout=settings.ollama_timeout_seconds,
            ),
            settings.ollama_model,
            settings.ollama_base_url,
        ),
        "Ollama Cloud": (
            OllamaProvider(
                settings.ollama_cloud_base_url,
                settings.ollama_cloud_model,
                api_key=ollama_cloud_api_key or settings.ollama_api_key,
                cloud=True,
                timeout=settings.ollama_cloud_timeout_seconds,
            ),
            settings.ollama_cloud_model,
            settings.ollama_cloud_base_url,
        ),
        "OpenAI": (
            CloudProvider("openai", openai_api_key or settings.openai_api_key, settings.openai_model),
            settings.openai_model,
            "https://api.openai.com/v1",
        ),
        "Anthropic": (
            CloudProvider("anthropic", anthropic_api_key or settings.anthropic_api_key, settings.anthropic_model),
            settings.anthropic_model,
            "https://api.anthropic.com/v1",
        ),
    }
    if settings.local_llm_provider == "lmstudio":
        candidates = {"LM Studio (local)": candidates["LM Studio (local)"]}
    elif settings.local_llm_provider == "ollama":
        candidates = {"Ollama (local)": candidates["Ollama (local)"]}
    elif settings.local_llm_provider == "ollama_cloud":
        candidates = {"Ollama Cloud": candidates["Ollama Cloud"]}
    elif settings.local_llm_provider in {"openai", "anthropic"}:
        name = settings.local_llm_provider.title()
        candidates = {name: candidates[name]}

    states: dict[str, tuple[LLMProvider, list[str], str, str]] = {}
    for name, (provider, configured_model, endpoint) in candidates.items():
        try:
            models = provider.list_models()
            status = f"Connected - {len(models)} model(s)"
        except LocalLLMError as exc:
            models = []
            status = str(exc) or f"{name} was not detected at {endpoint}."
        states[name] = (provider, models, status, configured_model)
    return states


def render_metric_group(
    title: str,
    frame: pd.DataFrame,
    metrics: list[str],
    *,
    key: str,
    ratio: bool = False,
    component_frame: pd.DataFrame | None = None,
) -> None:
    """Render a readable account table with row-selectable trend detail."""
    display = metric_trend_table(frame, metrics, ratio=ratio)
    st.markdown(f"#### {title}")
    if display.empty:
        st.info("No reliable mapped values are available for this section.")
        return

    visible_columns = [column for column in display.columns if column != "_metric"]
    column_config: dict[str, object] = {
        "Account": st.column_config.TextColumn("Account", width="large"),
        "Trend": st.column_config.LineChartColumn("Trend", width="medium"),
        "Latest change": st.column_config.TextColumn(
            "Latest change", width="small"
        ),
    }
    for column in visible_columns:
        if column.startswith("FY"):
            column_config[column] = st.column_config.TextColumn(column, width="small")

    event = st.dataframe(
        display,
        column_order=visible_columns,
        column_config=column_config,
        width="stretch",
        hide_index=True,
        height=min(390, 40 + 36 * len(display)),
        on_select="rerun",
        selection_mode="single-row",
        key=f"statement_table_{key}",
    )
    selected_rows = list(event.selection.rows)
    if not selected_rows:
        st.caption("Select an account row to expand its values and full trend chart.")
        return

    selected_row = display.iloc[selected_rows[0]]
    metric = str(selected_row["_metric"])
    label = str(selected_row["Account"])
    series = pd.to_numeric(frame[metric], errors="coerce").dropna()
    with st.expander(f"{label} detail", expanded=True):
        detail_columns = st.columns([1, 1, 1, 3])
        latest_value = float(series.iloc[-1]) if not series.empty else None
        prior_value = float(series.iloc[-2]) if len(series) > 1 else None
        detail_columns[0].metric(
            f"FY{int(series.index[-1])}" if not series.empty else "Latest",
            metric_display_value(metric, latest_value, ratio=ratio),
        )
        detail_columns[1].metric(
            f"FY{int(series.index[-2])}" if len(series) > 1 else "Prior",
            metric_display_value(metric, prior_value, ratio=ratio),
        )
        detail_columns[2].metric(
            "Latest change", metric_latest_change(frame, metric, ratio=ratio)
        )
        detail_columns[3].plotly_chart(
            account_trend_chart(
                frame,
                metric,
                LABELS.get(metric, label),
                ratio=ratio,
                multiple=ratio and metric in {"current_ratio", "debt_to_equity"},
            ),
            width="stretch",
            key=f"statement_chart_{key}_{metric}",
        )
        latest_year = int(series.index[-1]) if not series.empty else None
        source_frame = component_frame if component_frame is not None else frame
        component_table = (
            metric_component_table(source_frame, metric, latest_year)
            if latest_year is not None
            else pd.DataFrame()
        )
        st.markdown("**Composition or calculation**")
        if metric in METRIC_FORMULAS:
            st.caption(f"Formula: {METRIC_FORMULAS[metric]}")
        if not component_table.empty:
            st.dataframe(
                component_table,
                width="stretch",
                hide_index=True,
                key=f"statement_components_{key}_{metric}",
            )
        else:
            st.caption(
                "No reliable lower-level component breakdown is available in FilingLens's "
                "normalized SEC Company Facts for this account. The reported total remains "
                "visible without estimated components."
            )
        st.caption(
            "Annual values are calculated from FilingLens's normalized SEC/XBRL series. "
            "Open Value provenance on the Overview tab to inspect the exact source concept."
        )


settings = Settings.from_env()
st.title("FilingLens")
st.caption(
    "SEC filing intelligence · Deterministic financial analytics · Local or Ollama Cloud AI · "
    "Educational use only"
)

with st.sidebar:
    st.header("Company")
    ticker = st.text_input("Ticker", value="AAPL", max_chars=10).strip().upper()
    years_to_show = st.slider("Historical periods", min_value=3, max_value=10, value=5)
    if "refresh_nonce" not in st.session_state:
        st.session_state.refresh_nonce = 0
    if st.button("Refresh SEC cache"):
        st.session_state.refresh_nonce += 1
        st.cache_data.clear()
    st.divider()
    st.header("AI provider")
    with st.expander("Add Ollama Cloud API key"):
        st.caption(
            "Paste an Ollama API key here to connect without editing files or using Terminal. "
            "The key is hidden while you type."
        )
        pasted_cloud_key = st.text_input(
            "Ollama Cloud API key",
            type="password",
            value="",
            placeholder="Paste your Ollama key",
            key="ollama_cloud_key_input",
        )
        session_cloud_key = st.session_state.get("ollama_cloud_api_key", "")
        key_buttons = st.columns(2)
        if key_buttons[0].button(
            "Connect for this session",
            disabled=not pasted_cloud_key.strip(),
            width="stretch",
        ):
            st.session_state.ollama_cloud_api_key = pasted_cloud_key.strip()
            st.rerun()
        if key_buttons[1].button(
            "Save on this Mac",
            disabled=not pasted_cloud_key.strip(),
            width="stretch",
        ):
            try:
                save_env_value(
                    PROJECT_ROOT / ".env",
                    "OLLAMA_API_KEY",
                    pasted_cloud_key.strip(),
                )
                st.session_state.ollama_cloud_api_key = pasted_cloud_key.strip()
                st.session_state.ollama_cloud_key_saved = True
                st.rerun()
            except OSError as exc:
                st.error(f"The key could not be saved on this Mac: {exc}")
        if st.session_state.get("ollama_cloud_key_saved"):
            st.success("Ollama Cloud key saved privately on this Mac.")
        elif session_cloud_key:
            st.success("Ollama Cloud key is active for this browser session.")
        elif settings.ollama_api_key:
            st.success("An Ollama Cloud key is already saved on this Mac.")
        st.caption(
            "Saving writes only to this project's Git-ignored .env file with owner-only "
            "permissions. The key is sent only to Ollama when cloud access is used."
        )

    for provider_label, env_name in (("OpenAI", "OPENAI_API_KEY"), ("Anthropic", "ANTHROPIC_API_KEY")):
        session_name = env_name.lower()
        with st.expander(f"Add {provider_label} API key"):
            pasted_key = st.text_input(f"{provider_label} API key", type="password", value="",
                                       key=f"{session_name}_input")
            buttons = st.columns(2)
            if buttons[0].button("Connect for this session", disabled=not pasted_key.strip(),
                                 key=f"{session_name}_connect", width="stretch"):
                st.session_state[session_name] = pasted_key.strip()
                st.rerun()
            if buttons[1].button("Save on this Mac", disabled=not pasted_key.strip(),
                                 key=f"{session_name}_save", width="stretch"):
                try:
                    save_env_value(PROJECT_ROOT / ".env", env_name, pasted_key.strip())
                    st.session_state[session_name] = pasted_key.strip()
                    st.rerun()
                except OSError as exc:
                    st.error(f"The key could not be saved: {exc}")
            if st.session_state.get(session_name) or getattr(settings, session_name):
                st.success(f"{provider_label} key is available.")
            st.caption("Saved keys go to this project's Git-ignored .env file with owner-only permissions.")

    active_cloud_key = st.session_state.get("ollama_cloud_api_key", "")
    local_states = provider_states(settings, active_cloud_key,
                                   st.session_state.get("openai_api_key", ""),
                                   st.session_state.get("anthropic_api_key", ""))
    available_providers = [name for name, state in local_states.items() if state[1]]
    if available_providers:
        provider_state_key = "selected_ai_provider"
        if st.session_state.get(provider_state_key) not in available_providers:
            st.session_state[provider_state_key] = available_providers[0]
        provider_name = st.selectbox(
            "AI provider", available_providers, key=provider_state_key
        )
        provider, models, llm_status, configured_model = local_states[provider_name]
        selectable_models = models
        if provider_name == "Ollama Cloud":
            free_models = free_credit_cloud_models(models)
            show_paid_models = st.checkbox(
                "Show models that may require paid credits",
                value=False,
                key="show_paid_ollama_models",
                help=(
                    "Off shows only the Ollama Cloud models currently included with free "
                    "usage credits. Turn it on after adding credits or upgrading."
                ),
            )
            if free_models and not show_paid_models:
                selectable_models = free_models
                st.caption(
                    f"Showing {len(free_models)} free-credit Ollama Cloud model(s)."
                )
            elif not free_models and not show_paid_models:
                st.warning(
                    "None of the known free-credit models appeared in Ollama's model list. "
                    "All returned models are shown so you can inspect availability."
                )

        model_state_key = (
            "selected_model_" + provider_name.lower().replace(" ", "_").replace("(", "").replace(")", "")
        )
        default_model = (
            configured_model
            if configured_model in selectable_models
            else selectable_models[0]
        )
        if st.session_state.get(model_state_key) not in selectable_models:
            st.session_state[model_state_key] = default_model
        model = st.selectbox(
            "AI model", selectable_models, key=model_state_key
        )
        st.success(f"{provider_name}: {llm_status}")
        if provider_name in {"Ollama Cloud", "OpenAI", "Anthropic"}:
            st.warning(
                "Cloud mode sends your question, verified metrics, and selected SEC filing "
                f"passages to {provider_name}. API usage may incur charges."
            )
    else:
        provider_name = None
        provider = next(iter(local_states.values()))[0]
        models = []
        model = None
        llm_status = "No configured AI provider exposed an available chat model."
        st.warning(llm_status)
        st.caption(
            "Start LM Studio/local Ollama, or add a cloud provider key above. "
            "Deterministic features remain available."
        )
    with st.expander("Provider status"):
        for status_name, (_, status_models, status_text, _) in local_states.items():
            icon = "✓" if status_models else "•"
            st.caption(f"{icon} {status_name}: {status_text}")

if not ticker:
    st.info("Enter a ticker to begin.")
    st.stop()

try:
    with st.spinner(f"Loading official SEC data for {ticker}…"):
        bundle = load_company(ticker, st.session_state.refresh_nonce)
except (SECClientError, ValueError) as exc:
    st.error(str(exc))
    st.stop()

company = bundle["company"]
submissions = bundle["submissions"]
facts = bundle["facts"]
financials = financials_wide(facts).tail(years_to_show)
ratios = calculate_ratios(financials)
anomalies = detect_anomalies(pd.concat([financials, ratios], axis=1))
latest_10k = latest_filing(submissions, "10-K")
latest_10q = latest_filing(submissions, "10-Q")
active_filing_key = (
    f"{company.ticker}:{latest_10k.accession_number}" if latest_10k else f"{company.ticker}:no-10k"
)
synchronize_filing_session(st.session_state, active_filing_key)
metrics_context = verified_metrics_text(financials, ratios)

tabs = st.tabs(
    [
        "Overview",
        "Financial Trends",
        "Anomaly Analysis",
        "Insider Activity",
        "Ask the Filing",
        "Analyst Brief",
        "Methodology",
    ]
)

with tabs[0]:
    st.caption(
        "What this tab does: summarizes the active company, filings, financial changes, ratios, "
        "unusual-movement counts, and the selected AI provider. It also supports grounded general "
        "company questions using verified metrics and the latest 10-K."
    )
    st.subheader(f"{company.name} ({company.ticker})")
    cols = st.columns(4)
    cols[0].metric("CIK", company.cik)
    cols[1].metric("Latest 10-K", latest_10k.filing_date if latest_10k else "Unavailable")
    cols[2].metric("Latest 10-Q", latest_10q.filing_date if latest_10q else "Unavailable")
    cols[3].metric("AI provider", provider_name or "Offline")
    if model:
        st.caption(f"Selected model: `{model}`")
    if not financials.empty:
        latest_year = financials.index[-1]
        headline = st.columns(4)
        for column, metric_name in zip(
            headline, ("revenue", "operating_income", "net_income", "free_cash_flow")
        ):
            column.metric(
                f"{metric_name.replace('_', ' ').title()} FY{latest_year}",
                human_currency(financials.loc[latest_year, metric_name])
                if metric_name in financials
                else "Unavailable",
                delta=period_delta(financials, metric_name),
            )

        if not ratios.empty and latest_year in ratios.index:
            st.subheader(f"FY{latest_year} ratio snapshot")
            ratio_metrics = (
                ("revenue_growth", "Revenue growth"),
                ("gross_margin", "Gross margin"),
                ("operating_margin", "Operating margin"),
                ("current_ratio", "Current ratio"),
                ("debt_to_equity", "Debt to equity"),
            )
            ratio_columns = st.columns(len(ratio_metrics))
            for ratio_column, (ratio_name, ratio_label) in zip(
                ratio_columns, ratio_metrics
            ):
                ratio_value = (
                    ratios.loc[latest_year, ratio_name]
                    if ratio_name in ratios.columns
                    else None
                )
                ratio_column.metric(ratio_label, ratio_display(ratio_name, ratio_value))
    else:
        st.warning("No reliable XBRL concept mapping was found for this company.")

    st.subheader("Recent SEC filings")
    filing_columns = st.columns(2)
    for filing_column, filing, label in (
        (filing_columns[0], latest_10k, "Annual report"),
        (filing_columns[1], latest_10q, "Quarterly report"),
    ):
        if filing is None:
            filing_column.info(f"{label}: unavailable")
        else:
            filing_column.markdown(
                f"**{label}: {filing.form}**  \n"
                f"Filed {filing.filing_date} · Report period {filing.report_date}  \n"
                f"[Open official SEC filing]({filing.source_url})"
            )
            filing_column.caption(f"Accession {filing.accession_number}")

    latest_flags = (
        anomalies[
            (anomalies["period"] == latest_year)
            & anomalies["severity"].isin(["Notable", "Significant"])
        ]
        if not financials.empty and not anomalies.empty
        else pd.DataFrame()
    )
    flag_columns = st.columns(3)
    flag_columns[0].metric("Latest-period flags", len(latest_flags))
    flag_columns[1].metric(
        "Significant",
        int(latest_flags["severity"].eq("Significant").sum())
        if not latest_flags.empty
        else 0,
    )
    flag_columns[2].metric(
        "Notable",
        int(latest_flags["severity"].eq("Notable").sum())
        if not latest_flags.empty
        else 0,
    )
    st.caption(
        "Flags are screening signals from the latest displayed annual period, not findings of "
        "fraud, misconduct, or investment merit."
    )

    st.divider()
    st.subheader("Ask a general company question")
    st.caption(
        "Answers are grounded in verified FilingLens metrics and passages retrieved from the "
        "latest 10-K. This is not a live-news or stock-price assistant."
    )
    overview_question = st.text_input(
        "Company question",
        value="Give me a concise overview of the business, financial performance, and major risks.",
        key="overview_question",
    )
    overview_answer_key = (
        f"{active_filing_key}:{provider_name or 'offline'}:{model or 'none'}:{overview_question}"
    )
    if st.button(
        "Ask about this company",
        key="ask_company_overview",
        disabled=not models or latest_10k is None or not overview_question.strip(),
    ):
        try:
            with st.spinner("Indexing the latest 10-K and generating a grounded answer…"):
                overview_retriever = get_or_build_retriever(
                    company, latest_10k, st.session_state.refresh_nonce
                )
                overview_answer = ask_filing(
                    overview_question,
                    overview_retriever,
                    provider,
                    verified_metrics=metrics_context,
                    model=model,
                )
            st.session_state.overview_answer = overview_answer
            st.session_state.overview_answer_key = overview_answer_key
        except (LocalLLMError, SECClientError, ValueError) as exc:
            st.error(str(exc))

    overview_answer = (
        st.session_state.get("overview_answer")
        if st.session_state.get("overview_answer_key") == overview_answer_key
        else None
    )
    if overview_answer is not None:
        if overview_answer.status == "out_of_scope":
            st.warning(overview_answer.answer)
        else:
            st.markdown(overview_answer.answer)
            with st.expander("Answer sources"):
                for source_index, result in enumerate(overview_answer.sources, 1):
                    chunk = result.chunk
                    st.markdown(
                        f"**Source {source_index} · {chunk.section}** · "
                        f"[SEC filing]({chunk.source_url})"
                    )
                    st.write(chunk.text)
    with st.expander("Value provenance"):
        st.dataframe(facts, width="stretch", hide_index=True)

with tabs[1]:
    st.caption(
        "What this tab does: presents readable multi-year statements with an inline trend for "
        "each available account. Select any row to expand its full chart, latest value, prior "
        "value, and change."
    )
    if financials.empty:
        st.warning("SEC financial data for these metrics was unavailable.")
    else:
        st.info(
            "Values come from normalized annual SEC/XBRL facts. Missing accounts remain "
            "unavailable rather than being estimated."
        )
        statement_tabs = st.tabs(
            ["Income Statement", "Balance Sheet", "Cash Flow", "Ratios & Growth"]
        )
        with statement_tabs[0]:
            render_metric_group(
                "Revenue and gross profit",
                financials,
                ["revenue", "cost_of_revenue", "gross_profit"],
                key="income_revenue",
            )
            render_metric_group(
                "Operating and net income",
                financials,
                ["operating_income", "net_income"],
                key="income_profit",
            )
        with statement_tabs[1]:
            render_metric_group(
                "Assets",
                financials,
                ["cash", "current_assets", "total_assets"],
                key="balance_assets",
            )
            render_metric_group(
                "Liabilities and equity",
                financials,
                [
                    "current_liabilities",
                    "total_liabilities",
                    "long_term_debt",
                    "stockholders_equity",
                ],
                key="balance_liabilities",
            )
        with statement_tabs[2]:
            render_metric_group(
                "Cash generation and investment",
                financials,
                ["operating_cash_flow", "capital_expenditures", "free_cash_flow"],
                key="cash_flow",
            )
        with statement_tabs[3]:
            render_metric_group(
                "Growth",
                ratios,
                [
                    "revenue_growth",
                    "operating_income_growth",
                    "net_income_growth",
                    "operating_cash_flow_growth",
                    "free_cash_flow_growth",
                ],
                key="ratios_growth",
                ratio=True,
                component_frame=financials,
            )
            render_metric_group(
                "Margins",
                ratios,
                [
                    "gross_margin",
                    "operating_margin",
                    "net_margin",
                    "operating_cash_flow_margin",
                    "free_cash_flow_margin",
                ],
                key="ratios_margins",
                ratio=True,
                component_frame=financials,
            )
            render_metric_group(
                "Returns",
                ratios,
                ["return_on_assets", "return_on_equity"],
                key="ratios_returns",
                ratio=True,
                component_frame=financials,
            )
            render_metric_group(
                "Liquidity and leverage",
                ratios,
                ["current_ratio", "debt_to_assets", "debt_to_equity"],
                key="ratios_liquidity",
                ratio=True,
                component_frame=financials,
            )

with tabs[2]:
    st.caption(
        "What this tab does: screens year-over-year financial movements using documented economic "
        "thresholds and robust statistical scores so you can decide what to investigate further."
    )
    st.info(
        "This screen identifies unusual financial movements. It is not fraud detection and does not establish misconduct."
    )
    if anomalies.empty:
        st.warning("Insufficient historical observations for change analysis.")
    else:
        severity = st.multiselect(
            "Severity", ["Significant", "Notable", "Normal"], default=["Significant", "Notable"]
        )
        color_mode = st.selectbox(
            "Change coloring",
            ANOMALY_COLOR_MODES,
            help=(
                "Likely financial impact treats increases in costs, expenses, debt, and liabilities "
                "as unfavorable. Raw mode colors every increase green and every decrease red."
            ),
        )
        filtered_anomalies = anomalies[anomalies["severity"].isin(severity)]
        if color_mode == "Likely financial impact":
            st.caption(
                "Green indicates a likely favorable movement and red a likely unfavorable movement. "
                "Costs, expenses, debt, and liabilities are interpreted as lower-is-better; all "
                "other metrics are interpreted as higher-is-better. This directional label is a "
                "screening aid, not an investment conclusion."
            )
        elif color_mode == "Raw increase / decrease":
            st.caption(
                "Green indicates a numerical increase and red a numerical decrease, regardless of "
                "whether that movement is economically favorable."
            )
        if color_mode != "Off":
            st.caption(
                "Color intensity: light below 20% · medium from 20% to 39.9% · deep at 40% or more."
            )
        if color_mode == "Likely financial impact":
            st.caption(
                "Direction rank: 1 is strongly favorable and 6 is strongly unfavorable. Sort the "
                "Direction column ascending for most-to-least favorable or descending for the exact reverse."
            )
        else:
            st.caption(
                "Direction rank: 1 is the strongest gain and 6 is the strongest loss. Sort the "
                "Direction column ascending for gains-first or descending for the exact reverse."
            )
        if not filtered_anomalies.empty:
            detail_frame = filtered_anomalies.reset_index(drop=True)
            selected_detail = st.selectbox(
                "Full explanation",
                range(len(detail_frame)),
                format_func=lambda index: (
                    f"{str(detail_frame.loc[index, 'metric']).replace('_', ' ').title()} · "
                    f"FY{int(detail_frame.loc[index, 'period'])} · "
                    f"{float(detail_frame.loc[index, 'percentage_change']):+.1%}"
                    if pd.notna(detail_frame.loc[index, "percentage_change"])
                    else f"{str(detail_frame.loc[index, 'metric']).replace('_', ' ').title()} · "
                    f"FY{int(detail_frame.loc[index, 'period'])} · change unavailable"
                ),
            )
            selected_row = detail_frame.loc[selected_detail]
            st.info(str(selected_row["explanation"]))
            st.caption(f"Method: {selected_row['method']}")
        st.dataframe(
            anomaly_display_table(filtered_anomalies, color_mode),
            width="stretch",
            hide_index=True,
            height=min(500, 38 + 35 * max(len(filtered_anomalies), 1)),
            column_config={
                "Metric": st.column_config.TextColumn(width="medium"),
                "Direction": st.column_config.TextColumn(width="medium"),
            },
        )
        st.caption(
            "Economic thresholds: Notable ≥20%, Significant ≥40%. Robust change scores use median absolute deviation: Notable ≥2.5, Significant ≥3.5."
        )

with tabs[3]:
    st.caption(
        "What this tab does: retrieves recent official SEC Forms 4 and 4/A, separates open-market "
        "purchases and sales from grants, option exercises, gifts, and tax-related transactions, "
        "and preserves a direct link to every source filing."
    )
    st.info(
        "Insider filings are research signals, not trade recommendations. A sale may reflect taxes, "
        "diversification, compensation, or a pre-arranged 10b5-1 plan; a purchase does not guarantee "
        "future performance. Review the filing footnotes before drawing conclusions."
    )
    max_insider_filings = st.slider(
        "Recent Form 4 filings to review",
        min_value=5,
        max_value=50,
        value=20,
        step=5,
        help="Each filing is downloaded once from SEC.gov and then cached locally.",
    )
    insider_key = f"{company.ticker}:{max_insider_filings}:{st.session_state.refresh_nonce}"
    if st.button("Load insider activity", key="load_insider_activity"):
        try:
            with st.spinner("Retrieving and parsing official SEC ownership filings…"):
                st.session_state.insider_activity = load_insider_activity(
                    company.cik,
                    max_insider_filings,
                    st.session_state.refresh_nonce,
                )
                st.session_state.insider_activity_key = insider_key
        except (SECClientError, ValueError) as exc:
            st.error(str(exc))

    activity = (
        st.session_state.get("insider_activity")
        if st.session_state.get("insider_activity_key") == insider_key
        else None
    )
    if activity:
        records = activity["transactions"]
        failures = activity["failures"]
        st.caption(
            f"Reviewed {activity['filings_reviewed']} filing(s); found {len(records)} transaction row(s)."
        )
        if failures:
            st.warning(
                f"{len(failures)} filing(s) could not be parsed. Available transactions are shown below."
            )
        if not records:
            st.warning("No transaction rows were found in the selected recent Form 4 filings.")
        else:
            insider_frame = pd.DataFrame(records)
            unamended = insider_frame[insider_frame["form"] == "4"]
            open_market = unamended[unamended["transaction_code"].isin(["P", "S"])]
            purchases = open_market[open_market["transaction_code"] == "P"]
            sales = open_market[open_market["transaction_code"] == "S"]
            purchase_value = purchases["transaction_value"].sum(min_count=1)
            sale_value = sales["transaction_value"].sum(min_count=1)
            purchase_value = 0.0 if pd.isna(purchase_value) else float(purchase_value)
            sale_value = 0.0 if pd.isna(sale_value) else float(sale_value)
            summary_columns = st.columns(4)
            summary_columns[0].metric("Open-market purchases", human_currency(purchase_value))
            summary_columns[1].metric("Open-market sales", human_currency(sale_value))
            summary_columns[2].metric(
                "Net open-market value", human_currency(purchase_value - sale_value)
            )
            summary_columns[3].metric(
                "Reporting insiders", int(insider_frame["insider_name"].nunique())
            )
            st.caption(
                "Value totals include only non-amended P (purchase) and S (sale) rows with both "
                "shares and price reported. Form 4/A amendments remain visible but are excluded from totals."
            )

            categories = {
                "Open-market purchases": {"P"},
                "Open-market sales": {"S"},
                "Awards, exercises, gifts, taxes, and other": set(
                    insider_frame["transaction_code"].unique()
                )
                - {"P", "S"},
            }
            selected_categories = st.multiselect(
                "Transaction categories",
                list(categories),
                default=list(categories),
            )
            selected_codes: set[str] = set()
            for category in selected_categories:
                selected_codes.update(categories[category])
            displayed = insider_frame[
                insider_frame["transaction_code"].isin(selected_codes)
            ].copy()
            displayed["10b5-1 plan"] = displayed["plan_10b5_1"].map(
                {True: "Yes", False: "No/not indicated"}
            )
            displayed["Derivative"] = displayed["derivative"].map(
                {True: "Yes", False: "No"}
            )
            displayed = displayed.rename(
                columns={
                    "transaction_date": "Transaction date",
                    "filing_date": "Filed",
                    "insider_name": "Insider",
                    "insider_role": "Role",
                    "transaction_code": "Code",
                    "transaction_type": "Transaction type",
                    "acquired_disposed": "Acquired/disposed",
                    "shares": "Shares",
                    "price_per_share": "Price/share",
                    "transaction_value": "Estimated value",
                    "shares_owned_after": "Owned after",
                    "ownership_nature": "Ownership",
                    "security_title": "Security",
                    "source_url": "SEC filing",
                }
            )
            table_columns = [
                "Transaction date",
                "Filed",
                "Insider",
                "Role",
                "Code",
                "Transaction type",
                "Acquired/disposed",
                "Shares",
                "Price/share",
                "Estimated value",
                "Owned after",
                "Ownership",
                "10b5-1 plan",
                "Derivative",
                "form",
                "Security",
                "SEC filing",
            ]
            st.dataframe(
                displayed[table_columns],
                width="stretch",
                hide_index=True,
                column_config={
                    "Shares": st.column_config.NumberColumn(format="compact"),
                    "Price/share": st.column_config.NumberColumn(format="dollar"),
                    "Estimated value": st.column_config.NumberColumn(format="dollar"),
                    "Owned after": st.column_config.NumberColumn(format="compact"),
                    "SEC filing": st.column_config.LinkColumn(display_text="Open filing"),
                },
            )
            st.download_button(
                "Download insider transactions CSV",
                safe_csv(insider_frame),
                f"{company.ticker}_insider_activity.csv",
                mime="text/csv",
            )
    else:
        st.caption(
            "Click Load insider activity to retrieve the selected number of recent ownership filings."
        )

with tabs[4]:
    st.caption(
        "What this tab does: indexes this company's latest 10-K, retrieves the passages most "
        "relevant to your question, and asks the selected AI model to answer using only those "
        "passages and verified FilingLens metrics. Clearly unrelated questions and requests for "
        "price predictions or buy/sell advice are stopped before model generation. Load a new "
        "index after changing tickers."
    )
    if latest_10k is None:
        st.warning("No recent 10-K filing is available.")
    else:
        st.caption(f"Evidence source: {latest_10k.form} filed {latest_10k.filing_date}")
        retrieval_is_current = (
            "retrieval" in st.session_state
            and st.session_state.get("retrieval_accession") == latest_10k.accession_number
            and st.session_state.get("retrieval_ticker") == company.ticker
        )
        if not retrieval_is_current:
            if st.button("Load and index latest 10-K", key="load_10k"):
                with st.spinner("Retrieving, parsing, and indexing the official filing…"):
                    get_or_build_retriever(
                        company, latest_10k, st.session_state.refresh_nonce
                    )
                    st.rerun()
        else:
            retriever = st.session_state.retrieval
            st.success(f"Indexed {len(retriever.chunks)} chunks across {len(st.session_state.sections)} section(s).")
            question = st.text_area("Question", "What factors did management say affected revenue?")
            if st.button("Ask the filing", disabled=not models):
                try:
                    with st.spinner("Generating a source-grounded answer…"):
                        answer = ask_filing(
                            question,
                            retriever,
                            provider,
                            verified_metrics=metrics_context,
                            model=model,
                        )
                    if answer.status == "out_of_scope":
                        st.warning(answer.answer)
                    else:
                        st.markdown(answer.answer)
                        st.subheader("Sources")
                        for index, result in enumerate(answer.sources, 1):
                            chunk = result.chunk
                            with st.expander(
                                f"Source {index} · {chunk.section} · relevance {result.score:.3f}"
                            ):
                                st.markdown(
                                    f"[{chunk.filing_form} filed {chunk.filing_date}]({chunk.source_url})"
                                )
                                st.write(chunk.text)
                except LocalLLMError as exc:
                    st.error(str(exc))
            if not models:
                st.warning(llm_status)

with tabs[5]:
    st.caption(
        "What this tab does: creates an eight-section educational brief from the active company's "
        "verified metrics, compact anomaly summary, and indexed 10-K evidence. It requires the "
        "current ticker's filing index and a connected AI model; generation time depends on the provider."
    )
    retriever = st.session_state.get("retrieval")
    retrieval_is_current = (
        retriever is not None
        and latest_10k is not None
        and st.session_state.get("retrieval_accession") == latest_10k.accession_number
        and st.session_state.get("retrieval_ticker") == company.ticker
    )
    brief_key = f"{active_filing_key}:{years_to_show}:{model or 'offline'}"
    if not retrieval_is_current:
        st.info(
            f"Load and index {company.ticker}'s latest 10-K in Ask the Filing before generating a brief."
        )
    elif not models:
        st.warning(llm_status)
    else:
        if st.button("Generate analyst brief"):
            flagged = anomalies[anomalies["severity"].isin(["Notable", "Significant"])]
            anomaly_context = anomaly_summary_text(flagged)
            try:
                with st.spinner("Synthesizing verified metrics and filing evidence…"):
                    brief = generate_analyst_brief(
                        company.ticker,
                        metrics_context,
                        anomaly_context,
                        retriever,
                        provider,
                        model=model,
                )
                st.session_state.analyst_brief = brief.text
                st.session_state.analyst_brief_key = brief_key
            except LocalLLMError as exc:
                st.error(str(exc))
        brief_text = (
            st.session_state.get("analyst_brief")
            if st.session_state.get("analyst_brief_key") == brief_key
            else None
        )
        if brief_text:
            st.markdown(brief_text)
            st.download_button("Download Markdown", brief_text, f"{ticker}_filinglens_brief.md")
            st.download_button(
                "Download HTML",
                markdown_to_html(brief_text, f"{ticker} FilingLens Brief"),
                f"{ticker}_filinglens_brief.html",
                mime="text/html",
            )

with tabs[6]:
    st.caption(
        "What this tab does: explains FilingLens's data, analytics, retrieval, local-generation, "
        "privacy, and responsible-use methodology."
    )
    st.markdown(
        """
### Three-layer design

1. **Data layer:** official SEC submissions, Company Facts, and filing documents with source provenance.
2. **Analytics layer:** Python calculates financial statements, ratios, changes, free cash flow, and robust anomaly scores.
3. **Language layer:** the selected local or cloud model interprets only verified metrics and retrieved filing evidence.

### Selection and anomaly methodology

Annual XBRL observations prefer mapped US-GAAP concepts, full-year 10-K durations, and the latest filed duplicate. Missing or ambiguous mappings remain unavailable. Economic flags use absolute year-over-year percentage changes. Statistical flags use median absolute deviation on the change series, which is less sensitive to a single outlier than an ordinary mean/standard-deviation z-score.

### Retrieval and privacy

Filing HTML is cleaned, divided using recognized filing sections, chunked with overlap, and ranked locally with TF-IDF cosine similarity. Filing text is evidence—not instructions. Local provider traffic stays on loopback. When a cloud provider is selected, the prompt, verified metrics, and retrieved filing passages are sent to that provider's authenticated API. FilingLens contacts SEC.gov for public data; cloud usage may incur charges.

**Educational financial-analysis software. Not investment advice.**
"""
    )
