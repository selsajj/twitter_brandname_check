"""
Check direct interactions between two X accounts:
  - Replies from A to B and B to A
  - Mentions of each other
  - Quote tweets between them

Uses TwitterAPI.io provider.
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests

BASE_URL = "https://api.twitterapi.io"
DELAY_BETWEEN_SEARCHES = 2.0  # seconds between each API call
MAX_RETRIES = 3               # retry on 429 up to this many times
RETRY_BACKOFF = 5.0           # extra seconds to wait per retry attempt


def _get_headers() -> dict:
    token = os.getenv("TWITTERAPI_IO_KEY", "")
    if not token:
        raise EnvironmentError("TWITTERAPI_IO_KEY is not set.")
    return {"X-API-Key": token, "Content-Type": "application/json"}


def _search(query: str, count: int = 10) -> list[dict]:
    """Run a search query with retry logic on 429s."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                f"{BASE_URL}/twitter/tweet/advanced_search",
                headers=_get_headers(),
                params={"query": query, "queryType": "Latest", "count": count},
                timeout=30,
            )
            if resp.status_code == 429:
                wait = RETRY_BACKOFF * attempt
                print(f"  ⏳ Rate limited — waiting {wait:.0f}s before retry {attempt}/{MAX_RETRIES}...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {}).get("tweets") or data.get("tweets") or []
        except requests.HTTPError as exc:
            print(f"  ⚠️  Search failed for '{query}': {exc}")
            return []
        except Exception as exc:
            print(f"  ⚠️  Search failed for '{query}': {exc}")
            return []
    print(f"  ⚠️  Giving up on '{query}' after {MAX_RETRIES} retries.")
    return []


def _normalise(t: dict, relationship: str) -> dict[str, Any]:
    author = t.get("author") or t.get("user") or {}
    return {
        "relationship":     relationship,
        "author_handle":    (author.get("userName") or author.get("screenName") or "").lower(),
        "author_name":      author.get("name"),
        "author_followers": author.get("followers") or author.get("followersCount"),
        "text":             t.get("text") or t.get("fullText", ""),
        "created_at":       t.get("createdAt") or t.get("created_at"),
        "like_count":       t.get("likeCount") or t.get("favoriteCount"),
        "retweet_count":    t.get("retweetCount") or t.get("retweet_count"),
        "reply_count":      t.get("replyCount") or t.get("reply_count"),
        "tweet_url":        t.get("url") or "",
    }


def check_interactions(
    handle_a: str,
    handle_b: str,
    max_results: int = 10,
) -> dict[str, Any]:
    """
    Find all interactions between handle_a and handle_b.
    Returns a structured result dict.
    """
    handle_a = handle_a.lower().lstrip("@")
    handle_b = handle_b.lower().lstrip("@")

    print(f"\n🔗 Checking interactions between @{handle_a} and @{handle_b}...\n")

    searches = [
        (f"from:{handle_a} @{handle_b}",   f"{handle_a}_to_{handle_b}"),
        (f"from:{handle_b} @{handle_a}",   f"{handle_b}_to_{handle_a}"),
        (f"from:{handle_a} url:{handle_b}", f"{handle_a}_quotes_{handle_b}"),
        (f"from:{handle_b} url:{handle_a}", f"{handle_b}_quotes_{handle_a}"),
        (f"@{handle_a} @{handle_b}",        "third_party_mentions_both"),
    ]

    all_interactions: list[dict] = []
    seen_texts: set[str] = set()

    for i, (query, relationship) in enumerate(searches):
        print(f"  🔎 {relationship}")
        if i > 0:
            time.sleep(DELAY_BETWEEN_SEARCHES)
        items = _search(query, count=max_results)
        for t in items:
            normalised = _normalise(t, relationship)
            key = normalised["text"].strip().lower()
            if key in seen_texts:
                continue
            seen_texts.add(key)
            all_interactions.append(normalised)

    grouped: dict[str, list[dict]] = {}
    for item in all_interactions:
        rel = item["relationship"]
        grouped.setdefault(rel, []).append(item)

    return {
        "handle_a":     handle_a,
        "handle_b":     handle_b,
        "total_found":  len(all_interactions),
        "interactions": grouped,
        "flat":         all_interactions,
    }
