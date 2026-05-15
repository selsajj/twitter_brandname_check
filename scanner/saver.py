"""
Save tweets, mentions, and replies for found accounts as flat text files.

Output structure (all in one folder):
  saved_content/
    <variant_handle>_profile.txt
    <variant_handle>_tweets.txt
    <variant_handle>_mentions.txt
    <variant_handle>_replies.txt
    <variant_handle>_text_references.txt
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

DIVIDER = "-" * 60


def _fmt_tweet(t: dict, idx: int) -> str:
    text = t.get("text", "").strip()
    wrapped = textwrap.fill(text, width=80, subsequent_indent="    ")
    lines = [f"[{idx}] {wrapped}"]
    meta = []
    if t.get("created_at"):
        meta.append(f"date: {t['created_at']}")
    if t.get("like_count") is not None:
        meta.append(f"likes: {t['like_count']}")
    if t.get("retweet_count") is not None:
        meta.append(f"retweets: {t['retweet_count']}")
    if t.get("reply_count") is not None:
        meta.append(f"replies: {t['reply_count']}")
    if t.get("tweet_url"):
        meta.append(f"url: {t['tweet_url']}")
    if meta:
        lines.append("    " + " | ".join(meta))
    return "\n".join(lines)


def _fmt_mention(m: dict, idx: int) -> str:
    author    = m.get("author_handle", "unknown")
    name      = m.get("author_name", "")
    followers = m.get("author_followers")
    text      = m.get("text", "").strip()
    wrapped   = textwrap.fill(text, width=80, subsequent_indent="    ")
    header    = f"[{idx}] @{author}"
    if name:
        header += f" ({name})"
    if followers is not None:
        try:
            header += f"  [{int(followers):,} followers]"
        except (ValueError, TypeError):
            header += f"  [{followers} followers]"
    lines = [header, f"    {wrapped}"]
    meta = []
    if m.get("created_at"):
        meta.append(f"date: {m['created_at']}")
    if m.get("like_count") is not None:
        meta.append(f"likes: {m['like_count']}")
    if m.get("retweet_count") is not None:
        meta.append(f"retweets: {m['retweet_count']}")
    if m.get("tweet_url"):
        meta.append(f"url: {m['tweet_url']}")
    if meta:
        lines.append("    " + " | ".join(meta))
    return "\n".join(lines)


def _write(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines), encoding="utf-8")


def save_account_content(
    result: dict[str, Any],
    output_dir: str = "saved_content",
) -> list[str]:
    """
    Write flat files for a single found account.
    Returns list of file paths written.
    """
    variant = result["variant_handle"]
    folder  = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    written = []

    # --- <variant>_profile.txt ---
    p = folder / f"{variant}_profile.txt"
    _write(p, [
        f"IMPERSONATION ACCOUNT: @{variant}",
        DIVIDER,
        f"Display name : {result.get('name') or 'N/A'}",
        f"Bio          : {result.get('bio') or 'N/A'}",
        f"Followers    : {result.get('follower_count') or 'N/A'}",
        f"Following    : {result.get('following_count') or 'N/A'}",
        f"Tweets       : {result.get('tweet_count') or 'N/A'}",
        f"Created at   : {result.get('created_at') or 'N/A'}",
        f"Verified     : {result.get('verified', False)}",
        f"Profile image: {result.get('profile_image_url') or 'N/A'}",
        f"Local image  : {result.get('profile_image_local') or 'not downloaded'}",
        f"Original acct: @{result.get('original_handle')}",
    ])
    written.append(str(p))

    # --- <variant>_tweets.txt ---
    tweets = (result.get("recent_tweets") or [])[:2]
    p = folder / f"{variant}_tweets.txt"
    if tweets:
        lines = [f"OWN TWEETS — @{variant}", DIVIDER,
                 f"({len(tweets)} tweet(s) captured)", ""]
        for i, t in enumerate(tweets, 1):
            lines += [_fmt_tweet(t, i), ""]
    else:
        lines = [f"OWN TWEETS — @{variant}", DIVIDER, "No tweets captured."]
    _write(p, lines)
    written.append(str(p))

    # Split mentions by strategy
    all_mentions = [m for m in (result.get("mentions") or []) if "error" not in m]
    direct    = [m for m in all_mentions if m.get("search_strategy") == "direct_mention"][:2]
    replies   = [m for m in all_mentions if m.get("search_strategy") == "reply_to"][:2]
    text_refs = [m for m in all_mentions if m.get("search_strategy") == "text_reference"][:2]

    # --- <variant>_mentions.txt ---
    p = folder / f"{variant}_mentions.txt"
    if direct:
        lines = [f"DIRECT MENTIONS — @{variant}", DIVIDER,
                 f"({len(direct)} mention(s) — other users tagging @{variant})", ""]
        for i, m in enumerate(direct, 1):
            lines += [_fmt_mention(m, i), ""]
    else:
        lines = [f"DIRECT MENTIONS — @{variant}", DIVIDER, "No direct mentions found."]
    _write(p, lines)
    written.append(str(p))

    # --- <variant>_replies.txt ---
    p = folder / f"{variant}_replies.txt"
    if replies:
        lines = [f"REPLIES TO — @{variant}", DIVIDER,
                 f"({len(replies)} reply/replies — visible even if account is private)", ""]
        for i, m in enumerate(replies, 1):
            lines += [_fmt_mention(m, i), ""]
    else:
        lines = [f"REPLIES TO — @{variant}", DIVIDER, "No replies found."]
    _write(p, lines)
    written.append(str(p))

    # --- <variant>_text_references.txt ---
    p = folder / f"{variant}_text_references.txt"
    if text_refs:
        lines = [f"TEXT REFERENCES — @{variant}", DIVIDER,
                 f"({len(text_refs)} reference(s) — mentions without the @ symbol)", ""]
        for i, m in enumerate(text_refs, 1):
            lines += [_fmt_mention(m, i), ""]
    else:
        lines = [f"TEXT REFERENCES — @{variant}", DIVIDER, "No text references found."]
    _write(p, lines)
    written.append(str(p))

    return written


def save_all_content(
    results: list[dict[str, Any]],
    output_dir: str = "saved_content",
) -> list[str]:
    """Save flat files for all found accounts. Returns all file paths written."""
    all_files = []
    for r in results:
        if r.get("exists"):
            all_files.extend(save_account_content(r, output_dir=output_dir))
    return all_files
