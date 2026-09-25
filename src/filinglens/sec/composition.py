"""Traceable income-statement composition from one filing and its inline XBRL."""

from __future__ import annotations

from datetime import date
from collections import Counter
from itertools import combinations
import re
import warnings
from typing import Any

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning


INCOME_CONCEPTS: dict[str, tuple[str, ...]] = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "Revenues", "SalesRevenueGoodsNet"),
    "cost_of_revenue": ("CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"),
    "gross_profit": ("GrossProfit",),
    "operating_expenses": ("OperatingExpenses",),
    "research_development": ("ResearchAndDevelopmentExpense",),
    "selling_general_admin": ("SellingGeneralAndAdministrativeExpense",),
    "selling_marketing": ("SellingAndMarketingExpense", "SellingExpense"),
    "general_admin": ("GeneralAndAdministrativeExpense",),
    "other_operating_expenses": ("OtherOperatingExpenses",),
    "operating_income": ("OperatingIncomeLoss",),
    "income_before_tax": (
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ),
    "income_tax": ("IncomeTaxExpenseBenefit",),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "interest_expense": ("InterestExpenseNonOperating",),
    "interest_income": ("InvestmentIncomeInterest", "InterestIncomeExpenseNet"),
}

LABELS = {
    "revenue": "Revenue", "cost_of_revenue": "Cost of revenue", "gross_profit": "Gross profit",
    "operating_expenses": "Operating expenses", "research_development": "Research and development",
    "selling_general_admin": "Selling, general and administrative", "selling_marketing": "Sales and marketing",
    "general_admin": "General and administrative", "other_operating_expenses": "Other operating expenses",
    "operating_income": "Operating income", "income_before_tax": "Income before taxes",
    "income_tax": "Income tax expense (benefit)", "net_income": "Net income",
    "interest_expense": "Interest expense", "interest_income": "Interest income",
    "net_operating_costs": "Net operating costs", "net_nonoperating": "Net nonoperating items",
    "other_unmapped_operating": "Other or not separately mapped",
}


def _duration_days(fact: dict[str, Any]) -> int | None:
    try:
        return (date.fromisoformat(fact["end"]) - date.fromisoformat(fact["start"])).days
    except (KeyError, TypeError, ValueError):
        return None


def select_filing_income_facts(
    payload: dict[str, Any], accession: str, report_date: str, form: str
) -> dict[str, dict[str, Any]]:
    """Use only entity-wide USD facts from the selected filing and duration."""
    if form not in {"10-K", "10-Q"}:
        raise ValueError("Choose a 10-K or 10-Q filing.")
    us_gaap = payload.get("facts", {}).get("us-gaap", {})
    result: dict[str, dict[str, Any]] = {}
    anchor_start: str | None = None
    lower, upper, target = (300, 450, 365) if form == "10-K" else (70, 110, 90)
    for metric, concepts in INCOME_CONCEPTS.items():
        candidates = []
        for priority, concept in enumerate(concepts):
            for fact in us_gaap.get(concept, {}).get("units", {}).get("USD", []):
                if (fact.get("accn") != accession or fact.get("form") not in {form, f"{form}/A"}
                        or fact.get("end") != report_date or fact.get("val") is None):
                    continue
                days = _duration_days(fact)
                if days is None or not lower <= days <= upper:
                    continue
                if anchor_start is not None and fact.get("start") != anchor_start:
                    continue
                candidates.append((priority, abs(days - target), str(fact.get("filed", "")), fact, concept))
        if not candidates:
            continue
        priority, distance, filed, fact, concept = min(
            candidates, key=lambda item: (item[0], item[1], item[2]),
        )
        result[metric] = {
            "id": metric, "label": LABELS[metric], "value": float(fact["val"]),
            "concept": concept, "period_start": str(fact["start"]),
            "period_end": report_date, "origin": "reported",
        }
        if metric == "revenue":
            anchor_start = str(fact["start"])
    if anchor_start is None and result:
        anchor_start = Counter(item["period_start"] for item in result.values()).most_common(1)[0][0]
        result = {metric: item for metric, item in result.items() if item["period_start"] == anchor_start}
    return result


