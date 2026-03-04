"""Command-line interface for the scraper."""

import argparse
import sys

from scraper import crawl, save_results
from config import load_config


def parse_args():
    """Parse CLI arguments. Missing several useful options."""
    parser = argparse.ArgumentParser(description="Web link scraper")
    parser.add_argument("url", help="Starting URL to crawl")
    parser.add_argument("-o", "--output", default="results.json", help="Output file")
    parser.add_argument("-n", "--max-pages", type=int, default=10, help="Max pages to crawl")
    parser.add_argument("-d", "--domain", help="Filter links to this domain")
    # Missing: --config, --verbose, --timeout, --rate-limit
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config()

    # CLI args override config
    config['max_pages'] = args.max_pages
    config['output'] = args.output

    print(f"Crawling {args.url} (max {config['max_pages']} pages)")

    try:
        links = crawl(args.url, max_pages=config['max_pages'], domain=args.domain)
        save_results(links, config['output'])
        print(f"Done. Found {len(links)} unique links. Saved to {config['output']}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
