"""A simple web scraper with intentional issues for reeree to fix."""

import urllib.request
import json
import os


def fetch_page(url):
    """Fetch a web page with error handling, timeout, and retries."""
    import time
    max_retries = 3
    timeout = 10
    
    for attempt in range(max_retries):
        try:
            response = urllib.request.urlopen(url, timeout=timeout)
            return response.read().decode()
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                raise e


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
        'url': os.environ.get('SCRAPER_URL', 'http://example.com'),
        'output': os.environ.get('OUTPUT_FILE', 'output.json'),
        'max_pages': int(os.environ.get('MAX_PAGES', '10')),
    }


def main():
    config = load_config()
    html = fetch_page(config['url'])
    links = parse_links(html)
    save_results(links, config['output'])
    print(f"Found {len(links)} links")


if __name__ == '__main__':
    main()
