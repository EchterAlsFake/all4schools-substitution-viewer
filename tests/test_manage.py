from __future__ import annotations

import json

import pytest

from backend.database import Database
from backend.manage import (
    MAX_SOURCE_BYTES,
    TeacherImportError,
    import_teacher_file,
    main,
    parse_teacher_file,
)


def test_import_teachers_validates_deduplicates_and_sanitizes_cache(
    settings, tmp_path, monkeypatch, capsys
):
    source = tmp_path / "private-teachers.txt"
    source.write_text(
        "Frau Beispielperson\nHerr Dr. Testperson\nFrau Beispielperson\n",
        encoding="utf-8",
    )
    settings.cache_path.write_text(
        json.dumps(
            {
                "version": "before-import",
                "days": [
                    {
                        "date": "2026-08-24",
                        "entries": [
                            {
                                "oldSubject": "Beispielperson",
                                "newSubject": "",
                                "comment": "Rückfrage bei Testperson.",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("backend.manage.Settings.load", lambda: settings)

    assert main(["import-teachers", str(source)]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output == {
        "ok": True,
        "school_year": output["school_year"],
        "recognized_entries": 2,
        "redaction_values": 4,
        "newly_stored_values": 4,
        "cache_rewritten": True,
    }
    database = Database(settings.database_path)
    stored = database.learned_teacher_names(output["school_year"])
    assert set(stored) == {
        "Frau Beispielperson",
        "Beispielperson",
        "Herr Dr. Testperson",
        "Testperson",
    }
    cache = json.loads(settings.cache_path.read_text(encoding="utf-8"))
    assert cache["days"][0]["entries"][0]["oldSubject"] == "Lehrkraft"
    assert cache["days"][0]["entries"][0]["comment"] == "Rückfrage bei Lehrkraft."
    assert cache["version"] != "before-import"


def test_import_rejects_invalid_and_sql_injection_lines_without_partial_storage(
    settings, tmp_path
):
    source = tmp_path / "invalid-teachers.txt"
    source.write_text(
        "Frau Beispielperson\nHerr Test'); DROP TABLE learned_courses;--\n",
        encoding="utf-8",
    )

    with pytest.raises(TeacherImportError) as error:
        import_teacher_file(settings, source)

    assert error.value.code == "invalid_lines"
    assert error.value.line_numbers == (2,)
    assert not settings.database_path.exists()


def test_database_import_uses_bound_values_for_untrusted_names(settings):
    database = Database(settings.database_path)
    database.initialize()
    injection = "Test'); DROP TABLE learned_courses;--"

    assert database.import_teacher_names("2026-2027", {injection}) == 1
    database.learn("2026-2027", {"12_SAFE1"}, set())

    assert database.learned_courses("2026-2027") == ["12_SAFE1"]
    assert database.learned_teacher_names("2026-2027") == [injection]


def test_teacher_file_requires_utf8_titled_names_and_a_bounded_size(tmp_path):
    invalid_encoding = tmp_path / "invalid-encoding.txt"
    invalid_encoding.write_bytes(b"Frau M\xfcller")
    with pytest.raises(TeacherImportError, match="source_not_utf8"):
        parse_teacher_file(invalid_encoding)

    empty = tmp_path / "empty.txt"
    empty.write_text("\n", encoding="utf-8")
    with pytest.raises(TeacherImportError, match="no_names"):
        parse_teacher_file(empty)

    oversized = tmp_path / "oversized.txt"
    oversized.write_bytes(b"x" * (MAX_SOURCE_BYTES + 1))
    with pytest.raises(TeacherImportError, match="source_too_large"):
        parse_teacher_file(oversized)


def test_command_does_not_leak_names_when_storage_fails(
    settings, tmp_path, monkeypatch, capsys
):
    source = tmp_path / "private-teachers.txt"
    source.write_text("Frau Beispielperson\n", encoding="utf-8")
    monkeypatch.setattr("backend.manage.Settings.load", lambda: settings)

    def fail_import(*_args, **_kwargs):
        raise RuntimeError("Frau Beispielperson")

    monkeypatch.setattr("backend.manage.Database.import_teacher_names", fail_import)

    assert main(["import-teachers", str(source)]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err) == {"ok": False, "code": "import_failed"}
    assert "Beispielperson" not in output.err
