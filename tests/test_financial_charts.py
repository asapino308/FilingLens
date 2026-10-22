import pandas as pd

from filinglens.ui.charts import comparison_chart


def test_comparison_chart_keeps_units_and_missing_years_distinct():
    frame = pd.DataFrame(
        {"revenue_growth": [0.12, None, 0.08], "gross_margin": [0.3, 0.32, 0.34]},
        index=pd.Index([2022, 2023, 2024], name="fiscal_year"),
    )
    figure = comparison_chart(
        frame, ["revenue_growth", "gross_margin"], unit="percent",
        labels={"revenue_growth": "Revenue growth", "gross_margin": "Gross margin"},
    )

    assert len(figure.data) == 2
    assert figure.data[0].name == "Revenue growth"
    assert figure.data[0].y[0] == 12.0
    assert pd.isna(figure.data[0].y[1])
    assert figure.data[0].y[2] == 8.0
    assert figure.data[0].connectgaps is False
    assert figure.data[1].y[1] == 32.0
    assert figure.layout.yaxis.title.text == "Percent"
