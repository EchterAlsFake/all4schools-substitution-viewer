from __future__ import annotations

import json
import re
from pathlib import Path

from backend.config import Settings


I18N_DIR = Path(__file__).resolve().parents[1] / "public" / "i18n"
PLACEHOLDER_RE = re.compile(r"\{([A-Za-z0-9_]+)\}")


def test_enabled_catalogs_have_identical_keys_and_placeholders():
    languages = json.loads((I18N_DIR / "languages.json").read_text(encoding="utf-8"))
    catalogs = {
        language["code"]: json.loads(
            (I18N_DIR / f"{language['code']}.json").read_text(encoding="utf-8")
        )
        for language in languages["languages"]
    }
    source = catalogs["de"]
    source_keys = set(source) - {"_meta"}

    for code, catalog in catalogs.items():
        assert set(catalog) - {"_meta"} == source_keys, code
        assert all(isinstance(value, str) and "<" not in value for key, value in catalog.items() if key != "_meta")
        for key in source_keys:
            assert sorted(PLACEHOLDER_RE.findall(catalog[key])) == sorted(
                PLACEHOLDER_RE.findall(source[key])
            ), f"{code}:{key}"


def test_real_gate_answers_are_not_in_tracked_catalogs():
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in I18N_DIR.glob("*.json")
    )
    for answer in Settings.load().gate_answers:
        assert answer not in combined


def test_transparency_notice_remains_german_in_every_catalog():
    languages = json.loads((I18N_DIR / "languages.json").read_text(encoding="utf-8"))
    notice_keys = {
        "transparency.title",
        "transparency.architecture",
        "transparency.relay",
        "transparency.costs",
        "transparency.close",
    }
    source = json.loads((I18N_DIR / "de.json").read_text(encoding="utf-8"))

    for language in languages["languages"]:
        catalog = json.loads(
            (I18N_DIR / f"{language['code']}.json").read_text(encoding="utf-8")
        )
        assert {key: catalog[key] for key in notice_keys} == {
            key: source[key] for key in notice_keys
        }


def test_aggregate_visit_count_is_disclosed_without_claiming_no_analytics():
    index = (I18N_DIR.parents[1] / "index.html").read_text(encoding="utf-8")
    assert 'src="/__eaf/visit.js"' in index
    for code in ("de", "en"):
        catalog = json.loads((I18N_DIR / f"{code}.json").read_text(encoding="utf-8"))
        disclosure = catalog["privacy.no_tracking.text"].lower()
        assert "cookie" in disclosure
        assert "day" in disclosure or "tag" in disclosure
