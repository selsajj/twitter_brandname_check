"""
Base interface all providers must implement.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):

    @abstractmethod
    def get_profile(self, handle: str) -> dict[str, Any] | None:
        """
        Return normalised profile dict or None if account doesn't exist.
        Keys: name, bio, follower_count, following_count, tweet_count,
              created_at, verified, profile_image_url
        """

    @abstractmethod
    def get_recent_tweets(self, handle: str, count: int = 5) -> list[dict[str, Any]]:
        """
        Return list of recent tweet dicts.
        Keys: text, created_at, retweet_count, like_count, tweet_url
        """

    @abstractmethod
    def get_mentions(self, handle: str, count: int = 2) -> list[dict[str, Any]]:
        """
        Return list of external mention dicts.
        Keys: author_handle, author_name, author_followers, text,
              created_at, like_count, retweet_count, reply_count,
              tweet_url, is_reply, search_strategy
        """

    @abstractmethod
    def get_replies(self, tweet_urls: list[str], count: int = 2) -> list[dict[str, Any]]:
        """
        Return list of reply dicts scraped from tweet threads.
        Same keys as get_mentions.
        """
