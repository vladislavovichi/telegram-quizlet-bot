from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

try:
    from openpyxl import load_workbook  # type: ignore
except Exception:
    load_workbook = None  # type: ignore


def parse_items_file(
    file_name: str,
    file_bytes: bytes,
    mime_type: Optional[str] = None,
) -> List[Tuple[str, str]]:
    kind = _detect_kind(file_name, mime_type, file_bytes)

    if kind == "xlsx":
        rows = _read_xlsx(file_bytes)
    else:
        rows = _read_csv(file_bytes)

    header_map = _build_header_map(rows.headers)

    q_key = header_map.get("question")
    a_key = header_map.get("answer")

    if not q_key or not a_key:
        raise ValueError(
            "Ожидались колонки 'question' и 'answer' (или их синонимы). Найдены: "
            + ", ".join(rows.headers)
        )

    seen: set[str] = set()
    pairs: List[Tuple[str, str]] = []
    for row in rows.iter_dicts():
        q_raw = (row.get(q_key) or "").strip()
        a_raw = (row.get(a_key) or "").strip()
        if not q_raw or not a_raw:
            continue
        q = _normalize_text(q_raw)
        a = _normalize_text(a_raw)
        dedup_key = _dedup_key(q)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        pairs.append((q, a))

    if not pairs:
        raise ValueError("Файл прочитан, но валидных пар 'вопрос-ответ' не найдено.")

    return pairs


def parse_collections_file(
    file_name: str,
    file_bytes: bytes,
    mime_type: Optional[str] = None,
) -> Dict[str, List[Tuple[str, str]]]:
    kind = _detect_kind(file_name, mime_type, file_bytes)

    if kind == "xlsx":
        rows = _read_xlsx(file_bytes)
    else:
        rows = _read_csv(file_bytes)

    header_map = _build_header_map(rows.headers)

    t_key = header_map.get("title")
    q_key = header_map.get("question")
    a_key = header_map.get("answer")
    if not t_key or not q_key or not a_key:
        raise ValueError(
            "Ожидались колонки 'title', 'question', 'answer' (или их синонимы). Найдены: "
            + ", ".join(rows.headers)
        )

    grouped: Dict[str, List[Tuple[str, str]]] = {}
    seen_per_title: Dict[str, set[str]] = {}

    for row in rows.iter_dicts():
        t_raw = (row.get(t_key) or "").strip()
        q_raw = (row.get(q_key) or "").strip()
        a_raw = (row.get(a_key) or "").strip()
        if not t_raw or not q_raw or not a_raw:
            continue
        title = _normalize_text(t_raw)
        q = _normalize_text(q_raw)
        a = _normalize_text(a_raw)

        dd = _dedup_key(q)
        seen = seen_per_title.setdefault(title, set())
        if dd in seen:
            continue
        seen.add(dd)
        grouped.setdefault(title, []).append((q, a))

    if not grouped:
        raise ValueError("Файл прочитан, но коллекции не обнаружены.")

    return grouped


@dataclass(slots=True)
class _RowSet:
    headers: List[str]
    rows: List[List[str]]

    def iter_dicts(self) -> Iterable[Dict[str, str]]:
        idx = {i: h for i, h in enumerate(self.headers)}
        for r in self.rows:
            d: Dict[str, str] = {}
            for i, v in enumerate(r[: len(self.headers)]):

                d[idx[i]] = v if isinstance(v, str) else ("" if v is None else str(v))
            yield d


def _build_header_map(headers: Iterable[str]) -> Dict[str, str]:
    aliases = {
        "title": {"title", "название", "коллекция", "collection", "deck"},
        "question": {"question", "вопрос", "q", "term", "front"},
        "answer": {"answer", "ответ", "a", "definition", "back"},
    }
    lower = {h.lower().strip(): h for h in headers}
    mapping: Dict[str, str] = {}
    for canon, names in aliases.items():
        for name in names:
            if name in lower:
                mapping[canon] = lower[name]
                break
    return mapping


def _normalize_text(s: str) -> str:
    return " ".join((s or "").replace("\xa0", " ").split()).strip()


def _dedup_key(s: str) -> str:
    return _normalize_text(s).lower()


def _detect_kind(file_name: str, mime_type: Optional[str], file_bytes: bytes) -> str:
    name = (file_name or "").lower()
    if name.endswith(".xlsx") or (
        mime_type
        and mime_type
        in ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",)
    ):
        if load_workbook is None:
            raise ValueError(
                "Поддержка .xlsx не установлена (нет openpyxl). Установите 'openpyxl' или пришлите CSV."
            )
        return "xlsx"

    txt = _safe_peek_text(file_bytes, limit=2048)
    if "," in txt or ";" in txt or "\t" in txt or "question" in txt.lower():
        return "csv"
    if name.endswith(".csv"):
        return "csv"

    return "csv"


def _safe_peek_text(data: bytes, limit: int = 1024) -> str:
    return _decode_bytes(data[:limit])


def _read_csv(file_bytes: bytes) -> _RowSet:
    text = _decode_bytes(file_bytes)

    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(
            text.splitlines()[0] if text.splitlines() else text, delimiters=",;\t"
        )
    except Exception:

        class _D(csv.Dialect):
            delimiter = ","
            quotechar = '"'
            doublequote = True
            skipinitialspace = True
            lineterminator = "\n"
            quoting = csv.QUOTE_MINIMAL

        dialect = _D()
    reader = csv.reader(io.StringIO(text), dialect)
    rows: List[List[str]] = [
        list(r) for r in reader if any((c or "").strip() for c in r)
    ]
    if not rows:
        return _RowSet(headers=[], rows=[])
    headers = [h.strip() for h in rows[0]]
    data = rows[1:]

    norm_rows: List[List[str]] = []
    for r in data:
        if len(r) < len(headers):
            r = r + ["" for _ in range(len(headers) - len(r))]
        norm_rows.append(r[: len(headers)])
    return _RowSet(headers=headers, rows=norm_rows)


def _read_xlsx(file_bytes: bytes) -> _RowSet:
    if load_workbook is None:
        raise ValueError(
            "Поддержка .xlsx не установлена (нет openpyxl). Установите 'openpyxl' или пришлите CSV."
        )
    wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active
    rows: List[List[str]] = []
    headers: List[str] = []
    first = True
    for row in ws.iter_rows(values_only=True):
        vals = [
            (v if isinstance(v, str) else ("" if v is None else str(v))).strip()
            for v in row
        ]
        if first:
            headers = [v for v in vals]
            first = False
            continue
        if any(v.strip() for v in vals):
            rows.append(vals[: len(headers)])
    wb.close()
    return _RowSet(headers=headers, rows=rows)


def _decode_bytes(b: bytes) -> str:
    for enc in (
        "utf-8-sig",
        "utf-8",
        "cp1251",
        "windows-1251",
        "iso-8859-5",
        "koi8-r",
        "latin-1",
    ):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode("utf-8", errors="replace")
