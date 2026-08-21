from __future__ import annotations

import pytest


def make_fact(
    value: float,
    year: int,
    *,
    start: str | None = None,
    end: str | None = None,
    filed: str | None = None,
    form: str = "10-K",
    fp: str = "FY",
    accn: str | None = None,
) -> dict[str, object]:
    fact: dict[str, object] = {
        "val": value,
        "fy": year,
        "end": end or f"{year}-12-31",
        "filed": filed or f"{year + 1}-02-15",
        "form": form,
        "fp": fp,
        "accn": accn or f"0000000000-{str(year)[2:]}-000001",
    }
    if start:
        fact["start"] = start
    return fact


@pytest.fixture
def company_facts_payload() -> dict[str, object]:
    revenue = []
    net_income = []
    assets = []
    ocf = []
    capex = []
    for year, rev, net, asset in (
        (2021, 100.0, 10.0, 200.0),
        (2022, 110.0, 12.0, 220.0),
        (2023, 125.0, 14.0, 240.0),
        (2024, 150.0, 18.0, 260.0),
    ):
        start = f"{year}-01-01"
        revenue.append(make_fact(rev, year, start=start))
        net_income.append(make_fact(net, year, start=start))
        assets.append(make_fact(asset, year))
        ocf.append(make_fact(net + 10, year, start=start))
        capex.append(make_fact(5, year, start=start))
    return {
        "cik": 123456,
        "entityName": "Example Corp",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": revenue}},
                "NetIncomeLoss": {"units": {"USD": net_income}},
                "Assets": {"units": {"USD": assets}},
                "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": ocf}},
                "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": capex}},
            }
        },
    }

