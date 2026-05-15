"""
Check whether X (Twitter) handles exist using the Apify actor:
  logical_scrapers/x-twitter-user-profile-tweets-scraper

Runs checks concurrently using a thread pool to stay within free-tier limits.
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from apify_client import ApifyClient

ACTOR_ID = "logical_scrapers/x-twitter-user-profile-tweets-scraper"


def _get_client() -> ApifyClient:
    # Read token here (not at module level) so dotenv has already run
    token = os.getenv("APIFY_API_TOKEN", "")
    if not token:
        raise EnvironmentError(
            "APIFY_API_TOKEN is not set. "
            "Copy .env.example to .env and add your token."
        )
    return ApifyClient(token)


def check_single_handle(original: str, variant: str) -> dict[str, Any]:
    client = _get_client()
    result: dict[str, Any] = {
        "original_handle": original,
        "variant_handle": variant,
        "exists": False,
        "follower_count": None,
        "following_count": None,
        "tweet_count": None,
        "bio": None,
        "name": None,
        "created_at": None,
        "verified": False,
        "recent_tweets": [],
        "error": None,
    }

    try:
        run = client.actor(ACTOR_ID).call(
            run_input={
                "username": variant,
                "maxTweets": 5,
                "addUserInfo": True,
            },
            timeout_secs=120,
        )

        items = list(
            client.dataset(run["defaultDatasetId"]).iterate_items()
        )

        if not items:
            return result

        user = items[0]

        result["exists"] = True
        result["name"] = user.get("name") or user.get("full_name")
        result["follower_count"] = user.get("followersCount") or user.get("followers_count")
        result["following_count"] = user.get("friendsCount") or user.get("friends_count")
        result["tweet_count"] = user.get("statusesCount") or user.get("statuses_count")
        result["bio"] = user.get("description")
        result["created_at"] = user.get("createdAt") or user.get("created_at")
        result["verified"] = user.get("verified", False)

        tweets = user.get("tweets") or []
        result["recent_tweets"] = [
            {
                "text": t.get("text") or t.get("full_text", ""),
                "created_at": t.get("created_at"),
                "retweet_count": t.get("retweet_count"),
                "like_count": t.get("favorite_count"),
            }
            for t in tweets[:5]
        ]

    except Exception as exc:
        result["error"] = str(exc)

    return result


def check_handles_batch(
    all_variants: dict[str, list[str]],
    concurrency: int = 5,
) -> list[dict[str, Any]]:
    tasks: list[tuple[str, str]] = []
    for original, variants in all_variants.items():
        for variant in variants:
            tasks.append((original, variant))

    results: list[dict[str, Any]] = []
    total = len(tasks)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(check_single_handle, orig, var): (orig, var)
            for orig, var in tasks
        }
        for i, future in enumerate(as_completed(futures), 1):
            orig, var = futures[future]
            try:
                res = future.result()
            except Exception as exc:
                res = {
                    "original_handle": orig,
                    "variant_handle": var,
                    "exists": False,
                    "error": str(exc),
                }
            results.append(res)
            status = "✅ EXISTS" if res.get("exists") else "·"
            print(f"  [{i}/{total}] @{var:20s} {status}")

    return results
