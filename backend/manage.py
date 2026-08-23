from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

from .config import Settings
from .database import Database
from .upstream import (
    BERLIN,
    sanitize_cached_plan,
    school_year,
    teacher_name_variants,
)


MAX_SOURCE_BYTES = 256 * 1024
MAX_IMPORTED_NAMES = 1_000
PERSON_NAME_PART = (
    r"[A-ZÄÖÜÀ-ÖØ-ÞĀ-Ž]"
    r"[A-Za-zÄÖÜäöüßÀ-ÖØ-öø-ÿĀ-ž'’-]{1,60}"
)
TITLED_NAME_RE = re.compile(
    rf"^(?:Frau|Herr)\s+(?:(?:Dr|Prof)\.\s+)?{PERSON_NAME_PART}"
    rf"(?:\s+{PERSON_NAME_PART}){{0,2}}$"
)


class TeacherImportError(ValueError):
    def __init__(self, code: str, line_numbers: tuple[int, ...] = ()) -> None:
        super().__init__(code)
        self.code = code
        self.line_numbers = line_numbers


@dataclass(frozen=True, slots=True)
class TeacherImportResult:
    ok: bool
    school_year: str
    recognized_entries: int
    redaction_values: int
    newly_stored_values: int
    cache_rewritten: bool


def parse_teacher_file(source: Path) -> tuple[str, ...]:
    try:
        payload = source.read_bytes()
    except OSError as exc:
        raise TeacherImportError("source_unreadable") from exc
    if len(payload) > MAX_SOURCE_BYTES:
        raise TeacherImportError("source_too_large")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TeacherImportError("source_not_utf8") from exc

    names_by_key: dict[str, str] = {}
    invalid_lines: list[int] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        normalized = unicodedata.normalize("NFC", " ".join(raw_line.split()))
        if len(normalized) > 200 or TITLED_NAME_RE.fullmatch(normalized) is None:
            invalid_lines.append(line_number)
            continue
        names_by_key.setdefault(normalized.casefold(), normalized)
        if len(names_by_key) > MAX_IMPORTED_NAMES:
            raise TeacherImportError("too_many_names")
    if invalid_lines:
        raise TeacherImportError("invalid_lines", tuple(invalid_lines[:20]))
    if not names_by_key:
        raise TeacherImportError("no_names")
    return tuple(sorted(names_by_key.values(), key=str.casefold))


def import_teacher_file(settings: Settings, source: Path) -> TeacherImportResult:
    imported_names = parse_teacher_file(source)
    redaction_values: set[str] = set()
    for name in imported_names:
        redaction_values.update(teacher_name_variants(name))

    current_school_year = school_year(datetime.now(BERLIN).date())
    database = Database(settings.database_path)
    database.initialize()
    added = database.import_teacher_names(current_school_year, redaction_values)
    all_names = set(database.learned_teacher_names(current_school_year))
    cache_rewritten = sanitize_cached_plan(settings.cache_path, all_names)
    return TeacherImportResult(
        ok=True,
        school_year=current_school_year,
        recognized_entries=len(imported_names),
        redaction_values=len(redaction_values),
        newly_stored_values=added,
        cache_rewritten=cache_rewritten,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m backend.manage")
    subparsers = parser.add_subparsers(dest="command", required=True)
    import_parser = subparsers.add_parser("import-teachers")
    import_parser.add_argument("source", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        result = import_teacher_file(Settings.load(), arguments.source)
    except TeacherImportError as exc:
        error: dict[str, object] = {"ok": False, "code": exc.code}
        if exc.line_numbers:
            error["lineNumbers"] = list(exc.line_numbers)
        print(json.dumps(error, separators=(",", ":")), file=sys.stderr)
        return 2
    except Exception:
        print('{"ok":false,"code":"import_failed"}', file=sys.stderr)
        return 1
    print(json.dumps(asdict(result), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
