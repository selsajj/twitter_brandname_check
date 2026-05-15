"""
Check whether X (Twitter) handles exist using the Apify actor:
  logical_scrapers/x-twitter-user-profile-tweets-scraper

For accounts that exist, fetches mentions and replies via:
  - apidojo/tweet-scraper       → direct @mentions and text references
  - quacker/twitter-replies     → replies scraped directly from tweet threads
"""

from __future__ import annotations

import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from apify_client import ApifyClient

PROFILE_ACTOR_ID = "logical_scrapers/x-twitter-user-profile-tweets-scraper"
SEARCH_ACTOR_ID  = "apidojo/tweet-scraper"
REPLIES_ACTOR_ID = "quacker/twitter-replies"

MAX_MENTIONS = 2  # per strategy


def _get_client() -> ApifyClient:
    token = os.getenv("APIFY_API_TOKEN", "")
    if not token:
        raise EnvironmentError(
            "APIFY_API_TOKEN is not set. "
            "Copy .env.example to .env and add your token."
        )
    return ApifyClient(token)


def _download_profile_image(handle: str, image_url: str, output_dir: str = "profile_images") -> str | None:
    """Download profile image at 400x400 resolution. Returns local path or None."""
    if not image_url:
        return None
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        image_url = image_url.replace("_normal", "_400x400")
        ext = image_url.split("?")[0].rsplit(".", 1)[-1] or "jpg"
        dest = Path(output_dir) / f"{handle}.{ext}"
        urllib.request.urlretrieve(image_url, dest)
        return str(dest)
    except Exception:
        return None


def _normalise_tweet(t: dict, variant: str, strategy: str = "") -> dict[str, Any] | None:
    """
    Normalise a raw Apify tweet item into a consistent mention dict.
    Returns None if the tweet is by the variant account itself.
    """
    author = t.get("author") or t.get("user") or {}
    author_handle = (
        author.get("userName") or
        author.get("screen_name") or ""
    ).lower()

    if author_handle == variant.lower():
        return None

    text = t.get("text") or t.get("full_text", "")

    is_reply = bool(
        t.get("inReplyToId") or
        t.get("in_reply_to_status_id") or
        t.get("inReplyToUser") or
        text.strip().startswith("@")
    )

    return {
        "author_handle":    author_handle,
        "author_name":      author.get("name") or author.get("full_name"),
        "author_followers": author.get("followers") or author.get("followersCount"),
        "text":             text,
        "is_reply":         is_reply,
        "created_at":       t.get("createdAt") or t.get("created_at"),
        "retweet_count":    t.get("retweetCount") or t.get("retweet_count"),
        "like_count":       t.get("likeCount") or t.get("favorite_count"),
        "reply_count":      t.get("replyCount") or t.get("reply_count"),
        "tweet_url":        t.get("url") or t.get("tweetUrl"),
        "search_strategy":  strategy,
    }


def _run_search(client: ApifyClient, query: str) -> list[dict]:
    """Search tweets via apidojo/tweet-scraper."""
    run = client.actor(SEARCH_ACTOR_ID).call(
        run_input={
            "searchTerms": [query],
            "maxItems": MAX_MENTIONS,
            "queryType": "Latest",
        },
        timeout_secs=120,
    )
    return list(client.dataset(run["defaultDatasetId"]).iterate_items())


def _run_replies_scraper(client: ApifyClient, variant: str, tweet_urls: list[str]) -> list[dict[str, Any]]:
    """
    Use quacker/twitter-replies to scrape replies directly from tweet threads.
    Falls back gracefully if the actor errors or returns nothing.
    """
    if not tweet_urls:
        return []
    replies = []
    try:
        run = client.actor(REPLIES_ACTOR_ID).call(
            run_input={
                "tweetUrls": tweet_urls[:3],   # scrape replies on up to 3 recent tweets
                "maxReplies": MAX_MENTIONS * 2,
            },
            timeout_secs=120,
        )
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        for t in items:
            m = _normalise_tweet(t, variant, strategy="reply_to")
            if m:
                m["is_reply"] = True
                replies.append(m)
    except Exception as exc:
        replies.append({"error": str(exc), "search_strategy": "reply_to"})
    return replies


def _fetch_mentions(
    client: ApifyClient,
    variant: str,
    recent_tweet_urls: list[str],
) -> list[dict[str, Any]]:
    """
    Collect external mentions and replies via three strategies:
      1. @variant search       — direct @mentions
      2. "variant" search      — text references without @
      3. replies actor         — replies scraped from the account's own tweet threads
    """
    seen_texts: set[str] = set()
    all_mentions: list[dict[str, Any]] = []

    # Strategy 1 & 2: search-based
    search_strategies = [
        (f"@{variant}",  "direct_mention"),
        (f'"{variant}"', "text_reference"),
    ]
    for query, label in search_strategies:
        try:
            items = _run_search(client, query)
        except Exception as exc:
            all_mentions.append({"error": f"{label}: {exc}", "search_strategy": label})
            continue
        for t in items:
            m = _normalise_tweet(t, variant, strategy=label)
            if m is None:
                continue
            key = m["text"].strip().lower()
            if key in seen_texts:
                continue
            seen_texts.add(key)
            all_mentions.append(m)

    # Strategy 3: replies actor — scrapes actual reply threads
    reply_items = _run_replies_scraper(client, variant, recent_tweet_urls)
    for m in reply_items:
        if "error" in m:
            all_mentions.append(m)
            continue
        key = m["text"].strip().lower()
        if key in seen_texts:
            continue
        seen_texts.add(key)
        all_mentions.append(m)

    real   = [m for m in all_mentions if "error" not in m]
    errors = [m for m in all_mentions if "error" in m]
    real.sort(key=lambda m: m.get("like_count") or 0, reverse=True)

    return (real + errors)[:MAX_MENTIONS * 3]


