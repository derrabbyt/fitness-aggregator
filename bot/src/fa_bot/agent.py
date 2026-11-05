"""The Pydantic AI agent: read tools from the api's MCP endpoint plus one tool
that proposes diary changes. It has no way to write to MyFitnessPal itself."""

import datetime
import os
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.mcp import MCPToolset

from .changes import Add, CallTool, Change, QuickAdd, Remove, _norm

# The only mfp tools the model sees. Everything that writes (log/delete/modify
# food, weight, water, notes, pins) is left out; food writes go through cards.
MFP_READ_TOOLS = {
    "fitness_get_day",
    "fitness_get_activity",
    "fitness_search_food",
    "fitness_draft_food",
    "fitness_list_food_pins",
    "fitness_get_exercise",
    "fitness_get_exercise_entries",
    "fitness_get_note",
    "fitness_get_trends",
    "fitness_bulk_export",
}

MAX_QUICK_ADD_KCAL = 3000
MAX_ITEM_KCAL = 1500  # a single entry above this is almost always a quantity mix-up
DRAFT_OPTIONS = 5  # options per food draft; each lists every serving, so this drives input tokens

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

INSTRUCTIONS = """\
You are the user's fitness assistant in a private Telegram chat. Reply briefly,
in the language the user writes in (usually German or English), in metric units,
as plain text (no Markdown). Emojis are fine.

Tools: MyFitnessPal (`fitness_*`, read-only; steps and synced runs are in
`fitness_get_activity`) and Hevy strength workouts (`hevy_*`, read-only). You
cannot write to MyFitnessPal directly.

Food diary changes (adding, removing, replacing foods):
1. For each food to add, call `fitness_draft_food` with the quantity and the
   date. quantity = number of servings: for "200 g" either draft quantity=200
   and pick a "1 g" serving, or pick a "100 g" serving with quantity=2. Check
   the option's kcal for the whole entry makes sense before proposing. Use calorie/macro ranges when you know them (from a label, or "200
   kcal of X"). Prefer pinned and verified options and servings in grams when
   the user gave grams. German and English names both work; if the first query
   finds nothing good, try the other language or a simpler name.
   For anything specific ("mein Thunfisch", "the usual whey", "same as
   Tuesday"), first look at what the user logged before: `find_past_foods`
   (by keyword, or without one for the most frequent foods) or
   `fitness_get_day` for a given day. Then draft that exact food: the brand and
   food part of its name as the query, the same quantity, and min/max_calories
   within about 10% of its past kcal, and pick the option that matches it.
2. To remove or replace an entry, read the day with `fitness_get_day` and use
   the entry's exact name.
3. Call `propose_diary_change` once with everything from the message (a
   replacement = remove the old entry + add the new one). The user then sees a
   card with ✅/❌ buttons; nothing is written until they tap ✅.
4. After proposing, answer with one short line at most; the card shows the
   details. Don't claim anything was logged, and never say you prepared a card
   unless `propose_diary_change` succeeded. If the user corrects something,
   draft again and propose a new card (it replaces the old one).

The default meal is breakfast (the user logs everything there) unless they name
another. Dates: "today" is {today}; "gestern"/"yesterday" is {yesterday}. Use
past dates when the user says so.

Quick Add (calories without a food) is the fallback, via `quick_add` items in
`propose_diary_change`:
- when the user asks for it ("add 200 kcal"), or
- when nothing fits after you tried their history (`find_past_foods`) and the
  food search with a simpler name and the other language, e.g. a restaurant
  dish, a homemade meal, or something only shown in a photo.
Estimate realistically: think about the portion size (a typical serving if
none is given, or what the photo shows) and known values for similar dishes,
and estimate protein/carbs/fat in grams so they roughly add up to the kcal
(4/4/9 kcal per g). Give a short label ("Döner Kebab, groß"). Don't use Quick
Add for foods the search finds; mixing is fine (e.g. bread from the search +
a Quick Add for the homemade spread).

Photos: read packaging labels (kcal and macros per 100 g / per portion) and
draft with matching ranges; for plates of food, estimate and say so.

Voice notes arrive transcribed and may mishear names and numbers.

Never reveal secrets. Telegram access is managed only by the user on the server.
"""


class AddItem(BaseModel):
    draft_id: str = Field(description="draft_id from fitness_draft_food")
    option: int = Field(description="option number from that draft (1-based)")
    serving: int | None = Field(None, description="serving index of that option; default its suggested_serving")


class QuickAddItem(BaseModel):
    label: str = Field(description="short description of what was eaten, e.g. 'Döner Kebab, groß'")
    calories: float = Field(description="estimated kcal for the whole portion")
    protein: float | None = Field(None, description="estimated grams")
    carbs: float | None = Field(None, description="estimated grams")
    fat: float | None = Field(None, description="estimated grams")
    meal: str = Field("breakfast", description="breakfast|lunch|dinner|snacks")


