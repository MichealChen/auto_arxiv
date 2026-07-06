from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re

from .arxiv_client import Paper
from .config import AppConfig


@dataclass(frozen=True)
class ScoredPaper:
    paper: Paper
    score: float
    matched_keywords: tuple[str, ...]
    recommendation_reasons: tuple[str, ...]


def rank_papers(
    papers: list[Paper],
    config: AppConfig,
    now: datetime,
    *,
    apply_time_filter: bool = True,
    reference_time: datetime | None = None,
    include_recency_bonus: bool = True,
) -> list[ScoredPaper]:
    reference_time = reference_time or _latest_activity(papers) or now
    cutoff = reference_time - timedelta(days=config.search.days_back)
    scored: list[ScoredPaper] = []

    for paper in papers:
        if apply_time_filter and max(paper.published, paper.updated) < cutoff:
            continue
        if _contains_any(f"{paper.title} {paper.abstract}", config.profile.exclude_keywords):
            continue

        item = score_paper(
            paper,
            config=config,
            now=reference_time,
            include_recency_bonus=include_recency_bonus,
        )
        if item.score >= config.output.min_score:
            scored.append(item)

    return sorted(
        scored,
        key=lambda item: (item.score, item.paper.updated, item.paper.published),
        reverse=True,
    )


def followed_author_recommendations(
    papers: list[Paper],
    config: AppConfig,
    now: datetime,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[ScoredPaper]:
    followed = tuple(author.lower() for author in config.profile.followed_authors)
    if not followed:
        return []

    results: list[ScoredPaper] = []
    preferred_categories = set(config.profile.categories)
    for paper in papers:
        paper_date = paper.published.date()
        if start_date is not None and paper_date < start_date:
            continue
        if end_date is not None and paper_date > end_date:
            continue
        if not any(
            followed_name in author.lower()
            for followed_name in followed
            for author in paper.authors
        ):
            continue
        if preferred_categories and not preferred_categories.intersection(paper.categories):
            continue
        item = score_paper(paper, config=config, now=now, include_recency_bonus=False)
        matched_keywords = _followed_author_keyword_matches(paper, config.profile.keywords)
        if not matched_keywords:
            continue
        reasons = (
            f"Matched followed author: {_matched_followed_author_name(paper, followed)}",
            f"Matched followed-author keyword: {', '.join(matched_keywords)}",
        ) + tuple(
            reason
            for reason in item.recommendation_reasons
            if reason.startswith("Matched arXiv category")
        )
        results.append(
            ScoredPaper(
                paper=paper,
                score=item.score,
                matched_keywords=matched_keywords,
                recommendation_reasons=reasons,
            )
        )

    return sorted(results, key=lambda item: item.score, reverse=True)


def score_paper(
    paper: Paper,
    config: AppConfig,
    now: datetime,
    *,
    include_recency_bonus: bool = True,
) -> ScoredPaper:
    title = paper.title.lower()
    abstract = paper.abstract.lower()
    matched_keywords: list[str] = []
    reasons: list[str] = []
    score = 0.0

    preferred_categories = set(config.profile.categories)
    category_hits = preferred_categories.intersection(paper.categories)
    score += 2.0 * len(category_hits)
    for category in sorted(category_hits):
        reasons.append(f"Matched arXiv category: {category}")

    for keyword in config.profile.keywords:
        needle = keyword.lower()
        title_hits = _phrase_count(title, needle)
        abstract_hits = _phrase_count(abstract, needle)
        if title_hits or abstract_hits:
            matched_keywords.append(keyword)
            locations = []
            if title_hits:
                locations.append("title")
            if abstract_hits:
                locations.append("abstract")
            reasons.append(f"Matched keyword '{keyword}' in {' and '.join(locations)}")
        score += min(title_hits, 2) * 3.0
        score += min(abstract_hits, 3) * 1.5

    if include_recency_bonus:
        age_hours = max((now - paper.updated).total_seconds() / 3600, 0)
        if age_hours <= 24:
            score += 2.0
            reasons.append("Recently updated within 24 hours")
        elif age_hours <= 48:
            score += 1.0
            reasons.append("Recently updated within 48 hours")

    return ScoredPaper(
        paper=paper,
        score=score,
        matched_keywords=tuple(matched_keywords),
        recommendation_reasons=tuple(reasons),
    )


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    haystack = text.lower()
    return any(_phrase_count(haystack, phrase.lower()) > 0 for phrase in phrases)


def _followed_author_keyword_matches(paper: Paper, keywords: tuple[str, ...]) -> tuple[str, ...]:
    text = f"{paper.title} {paper.abstract}".lower()
    matched: list[str] = []
    for keyword in keywords:
        keyword = keyword.strip()
        if not keyword:
            continue
        needle = keyword.lower()
        if _phrase_count(text, needle) > 0 or any(_phrase_count(text, token) > 0 for token in _keyword_tokens(needle)):
            matched.append(keyword)
    return tuple(matched)


def _keyword_tokens(keyword: str) -> tuple[str, ...]:
    ignored = {"and", "for", "the", "with", "from", "into", "onto", "model", "models"}
    tokens = re.findall(r"[a-z0-9][a-z0-9-]{3,}", keyword.lower())
    return tuple(token for token in tokens if token not in ignored)


def _matched_followed_author_name(paper: Paper, followed: tuple[str, ...]) -> str:
    for followed_name in followed:
        for author in paper.authors:
            if followed_name in author.lower():
                return author
    return "N/A"


def _phrase_count(text: str, phrase: str) -> int:
    if not phrase:
        return 0
    pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
    return len(re.findall(pattern, text))


def _latest_activity(papers: list[Paper]) -> datetime | None:
    if not papers:
        return None
    return max(max(paper.published, paper.updated) for paper in papers)
