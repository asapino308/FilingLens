from filinglens.evaluation.qa_eval import (
    EVALUATION_QUESTIONS,
    citation_present,
    reports_insufficient_evidence,
)
from filinglens.reporting.export import markdown_to_html


def test_evaluation_dataset_size_and_unsupported_cases():
    assert 15 <= len(EVALUATION_QUESTIONS) <= 25
    assert sum(question.deliberately_unsupported for question in EVALUATION_QUESTIONS) >= 2


def test_evaluation_compliance_checks():
    assert citation_present("Claim [Source 2]")
    assert reports_insufficient_evidence("The supplied evidence is insufficient.")


def test_html_export_escapes_untrusted_markup():
    result = markdown_to_html("# Brief\n## Risk\n<script>alert(1)</script>")
    assert "<h1>Brief</h1>" in result
    assert "<script>" not in result
    assert "&lt;script&gt;" in result

