import pandas as pd

from filinglens.sec.csv_export import safe_csv


def test_insider_csv_preserves_numbers_and_neutralizes_formulas():
    frame = pd.DataFrame({"name": ["=HYPERLINK(\"https://example.com\")", "  @SUM(1)", "Ordinary"],
                          "shares": [100, 200, 300]})
    exported = safe_csv(frame)
    assert "'=HYPERLINK" in exported
    assert "'  @SUM(1)" in exported
    assert "Ordinary,300" in exported
