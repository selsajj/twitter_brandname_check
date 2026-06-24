"""
Save interaction results as JSON, CSV, and a readable text summary.
Files are named: interactions_<handle_a>_<handle_b>.*
"""

from __future__ import annotations

import csv
import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DIVIDER = "-" * 60
LABELS = {
    "handle_a_to_handle_b":          "{a} → {b}  (A mentions/replies to B)",
    "handle_b_to_handle_a":          "{b} → {a}  (B mentions/replies to A)",
    "handle_a_quotes_handle_b":      "{a} quotes {b}",
    "handle_b_quotes_handle_a":      "{b} quotes {a}",
    "third_party_mentions_both":     "Third party mentions both",
}


def _fmt(item: dict, idx: int) -> str:
    text = textwrap.fill(item.get("text", "").strip(), width=80, subsequent_indent="    ")
    lines = [f"[{idx}] @{item.get('author_handle', '?')}  ({item.get('author_name', '')})",
             f"    {text}"]
    meta = []
    if item.get("created_at"):
        meta.append(f"date: {item['created_at']}")
    if item.get("like_count") is not None:
        meta.append(f"likes: {item['like_count']}")
    if item.get("retweet_count") is not None:
        meta.append(f"retweets: {item['retweet_count']}")
    if item.get("tweet_url"):
        meta.append(f"url: {item['tweet_url']}")
    if meta:
        lines.append("    " + " | ".join(meta))
    return "\n".join(lines)


def save_interaction_report(
    result: dict[str, Any],
    output_dir: str = "saved_content",
) -> tuple[str, str, str]:
    """
    Write JSON, CSV, and TXT reports.
    Returns (json_path, csv_path, txt_path).
    """
    a = result["handle_a"]
    b = result["handle_b"]
    base = f"interactions_{a}_{b}"
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()

    # --- JSON ---
    json_path = str(Path(output_dir) / f"{base}.json")
    Path(json_path).write_text(
        json.dumps({"generated_at": timestamp, **result}, indent=2, default=str),
        encoding="utf-8"
    )

    # --- CSV ---
    csv_path = str(Path(output_dir) / f"{base}.csv")
    fieldnames = [
        "relationship", "author_handle", "author_name", "author_followers",
        "text", "created_at", "like_count", "retweet_count", "reply_count", "tweet_url"
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for item in result.get("flat", []):
            writer.writerow(item)

    # --- TXT ---
    txt_path = str(Path(output_dir) / f"{base}.txt")
    lines = [
        f"INTERACTION REPORT: @{a} ↔ @{b}",
        f"Generated : {timestamp}",
        f"Total     : {result['total_found']} interaction(s) found",
        "",
    ]
    grouped = result.get("interactions", {})
    for rel, items in grouped.items():
        label = rel.replace("handle_a", a).replace("handle_b", b).replace("_", " ")
        lines += [f"\n{'='*60}", f"  {label.upper()}  ({len(items)} result(s))", f"{'='*60}", ""]
        for i, item in enumerate(items, 1):
            lines += [_fmt(item, i), ""]

    if not grouped:
        lines.append("No interactions found between these two accounts.")

    Path(txt_path).write_text("\n".join(lines), encoding="utf-8")

    return json_path, csv_path, txt_path
