"""
TwitterAPI.io provider.
Docs: https://docs.twitterapi.io

Endpoints used:
  GET /twitter/user/info             — profile lookup
  GET /twitter/user/last_tweets      — recent tweets
  GET /twitter/user/mentions         — direct mentions
  GET /twitter/tweet/replies         — replies on a tweet thread
  GET /twitter/search/tweet          — text reference search
"""

from __future__ import annotations

import os
from typing import Any

import requests

from .base import BaseProvider

BASE_URL = "https://api.twitterapi.io"


class TwitterAPIProvider(BaseProvider):

    def __init__(self) -> None:
        token = os.getenv("TWITTERAPI_IO_KEY", "")
        if not token:
            raise EnvironmentError("TWITTERAPI_IO_KEY is not set.")
        self._headers = {
            "X-API-Key": token,
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict) -> dict:
        resp = requests.get(f"{BASE_URL}{path}", headers=self._headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_profile(self, handle: str) -> dict[str, Any] | None:
        try:
            data = self._get("/twitter/user/info", {"userName": handle})
            u = data.get("data") or data
            if not u or not u.get("userName"):
                return None
            return {
                "name":              u.get("name"),
                "bio":               u.get("description"),
                "follower_count":    u.get("followers") or u.get("followersCount"),
                "following_count":   u.get("following") or u.get("followingCount"),
                "tweet_count":       u.get("statusesCount") or u.get("tweetsCount"),
                "created_at":        u.get("createdAt"),
                "verified":          u.get("isBlueVerified", False),
                "profile_image_url": u.get("profilePicture") or u.get("profileImageUrl", ""),
            }
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return None
            raise

    def get_recent_tweets(self, handle: str, count: int = 5) -> list[dict[str, Any]]:
        try:
            data = self._get("/twitter/user/last_tweets", {"userName": handle, "limit": count})
            tweets = data.get("data", {}).get("tweets") or data.get("tweets") or []
            return [
                {
                    "text":          t.get("text") or t.get("fullText", ""),
                    "created_at":    t.get("createdAt"),
                    "retweet_count": t.get("retweetCount"),
                    "like_count":    t.get("likeCount") or t.get("favoriteCount"),
                    "tweet_url":     t.get("url") or f"https://x.com/{handle}/status/{t.get('id', '')}",
                }
                for t in tweets[:count]
            ]
        except Exception:
            return []

    def get_mentions(self, handle: str, count: int = 2) -> list[dict[str, Any]]:
        results = []

        # Direct mentions via dedicated endpoint
        try:
            data = self._get("/twitter/user/mentions", {"userName": handle, "limit": count})
            tweets = data.get("data", {}).get("tweets") or data.get("tweets") or []
            for t in tweets[:count]:
                author = t.get("author") or t.get("user") or {}
                author_handle = (author.get("userName") or author.get("screenName") or "").lower()
                if author_handle == handle.lower():
                    continue
                text = t.get("text") or t.get("fullText", "")
                results.append({
                    "author_handle":    author_handle,
                    "author_name":      author.get("name"),
                    "author_followers": author.get("followers") or author.get("followersCount"),
                    "text":             text,
                    "is_reply":         bool(t.get("inReplyToId") or text.strip().startswith("@")),
                    "created_at":       t.get("createdAt"),
                    "retweet_count":    t.get("retweetCount"),
                    "like_count":       t.get("likeCount") or t.get("favoriteCount"),
                    "reply_count":      t.get("replyCount"),
                    "tweet_url":        t.get("url") or "",
                    "search_strategy":  "direct_mention",
                })
        except Exception:
            pass

        # Text references via search
        try:
            data = self._get("/twitter/search/tweet", {"query": f'"{handle}"', "queryType": "Latest", "count": count})
            tweets = data.get("data", {}).get("tweets") or data.get("tweets") or []
            for t in tweets[:count]:
                author = t.get("author") or t.get("user") or {}
                author_handle = (author.get("userName") or author.get("screenName") or "").lower()
                if author_handle == handle.lower():
                    continue
                results.append({
                    "author_handle":    author_handle,
                    "author_name":      author.get("name"),
                    "author_followers": author.get("followers") or author.get("followersCount"),
                    "text":             t.get("text") or t.get("fullText", ""),
                    "is_reply":         False,
                    "created_at":       t.get("createdAt"),
                    "retweet_count":    t.get("retweetCount"),
                    "like_count":       t.get("likeCount") or t.get("favoriteCount"),
                    "reply_count":      t.get("replyCount"),
                    "tweet_url":        t.get("url") or "",
                    "search_strategy":  "text_reference",
                })
        except Exception:
            pass

        return results

    def get_replies(self, tweet_urls: list[str], count: int = 2) -> list[dict[str, Any]]:
        results = []
        for url in tweet_urls[:3]:
            try:
                tweet_id = url.rstrip("/").split("/")[-1]
                data = self._get("/twitter/tweet/replies", {"tweetId": tweet_id, "count": count})
                replies = data.get("data", {}).get("replies") or data.get("replies") or []
                for t in replies[:count]:
                    author = t.get("author") or t.get("user") or {}
                    results.append({
                        "author_handle":    (author.get("userName") or author.get("screenName") or "").lower(),
                        "author_name":      author.get("name"),
                        "author_followers": author.get("followers") or author.get("followersCount"),
                        "text":             t.get("text") or t.get("fullText", ""),
                        "is_reply":         True,
                        "created_at":       t.get("createdAt"),
                        "retweet_count":    t.get("retweetCount"),
                        "like_count":       t.get("likeCount") or t.get("favoriteCount"),
                        "reply_count":      t.get("replyCount"),
                        "tweet_url":        t.get("url") or url,
                        "search_strategy":  "reply_to",
                    })
            except Exception:
                pass
        return results[:count]
