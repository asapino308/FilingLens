"""Normalize SEC Company Facts into annual financial observations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Literal

import pandas as pd


PeriodType = Literal["duration", "instant"]


@dataclass(frozen=True)
class MetricDefinition:
    concepts: tuple[str, ...]
    period_type: PeriodType


METRIC_DEFINITIONS: dict[str, MetricDefinition] = {
    "revenue": MetricDefinition(
        (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet",
            "Revenues",
            "SalesRevenueGoodsNet",
        ),
        "duration",
    ),
    "cost_of_revenue": MetricDefinition(
        ("CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"), "duration"
    ),
    "gross_profit": MetricDefinition(("GrossProfit",), "duration"),
    "operating_income": MetricDefinition(("OperatingIncomeLoss",), "duration"),
    "net_income": MetricDefinition(
        ("NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"),
        "duration",
    ),
    "cash": MetricDefinition(
        (
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        ),
        "instant",
    ),
    "current_assets": MetricDefinition(("AssetsCurrent",), "instant"),
    "total_assets": MetricDefinition(("Assets",), "instant"),
    "current_liabilities": MetricDefinition(("LiabilitiesCurrent",), "instant"),
    "total_liabilities": MetricDefinition(("Liabilities",), "instant"),
    "stockholders_equity": MetricDefinition(
        ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
        "instant",
    ),
    "long_term_debt": MetricDefinition(
        (
            "LongTermDebtAndFinanceLeaseObligationsCurrentAndNoncurrent",
            "LongTermDebt",
            "LongTermDebtNoncurrent",
        ),
        "instant",
    ),
    "operating_cash_flow": MetricDefinition(
        ("NetCashProvidedByUsedInOperatingActivities",), "duration"
    ),
    "capital_expenditures": MetricDefinition(
        (
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsForAdditionsToPropertyPlantAndEquipment",
        ),
        "duration",
    ),
}


@dataclass(frozen=True)
class FinancialFact:
    ticker: str
    company_name: str
    cik: str
    form: str
    accession_number: str
    filing_date: str
    fiscal_year: int
    fiscal_period: str
    period_start: str | None
    period_end: str
    metric: str
    value: float
    unit: str
    xbrl_concept: str


def _duration_days(fact: dict[str, Any]) -> int | None:
    if not fact.get("start") or not fact.get("end"):
        return None
    try:
        return (date.fromisoformat(fact["end"]) - date.fromisoformat(fact["start"])).days
    except (TypeError, ValueError):
        return None


def _is_annual_candidate(fact: dict[str, Any], period_type: PeriodType) -> bool:
    if fact.get("form") not in {"10-K", "10-K/A"}:
        return False
    if not fact.get("end") or fact.get("val") is None:
        return False
    if fact.get("fp") not in {"FY", None, ""}:
        return False
    if period_type == "duration":
        days = _duration_days(fact)
        return days is not None and 300 <= days <= 450
    return not fact.get("start")


def select_annual_facts(
    payload: dict[str, Any], ticker: str, years: int | None = None
) -> pd.DataFrame:
    """Select one traceable annual fact per mapped metric and fiscal year.

    Concept priority is explicit. Within a concept/year, the most recently filed
    observation wins, which accommodates amended/restated facts without mixing
    duplicate contexts.
    """

    us_gaap = payload.get("facts", {}).get("us-gaap", {})
    company_name = str(payload.get("entityName", ""))
    cik = str(payload.get("cik", "")).zfill(10)
    selected: list[FinancialFact] = []

    for metric, definition in METRIC_DEFINITIONS.items():
        by_year: dict[int, tuple[int, dict[str, Any], str, str]] = {}
        for priority, concept in enumerate(definition.concepts):
            concept_data = us_gaap.get(concept, {})
            for unit, facts in concept_data.get("units", {}).items():
                if unit not in {"USD", "USD/shares"}:
                    continue
                for fact in facts:
                    if not _is_annual_candidate(fact, definition.period_type):
                        continue
                    try:
                        # SEC's `fy` describes the filing in which a fact appeared.
                        # Comparative prior-period facts in a newer 10-K therefore
                        # inherit the newer filing's FY. The observation's period end
                        # is the stable grouping key for annual history.
                        fiscal_year = int(str(fact["end"])[:4])
                    except (TypeError, ValueError):
                        continue
                    candidate = (priority, fact, concept, unit)
                    current = by_year.get(fiscal_year)
                    if current is None:
                        by_year[fiscal_year] = candidate
                    elif priority < current[0]:
                        by_year[fiscal_year] = candidate
                    elif priority == current[0] and str(fact.get("filed", "")) > str(
                        current[1].get("filed", "")
                    ):
                        by_year[fiscal_year] = candidate

        keep_years = sorted(by_year, reverse=True)[:years] if years else sorted(by_year)
        for fiscal_year in keep_years:
            _, fact, concept, unit = by_year[fiscal_year]
            selected.append(
                FinancialFact(
                    ticker=ticker.upper(),
                    company_name=company_name,
                    cik=cik,
                    form=str(fact.get("form", "")),
                    accession_number=str(fact.get("accn", "")),
                    filing_date=str(fact.get("filed", "")),
                    fiscal_year=fiscal_year,
                    fiscal_period=str(fact.get("fp", "FY")),
                    period_start=fact.get("start"),
                    period_end=str(fact.get("end", "")),
                    metric=metric,
                    value=float(fact["val"]),
                    unit=unit,
                    xbrl_concept=concept,
                )
            )

    columns = list(FinancialFact.__annotations__)
    frame = pd.DataFrame([asdict(fact) for fact in selected], columns=columns)
    if not frame.empty:
        frame = frame.sort_values(["fiscal_year", "metric"]).reset_index(drop=True)
    return frame


def select_quarterly_facts(
    payload: dict[str, Any], ticker: str, accession_number: str, report_date: str
) -> pd.DataFrame:
    """Select facts from one 10-Q without mixing quarter and year-to-date periods.

    Income statement values use a roughly three-month duration. Cash-flow facts
    in a 10-Q are usually fiscal year-to-date, so prefer the longest duration
    ending on the report date. Balance-sheet observations are point-in-time.
    """
    us_gaap = payload.get("facts", {}).get("us-gaap", {})
    company_name = str(payload.get("entityName", ""))
    cik = str(payload.get("cik", "")).zfill(10)
    selected: list[FinancialFact] = []
    ytd_metrics = {"operating_cash_flow", "capital_expenditures"}

    for metric, definition in METRIC_DEFINITIONS.items():
        candidates: list[tuple[tuple[int, int, str], dict[str, Any], str, str]] = []
        for priority, concept in enumerate(definition.concepts):
            for unit, facts in us_gaap.get(concept, {}).get("units", {}).items():
                if unit != "USD":
                    continue
                for fact in facts:
                    if (fact.get("accn") != accession_number or fact.get("form") not in {"10-Q", "10-Q/A"}
                            or fact.get("end") != report_date or fact.get("val") is None):
                        continue
                    if definition.period_type == "instant":
                        if fact.get("start"):
                            continue
                        duration_rank = 0
                    else:
                        days = _duration_days(fact)
                        if days is None:
                            continue
                        if metric in ytd_metrics:
                            if not 70 <= days <= 300:
                                continue
                            duration_rank = -days
                        else:
                            if not 70 <= days <= 110:
                                continue
                            duration_rank = abs(days - 90)
                    candidates.append(((priority, duration_rank, str(fact.get("filed", ""))), fact, concept, unit))
        if not candidates:
            continue
        if metric in ytd_metrics:
            rank = lambda item: (item[0][1], item[0][0], -int(item[0][2].replace("-", "") or 0))
        else:
            rank = lambda item: (item[0][0], item[0][1], -int(item[0][2].replace("-", "") or 0))
        _, fact, concept, unit = min(candidates, key=rank)
        selected.append(FinancialFact(
            ticker=ticker.upper(), company_name=company_name, cik=cik,
            form=str(fact.get("form", "")), accession_number=accession_number,
            filing_date=str(fact.get("filed", "")), fiscal_year=int(report_date[:4]),
            fiscal_period=str(fact.get("fp", "")), period_start=fact.get("start"),
            period_end=report_date, metric=metric, value=float(fact["val"]),
            unit=unit, xbrl_concept=concept,
        ))

    columns = list(FinancialFact.__annotations__)
    return pd.DataFrame([asdict(fact) for fact in selected], columns=columns).sort_values("metric").reset_index(drop=True)
