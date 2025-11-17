from __future__ import annotations

from typing import Iterable, List, Tuple, Optional
import html


def fmt_online_root() -> str:
    return (
        "🤼 <b>Онлайн режим</b>\n\n"
        "• Создай комнату, выбери коллекцию и позови друзей.\n"
        "• До 30 игроков в одной комнате.\n"
        "• Владелец видит live-рейтинг, игроки отвечают на вопросы в реальном времени."
    )


def fmt_room_waiting(
    title: str,
    room_id: str,
    seconds_per_question: int,
    points_per_correct: int,
    players_count: int,
    deep_link: Optional[str] = None,
) -> str:
    title_safe = html.escape(title)
    lines: List[str] = [
        f"🧩 Коллекция: <b>{title_safe}</b>",
        "",
        f"🔢 Код комнаты: <code>{room_id}</code>",
        f"⏱ Время на ответ: <b>{seconds_per_question}</b> сек.",
        f"🏆 Баллы за верный ответ: <b>{points_per_correct}</b>",
        "",
        f"👥 Подключено игроков: <b>{players_count}</b>",
    ]

    if deep_link:
        lines.append("")
        lines.append("🔗 Пригласительная ссылка для игроков:")
        lines.append(html.escape(deep_link))

    lines.append("")
    lines.append("Когда все подключатся, нажми <b>«🚀 Начать игру»</b>.")
    lines.append(
        "Через кнопки ниже можно изменить <b>время на ответ</b> "
        "и <b>баллы за верный ответ</b>."
    )
    return "\n".join(lines)


def fmt_player_waiting(
    title: str,
    room_id: str,
    seconds_per_question: int,
    points_per_correct: int,
) -> str:
    title_safe = html.escape(title)
    return (
        f"🧩 Коллекция: <b>{title_safe}</b>\n"
        f"🔢 Код комнаты: <code>{room_id}</code>\n\n"
        "Ожидаем старт игры…\n\n"
        f"⏱ Время на ответ: <b>{seconds_per_question}</b> сек.\n"
        f"🏆 Баллы за верный ответ: <b>{points_per_correct}</b>\n\n"
        "Владелец комнаты может поменять настройки перед стартом.\n"
        "Если что-то пошло не так — нажми «🚪 Выйти из комнаты»."
    )


def fmt_online_question(
    title: str,
    q: str,
    idx: int,
    total: int,
    seconds_per_question: int,
) -> str:
    title_safe = html.escape(title)
    q_safe = html.escape(q)
    return (
        f"🧩 <b>{title_safe}</b>\n"
        f"❓ Вопрос {idx}/{total}\n\n"
        f"{q_safe}\n\n"
        f"⏱ У тебя <b>{seconds_per_question}</b> сек. на ответ.\n"
        "Просто отправь сообщение с ответом."
    )


def fmt_online_answer(
    title: str,
    q: str,
    a: str,
    idx: int,
    total: int,
) -> str:
    title_safe = html.escape(title)
    q_safe = html.escape(q)
    a_safe = html.escape(a)
    return (
        f"🧩 <b>{title_safe}</b>\n"
        f"❓ Вопрос {idx}/{total}\n\n"
        f"{q_safe}\n\n"
        f"✅ Правильный ответ: <b>{a_safe}</b>"
    )


def fmt_owner_scoreboard(title: str, lines: Iterable[str]) -> str:
    title_safe = html.escape(title)
    body = "\n".join(lines) if lines else "Пока никто не набрал очков."
    return (
        f"🏁 <b>Игра завершена</b>\n"
        f"🧩 Коллекция: <b>{title_safe}</b>\n\n"
        "📊 Итоговый рейтинг игроков:\n\n"
        f"{body}"
    )


def format_top_lines(top: Iterable[Tuple[str, int, float]]) -> str:
    lines: List[str] = []
    for i, (name, score, total_answer_time) in enumerate(top, start=1):
        name_safe = html.escape(name)
        seconds = int(round(total_answer_time))
        lines.append(f"{i}. {name_safe} — {score} очков — {seconds} сек.")
    return "\n".join(lines) if lines else "Пока нет результатов."


def fmt_player_scoreboard(
    title: str,
    place: Optional[int],
    score: int,
    total_answer_time: float,
    top_lines: str,
) -> str:
    title_safe = html.escape(title)

    if place is None:
        place_line = "Твоё место: неизвестно (ошибка определения места)."
    else:
        place_line = f"Твоё место: <b>{place}</b>."

    seconds = int(round(total_answer_time))

    return (
        f"🏁 <b>Игра завершена</b>\n"
        f"🧩 Коллекция: <b>{title_safe}</b>\n\n"
        f"{place_line}\n"
        f"Твои очки: <b>{score}</b>\n"
        f"Суммарное время ответов: <b>{seconds}</b> сек.\n\n"
        "🏆 <b>ТОП-3 игроков:</b>\n"
        f"{top_lines}"
    )
