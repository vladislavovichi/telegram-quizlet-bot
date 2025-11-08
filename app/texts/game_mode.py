from __future__ import annotations


def fmt_question(title: str, q: str, progress: str) -> str:
    return (
        f"🧩 <b>{escape(title)}</b>\n\n"
        f"<b>Вопрос:</b>\n{escape(q)}\n\n"
        f"Прогресс: <code>{progress}</code>"
    )


def fmt_answer(title: str, q: str, a: str, progress: str) -> str:
    return (
        f"🧩 <b>{escape(title)}</b>\n\n"
        f"<b>Вопрос:</b>\n{escape(q)}\n\n"
        f"<b>Ответ:</b>\n{escape(a)}\n\n"
        f"Прогресс: <code>{progress}</code>"
    )


def fmt_finished(title: str) -> str:
    return f"✔️ Все карточки в «{escape(title)}» просмотрены!"


def fmt_choose_collection() -> str:
    return "Выбери коллекцию для игры:"


def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
