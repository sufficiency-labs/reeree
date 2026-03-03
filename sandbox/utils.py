"""Utility functions. Some are unused, some are broken."""


def retry(func, max_attempts=3):
    """Retry a function. But it swallows all exceptions silently."""
    for i in range(max_attempts):
        try:
            return func()
        except:
            pass
    return None


def validate_url(url):
    """Check if a URL is valid. But the check is wrong."""
    return url.startswith("http")


def format_size(bytes):
    """Format bytes as human readable. Shadows builtin."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024
    return f"{bytes:.1f} TB"