class RemoveItem(BaseModel):
    name: str = Field(description="the entry's exact name from fitness_get_day")
    meal: str | None = Field(None, description="the entry's meal, if several entries share the name")


@dataclass
class Deps:
    chat_id: int
    call: CallTool  # direct mfp tool calls (reads only, from here)
    drafts: "DraftCache"
    card: Change | None = None
    today: datetime.date = field(default_factory=datetime.date.today)


class DraftCache:
    """Drafts the model fetched, by draft_id. Cards are built from these, so the
    numbers on a card come from MFP, not from the model."""

    def __init__(self, size: int = 200):
        self.size = size
        self._drafts: OrderedDict[str, dict] = OrderedDict()

    def put(self, draft: dict) -> None:
        self._drafts[draft["draft_id"]] = draft
        self._drafts.move_to_end(draft["draft_id"])
        while len(self._drafts) > self.size:
            self._drafts.popitem(last=False)

    def get(self, draft_id: str) -> dict | None:
        return self._drafts.get(draft_id)


def past_foods(days: list[dict], query: str | None, limit: int = 25) -> list[dict]:
    """Foods from exported diary days, grouped by exact entry name, most used
    first; `query` words must all appear (case- and space-insensitive)."""
    words = _norm(query).split() if query else []
    foods: dict[str, dict] = {}
    for day in days:
        for e in day.get("diary") or []:
            name = e.get("name") or ""
            norm = _norm(name)
            if not name or norm.startswith("quick add") or not all(w in norm for w in words):
                continue
            food = foods.setdefault(name, {"name": name, "times": 0, "last_logged": "", "meals": set()})
            food["times"] += 1
            food["meals"].add(e.get("meal"))
            if day["day"] >= food["last_logged"]:  # nutrition of the most recent entry
                food["last_logged"] = day["day"]
                food.update({k: e.get(k) for k in ("calories", "protein", "carbs", "fat")})
    ranked = sorted(foods.values(), key=lambda f: f["last_logged"], reverse=True)
    ranked.sort(key=lambda f: f["times"], reverse=True)  # stable: ties stay most recent first
    return [{**f, "meals": sorted(m for m in f["meals"] if m)} for f in ranked[:limit]]


def build_change(
    deps: Deps,
    date: str,
    add: list[AddItem],
    remove: list[RemoveItem],
    day: dict | None,
    quick_add: list[QuickAddItem] | None = None,
) -> Change:
    """Validate a proposal against cached drafts and the day's entries. Raises
    ModelRetry with a fix-it message for the model."""
    try:
        day_date = datetime.date.fromisoformat(date)
    except ValueError:
        raise ModelRetry(f"date must be YYYY-MM-DD, got {date!r}") from None
    if day_date > deps.today:
        raise ModelRetry("date is in the future")
    quick_add = quick_add or []
    if not add and not remove and not quick_add:
        raise ModelRetry("nothing to propose: pass add, quick_add and/or remove items")

    change = Change(chat_id=deps.chat_id, date=date)
    for item in add:
        draft = deps.drafts.get(item.draft_id)
        if draft is None:
            raise ModelRetry(f"unknown draft_id {item.draft_id!r}: call fitness_draft_food first")
        if draft["day"] != date:
            raise ModelRetry(f"draft {item.draft_id} is for {draft['day']}, not {date}: draft again with date={date}")
        options = draft["options"]
        if not 1 <= item.option <= len(options):
            raise ModelRetry(f"option must be 1..{len(options)} for draft {item.draft_id}")
        option = options[item.option - 1]
        servings = option["servings"]
        index = option["suggested_serving"] if item.serving is None else item.serving
        if servings and not 0 <= index < len(servings):
            raise ModelRetry(f"serving must be 0..{len(servings) - 1} for option {item.option}")
        serving: dict[str, Any] = servings[index] if servings else {}
        if (serving.get("calories") or 0) > MAX_ITEM_KCAL:
            raise ModelRetry(
                f"{option['name']} would be {serving['calories']:.0f} kcal ({draft['quantity']:g} × "
                f"{serving.get('label')}): quantity counts servings, so 200 g with a 100 g serving is quantity 2. "
                "Draft again with the right quantity, or pick a matching serving."
            )
        change.adds.append(
            Add(
                draft_id=item.draft_id,
                option=item.option,
                serving=index if servings else 0,
                name=option["name"],
                serving_label=serving.get("label"),
                quantity=draft["quantity"],
                meal=draft["meal"],
                kcal=serving.get("calories"),
                protein=serving.get("protein"),
                carbs=serving.get("carbs"),
                fat=serving.get("fat"),
                brand=option.get("brand"),
            )
        )

    for item in quick_add:
        if not 0 < item.calories <= MAX_QUICK_ADD_KCAL:
            raise ModelRetry(f"quick_add calories must be 1..{MAX_QUICK_ADD_KCAL}; split a bigger meal into parts")
        macros = [v for v in (item.protein, item.carbs, item.fat) if v is not None]
        if any(v < 0 for v in macros):
            raise ModelRetry("macros can't be negative")
        if len(macros) == 3:
            from_macros = 4 * item.protein + 4 * item.carbs + 9 * item.fat
            if abs(from_macros - item.calories) > max(0.25 * item.calories, 40):
                raise ModelRetry(
                    f"macros give {from_macros:.0f} kcal but calories is {item.calories:.0f}: make them consistent"
                )
        change.quick_adds.append(
            QuickAdd(
                label=item.label.strip()[:60] or "Quick Add",
                meal=item.meal or "breakfast",
                kcal=round(item.calories),
                protein=item.protein,
                carbs=item.carbs,
                fat=item.fat,
            )
        )

    entries = (day or {}).get("diary") or []
    for item in remove:
        matches = [
            e
            for e in entries
            if _norm(e.get("name")) == _norm(item.name)
            and (item.meal is None or _norm(e.get("meal")) == _norm(item.meal))
        ]
        if not matches:
            listed = "; ".join(f"{e.get('meal')}: {e.get('name')}" for e in entries) or "nothing"
            raise ModelRetry(f"no entry named {item.name!r} on {date}. Logged that day: {listed}")
        entry = matches[0]
        change.removes.append(Remove(name=entry["name"], meal=entry.get("meal") or "breakfast", kcal=entry.get("calories")))
    return change


