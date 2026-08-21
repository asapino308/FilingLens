"""Parse official SEC Forms 4/4-A into traceable insider transactions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
import xml.etree.ElementTree as ET

from .client import SECClient, SECClientError
from .submissions import FilingMetadata, parse_recent_filings


TRANSACTION_CODE_LABELS = {
    "P": "Open-market/private purchase",
    "S": "Open-market/private sale",
    "A": "Grant or award",
    "D": "Disposition to issuer",
    "F": "Tax or exercise-price payment",
    "M": "Option exercise or conversion",
    "G": "Gift",
    "C": "Conversion",
    "I": "Discretionary transaction",
    "J": "Other transaction",
    "K": "Equity swap",
    "W": "Acquisition/disposition by will or succession",
    "Z": "Deposit into or withdrawal from voting trust",
}


@dataclass(frozen=True)
class InsiderTransaction:
    ticker: str
    filing_date: str
    transaction_date: str
    insider_name: str
    insider_role: str
    transaction_code: str
    transaction_type: str
    acquired_disposed: str
    shares: float | None
    price_per_share: float | None
    transaction_value: float | None
    shares_owned_after: float | None
    ownership_nature: str
    security_title: str
    derivative: bool
    plan_10b5_1: bool
    form: str
    accession_number: str
    source_url: str

    def as_record(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class InsiderActivityResult:
    transactions: tuple[InsiderTransaction, ...]
    filings_reviewed: int
    failures: tuple[str, ...] = ()


def raw_ownership_url(filing: FilingMetadata) -> str:
    """Return the untransformed ownership XML URL for a Form 4 filing."""
    accession = filing.accession_number.replace("-", "")
    filename = PurePosixPath(filing.primary_document).name
    return (
        f"https://www.sec.gov/Archives/edgar/data/{int(filing.cik)}/"
        f"{accession}/{filename}"
    )


def _strip_namespaces(root: ET.Element) -> None:
    for element in root.iter():
        element.tag = element.tag.rsplit("}", 1)[-1]


def _text(element: ET.Element, path: str, default: str = "") -> str:
    node = element.find(path)
    return (node.text or "").strip() if node is not None else default


def _number(element: ET.Element, path: str) -> float | None:
    value = _text(element, path).replace(",", "").replace("$", "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


def _owner_details(root: ET.Element) -> tuple[str, str]:
    names: list[str] = []
    roles: list[str] = []
    for owner in root.findall("reportingOwner"):
        name = _text(owner, "reportingOwnerId/rptOwnerName")
        relationship = owner.find("reportingOwnerRelationship")
        owner_roles: list[str] = []
        if relationship is not None:
            if _truthy(_text(relationship, "isDirector")):
                owner_roles.append("Director")
            if _truthy(_text(relationship, "isOfficer")):
                title = _text(relationship, "officerTitle")
                owner_roles.append(title or "Officer")
            if _truthy(_text(relationship, "isTenPercentOwner")):
                owner_roles.append("10% Owner")
            if _truthy(_text(relationship, "isOther")):
                owner_roles.append(_text(relationship, "otherText") or "Other")
        if name:
            names.append(name)
        roles.extend(owner_roles)
    return "; ".join(dict.fromkeys(names)), "; ".join(dict.fromkeys(roles)) or "Unspecified"


def _parse_transaction(
    element: ET.Element,
    filing: FilingMetadata,
    *,
    ticker: str,
    insider_name: str,
    insider_role: str,
    derivative: bool,
    plan_10b5_1: bool,
) -> InsiderTransaction | None:
    transaction_date = _text(element, "transactionDate/value")
    code = _text(element, "transactionCoding/transactionCode").upper()
    if not transaction_date and not code:
        return None

    shares = _number(element, "transactionAmounts/transactionShares/value")
    price = _number(element, "transactionAmounts/transactionPricePerShare/value")
    value = shares * price if shares is not None and price is not None else None
    acquired_disposed = _text(
        element, "transactionAmounts/transactionAcquiredDisposedCode/value"
    ).upper()
    ownership = _text(
        element, "ownershipNature/directOrIndirectOwnership/value"
    ).upper()
    return InsiderTransaction(
        ticker=ticker,
        filing_date=filing.filing_date,
        transaction_date=transaction_date,
        insider_name=insider_name or "Unspecified reporting owner",
        insider_role=insider_role,
        transaction_code=code or "—",
        transaction_type=TRANSACTION_CODE_LABELS.get(code, "Other/see filing"),
        acquired_disposed={"A": "Acquired", "D": "Disposed"}.get(
            acquired_disposed, acquired_disposed or "Unspecified"
        ),
        shares=shares,
        price_per_share=price,
        transaction_value=value,
        shares_owned_after=_number(
            element, "postTransactionAmounts/sharesOwnedFollowingTransaction/value"
        ),
        ownership_nature={"D": "Direct", "I": "Indirect"}.get(
            ownership, ownership or "Unspecified"
        ),
        security_title=_text(element, "securityTitle/value", "Unspecified security"),
        derivative=derivative,
        plan_10b5_1=plan_10b5_1,
        form=filing.form,
        accession_number=filing.accession_number,
        source_url=filing.source_url,
    )


def parse_ownership_document(
    xml_text: str, filing: FilingMetadata
) -> list[InsiderTransaction]:
    """Parse transaction rows from one raw SEC ownership XML document."""
    root = ET.fromstring(xml_text)
    _strip_namespaces(root)
    ticker = _text(root, "issuer/issuerTradingSymbol").upper()
    insider_name, insider_role = _owner_details(root)
    footnotes = " ".join(node.text or "" for node in root.findall(".//footnote"))
    plan_10b5_1 = _truthy(_text(root, "aff10b5One")) or "10b5-1" in footnotes.lower()

    transactions: list[InsiderTransaction] = []
    for path, derivative in (
        ("nonDerivativeTable/nonDerivativeTransaction", False),
        ("derivativeTable/derivativeTransaction", True),
    ):
        for element in root.findall(path):
            transaction = _parse_transaction(
                element,
                filing,
                ticker=ticker,
                insider_name=insider_name,
                insider_role=insider_role,
                derivative=derivative,
                plan_10b5_1=plan_10b5_1,
            )
            if transaction is not None:
                transactions.append(transaction)
    return transactions


def fetch_insider_activity(
    client: SECClient,
    submissions: dict[str, object],
    *,
    max_filings: int = 20,
    refresh: bool = False,
) -> InsiderActivityResult:
    """Fetch and parse recent official Forms 4/4-A with partial-failure tolerance."""
    if max_filings < 1:
        raise ValueError("max_filings must be at least 1")
    filings = parse_recent_filings(submissions, ("4", "4/A"))[:max_filings]
    transactions: list[InsiderTransaction] = []
    failures: list[str] = []
    for filing in filings:
        try:
            xml_text = client.filing_document(raw_ownership_url(filing), refresh=refresh)
            transactions.extend(parse_ownership_document(xml_text, filing))
        except (SECClientError, ET.ParseError, ValueError) as exc:
            failures.append(f"{filing.accession_number}: {exc}")
    transactions.sort(
        key=lambda item: (item.transaction_date, item.filing_date, item.accession_number),
        reverse=True,
    )
    return InsiderActivityResult(tuple(transactions), len(filings), tuple(failures))
