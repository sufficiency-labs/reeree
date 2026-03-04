"""A simple web scraper with intentional issues for reeree to fix."""

import urllib.request
import json
import os


def fetch_page(url):
    """Fetch a web page. No error handling, no timeout, no retries."""
    response = urllib.request.urlopen(url)
    return response.read().decode()


def parse_links(html):
    """Extract links from HTML. Fragile regex approach."""
    import re
    links = re.findall(r'href="([^"]*)"', html)
    return links


def save_results(results, filename):
    """Save results to JSON. Overwrites without checking."""
    with open(filename, 'w') as f:
        json.dump(results, f)


def load_config():
    """Load config from environment. No defaults, no validation."""
    return {
        'url': os.environ['SCRAPER_URL'],
        'output': os.environ['OUTPUT_FILE'],
        'max_pages': int(os.environ['MAX_PAGES']),
    }


def main():
    config = load_config()
    html = fetch_page(config['url'])
    links = parse_links(html)
    save_results(links, config['output'])
    print(f"Found {len(links)} links")


if __name__ == '__main__':
    main()
