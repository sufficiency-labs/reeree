"""Tests for the scraper. Incomplete — only covers happy paths."""

from scraper import parse_links, filter_links, deduplicate


def test_parse_links_basic():
    html = '<a href="https://example.com">link</a>'
    links = parse_links(html)
    assert links == ["https://example.com"]


def test_parse_links_multiple():
    html = '<a href="a.html">A</a><a href="b.html">B</a>'
    links = parse_links(html)
    assert len(links) == 2


def test_filter_links_with_domain():
    links = ["https://example.com/a", "https://other.com/b", "https://example.com/c"]
    filtered = filter_links(links, domain="example.com")
    assert len(filtered) == 2


def test_filter_links_no_domain():
    links = ["a", "b", "c"]
    assert filter_links(links) == links


def test_deduplicate():
    links = ["a", "b", "a", "c", "b"]
    result = deduplicate(links)
    assert len(result) == 3


# Missing tests:
# - fetch_page error handling
# - crawl with visited tracking
# - normalize_url
# - config loading
# - rate limiting
# - CLI argument parsing
