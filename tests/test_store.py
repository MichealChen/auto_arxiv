from datetime import datetime, timezone

from auto_arxiv.arxiv_client import Paper
from auto_arxiv.config import AppConfig, OutputConfig, ProfileConfig, SearchConfig
from auto_arxiv.scoring import ScoredPaper
from auto_arxiv.store import (
    load_history,
    load_latest_recommendations,
    load_reading_list,
    load_user_state,
    update_user_state,
    write_recommendation_data,
)


NOW = datetime(2026, 7, 6, 8, 0, tzinfo=timezone.utc)


def test_write_recommendation_data_creates_latest_daily_history_and_papers(tmp_path):
    config = AppConfig(
        profile=ProfileConfig(
            name="Test Radar",
            categories=("cs.AI",),
            keywords=("agent",),
            exclude_keywords=(),
            followed_authors=(),
        ),
        search=SearchConfig(days_back=2, max_results=20),
        output=OutputConfig(
            limit=10,
            min_score=2.0,
            directory=tmp_path / "recommendations",
            data_directory=tmp_path / "data",
            download_directory=tmp_path / "downloads",
        ),
    )
    paper = Paper(
        arxiv_id="2607.00001v1",
        title="Agent Systems",
        abstract="A paper about agents.",
        authors=("Ada Lovelace",),
        categories=("cs.AI",),
        published=NOW,
        updated=NOW,
        abs_url="https://arxiv.org/abs/2607.00001v1",
        pdf_url="https://arxiv.org/pdf/2607.00001v1",
    )
    scored = ScoredPaper(
        paper=paper,
        score=7.5,
        matched_keywords=("agent",),
        recommendation_reasons=("Matched keyword 'agent' in title",),
    )

    latest_path = write_recommendation_data(
        all_papers=[paper],
        selected_papers=[scored],
        ranked_count=1,
        fetched_count=1,
        config=config,
        generated_at=NOW,
    )

    latest = load_latest_recommendations(config.output.data_directory)
    history = load_history(config.output.data_directory)

    assert latest_path == tmp_path / "data" / "recommendations.json"
    assert latest["papers"][0]["arxiv_id"] == "2607.00001v1"
    assert latest["papers"][0]["recommendation_reasons"]
    assert (tmp_path / "data" / "daily" / "2026-07-06.json").exists()
    assert (tmp_path / "data" / "papers.json").exists()
    assert history["dates"][0]["date"] == "2026-07-06"

    update_user_state(
        config.output.data_directory,
        "2607.00001v1",
        {"reading_list": True},
    )
    reading_list = load_reading_list(config.output.data_directory)
    assert reading_list[0]["arxiv_id"] == "2607.00001v1"


def test_update_user_state_persists_paper_flags(tmp_path):
    data_dir = tmp_path / "data"

    state = update_user_state(
        data_dir,
        arxiv_id="2607.00001v1",
        values={"favorite": True, "read": True, "ignored": False, "reading_list": True},
    )

    assert state["papers"]["2607.00001v1"]["favorite"] is True
    assert state["papers"]["2607.00001v1"]["read"] is True
    assert load_user_state(data_dir)["papers"]["2607.00001v1"]["ignored"] is False
    assert load_user_state(data_dir)["papers"]["2607.00001v1"]["reading_list"] is True
    update_user_state(data_dir, "2607.00001v1", {"note": "Important paper."})
    assert load_user_state(data_dir)["papers"]["2607.00001v1"]["note"] == "Important paper."
