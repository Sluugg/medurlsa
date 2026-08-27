"""
Loads content_config.json from the project root and merges it over hardcoded
defaults. Read at import time and again whenever reload_content_config() runs
(the admin settings page calls this right after writing the file, via
save_content_config() — see app/routes/settings.py) — no restart required for
changes made that way. A manual edit of the file on disk still needs either a
restart or a save from the settings page to be picked up.
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
    # Independent of animations_enabled — lets the floating flavor-text
    # feature specifically be turned off while background/logo/title effects
    # stay on. Has no effect if animations_enabled (or the per-link
    # flavor_enabled) is already off.
    "flavor_texts_enabled": True,
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


def reload_content_config() -> None:
    """
    Re-read content_config.json from disk. Mutates CONTENT_CONFIG in place
    (clear + update, not reassignment) so every module that already did
    `from app.content_config import CONTENT_CONFIG` sees the change — that
    import binds to this dict object, not a copy of its current contents.
    """
    CONTENT_CONFIG.clear()
    CONTENT_CONFIG.update(_load())


def save_content_config(updates: dict) -> None:
    """
    Shallow-merge `updates` onto whatever's currently on disk (creating the
    file from defaults if it doesn't exist yet), write it back, and reload
    CONTENT_CONFIG so the change applies immediately. Only touches the
    top-level keys present in `updates` — any custom timing/font overrides
    already in the file that aren't managed by the settings page are left
    untouched.
    """
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            current = json.load(f)
    else:
        current = {}
    current.update(updates)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
        f.write("\n")
    reload_content_config()
