import pytest

from app.services.importers import (
    _decode_bytes,
    _detect_kind,
    parse_collections_file,
    parse_items_file,
)


def test_decode_bytes_fallback_and_trim():
    s = _decode_bytes("  test\xa0".encode("cp1251"))
    assert "test" in s.replace("\xa0", " ").strip()


def test_detect_kind_unknown_extension_treated_as_csv():
    kind = _detect_kind("notes.custom", None, b"q,a\n1,2")
    assert kind == "csv"


def test_parse_collections_file_ignores_empty_and_whitespace_only():
    csv_bytes = (
        "title,question,answer\n" "Set,Q1,A1\n" "Set, , \n" "Set,\t,\t\n"
    ).encode("utf-8")
    grouped = parse_collections_file("cols.csv", csv_bytes)
    assert grouped["Set"] == [("Q1", "A1")]


def test_parse_items_file_raises_when_no_valid_pairs():
    csv_bytes = ("question,answer\n" "Q1, \n" " ,A2\n").encode("utf-8")
    with pytest.raises(ValueError):
        parse_items_file("items.csv", csv_bytes)
