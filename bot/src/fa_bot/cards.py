"""Telegram text for confirmation cards and their results (HTML parse mode)."""

import datetime
import re
from html import escape

from .changes import Change, is_old

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _num(value: float | None) -> str:
    return "?" if value is None else f"{value:.0f}"


def _date(date: str, today: datetime.date | None = None) -> str:
    today = today or datetime.date.today()
    day = datetime.date.fromisoformat(date)
    text = f"<b>{WEEKDAYS[day.weekday()]} {day.day}.{day.month}.{day.year if day.year != today.year else ''}</b>"
    if is_old(date, today):
        text += f" ⚠️ {(today - day).days} days ago"
    return text


def _amount(quantity: float, label: str | None) -> str:
    """30 × "1 g" -> "30 g"; 1.5 × "1 Dose" -> "1.5× 1 Dose"."""
    if not label:
        return f"{quantity:g}×"
    unit = re.fullmatch(r"1\s*(g|gram|grams|gramm|ml|milliliter)", label.strip(), re.IGNORECASE)
    if unit:
        return f"{quantity:g} {'ml' if unit.group(1).lower().startswith('m') else 'g'}"
    return label if quantity == 1 else f"{quantity:g}× {label}"


def _lines(change: Change) -> list[str]:
    lines = []
    for a in change.adds:
        name = f"{a.brand} – {a.name}" if a.brand and a.brand.lower() not in a.name.lower() else a.name
        lines.append(
            f"➕ {escape(name)} — {escape(_amount(a.quantity, a.serving_label))}\n"
            f"     {_num(a.kcal)} kcal · P {_num(a.protein)} · K {_num(a.carbs)} · F {_num(a.fat)}"
        )
    for q in change.quick_adds:
        generic = q.label.strip().lower() in ("", "quick add")
        lines.append(
            ("⚡ Quick Add" if generic else f"⚡ Quick Add: {escape(q.label)} (≈ estimate)") + "\n"
            f"     {_num(q.kcal)} kcal · P {_num(q.protein)} · K {_num(q.carbs)} · F {_num(q.fat)}"
        )
    for r in change.removes:
        lines.append(f"➖ {escape(r.name)} — {_num(r.kcal)} kcal")
    return lines


def card_text(change: Change, today: datetime.date | None = None) -> str:
    meals = {a.meal for a in change.adds} | {q.meal for q in change.quick_adds} | {r.meal for r in change.removes}
    meal = f" · {escape(', '.join(sorted({m.title() for m in meals})))}" if meals else ""
    total = (
        sum(a.kcal or 0 for a in change.adds)
        + sum(q.kcal for q in change.quick_adds)
        - sum(r.kcal or 0 for r in change.removes)
    )
    return "\n".join([f"📝 {_date(change.date, today)}{meal}", *_lines(change), f"Σ {total:+.0f} kcal"])


def status_text(change: Change, status: str, today: datetime.date | None = None) -> str:
    """A card that no longer runs: cancelled, expired or replaced."""
    label = {"cancelled": "❌ cancelled", "expired": "⌛ expired, nothing logged", "superseded": "↩️ replaced"}.get(
        status, status
    )
    return f"<s>{card_text(change, today)}</s>\n{label}"


def result_text(change: Change, result: dict, today: datetime.date | None = None) -> str:
    lines = [f"📝 {_date(change.date, today)}"]
    for outcome in result["outcomes"]:
        mark = "✅" if outcome["ok"] else "⚠️"
        line = f"{mark} {escape(outcome['item'])}"
        if outcome["error"]:
            line += f"\n     {escape(outcome['error'])}"
        lines.append(line)
    n = result.get("nutrition")
    if n:
        goal = f" / {_num(n.get('goal_calories'))}" if n.get("goal_calories") else ""
        lines.append(
            f"Σ {_num(n.get('calories'))}{goal} kcal · P {_num(n.get('protein'))} g · "
            f"K {_num(n.get('carbs'))} g · F {_num(n.get('fat'))} g"
        )
    elif result.get("day_error"):
        lines.append(f"⚠️ couldn't read the diary afterwards: {escape(result['day_error'])}")
    return "\n".join(lines)
