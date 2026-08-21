"""Parse SEC submissions metadata into usable filing records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class FilingMetadata:
    form: str
    filing_date: str
    report_date: str
    accession_number: str
    primary_document: str
    cik: str

    @property
    def source_url(self) -> str:
        accession = self.accession_number.replace("-", "")
        return (
            f"https://www.sec.gov/Archives/edgar/data/{int(self.cik)}/"
            f"{accession}/{self.primary_document}"
        )


def parse_recent_filings(
    submissions: dict[str, Any], forms: Iterable[str] = ("10-K", "10-Q")
) -> list[FilingMetadata]:
    cik = str(submissions.get("cik", "")).zfill(10)
    recent = submissions.get("filings", {}).get("recent", {})
    wanted = set(forms)
    fields = ("form", "filingDate", "reportDate", "accessionNumber", "primaryDocument")
    arrays = [recent.get(field, []) for field in fields]
    filings: list[FilingMetadata] = []
    for values in zip(*arrays):
        form, filing_date, report_date, accession, primary_document = values
        if form in wanted:
            filings.append(
                FilingMetadata(
                    form=form,
                    filing_date=filing_date,
                    report_date=report_date,
                    accession_number=accession,
                    primary_document=primary_document,
                    cik=cik,
                )
            )
    return filings


def latest_filing(submissions: dict[str, Any], form: str) -> FilingMetadata | None:
    return next(iter(parse_recent_filings(submissions, (form,))), None)

