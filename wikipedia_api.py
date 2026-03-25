from __future__ import annotations

import html
import json
import logging
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import wikipediaapi

LOGGER = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "uz"
MAX_SUMMARY_LENGTH = 500
MAX_CONTENT_LENGTH = 2000
MAX_SEARCH_RESULTS = 8
REQUEST_TIMEOUT = 10
REQUEST_RETRIES = 3
REQUEST_RETRY_DELAY = 1.0
WIKIPEDIA_HEADERS = {
    "User-Agent": "WikiAIBot/2.0 (educational Telegram bot; contact: local-development)"
}


def _build_client(language: str) -> wikipediaapi.Wikipedia:
    return wikipediaapi.Wikipedia(
        language=language,
        headers=WIKIPEDIA_HEADERS,
        extract_format=wikipediaapi.ExtractFormat.WIKI,
    )


def _request_json(url: str) -> dict[str, Any]:
    last_error: Exception | None = None

    for attempt in range(1, REQUEST_RETRIES + 1):
        request = Request(url, headers=WIKIPEDIA_HEADERS)
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            last_error = exc
            should_retry = exc.code in {408, 409, 425, 429, 500, 502, 503, 504}
            if exc.code == 404:
                raise
            if not should_retry or attempt == REQUEST_RETRIES:
                raise
            LOGGER.warning(
                "Wikipedia so'rovi HTTP xatolik bilan tugadi. Qayta urinish %s/%s: %s",
                attempt,
                REQUEST_RETRIES,
                exc,
            )
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == REQUEST_RETRIES:
                raise
            LOGGER.warning(
                "Wikipedia so'rovi vaqtincha bajarilmadi. Qayta urinish %s/%s: %s",
                attempt,
                REQUEST_RETRIES,
                exc,
            )

        time.sleep(REQUEST_RETRY_DELAY * attempt)

    if last_error:
        raise last_error
    raise RuntimeError("Wikipedia so'rovi bajarilmadi.")


def _article_url(title: str, language: str) -> str:
    return f"https://{language}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"


def _clean_snippet(snippet: str) -> str:
    clean = html.unescape(re.sub(r"<[^>]+>", "", snippet or ""))
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) <= 180:
        return clean
    return f"{clean[:177].rstrip()}..."


def _search_candidates(query: str, language: str) -> list[dict[str, Any]]:
    params = urlencode(
        {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": MAX_SEARCH_RESULTS,
            "srprop": "snippet",
            "format": "json",
            "utf8": 1,
        }
    )
    url = f"https://{language}.wikipedia.org/w/api.php?{params}"
    payload = _request_json(url)
    items = payload.get("query", {}).get("search", [])

    results: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        title = (item.get("title") or "").strip()
        if not title:
            continue

        results.append(
            {
                "title": title,
                "lang": language,
                "snippet": _clean_snippet(item.get("snippet", "")),
                "url": _article_url(title, language),
                "search_rank": index,
            }
        )
    return results


def _normalized_query(query: str) -> str:
    return re.sub(r"\s+", " ", (query or "").strip())


def _generate_query_variants(query: str) -> list[str]:
    normalized = _normalized_query(query)
    variants: list[str] = []

    def add_variant(value: str) -> None:
        cleaned = _normalized_query(value)
        if cleaned and cleaned not in variants:
            variants.append(cleaned)

    add_variant(normalized)

    words = normalized.split()
    if len(words) > 1:
        add_variant(f'"{normalized}"')

    punctuation_light = re.sub(r"[^\w\s'\-]", " ", normalized)
    add_variant(punctuation_light)

    if len(words) >= 5:
        add_variant(" ".join(words[:5]))
    if len(words) >= 3:
        add_variant(" ".join(words[:3]))

    return variants


def _rank_candidates(query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_query = query.casefold()
    ranked: list[dict[str, Any]] = []

    for candidate in candidates:
        title = candidate["title"]
        normalized_title = title.casefold()
        starts_with_query = normalized_title.startswith(normalized_query)
        exact_match = normalized_title == normalized_query

        ranked.append(
            {
                **candidate,
                "exact_match": exact_match,
                "starts_with_query": starts_with_query,
            }
        )

    ranked.sort(
        key=lambda item: (
            item["exact_match"],
            item["starts_with_query"],
            -item["search_rank"],
        ),
        reverse=True,
    )
    return ranked


def _page_to_result(page: wikipediaapi.WikipediaPage, language: str) -> dict[str, str]:
    summary = (page.summary or "").strip()
    content = (page.text or "").strip()

    if not summary:
        summary = content[:MAX_SUMMARY_LENGTH]

    return {
        "title": page.title,
        "url": page.fullurl,
        "summary": summary[:MAX_SUMMARY_LENGTH],
        "content": content[:MAX_CONTENT_LENGTH],
        "language": language,
    }


def get_page_by_title(title: str, lang: str = DEFAULT_LANGUAGE) -> dict[str, str] | None:
    page_title = (title or "").strip()
    if not page_title:
        return None

    try:
        page = _build_client(lang).page(page_title)
        if not page.exists():
            return None
    except Exception as exc:
        LOGGER.warning("Maqola yuklashda muammo: %s", exc)
        return None

    return _page_to_result(page, lang)


def search_wikipedia(query: str, lang: str = DEFAULT_LANGUAGE) -> dict[str, Any]:
    """
    Wikipedia'dan tanlangan tildagi mavzuga oid maqolalarni qidiradi.
    Qaytadi: {'options': [...], 'language': 'uz'} yoki {'error': ...}
    """
    search_query = _normalized_query(query)
    if not search_query:
        return {"error": "empty_query"}

    language = (lang or DEFAULT_LANGUAGE).strip().lower()

    try:
        for variant in _generate_query_variants(search_query):
            candidates = _search_candidates(variant, language)
            if candidates:
                return {
                    "options": _rank_candidates(search_query, candidates),
                    "language": language,
                }

        exact_page = get_page_by_title(search_query, language)
        if exact_page:
            return {
                "options": [
                    {
                        "title": exact_page["title"],
                        "lang": language,
                        "snippet": exact_page["summary"][:180],
                        "url": exact_page["url"],
                        "search_rank": 0,
                        "exact_match": True,
                        "starts_with_query": True,
                    }
                ],
                "language": language,
            }

        return {"error": "not_found"}

    except (HTTPError, URLError) as exc:
        LOGGER.warning("Wikipedia tarmoq xatoligi: %s", exc)
        return {"error": "network_error"}
    except Exception as exc:
        LOGGER.exception("Wikipedia qidiruvida kutilmagan xatolik")
        return {"error": str(exc)}


def search_with_language(query: str, lang: str = DEFAULT_LANGUAGE) -> dict[str, Any]:
    """Berilgan tilda mashhur maqolalarni qidirish."""
    return search_wikipedia(query, lang=lang)
