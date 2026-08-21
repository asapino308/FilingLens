# Verified example analysis

This file records an integration snapshot from 2026-08-20. It is not investment advice and is not a substitute for the original filings.

## Companies exercised

- AAPL: five annual periods from 2021–2025; latest tested 10-K filed 2025-10-31
- MSFT: five annual periods from 2022–2026; latest tested 10-K filed 2026-07-29

Both companies completed ticker lookup, CIK normalization, Company Facts mapping, statements, ratios, unusual-change screening, 10-K retrieval, parsing, chunking, and TF-IDF retrieval.

## Latest normalized observations

After regression-fixing comparative-period grouping, FilingLens selected AAPL FY2025 revenue of $416.161 billion from `RevenueFromContractWithCustomerExcludingAssessedTax` and long-term debt of $90.678 billion from `LongTermDebt`. For MSFT FY2026 it selected revenue of $331.839 billion from the same revenue concept and long-term debt of $40.294 billion from `LongTermDebt`.

These values are examples of selected SEC facts, not hard-coded application data. The UI exposes their accessions, dates, periods, units, and concepts.

## Retrieval snapshot

For “What factors affected revenue and operating margin?”, the top AAPL result came from Item 7, Management's Discussion and Analysis. MSFT's top three results came from Item 7. Section-aware parsing produced 76 AAPL chunks and 122 MSFT chunks in the tested filings.

## Local Q&A snapshot

The discovered model ID was `google/gemma-4-12b`. A live AAPL net-sales-driver question returned a sourced answer referencing product categories and geographic segments. Four source passages were displayed. A deliberately unsupported request about a private CEO/board conversation was rejected because the filing evidence did not contain that information.

## Analyst brief snapshot

The final corrected-metrics brief contained all required sections: company overview, financial trend summary, key year-over-year changes, anomaly flags, management commentary, major risk factors, liquidity/capital structure, and questions for further research. It contained 14 source markers and the educational-use disclaimer. Generation took 177.5 seconds at roughly 7.66 tokens per second on the tested local model and hardware.
