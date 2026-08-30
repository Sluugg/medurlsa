"""
Covers share-link ID generation (app/routes/admin.py) — the entire security
boundary for a share link rests on these being the right length and
genuinely unpredictable. See TECHNICAL.md's "Client identification" section.
"""

import re

from app.config import LINK_ID_LENGTH
from app.routes.admin import _generate_link_id


def test_generated_ids_match_the_configured_length():
    for _ in range(20):
        assert len(_generate_link_id()) == LINK_ID_LENGTH


def test_generated_ids_are_url_safe():
    for _ in range(20):
        assert re.fullmatch(r"[A-Za-z0-9_-]+", _generate_link_id())


def test_generated_ids_are_unique_across_many_calls():
    ids = {_generate_link_id() for _ in range(500)}
    assert len(ids) == 500
