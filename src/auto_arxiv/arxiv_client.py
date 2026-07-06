from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import re
import xml.etree.ElementTree as ET


ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
ARXIV_API_URL = "https://export.arxiv.org/api/query"


@dataclass(frozen=True)
class Paper:
    arxiv_id: str
    title: str
    abstract: str
    authors: tuple[str, ...]
    categories: tuple[str, ...]
    published: datetime
    updated: datetime
    abs_url: str
    pdf_url: str


def fetch_recent_papers(
    categories: Iterable[str],
    keywords: Iterable[str],
    max_results: int,
) -> list[Paper]:
    query = _build_query(categories, keywords)
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "lastUpdatedDate",
        "sortOrder": "descending",
    }
    url = f"{ARXIV_API_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "auto-arxiv/0.1"})

    with urlopen(request, timeout=30) as response:
        xml_body = response.read()

    return parse_arxiv_feed(xml_body)


def fetch_papers_for_date(
    categories: Iterable[str],
    keywords: Iterable[str],
    target_date: date,
    max_results: int,
    lookback_days: int = 7,
) -> list[Paper]:
    date_filter = _submitted_date_window(target_date, lookback_days)
    query = _build_query(categories, keywords, extra_terms=[date_filter])
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = f"{ARXIV_API_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "auto-arxiv/0.1"})

    with urlopen(request, timeout=30) as response:
        xml_body = response.read()

    return parse_arxiv_feed(xml_body)


def fetch_followed_author_papers(
    categories: Iterable[str],
    followed_authors: Iterable[str],
    max_results: int,
    *,
    target_date: date | None = None,
    lookback_days: int = 7,
) -> list[Paper]:
    authors = [author.strip() for author in followed_authors if author.strip()]
    if not authors:
        return []

    filters = []
    if target_date is not None:
        filters.append(_submitted_date_window(target_date, lookback_days))
    query = _build_author_query(categories, authors, filters)
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = f"{ARXIV_API_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "auto-arxiv/0.1"})

    with urlopen(request, timeout=30) as response:
        xml_body = response.read()

    return parse_arxiv_feed(xml_body)


def _submitted_date_window(target_date: date, lookback_days: int) -> str:
    lookback_days = max(0, lookback_days)
    start_date = target_date - timedelta(days=lookback_days)
    return f"submittedDate:[{start_date:%Y%m%d}0000 TO {target_date:%Y%m%d}2359]"


def parse_arxiv_feed(xml_body: bytes) -> list[Paper]:
    root = ET.fromstring(xml_body)
    papers: list[Paper] = []

    for entry in root.findall("atom:entry", ATOM_NS):
        title = _clean_text(_required_text(entry, "atom:title"))
        abstract = _clean_text(_required_text(entry, "atom:summary"))
        arxiv_id = _extract_arxiv_id(_required_text(entry, "atom:id"))
        authors = tuple(
            _clean_text(name.text or "")
            for name in entry.findall("atom:author/atom:name", ATOM_NS)
        )
        categories = tuple(
            category.attrib["term"]
            for category in entry.findall("atom:category", ATOM_NS)
            if "term" in category.attrib
        )

        abs_url = _required_text(entry, "atom:id")
        pdf_url = ""
        for link in entry.findall("atom:link", ATOM_NS):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href", "")
                break

        papers.append(
            Paper(
                arxiv_id=arxiv_id,
                title=title,
                abstract=abstract,
                authors=authors,
                categories=categories,
                published=_parse_arxiv_datetime(_required_text(entry, "atom:published")),
                updated=_parse_arxiv_datetime(_required_text(entry, "atom:updated")),
                abs_url=abs_url,
                pdf_url=pdf_url,
            )
        )

    return papers


def _build_query(
    categories: Iterable[str],
    keywords: Iterable[str],
    extra_terms: Iterable[str] = (),
) -> str:
    category_terms = [f"cat:{category.strip()}" for category in categories if category.strip()]
    keyword_terms = [f'all:"{keyword.strip()}"' for keyword in keywords if keyword.strip()]
    filters = [term for term in extra_terms if term]

    if category_terms:
        base = "(" + " OR ".join(category_terms) + ")"
    elif keyword_terms:
        base = "(" + " OR ".join(keyword_terms) + ")"
    else:
        base = "all:*"

    if filters:
        return f"{base} AND " + " AND ".join(filters)
    return base


def _build_author_query(
    categories: Iterable[str],
    authors: Iterable[str],
    extra_terms: Iterable[str] = (),
) -> str:
    category_terms = [f"cat:{category.strip()}" for category in categories if category.strip()]
    author_terms = [f'au:"{author.strip()}"' for author in authors if author.strip()]
    filters = [term for term in extra_terms if term]

    if author_terms:
        base = "(" + " OR ".join(author_terms) + ")"
    else:
        base = "all:*"
    if category_terms:
        base = "(" + " OR ".join(category_terms) + ") AND " + base
    if filters:
        return f"{base} AND " + " AND ".join(filters)
    return base


def _required_text(entry: ET.Element, path: str) -> str:
    node = entry.find(path, ATOM_NS)
    if node is None or node.text is None:
        raise ValueError(f"arXiv feed entry is missing {path}")
    return node.text


def _parse_arxiv_datetime(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _extract_arxiv_id(value: str) -> str:
    return value.rstrip("/").split("/")[-1]
