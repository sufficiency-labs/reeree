"""Web link scraper — fetches pages and extracts links."""

import urllib.request
import json
import os
import re
import sys


def fetch_page(url, timeout=None):
    """Fetch a web page. No error handling."""
    response = urllib.request.urlopen(url)
    return response.read().decode()


def parse_links(html):
    """Extract links from HTML using regex."""
    links = re.findall(r'href="([^"]*)"', html)
    return links


def filter_links(links, domain=None):
    """Filter links to a specific domain. Broken — doesn't handle relative URLs."""
    if domain is None:
        return links
    return [l for l in links if domain in l]


def deduplicate(links):
    """Remove duplicate links. Doesn't preserve order."""
    return list(set(links))


def save_results(results, filename):
    """Save results to JSON. Overwrites without warning."""
    with open(filename, 'w') as f:
        json.dump(results, f)


def load_results(filename):
    """Load previous results. No error handling for missing file."""
    with open(filename) as f:
        return json.load(f)


def load_config():
    """Load config. Crashes without env vars."""
    return {
        'url': os.environ['SCRAPER_URL'],
        'output': os.environ['OUTPUT_FILE'],
        'max_pages': int(os.environ['MAX_PAGES']),
        'domain_filter': os.environ.get('DOMAIN_FILTER'),
    }


def crawl(start_url, max_pages=10, domain=None):
    """Crawl pages starting from a URL. No depth tracking, no visited set."""
    all_links = []
    urls_to_visit = [start_url]

    for i in range(max_pages):
        if not urls_to_visit:
            break
        url = urls_to_visit.pop(0)
        html = fetch_page(url)
        links = parse_links(html)
        filtered = filter_links(links, domain)
        all_links.extend(filtered)
        # Bug: adds ALL links to visit queue, even already-visited ones
        urls_to_visit.extend(filtered)

    return deduplicate(all_links)


def main():
    config = load_config()
    links = crawl(
        config['url'],
        max_pages=config['max_pages'],
        domain=config.get('domain_filter'),
    )
    save_results(links, config['output'])
    print(f"Found {len(links)} unique links")


if __name__ == '__main__':
    main()