def check_single_handle(
    original: str,
    variant: str,
    download_images: bool = True,
    images_dir: str = "profile_images",
) -> dict[str, Any]:
    client = _get_client()
    result: dict[str, Any] = {
        "original_handle":     original,
        "variant_handle":      variant,
        "exists":              False,
        "name":                None,
        "bio":                 None,
        "profile_image_url":   None,
        "profile_image_local": None,
        "follower_count":      None,
        "following_count":     None,
        "tweet_count":         None,
        "created_at":          None,
        "verified":            False,
        "recent_tweets":       [],
        "mentions":            [],
        "mention_count":       0,
        "error":               None,
    }

    try:
        # --- Step 1: profile lookup ---
        run = client.actor(PROFILE_ACTOR_ID).call(
            run_input={
                "username": [variant],
                "maxTweets": 5,
                "addUserInfo": True,
            },
            timeout_secs=120,
        )
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

        if not items:
            return result

        user = items[0]
        result["exists"]          = True
        result["name"]            = user.get("name") or user.get("full_name")
        result["bio"]             = user.get("description")
        result["follower_count"]  = user.get("followersCount") or user.get("followers_count")
        result["following_count"] = user.get("friendsCount") or user.get("friends_count")
        result["tweet_count"]     = user.get("statusesCount") or user.get("statuses_count")
        result["created_at"]      = user.get("createdAt") or user.get("created_at")
        result["verified"]        = user.get("verified", False)

        image_url = (
            user.get("profileImageUrl") or
            user.get("profile_image_url_https") or
            user.get("profile_image_url") or
            user.get("avatarUrl") or ""
        )
        result["profile_image_url"] = image_url
        if download_images and image_url:
            result["profile_image_local"] = _download_profile_image(variant, image_url, images_dir)

        tweets = user.get("tweets") or []
        result["recent_tweets"] = [
            {
                "text":          t.get("text") or t.get("full_text", ""),
                "created_at":    t.get("created_at"),
                "retweet_count": t.get("retweet_count"),
                "like_count":    t.get("favorite_count"),
                "tweet_url":     t.get("url") or t.get("tweetUrl") or "",
            }
            for t in tweets[:5]
        ]

        # Collect tweet URLs to feed into the replies actor
        recent_tweet_urls = [
            t["tweet_url"] for t in result["recent_tweets"] if t.get("tweet_url")
        ]

        # --- Step 2: mentions + replies ---
        mentions = _fetch_mentions(client, variant, recent_tweet_urls)
        result["mentions"]      = mentions
        result["mention_count"] = len([m for m in mentions if "error" not in m])

    except Exception as exc:
        result["error"] = str(exc)

    return result


def check_handles_batch(
    all_variants: dict[str, list[str]],
    concurrency: int = 5,
    download_images: bool = True,
    images_dir: str = "profile_images",
) -> list[dict[str, Any]]:
    tasks: list[tuple[str, str]] = []
    for original, variants in all_variants.items():
        for variant in variants:
            tasks.append((original, variant))

    results: list[dict[str, Any]] = []
    total = len(tasks)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(check_single_handle, orig, var, download_images, images_dir): (orig, var)
            for orig, var in tasks
        }
        for i, future in enumerate(as_completed(futures), 1):
            orig, var = futures[future]
            try:
                res = future.result()
            except Exception as exc:
                res = {
                    "original_handle": orig,
                    "variant_handle":  var,
                    "exists":          False,
                    "error":           str(exc),
                }
            results.append(res)
            if res.get("exists"):
                mentions = res.get("mention_count", 0)
                img = "🖼️ " if res.get("profile_image_local") else ""
                print(f"  [{i}/{total}] @{var:20s} ✅ EXISTS  — {mentions} mention(s) {img}")
            else:
                print(f"  [{i}/{total}] @{var:20s} ·")

    return results


def check_originals(
    handles: list[str],
    download_images: bool = True,
    images_dir: str = "profile_images",
) -> list[dict[str, Any]]:
    """
    Run the full profile + mention + reply check on the original handles themselves.
    Results are tagged with is_original=True.
    """
    results = []
    total = len(handles)
    print(f"\n📌 Checking {total} original handle(s)...\n")
    for i, handle in enumerate(handles, 1):
        print(f"  [{i}/{total}] @{handle:20s} (original)")
        res = check_single_handle(
            original=handle,
            variant=handle,
            download_images=download_images,
            images_dir=images_dir,
        )
        res["is_original"] = True
        results.append(res)
    return results
