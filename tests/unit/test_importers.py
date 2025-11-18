
import pytest

from app.services.importers import (_dedup_key, _detect_kind, _normalize_text,
                                    parse_collections_file, parse_items_file)


def test_normalize_text():
    s = "  Привет\tмир\xa0  "
    assert _normalize_text(s) == "Привет мир"


def test_dedup_key_case_and_spaces():
    assert _dedup_key("Hello  WORLD") == _dedup_key("  hello world ")


def test_detect_kind_csv_by_content():
    data = b"question,answer\nq,a\n"
    kind = _detect_kind("file.txt", None, data)
    assert kind == "csv"


def test_parse_items_file_basic():
    csv_bytes = (
        "question,answer\n"
        " Q1 , A1 \n"
        " Q2 , A2 \n"
        " , \n"
    ).encode("utf-8")

    pairs = parse_items_file("items.csv", csv_bytes)
    assert pairs == [("Q1", "A1"), ("Q2", "A2")]


def test_parse_items_file_deduplicates_questions():
    csv_bytes = (
        "question,answer\n"
        "Q1,A1\n"
        "Q1,A2\n"
    ).encode("utf-8")

    pairs = parse_items_file("items.csv", csv_bytes)
    assert pairs == [("Q1", "A1")]


def test_parse_items_file_raises_on_empty():
    csv_bytes = "question,answer\n,\n".encode("utf-8")
    with pytest.raises(ValueError):
        parse_items_file("items.csv", csv_bytes)


def test_parse_collections_file_groups_by_title():
    csv_bytes = (
        "title,question,answer\n"
        " Set1 , Q1 , A1 \n"
        " Set1 , Q2 , A2 \n"
        " Set2 , Q3 , A3 \n"
    ).encode("utf-8")

    grouped = parse_collections_file("cols.csv", csv_bytes)
    assert set(grouped.keys()) == {"Set1", "Set2"}
    assert grouped["Set1"] == [("Q1", "A1"), ("Q2", "A2")]
    assert grouped["Set2"] == [("Q3", "A3")]


def test_parse_collections_file_deduplicates_per_collection():
    csv_bytes = (
        "title,question,answer\n"
        "Set,Q1,A1\n"
        "Set,Q1,A2\n"
    ).encode("utf-8")

    grouped = parse_collections_file("cols.csv", csv_bytes)
    assert grouped["Set"] == [("Q1", "A1")]


def test_parse_collections_file_missing_columns():
    csv_bytes = "q,a\n1,2\n".encode("utf-8")
    with pytest.raises(ValueError):
        parse_collections_file("cols.csv", csv_bytes)
