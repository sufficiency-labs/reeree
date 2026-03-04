# Link Dashboard

A small web app for saving and organizing links. Has a web interface with obvious gaps.

## Run
```bash
python app.py
# → http://localhost:8080
```

## What works
- Dashboard renders with saved links
- Links stored in links.json
- Basic CSS dark theme

## What's broken / incomplete
- Add link form submits but API returns 501
- Delete button calls API but returns 501
- Search box is just a text input that does nothing
- No tag filtering or management
- No input validation
- No error handling on API routes
- Tests only cover load/save, not HTTP handlers
- CSS needs work (hover states, responsive, form layout)

## Files
- `app.py` — HTTP server + dashboard handler
- `style.css` — minimal dark theme
- `links.json` — data store
- `tests/test_app.py` — incomplete test suite
- `scraper.py` — link scraper (legacy, not wired to dashboard)
- `config.py` — config management
- `utils.py` — utility functions
- `cli.py` — CLI for scraper
