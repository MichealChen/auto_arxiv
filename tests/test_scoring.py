from datetime import datetime, timezone

from auto_arxiv.arxiv_client import Paper
from auto_arxiv.config import AppConfig, OutputConfig, ProfileConfig, SearchConfig
from auto_arxiv.scoring import followed_author_recommendations, rank_papers, score_paper


NOW = datetime(2026, 7, 6, tzinfo=timezone.utc)


def test_score_paper_matches_title_keywords_and_category(tmp_path):
    config = _config(tmp_path)
    paper = _paper(
        title="Agentic Retrieval Augmented Generation for Planning",
        abstract="A method for large language model reasoning.",
        categories=("cs.AI",),
    )

    scored = score_paper(paper, config=config, now=NOW)

    assert scored.score >= 8.0
    assert "retrieval augmented generation" in scored.matched_keywords
    assert "reasoning" in scored.matched_keywords


def test_rank_papers_filters_excluded_keywords(tmp_path):
    config = _config(tmp_path)
    paper = _paper(
        title="A position paper about agent systems",
        abstract="This paper mentions retrieval augmented generation.",
        categories=("cs.AI",),
    )

    assert rank_papers([paper], config=config, now=NOW) == []


def test_rank_papers_uses_latest_feed_activity_as_cutoff_anchor(tmp_path):
    config = _config(tmp_path)
    paper = _paper(
        title="Retrieval Augmented Generation for Agents",
        abstract="Reasoning with language models.",
        categories=("cs.AI",),
    )
    later_local_clock = datetime(2026, 7, 10, tzinfo=timezone.utc)

    ranked = rank_papers([paper], config=config, now=later_local_clock)

    assert len(ranked) == 1


def test_rank_papers_can_disable_time_filter_for_historical_date(tmp_path):
    config = _config(tmp_path)
    paper = _paper(
        title="Retrieval Augmented Generation for Agents",
        abstract="Reasoning with language models.",
        categories=("cs.AI",),
    )
    historical_reference = datetime(2022, 3, 3, tzinfo=timezone.utc)

    ranked = rank_papers(
        [paper],
        config=config,
        now=historical_reference,
        apply_time_filter=False,
        reference_time=historical_reference,
        include_recency_bonus=False,
    )

    assert len(ranked) == 1
    assert all("Recently updated" not in reason for reason in ranked[0].recommendation_reasons)


def test_followed_author_recommendations_match_author_category_and_keyword(tmp_path):
    config = AppConfig(
        profile=ProfileConfig(
            name="Test",
            categories=("cs.AI",),
            keywords=("reasoning",),
            exclude_keywords=(),
            followed_authors=("Ada Lovelace",),
        ),
        search=SearchConfig(days_back=2, max_results=10),
        output=OutputConfig(
            limit=1,
            min_score=2.0,
            directory=tmp_path / "recommendations",
            data_directory=tmp_path / "data",
            download_directory=tmp_path / "downloads",
        ),
    )
    paper = _paper(
        title="Reasoning Systems",
        abstract="A reasoning method.",
        categories=("cs.AI",),
    )

    followed = followed_author_recommendations([paper], config=config, now=NOW)

    assert len(followed) == 1
    assert any(reason.startswith("Matched followed author") for reason in followed[0].recommendation_reasons)


def test_followed_author_recommendations_use_keyword_tokens_without_min_score(tmp_path):
    config = AppConfig(
        profile=ProfileConfig(
            name="Test",
            categories=("quant-ph",),
            keywords=("Quantum Information",),
            exclude_keywords=(),
            followed_authors=("Jens Eisert",),
        ),
        search=SearchConfig(days_back=2, max_results=10),
        output=OutputConfig(
            limit=1,
            min_score=99.0,
            directory=tmp_path / "recommendations",
            data_directory=tmp_path / "data",
            download_directory=tmp_path / "downloads",
        ),
    )
    paper = _paper(
        title="Optimal stellar rank approximation of squeezed cat states",
        abstract="Non-Gaussian quantum states are useful resources.",
        categories=("quant-ph",),
        authors=("Julian K. Nauth", "Jens Eisert"),
    )

    followed = followed_author_recommendations([paper], config=config, now=NOW)

    assert len(followed) == 1
    assert followed[0].matched_keywords == ("Quantum Information",)
    assert followed[0].recommendation_reasons[0] == "Matched followed author: Jens Eisert"


def _config(tmp_path):
    return AppConfig(
        profile=ProfileConfig(
            name="Test",
            categories=("cs.AI",),
            keywords=("retrieval augmented generation", "reasoning"),
            exclude_keywords=("position paper",),
            followed_authors=(),
        ),
        search=SearchConfig(days_back=2, max_results=10),
        output=OutputConfig(
            limit=5,
            min_score=2.0,
            directory=tmp_path / "recommendations",
            data_directory=tmp_path / "data",
            download_directory=tmp_path / "downloads",
        ),
    )


def _paper(title, abstract, categories, authors=("Ada Lovelace",)):
    return Paper(
        arxiv_id="2607.00001",
        title=title,
        abstract=abstract,
        authors=authors,
        categories=categories,
        published=NOW,
        updated=NOW,
        abs_url="https://arxiv.org/abs/2607.00001",
        pdf_url="https://arxiv.org/pdf/2607.00001",
    )
