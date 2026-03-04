# Link Scraper

A web crawling tool that extracts and filters links from web pages.

## Usage
```bash
python cli.py https://example.com -o links.json -n 20 -d example.com
```

## Known Issues
- No visited URL tracking (infinite loops possible)
- No timeout on HTTP requests
- No robots.txt support
- Config env vars not type-converted
- Relative URLs not normalized
- Tests incomplete

## Files
- `scraper.py` — core crawling and parsing logic
- `utils.py` — retry, rate limiting, URL normalization utilities
- `config.py` — configuration management (file + env vars)
- `cli.py` — command-line interface
- `tests/` — test suite (incomplete)
