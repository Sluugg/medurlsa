"""
Loads content_config.json from the project root and merges it over hardcoded defaults.
Read once at import time — server restart required for changes to take effect.
"""

import json
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH  = os.path.join(_PROJECT_ROOT, "content_config.json")

_DEFAULTS: dict = {
    "site_title": "dopelink",
    "logo_path":  None,
    "flavor_texts": [],
    "fonts": {
        "title": {
            "family": "'VCROSDMono', 'Courier New', monospace",
            "size":   "1.25rem",
            "weight": "bold",
        },
        "flavor_text": {
            "family": "'VCROSDMono', 'Courier New', monospace",
            "size":   "0.7rem",
            "weight": "normal",
        },
    },
    "timing": {
        "glitch": {
            "interval_min_s": 8,
            "interval_max_s": 20,
            "duration_ms":    400,
        },
        "color_cycle": {
            "interval_min_s": 15,
            "interval_max_s": 40,
            "duration_ms":    3000,
            "rate_ms":        300,
        },
        "flavor_text": {
            "interval_min_s": 12,
            "interval_max_s": 25,
            "duration_ms":    4000,
        },
        "logo_flash": {
            "interval_min_s": 20,
            "interval_max_s": 60,
            "duration_ms":    3000,
        },
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _load() -> dict:
    if not os.path.exists(_CONFIG_PATH):
        return dict(_DEFAULTS)
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        user_config = json.load(f)
    return _deep_merge(_DEFAULTS, user_config)


CONTENT_CONFIG: dict = _load()
