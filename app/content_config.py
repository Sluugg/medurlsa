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
    # Deployment-wide master switch for the whole visual flavor system
    # (title glitch/jitter/color-cycle, background, floating flavor text,
    # logo overlay). Distinct from the per-link `flavor_enabled` DB column,
    # which only has effect when this is true. Defaults to off so a fresh
    # clone with no content_config.json renders a plain watch page.
    "animations_enabled": False,
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
        "pearl_border": {
            "cycle_rate_s":    8,
            "border_width_px": 2,
        },
        "jitter": {
            "delay_ms":    300,
            "distance_px": 4,
        },
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
