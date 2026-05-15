"""
Generate JSON and CSV reports from scan results.
Originals and variants are reported separately.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def generate_report(
    results: list[dict[str, Any]],
    base_name: str = "report",
) -> tuple[str, str]:
    timestamp     = datetime.now(timezone.utc).isoformat()
    originals     = [r for r in results if r.get("is_original")]
    variants      = [r for r in results if not r.get("is_original")]
    existing      = [r for r in variants if r.get("exists")]
    with_mentions = [r for r in existing if r.get("mention_count", 0) > 0]

    payload = {
        "generated_at": timestamp,
        "original_handles": {
            "count": len(originals),
            "results": originals,
        },
        "variant_scan": {
            "total_variants_checked": len(variants),
            "impersonation_accounts_found": len(existing),
            "accounts_with_external_mentions": len(with_mentions),
            "results": variants,
        },
    }

    json_path = f"{base_name}.json"
    Path(json_path).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    # CSV — single flat file, is_original column distinguishes the two
    csv_path = f"{base_name}.csv"

    mention_cols = []
    for idx in range(1, 3):
        mention_cols += [
            f"mention_{idx}_author",
            f"mention_{idx}_text",
            f"mention_{idx}_likes",
            f"mention_{idx}_strategy",
            f"mention_{idx}_url",
        ]

    fieldnames = [
        "is_original",
        "original_handle",
        "variant_handle",
        "exists",
        "name",
        "bio",
        "profile_image_url",
        "profile_image_local",
        "follower_count",
        "following_count",
        "tweet_count",
        "verified",
        "created_at",
        "recent_tweet_1",
        "recent_tweet_2",
        "mention_count",
        *mention_cols,
        "error",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row = {**r}
            row["is_original"] = r.get("is_original", False)

            tweets = r.get("recent_tweets") or []
            for idx in range(1, 3):
                t = tweets[idx - 1] if idx <= len(tweets) else {}
                row[f"recent_tweet_{idx}"] = t.get("text", "") if t else ""

            mentions = [m for m in (r.get("mentions") or []) if "error" not in m]
            row["mention_count"] = len(mentions)
            for idx in range(1, 3):
                m = mentions[idx - 1] if idx <= len(mentions) else {}
                row[f"mention_{idx}_author"]   = m.get("author_handle", "")   if m else ""
                row[f"mention_{idx}_text"]     = m.get("text", "")            if m else ""
                row[f"mention_{idx}_likes"]    = m.get("like_count", "")      if m else ""
                row[f"mention_{idx}_strategy"] = m.get("search_strategy", "") if m else ""
                row[f"mention_{idx}_url"]      = m.get("tweet_url", "")       if m else ""

            writer.writerow(row)

    return json_path, csv_path
