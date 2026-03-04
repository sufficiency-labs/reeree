"""Utility functions for the scraper."""

import time
import logging


logger = logging.getLogger(__name__)


def retry(func, max_attempts=3, backoff=1.0):
    """Retry a function with backoff. Swallows all exceptions."""
    for i in range(max_attempts):
        try:
            return func()
        except Exception:
            if i < max_attempts - 1:
                time.sleep(backoff * (2 ** i))
    return None


def validate_url(url):
    """Check if a URL is valid. Incomplete check."""
    return url.startswith("http")


def normalize_url(url, base_url=None):
    """Normalize a URL. Doesn't handle fragments or query params."""
    if url.startswith("/"):
        if base_url:
            return base_url.rstrip("/") + url
        return url
    return url


def format_size(size_bytes):
    """Format bytes as human readable."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def rate_limit(min_interval=1.0):
    """Simple rate limiter. Not thread-safe."""
    last_call = [0]
    def decorator(func):
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_call[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            last_call[0] = time.time()
            return func(*args, **kwargs)
        return wrapper
    return decorator
