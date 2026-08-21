from __future__ import annotations

from filinglens.sec.client import SECClientError
from filinglens.sec.insiders import (
    fetch_insider_activity,
    parse_ownership_document,
    raw_ownership_url,
)
from filinglens.sec.submissions import FilingMetadata


OWNERSHIP_XML = """<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType>
  <issuer>
    <issuerTradingSymbol>EXM</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>Doe Jane</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>1</isDirector>
      <isOfficer>1</isOfficer>
      <officerTitle>Chief Financial Officer</officerTitle>
      <isTenPercentOwner>0</isTenPercentOwner>
      <isOther>0</isOther>
    </reportingOwnerRelationship>
  </reportingOwner>
  <aff10b5One>1</aff10b5One>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-08-10</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>1,000</value></transactionShares>
        <transactionPricePerShare><value>25.50</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction><value>5000</value></sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
      <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
  <derivativeTable>
    <derivativeTransaction>
      <securityTitle><value>Stock Option</value></securityTitle>
      <transactionDate><value>2026-08-10</value></transactionDate>
      <transactionCoding><transactionCode>M</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>200</value></transactionShares>
        <transactionPricePerShare><value>5</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction><value>800</value></sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
      <ownershipNature><directOrIndirectOwnership><value>I</value></directOrIndirectOwnership></ownershipNature>
    </derivativeTransaction>
  </derivativeTable>
</ownershipDocument>
"""


def filing(accession: str = "0000000001-26-000001") -> FilingMetadata:
    return FilingMetadata(
        form="4",
        filing_date="2026-08-11",
        report_date="2026-08-10",
        accession_number=accession,
        primary_document="xslF345X06/ownership.xml",
        cik="0000000001",
    )


def submissions() -> dict[str, object]:
    return {
        "cik": "1",
        "filings": {
            "recent": {
                "form": ["4", "4"],
                "filingDate": ["2026-08-11", "2026-08-09"],
                "reportDate": ["2026-08-10", "2026-08-08"],
                "accessionNumber": ["0000000001-26-000001", "0000000001-26-000002"],
                "primaryDocument": [
                    "xslF345X06/ownership.xml",
                    "xslF345X06/ownership.xml",
                ],
            }
        },
    }


def test_raw_ownership_url_removes_xsl_directory():
    assert raw_ownership_url(filing()) == (
        "https://www.sec.gov/Archives/edgar/data/1/"
        "000000000126000001/ownership.xml"
    )


def test_form_4_parser_preserves_transaction_details():
    transactions = parse_ownership_document(OWNERSHIP_XML, filing())

    assert len(transactions) == 2
    purchase, option = transactions
    assert purchase.ticker == "EXM"
    assert purchase.insider_name == "Doe Jane"
    assert purchase.insider_role == "Director; Chief Financial Officer"
    assert purchase.transaction_type == "Open-market/private purchase"
    assert purchase.shares == 1000
    assert purchase.price_per_share == 25.5
    assert purchase.transaction_value == 25_500
    assert purchase.shares_owned_after == 5000
    assert purchase.ownership_nature == "Direct"
    assert purchase.plan_10b5_1 is True
    assert option.derivative is True
    assert option.transaction_type == "Option exercise or conversion"


def test_fetch_activity_tolerates_one_bad_filing():
    class StubClient:
        def filing_document(self, url: str, *, refresh: bool = False) -> str:
            if "000002" in url:
                raise SECClientError("temporary failure")
            return OWNERSHIP_XML

    result = fetch_insider_activity(StubClient(), submissions(), max_filings=2)

    assert result.filings_reviewed == 2
    assert len(result.transactions) == 2
    assert len(result.failures) == 1


def test_fetch_activity_validates_limit():
    class StubClient:
        pass

    try:
        fetch_insider_activity(StubClient(), submissions(), max_filings=0)
    except ValueError as exc:
        assert "at least 1" in str(exc)
    else:
        raise AssertionError("Expected max_filings validation")
