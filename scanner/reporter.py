"""
Generate JSON and CSV reports from scan results.
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
    """
    Write results to <base_name>.json and <base_name>.csv.
    Returns (json_path, csv_path).
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    existing = [r for r in results if r.get("exists")]

    payload = {
        "generated_at": timestamp,
        "total_variants_checked": len(results),
        "impersonation_accounts_found": len(existing),
        "results": results,
    }

    json_path = f"{base_name}.json"
    Path(json_path).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    csv_path = f"{base_name}.csv"
    fieldnames = [
        "original_handle",
        "variant_handle",
        "exists",
        "name",
        "follower_count",
        "following_count",
        "tweet_count",
        "verified",
        "bio",
        "created_at",
        "recent_tweet_1",
        "recent_tweet_2",
        "recent_tweet_3",
        "error",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            tweets = r.get("recent_tweets") or []
            row = {**r}
            for idx in range(1, 4):
                tweet = tweets[idx - 1] if idx <= len(tweets) else {}
                row[f"recent_tweet_{idx}"] = tweet.get("text", "") if tweet else ""
            writer.writerow(row)

    return json_path, csv_path
