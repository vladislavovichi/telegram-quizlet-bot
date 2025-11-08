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


def fmt_finished_summary(title: str, total: int, counts: dict, total_sec: int) -> str:
    acc = accuracy(
        counts.get("known", 0), counts.get("known", 0) + counts.get("unknown", 0)
    )
    dur = human_duration(total_sec)
    return (
        f"✔️ Все карточки в «{escape(title)}» просмотрены!\n\n"
        f"<b>Итоги</b>\n"
        f"• Всего карточек: <b>{total}</b>\n"
        f"• Знал: <b>{counts.get('known', 0)}</b>\n"
        f"• Не знал: <b>{counts.get('unknown', 0)}</b>\n"
        f"• Пропущено: <b>{counts.get('skipped', 0)}</b>\n"
        f"• Без оценки: <b>{counts.get('neutral', 0)}</b>\n"
        f"• Точность: <b>{acc}%</b>\n"
        f"• Время: <b>{dur}</b>"
    )


def fmt_choose_collection() -> str:
    return "Выбери коллекцию для игры:"


def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def human_duration(total_sec: int) -> str:
    total_sec = int(total_sec or 0)
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    if h:
        return f"{h} ч {m} мин {s} с"
    if m:
        return f"{m} мин {s} с"
    return f"{s} с"


def accuracy(known: int, total_answered: int) -> int:
    if total_answered <= 0:
        return 0
    return round(100 * known / total_answered)
