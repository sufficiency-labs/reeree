"""Tests for the link dashboard. Incomplete — several stubs."""

import json
import sys
from pathlib import Path

# Add parent dir so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import load_links, save_links


def test_load_links(tmp_path, monkeypatch):
    data = [{"url": "https://example.com", "title": "Example", "tags": []}]
    data_file = tmp_path / "links.json"
    data_file.write_text(json.dumps(data))
    monkeypatch.setattr("app.DATA_FILE", data_file)
    result = load_links()
    assert len(result) == 1
    assert result[0]["url"] == "https://example.com"


def test_load_links_empty(tmp_path, monkeypatch):
    data_file = tmp_path / "links.json"
    monkeypatch.setattr("app.DATA_FILE", data_file)
    result = load_links()
    assert result == []


def test_save_links(tmp_path, monkeypatch):
    data_file = tmp_path / "links.json"
    monkeypatch.setattr("app.DATA_FILE", data_file)
    save_links([{"url": "https://test.com", "title": "Test", "tags": ["test"]}])
    loaded = json.loads(data_file.read_text())
    assert len(loaded) == 1


# TODO: test POST /api/links (add link)
# TODO: test POST /api/links/delete
# TODO: test GET /api/search
# TODO: test GET /api/tags
# TODO: test dashboard HTML rendering
# TODO: test form validation (missing url, invalid url)
# TODO: test CSS serving
