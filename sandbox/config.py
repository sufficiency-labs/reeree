"""Configuration management. Mix of env vars and file-based config."""

import json
import os
from pathlib import Path


DEFAULT_CONFIG = {
    'max_pages': 10,
    'timeout': 30,
    'output': 'results.json',
    'user_agent': 'LinkScraper/1.0',
    'respect_robots': True,
    'rate_limit': 1.0,
}


def load_config(config_path=None):
    """Load config from file, with env var overrides.

    Priority: env vars > config file > defaults
    Bug: env vars aren't type-converted properly
    """
    config = dict(DEFAULT_CONFIG)

    # Load from file
    if config_path is None:
        config_path = Path("scraper.json")
    if config_path.exists():
        with open(config_path) as f:
            file_config = json.load(f)
            config.update(file_config)

    # Env var overrides (all come in as strings — not converted)
    for key in config:
        env_key = f"SCRAPER_{key.upper()}"
        env_val = os.environ.get(env_key)
        if env_val is not None:
            config[key] = env_val  # Bug: should convert types

    return config


def save_config(config, config_path=None):
    """Save config to file."""
    if config_path is None:
        config_path = Path("scraper.json")
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