def _derived(metric: str, value: float, start: str, end: str) -> dict[str, Any]:
    return {"id": metric, "label": LABELS.get(metric, metric.replace("_", " ").title()),
            "value": value, "concept": None, "period_start": start,
            "period_end": end, "origin": "calculated"}


def compose_income(facts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Create a cautious revenue-to-profit bridge and nonoverlapping cost detail."""
    items = dict(facts)
    start = next((item["period_start"] for item in items.values()), "")
    end = next((item["period_end"] for item in items.values()), "")

    def value(metric: str) -> float | None:
        return items[metric]["value"] if metric in items else None

    revenue, cost, gross = value("revenue"), value("cost_of_revenue"), value("gross_profit")
    if gross is None and revenue is not None and cost is not None:
        items["gross_profit"] = _derived("gross_profit", revenue - cost, start, end)
        gross = revenue - cost
    operating_income, operating_expenses = value("operating_income"), value("operating_expenses")
    if operating_expenses is None and gross is not None and operating_income is not None:
        items["net_operating_costs"] = _derived("net_operating_costs", gross - operating_income, start, end)
    pretax = value("income_before_tax")
    if pretax is not None and operating_income is not None:
        items["net_nonoperating"] = _derived("net_nonoperating", pretax - operating_income, start, end)

    detail_ids = ["research_development"]
    if "selling_general_admin" in items:
        detail_ids.append("selling_general_admin")
    else:
        detail_ids.extend(("selling_marketing", "general_admin"))
    detail_ids.append("other_operating_expenses")
    details = [items[metric] for metric in detail_ids if metric in items]
    detail_total = sum(item["value"] for item in details)
    if operating_expenses is not None and details and detail_total <= operating_expenses + max(1, operating_expenses * 0.001):
        remainder = operating_expenses - detail_total
        if remainder > max(1, operating_expenses * 0.001):
            details.append(_derived("other_unmapped_operating", remainder, start, end))
    elif operating_expenses is not None and detail_total > operating_expenses + max(1, operating_expenses * 0.001):
        # Tagged expense categories can overlap. Do not present them as a sum.
        details = []

    bridge_ids = ("revenue", "cost_of_revenue", "gross_profit", "operating_expenses",
                  "net_operating_costs", "operating_income", "net_nonoperating",
                  "income_before_tax", "income_tax", "net_income")
    tolerance = max(1, min(5_000_000, abs(revenue or 0) * 0.001))
    def reconciles(left: float | None, right: float | None, reported: float | None) -> bool | None:
        if left is None or right is None or reported is None:
            return None
        return abs(left - right - reported) <= tolerance
    checks = {
        "gross_profit": reconciles(revenue, cost, gross),
        "operating_income": reconciles(gross, operating_expenses, operating_income),
        "net_income": reconciles(pretax, value("income_tax"), value("net_income")),
    }
    return {"metrics": items, "bridge": [items[key] for key in bridge_ids if key in items],
            "expense_details": details, "reconciliations": checks}


def _local_name(tag: Any) -> str:
    return str(getattr(tag, "name", "") or "").lower().split(":")[-1]


def _child_text(tag: Any, name: str) -> str | None:
    found = tag.find(lambda child: _local_name(child) == name)
    return found.get_text(" ", strip=True) if found else None


def _number(tag: Any) -> float | None:
    raw = tag.get_text("", strip=True).replace(",", "").replace("\u2212", "-").strip()
    if not raw or raw in {"—", "–", "-"}:
        return None
    negative = raw.startswith("(") and raw.endswith(")")
    try:
        value = float(raw.strip("()")) * (10 ** int(tag.get("scale", 0)))
    except (TypeError, ValueError, OverflowError):
        return None
    return -value if negative or tag.get("sign") == "-" else value


def _member_label(member: str) -> str:
    name = member.split(":")[-1].removesuffix("Member").removesuffix("Segment")
    name = re.sub(r"(?<=[a-z])and(?=[A-Z])", "And", name)
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    name = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", name)
    name = name.replace("I Phone", "iPhone").replace("I Pad", "iPad").replace("I Mac", "iMac")
    name = re.sub(r"\bAnd\b", "and", name)
    name = re.sub(r"\bOf\b", "of", name)
    return {"US": "United States", "TW": "Taiwan", "CN": "China"}.get(name, name).strip()


def _visible_label(tag: Any, member: str) -> str:
    row = tag.find_parent("tr")
    if row:
        first = row.find(["td", "th"])
        if first:
            label = re.sub(r"\s+", " ", first.get_text(" ", strip=True)).replace("®", "").replace("™", "").strip()
            generic = {"revenue", "revenues", "net revenue", "net revenues", "net sales", "sales",
                       "total revenue", "total revenues", "total net sales", "total sales"}
            if 2 <= len(label) <= 85 and label.lower() not in generic and not re.fullmatch(r"[$\d,().\- ]+", label):
                return label
    return _member_label(member)


def _axis_type(axis: str) -> str | None:
    name = axis.split(":")[-1].lower()
    if "productorservice" in name or "productsandservices" in name:
        return "Product and service revenue"
    if "businesssegment" in name or "operatingsegment" in name:
        return "Revenue by business segment"
    if "geograph" in name or "region" in name:
        return "Revenue by geography"
    return None


def _reconciled_subset(items: list[dict[str, Any]], total: float) -> list[dict[str, Any]]:
    if not 2 <= len(items) <= 16 or total <= 0:
        return []
    tolerance = max(1, min(5_000_000, abs(total) * 0.001))
    # Some filings tag both a parent category (such as all products) and its
    # individual products. Remove a parent only when its children reconcile.
    parents: set[str] = set()
    for item in items:
        member = item["member"].split(":")[-1].lower()
        if member not in {"productmember", "productsmember", "goodsmember", "servicemember", "servicesmember"}:
            continue
        others = [other for other in items if other is not item and other["value"] < item["value"]]
        for size in range(2, len(others) + 1):
            if any(abs(sum(child["value"] for child in subset) - item["value"]) <= tolerance
                   for subset in combinations(others, size)):
                parents.add(item["member"])
                break
    items = [item for item in items if item["member"] not in parents]
    best: list[dict[str, Any]] = []
    for size in range(len(items), 1, -1):
        for subset in combinations(items, size):
            if abs(sum(item["value"] for item in subset) - total) <= tolerance:
                best = list(subset)
                break
        if best:
            break
    return sorted(best, key=lambda item: item["value"], reverse=True)


def revenue_disaggregations(
    html: str, period_start: str, period_end: str, total_revenue: float
) -> list[dict[str, Any]]:
    """Return dimensional revenue groups only when they sum to the filing total."""
    if not period_start or not period_end or total_revenue <= 0:
        return []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(html, "lxml")
    contexts: dict[str, list[tuple[str, str]]] = {}
    for context in soup.find_all(lambda tag: _local_name(tag) == "context"):
        if _child_text(context, "startdate") != period_start or _child_text(context, "enddate") != period_end:
            continue
        members = [(str(member.get("dimension", "")), member.get_text(" ", strip=True))
                   for member in context.find_all(lambda tag: _local_name(tag) == "explicitmember")]
        if members:
            contexts[str(context.get("id", ""))] = members

    revenue_concepts = set(INCOME_CONCEPTS["revenue"])
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for tag in soup.find_all(lambda item: _local_name(item) == "nonfraction"):
        concept = str(tag.get("name", "")).split(":")[-1]
        if concept not in revenue_concepts:
            continue
        members = contexts.get(str(tag.get("contextref", "")))
        amount = _number(tag)
        if not members or amount is None or amount <= 0 or amount > total_revenue:
            continue
        relevant = [(axis, member, _axis_type(axis)) for axis, member in members if _axis_type(axis)]
        if len(relevant) != 1:
            continue
        axis, member, title = relevant[0]
        if not title:
            continue
        # An additional consolidation axis is common in segment contexts.
        if any(other_axis != axis and "consolidationitemsaxis" not in other_axis.lower()
               for other_axis, _ in members):
            continue
        grouped.setdefault(title, {}).setdefault(member, {
            "label": _visible_label(tag, member), "value": amount, "member": member,
            "axis": axis, "concept": concept,
        })

    results = []
    for title, by_member in grouped.items():
        selected = _reconciled_subset(list(by_member.values()), total_revenue)
        if selected:
            results.append({"title": title, "total": total_revenue,
                            "period_start": period_start, "period_end": period_end,
                            "items": selected})
    return results
