"""
Provider-agnostic checker.
Supports --provider apify (default) or --provider twitterapi
"""

from __future__ import annotations

import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .providers.base import BaseProvider


def _get_provider(name: str = "twitterapi") -> BaseProvider:

    from .providers.twitterapi_provider import TwitterAPIProvider
    return TwitterAPIProvider()


def _download_profile_image(handle: str, image_url: str, output_dir: str = "profile_images") -> str | None:
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


def check_single_handle(
    original: str,
    variant: str,
    provider_name: str = "twitterapi",
    download_images: bool = True,
    images_dir: str = "profile_images",
) -> dict[str, Any]:
    provider = _get_provider(provider_name)

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
        "provider":            provider_name,
        "error":               None,
    }

    try:
        # --- Step 1: profile ---
        profile = provider.get_profile(variant)
        if not profile:
            return result

        result["exists"]          = True
        result["name"]            = profile.get("name")
        result["bio"]             = profile.get("bio")
        result["follower_count"]  = profile.get("follower_count")
        result["following_count"] = profile.get("following_count")
        result["tweet_count"]     = profile.get("tweet_count")
        result["created_at"]      = profile.get("created_at")
        result["verified"]        = profile.get("verified", False)
        result["profile_image_url"] = profile.get("profile_image_url", "")

        if download_images and result["profile_image_url"]:
            result["profile_image_local"] = _download_profile_image(
                variant, result["profile_image_url"], images_dir
            )

        # --- Step 2: recent tweets ---
        result["recent_tweets"] = provider.get_recent_tweets(variant, count=5)
        recent_urls = [t["tweet_url"] for t in result["recent_tweets"] if t.get("tweet_url")]

        # --- Step 3: mentions + replies ---
        mentions  = provider.get_mentions(variant, count=2)
        replies   = provider.get_replies(recent_urls, count=2)

        # Deduplicate by text
        seen: set[str] = set()
        combined: list[dict] = []
        for m in mentions + replies:
            key = m.get("text", "").strip().lower()
            if key and key not in seen:
                seen.add(key)
                combined.append(m)

        result["mentions"]      = combined
        result["mention_count"] = len(combined)

    except Exception as exc:
        result["error"] = str(exc)

    return result


def check_handles_batch(
    all_variants: dict[str, list[str]],
    provider_name: str = "twitterapi",
    concurrency: int = 3,
    download_images: bool = True,
    images_dir: str = "profile_images",
) -> list[dict[str, Any]]:
    tasks: list[tuple[str, str]] = [
        (orig, var)
        for orig, variants in all_variants.items()
        for var in variants
    ]
    results: list[dict[str, Any]] = []
    total = len(tasks)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(
                check_single_handle, orig, var, provider_name, download_images, images_dir
            ): (orig, var)
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
                    "provider":        provider_name,
                    "error":           str(exc),
                }
            results.append(res)
            if res.get("exists"):
                print(f"  [{i}/{total}] @{var:20s} ✅ EXISTS  — {res.get('mention_count', 0)} mention(s) {'🖼️' if res.get('profile_image_local') else ''}")
            else:
                print(f"  [{i}/{total}] @{var:20s} ·")

    return results


def check_originals(
    handles: list[str],
    provider_name: str = "twitterapi",
    download_images: bool = True,
    images_dir: str = "profile_images",
) -> list[dict[str, Any]]:
    results = []
    total = len(handles)
    print(f"\n📌 Checking {total} original handle(s) via {provider_name}...\n")
    for i, handle in enumerate(handles, 1):
        print(f"  [{i}/{total}] @{handle:20s} (original)")
        res = check_single_handle(handle, handle, provider_name, download_images, images_dir)
        res["is_original"] = True
        results.append(res)
    return results
