from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path

from .arxiv_client import fetch_followed_author_papers, fetch_papers_for_date, fetch_recent_papers
from .config import AppConfig
from .render import write_markdown_report
from .scoring import ScoredPaper, followed_author_recommendations, rank_papers
from .store import write_recommendation_data


@dataclass(frozen=True)
class GenerationResult:
    profile_name: str
    fetched_count: int
    ranked_count: int
    selected_count: int
    markdown_path: Path
    data_path: Path
    selected: list[ScoredPaper]


def generate_recommendations(
    config: AppConfig,
    generated_at: datetime | None = None,
) -> GenerationResult:
    now = generated_at or datetime.now(timezone.utc)
    followed_lookback_days = max(config.search.days_back, 7)
    papers = fetch_recent_papers(
        categories=config.profile.categories,
        keywords=config.profile.keywords,
        max_results=config.search.max_results,
    )
    papers = _merge_unique_papers(
        papers,
        fetch_followed_author_papers(
            categories=config.profile.categories,
            followed_authors=config.profile.followed_authors,
            max_results=config.search.max_results,
            target_date=now.date(),
            lookback_days=followed_lookback_days,
        ),
    )
    ranked = rank_papers(papers, config=config, now=now)
    selected = _select_with_followed_authors(
        papers,
        ranked,
        config,
        now,
        followed_start_date=now.date().fromordinal(now.date().toordinal() - followed_lookback_days),
        followed_end_date=now.date(),
    )
    markdown_path = write_markdown_report(selected, config=config, generated_at=now)
    data_path = write_recommendation_data(
        all_papers=papers,
        selected_papers=selected,
        ranked_count=len(ranked),
        fetched_count=len(papers),
        config=config,
        generated_at=now,
    )

    return GenerationResult(
        profile_name=config.profile.name,
        fetched_count=len(papers),
        ranked_count=len(ranked),
        selected_count=len(selected),
        markdown_path=markdown_path,
        data_path=data_path,
        selected=selected,
    )


def generate_recommendations_for_date(
    config: AppConfig,
    target_date: date,
) -> GenerationResult:
    generated_at = datetime.combine(target_date, time(hour=12), tzinfo=timezone.utc)
    papers = fetch_papers_for_date(
        categories=config.profile.categories,
        keywords=config.profile.keywords,
        target_date=target_date,
        max_results=config.search.max_results,
        lookback_days=max(config.search.days_back, 7),
    )
    papers = _merge_unique_papers(
        papers,
        fetch_followed_author_papers(
            categories=config.profile.categories,
            followed_authors=config.profile.followed_authors,
            max_results=config.search.max_results,
            target_date=target_date,
            lookback_days=0,
        ),
    )
    ranked = rank_papers(
        papers,
        config=config,
        now=generated_at,
        apply_time_filter=False,
        reference_time=generated_at,
        include_recency_bonus=False,
    )
    selected = _select_with_followed_authors(
        papers,
        ranked,
        config,
        generated_at,
        followed_start_date=target_date,
        followed_end_date=target_date,
    )
    markdown_path = write_markdown_report(selected, config=config, generated_at=generated_at)
    data_path = write_recommendation_data(
        all_papers=papers,
        selected_papers=selected,
        ranked_count=len(ranked),
        fetched_count=len(papers),
        config=config,
        generated_at=generated_at,
    )

    return GenerationResult(
        profile_name=config.profile.name,
        fetched_count=len(papers),
        ranked_count=len(ranked),
        selected_count=len(selected),
        markdown_path=markdown_path,
        data_path=data_path,
        selected=selected,
    )


def _select_with_followed_authors(
    papers,
    ranked: list[ScoredPaper],
    config: AppConfig,
    now: datetime,
    *,
    followed_start_date: date | None = None,
    followed_end_date: date | None = None,
) -> list[ScoredPaper]:
    extras = followed_author_recommendations(
        papers,
        config=config,
        now=now,
        start_date=followed_start_date,
        end_date=followed_end_date,
    )
    extra_ids = {item.paper.arxiv_id for item in extras}
    regular = [item for item in ranked if item.paper.arxiv_id not in extra_ids][: config.output.limit]
    return extras + regular


def _merge_unique_papers(*paper_groups) -> list:
    merged = {}
    for papers in paper_groups:
        for paper in papers:
            merged.setdefault(paper.arxiv_id, paper)
    return list(merged.values())