def build_agent(model: str, tools_url: str) -> tuple[Agent[Deps, str], MCPToolset]:
    for key in [k for k, v in os.environ.items() if k.endswith("_BASE_URL") and not v]:
        del os.environ[key]  # compose passes unset ones as "", which the SDKs treat as a URL
    async def capture_drafts(ctx: RunContext[Deps], call_tool, name: str, args: dict[str, Any]):
        if name == "fitness_draft_food":
            args = {**args, "limit": min(int(args.get("limit") or DRAFT_OPTIONS), DRAFT_OPTIONS)}
        result = await call_tool(name, args)
        if name == "fitness_draft_food" and isinstance(result, dict) and "draft_id" in result:
            ctx.deps.drafts.put(result)
        return result

    mfp = MCPToolset(
        f"{tools_url}/mfp/mcp", id="mfp", init_timeout=10, read_timeout=180, process_tool_call=capture_drafts
    )
    hevy = MCPToolset(f"{tools_url}/hevy/mcp", id="hevy", init_timeout=10, read_timeout=120)

    agent = Agent(
        model,
        deps_type=Deps,
        toolsets=[mfp.filtered(lambda _ctx, tool: tool.name in MFP_READ_TOOLS), hevy],
    )

    @agent.instructions
    def instructions(ctx: RunContext[Deps]) -> str:
        today = ctx.deps.today
        yesterday = today - datetime.timedelta(days=1)
        return INSTRUCTIONS.format(
            today=f"{WEEKDAYS[today.weekday()]} {today.isoformat()}",
            yesterday=yesterday.isoformat(),
        )

    @agent.tool
    async def find_past_foods(ctx: RunContext[Deps], query: str | None = None, days: int = 180) -> dict:
        """Foods the user logged before, most used first, with the entry's exact
        name (brand - food, serving), times logged, last date, meals, and kcal
        and macros of one entry. query: keywords (German or English, as logged),
        or none for the most frequent foods. days: how far back (max 365).
        Quick Adds are left out (they can't be re-logged)."""
        days = max(1, min(days, 365))
        start = (ctx.deps.today - datetime.timedelta(days=days)).isoformat()
        export = await ctx.deps.call("fitness_bulk_export", {"start": start, "end": ctx.deps.today.isoformat()})
        foods = past_foods(export.get("days") or [], query)
        note = None if foods else "nothing found: try fewer or other keywords, or the other language"
        return {"since": start, "foods": foods, **({"note": note} if note else {})}

    @agent.tool
    async def propose_diary_change(
        ctx: RunContext[Deps],
        date: str,
        add: list[AddItem] | None = None,
        quick_add: list[QuickAddItem] | None = None,
        remove: list[RemoveItem] | None = None,
    ) -> str:
        """Show the user a confirmation card for food diary changes on one date
        (YYYY-MM-DD). add: foods from fitness_draft_food drafts. quick_add:
        estimated calories (+ macros) when no food fits. remove: existing
        entries by exact name. Nothing is written until the user taps ✅."""
        day = await ctx.deps.call("fitness_get_day", {"date": date}) if remove else None
        ctx.deps.card = build_change(ctx.deps, date, add or [], remove or [], day, quick_add or [])
        return "Card ready; it is shown to the user after your reply. Nothing is written until they tap ✅."

    return agent, mfp
