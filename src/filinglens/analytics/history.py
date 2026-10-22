"""Exact-period reported-value histories and conservative quarterly analytics.

These are views of observations retained in today's Company Facts, not a
point-in-time database. All derived values retain their source operands.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
import math
import re
from typing import Any

from filinglens.sec.xbrl import METRIC_DEFINITIONS
from filinglens.ui.components import LABELS


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def _ratio(a: float, b: float) -> float | None:
    if b == 0:
        return None
    result = a / b
    return result if math.isfinite(result) else None


def _sources(*items: dict[str, Any]) -> list[dict[str, Any]]:
    sources: dict[tuple, dict[str, Any]] = {}
    for item in items:
        for source in item.get("sources", [item]):
            key = (source["accession"], source["concept"], source["start"], source["end"], source["value"])
            sources[key] = source
    return list(sources.values())


def observations(payload: dict[str, Any], metric: str, filings: dict[str, str]) -> list[dict[str, Any]]:
    """Only finite, dated USD observations from annual/quarterly reports.

    Conflicting values in the same filing/context are excluded, rather than
    interpreted as a revision. Source URLs are constructed from validated IDs.
    """
    definition = METRIC_DEFINITIONS[metric]
    grouped: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    cik = str(payload.get("cik", ""))
    if not cik.isdigit():
        return []
    for priority, concept in enumerate(definition.concepts):
        raw = payload.get("facts", {}).get("us-gaap", {}).get(concept, {}).get("units", {}).get("USD", [])
        for fact in raw:
            if fact.get("form") not in {"10-K", "10-K/A", "10-Q", "10-Q/A"}:
                continue
            accession = str(fact.get("accn", ""))
            if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
                continue
            start, end, filed = fact.get("start"), fact.get("end"), fact.get("filed")
            try:
                value = float(fact["val"])
                if not math.isfinite(value) or isinstance(fact["val"], bool):
                    continue
                date.fromisoformat(end)
                date.fromisoformat(filed)
                if filed < end:
                    continue
                if definition.period_type == "duration":
                    if not start or not 70 <= _days(start, end) <= 450:
                        continue
                elif start:
                    continue
            except (ValueError, TypeError, KeyError, OverflowError):
                continue
            directory = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}"
            source = {"value": value, "start": start, "end": end, "filed": filed,
                      "accession": accession, "concept": concept, "form": fact["form"],
                      "url": filings.get(accession, f"{directory}/{accession}-index.html"),
                      "priority": priority}
            grouped[(concept, start, end, accession)].append(source)
    return [items[0] for items in grouped.values() if len({item["value"] for item in items}) == 1]


def revision_history(payload: dict[str, Any], filings: dict[str, str], years: int = 5) -> dict[str, Any]:
    """Keep concept/period boundaries intact, including value reversions A→B→A."""
    series: list[dict[str, Any]] = []
    for metric, definition in METRIC_DEFINITIONS.items():
        groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
        for fact in observations(payload, metric, filings):
            if fact["form"] not in {"10-K", "10-K/A"}:
                continue
            if definition.period_type == "duration" and not 300 <= _days(fact["start"], fact["end"]) <= 450:
                continue
            groups[(fact["start"], fact["end"], fact["concept"])].append(fact)
        # One preferred concept per exact period. Never compare different tags.
        preferred: dict[tuple, tuple[int, list[dict[str, Any]]]] = {}
        for (start, end, _), items in groups.items():
            key = (start, end)
            if key not in preferred or items[0]["priority"] < preferred[key][0]:
                preferred[key] = (items[0]["priority"], items)
        for (start, end), (_, items) in preferred.items():
            # A filing date without intraday order cannot establish a revision
            # sequence if two accessions disagree on that date.
            dates: dict[str, set[float]] = defaultdict(set)
            for item in items:
                dates[item["filed"]].add(item["value"])
            if any(len(values) > 1 for values in dates.values()):
                continue
            versions: list[dict[str, Any]] = []
            for item in sorted(items, key=lambda item: (item["filed"], item["accession"])):
                if versions and item["value"] == versions[-1]["value"]:
                    versions[-1]["last_seen"] = item["filed"]
                    versions[-1]["last_url"] = item["url"]
                    continue
                versions.append({**item, "last_seen": item["filed"], "last_url": item["url"]})
            first, latest = versions[0]["value"], versions[-1]["value"]
            series.append({"id": f"{metric}:{start or 'instant'}:{end}", "metric": metric,
                           "label": LABELS.get(metric, metric), "year": int(end[:4]),
                           "start": start, "end": end, "concept": items[0]["concept"],
                           "first": first, "latest": latest, "change": latest - first,
                           "percent_change": _ratio(latest - first, abs(first)),
                           "revision_count": len(versions) - 1, "versions": versions})
    available_years = sorted({row["year"] for row in series})[-years:]
    # Keep an extra year while computing growth consequences, then limit display.
    impacts = _revision_impacts(series)
    series = sorted([row for row in series if row["year"] in available_years],
                    key=lambda row: (-row["year"], row["metric"], row["end"]))
    return {"years": available_years, "series": series,
            "impacts": [item for item in impacts if item["year"] in available_years],
            "revised_periods": len({row["end"] for row in series if row["revision_count"]}),
            "revised_series": sum(bool(row["revision_count"]) for row in series)}


def _revision_impacts(series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in series:
        if row["start"]:
            grouped[(row["start"], row["end"])][row["metric"]] = row
    result = []

    def add(metric: str, label: str, start: str, end: str, parts: list[dict[str, Any]], formula, unit: str):
        if not any(part["revision_count"] for part in parts):
            return
        first = formula(*[part["first"] for part in parts])
        latest = formula(*[part["latest"] for part in parts])
        if first is None or latest is None or first == latest:
            return
        result.append({"metric": metric, "label": label, "year": int(end[:4]),
                       "start": start, "end": end, "first": first, "latest": latest,
                       "unit": unit, "sources": _sources(*[v for part in parts for v in (part["versions"][0], part["versions"][-1])])})

    for (start, end), metrics in sorted(grouped.items()):
        if {"operating_cash_flow", "capital_expenditures"} <= metrics.keys():
            add("free_cash_flow", "Free cash flow", start, end,
                [metrics["operating_cash_flow"], metrics["capital_expenditures"]], lambda a, b: a - b, "usd")
        for income, label in (("operating_income", "Operating margin"), ("net_income", "Net margin")):
            if {income, "revenue"} <= metrics.keys():
                add(f"{income}_margin", label, start, end, [metrics[income], metrics["revenue"]], _ratio, "percent")
        for metric in ("revenue", "net_income", "operating_cash_flow"):
            if metric not in metrics:
                continue
            prior = [m[metric] for (s, e), m in grouped.items() if metric in m
                     and 0 < (date.fromisoformat(start) - date.fromisoformat(e)).days <= 7
                     and 300 <= _days(s, e) <= 450
                     and abs(_days(s, e) - _days(start, end)) <= 10
                     and m[metric]["concept"] == metrics[metric]["concept"]]
            if len(prior) == 1:
                add(f"{metric}_growth", f"{LABELS.get(metric, metric)} growth", start, end,
                    [metrics[metric], prior[0]], lambda a, b: _ratio(a - b, abs(b)), "percent")
    return result


def quarterly_history(payload: dict[str, Any], filings: dict[str, str], years: int = 5) -> dict[str, Any]:
    """Reported 3-month values or exact same-concept YTD differences.

    Four quarters are summed only if every component has the same quarter
    boundaries and all four periods are contiguous. Instants are never summed.
    """
    by_end: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for metric, definition in METRIC_DEFINITIONS.items():
        if definition.period_type != "duration":
            continue
        by_concept: dict[str, dict[tuple, dict[str, Any]]] = defaultdict(dict)
        reported = observations(payload, metric, filings)
        dated_values: dict[tuple, set[float]] = defaultdict(set)
        for fact in reported:
            dated_values[(fact["concept"], fact["start"], fact["end"], fact["filed"])].add(fact["value"])
        ambiguous = {key[:3] for key, values in dated_values.items() if len(values) > 1}
        for fact in reported:
            if (fact["concept"], fact["start"], fact["end"]) in ambiguous:
                continue
            key = (fact["start"], fact["end"])
            current = by_concept[fact["concept"]].get(key)
            if current is None or (fact["filed"], fact["accession"]) > (current["filed"], current["accession"]):
                by_concept[fact["concept"]][key] = fact
        candidates = []
        for periods in by_concept.values():
            for (start, end), fact in periods.items():
                duration = _days(start, end)
                if 70 <= duration <= 110:
                    candidates.append({**fact, "origin": "reported", "sources": [fact]})
                elif 140 <= duration <= 450:
                    previous = [p for (s, e), p in periods.items() if s == start and e < end
                                and 70 <= _days(e, end) - 1 <= 110]
                    if len(previous) != 1:
                        continue
                    prior = previous[0]
                    quarter_start = (date.fromisoformat(prior["end"]) + timedelta(days=1)).isoformat()
                    candidates.append({**fact, "start": quarter_start,
                                       "value": fact["value"] - prior["value"],
                                       "origin": "ytd_difference", "sources": [fact, prior]})
        for item in sorted(candidates, key=lambda item: (item["priority"], item["origin"] != "reported",
                                                       -int(item["filed"].replace("-", "")), item["start"])):
            if metric not in by_end[item["end"]]:
                by_end[item["end"]][metric] = item

    periods = []
    for end, metrics in sorted(by_end.items()):
        # A shared quarter boundary prevents mixing a stub or an alternate
        # fiscal context into a quarter's calculations or its TTM total.
        start = metrics["revenue"]["start"] if "revenue" in metrics else Counter(
            item["start"] for item in metrics.values()).most_common(1)[0][0]
        metrics = {metric: item for metric, item in metrics.items() if item["start"] == start}
        for metric, left, right in (("free_cash_flow", "operating_cash_flow", "capital_expenditures"),
                                    ("gross_profit", "revenue", "cost_of_revenue")):
            if metric not in metrics and left in metrics and right in metrics:
                a, b = metrics[left], metrics[right]
                metrics[metric] = {"value": a["value"] - b["value"], "start": start, "end": end,
                                   "origin": "calculated", "sources": _sources(a, b)}
        periods.append({"start": start, "end": end, "metrics": metrics})

    ttm = None
    last = periods[-4:]
    if len(last) == 4 and 335 <= _days(last[0]["start"], last[-1]["end"]) <= 400 and all(
        date.fromisoformat(b["start"]) == date.fromisoformat(a["end"]) + timedelta(days=1)
        for a, b in zip(last, last[1:])
    ):
        metrics = {}
        for metric in METRIC_DEFINITIONS.keys() | {"free_cash_flow"}:
            if all(metric in period["metrics"] for period in last):
                parts = [period["metrics"][metric] for period in last]
                # A mapped label can span different tags over time. Retain
                # quarterly values, but do not silently sum different concepts.
                concepts = [{source["concept"] for source in part["sources"]} for part in parts]
                if any(tags != concepts[0] for tags in concepts[1:]):
                    continue
                metrics[metric] = {"value": sum(part["value"] for part in parts), "origin": "four_quarters",
                                   "start": last[0]["start"], "end": last[-1]["end"], "sources": _sources(*parts)}
        if metrics:
            ttm = {"start": last[0]["start"], "end": last[-1]["end"], "metrics": metrics}
    # Instant balance sheet values are displayed at quarter end, never in TTM.
    for metric, definition in METRIC_DEFINITIONS.items():
        if definition.period_type != "instant":
            continue
        reported = observations(payload, metric, filings)
        dated_values = defaultdict(set)
        for fact in reported:
            dated_values[(fact["concept"], fact["end"], fact["filed"])].add(fact["value"])
        ambiguous_instants = {key[:2] for key, values in dated_values.items() if len(values) > 1}
        facts = sorted([fact for fact in reported if (fact["concept"], fact["end"]) not in ambiguous_instants],
                       key=lambda f: (f["priority"], -int(f["filed"].replace("-", ""))))
        for period in periods:
            match = next((fact for fact in facts if fact["end"] == period["end"]), None)
            if match:
                period["metrics"][metric] = {**match, "origin": "reported", "sources": [match]}
    return {"periods": periods[-years * 4:], "ttm": ttm}


def annual_peer(series: list[dict[str, Any]], year: int) -> dict[str, Any] | None:
    """An annual peer row anchored to revenue's exact reporting period."""
    revenue = sorted([row for row in series if row["metric"] == "revenue" and row["year"] == year],
                     key=lambda row: row["end"])
    if not revenue:
        return None
    anchor = revenue[-1]
    matching = {row["metric"]: row for row in series if row["end"] == anchor["end"]
                and (row["start"] is None or row["start"] == anchor["start"])}
    metrics: dict[str, Any] = {}

    def add(metric: str, parts: list[str], formula):
        if not all(part in matching for part in parts):
            return
        rows = [matching[part] for part in parts]
        metrics[metric] = {"value": formula(*[row["latest"] for row in rows]),
                           "sources": _sources(*[row["versions"][-1] for row in rows])}

    add("revenue", ["revenue"], lambda a: a)
    add("operating_margin", ["operating_income", "revenue"], _ratio)
    add("net_margin", ["net_income", "revenue"], _ratio)
    add("free_cash_flow", ["operating_cash_flow", "capital_expenditures"], lambda a, b: a - b)
    add("free_cash_flow_margin", ["operating_cash_flow", "capital_expenditures", "revenue"],
        lambda a, b, c: _ratio(a - b, c))
    add("current_ratio", ["current_assets", "current_liabilities"], _ratio)
    add("debt_to_assets", ["long_term_debt", "total_assets"], _ratio)
    prior = [row for row in series if row["metric"] == "revenue" and row["year"] == year - 1
             and row["concept"] == anchor["concept"]
             and 0 < (date.fromisoformat(anchor["start"]) - date.fromisoformat(row["end"])).days <= 7
             and abs(_days(row["start"], row["end"]) - _days(anchor["start"], anchor["end"])) <= 10]
    if len(prior) == 1:
        metrics["revenue_growth"] = {"value": _ratio(anchor["latest"] - prior[0]["latest"], abs(prior[0]["latest"])),
                                     "sources": _sources(anchor["versions"][-1], prior[0]["versions"][-1])}
    return {"start": anchor["start"], "end": anchor["end"], "metrics": metrics}
