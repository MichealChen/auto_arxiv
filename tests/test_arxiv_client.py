from datetime import date

from auto_arxiv.arxiv_client import _build_author_query, _submitted_date_window


def test_submitted_date_window_looks_back_from_target_date():
    assert (
        _submitted_date_window(date(2026, 7, 6), lookback_days=7)
        == "submittedDate:[202606290000 TO 202607062359]"
    )


def test_submitted_date_window_can_match_exact_date():
    assert (
        _submitted_date_window(date(2026, 7, 6), lookback_days=0)
        == "submittedDate:[202607060000 TO 202607062359]"
    )


def test_build_author_query_combines_categories_authors_and_date_filter():
    query = _build_author_query(
        ["quant-ph", "cond-mat.str-el"],
        ["Jens Eisert"],
        ["submittedDate:[202607020000 TO 202607022359]"],
    )

    assert "cat:quant-ph" in query
    assert 'au:"Jens Eisert"' in query
    assert "submittedDate:[202607020000 TO 202607022359]" in query
