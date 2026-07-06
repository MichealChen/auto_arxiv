from datetime import datetime, timezone

from auto_arxiv.arxiv_client import Paper
from auto_arxiv.config import AppConfig, OutputConfig, ProfileConfig, SearchConfig
from auto_arxiv.scoring import ScoredPaper
from auto_arxiv.workflow import _select_with_followed_authors


NOW = datetime(2026, 7, 6, tzinfo=timezone.utc)


def test_followed_author_selection_does_not_occupy_limit(tmp_path):
    followed = _paper(
        arxiv_id="2607.02427",
        title="Squeezed cat states",
        abstract="Non-Gaussian quantum states are useful.",
        authors=("Jens Eisert",),
    )
    regular = _paper(
        arxiv_id="2607.00001",
        title="Quantum Information Protocols",
        abstract="Quantum information protocol.",
        authors=("Ada Lovelace",),
    )
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
            min_score=2.0,
            directory=tmp_path / "recommendations",
            data_directory=tmp_path / "data",
            download_directory=tmp_path / "downloads",
        ),
    )
    ranked = [
        ScoredPaper(followed, 2.0, ("Quantum Information",), ("Matched arXiv category: quant-ph",)),
        ScoredPaper(regular, 8.0, ("Quantum Information",), ("Matched keyword",)),
    ]

    selected = _select_with_followed_authors([followed, regular], ranked, config, NOW)

    assert [item.paper.arxiv_id for item in selected] == ["2607.02427", "2607.00001"]


def _paper(arxiv_id, title, abstract, authors):
    return Paper(
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        authors=authors,
        categories=("quant-ph",),
        published=NOW,
        updated=NOW,
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
    )
