"""Confirmation cards: nothing is written without a tap, a tap runs once,
cards expire, and failures are reported, never retried."""

import datetime

import pytest
from pydantic_ai import ModelRetry

from fa_bot.agent import AddItem, Deps, DraftCache, RemoveItem, build_change
from fa_bot.cards import card_text, result_text
from fa_bot.changes import EXPIRY_SECONDS, ChangeStore, execute

TODAY = datetime.date(2026, 11, 5)
DRAFT = {
    "draft_id": "d1",
    "query": "banane",
    "day": "2026-11-05",
    "meal": "breakfast",
    "quantity": 2.0,
    "options": [
        {
            "option": 1,
            "name": "Banane",
            "suggested_serving": 0,
            "servings": [{"serving": 0, "label": "1 medium", "calories": 210.0, "protein": 2.6, "carbs": 54.0, "fat": 0.8}],
        }
    ],
}
DAY = {
    "diary": [{"meal": "Breakfast", "name": "Magerquark 250 g", "calories": 150, "protein": 30, "carbs": 10, "fat": 1}],
    "nutrition": {"calories": 150, "goal_calories": 2100, "protein": 30, "carbs": 10, "fat": 1},
}


class FakeMfp:
    """Records every call; writes can be made to fail."""

    def __init__(self, fail: set[str] = frozenset(), land_anyway: bool = False):
        self.calls: list[tuple[str, dict]] = []
        self.fail = fail
        self.land_anyway = land_anyway
        self.diary = list(DAY["diary"])

    async def __call__(self, name, args):
        self.calls.append((name, args))
        if name == "fitness_get_day":
            return {"diary": list(self.diary), "nutrition": DAY["nutrition"]}
        if name in self.fail:
            if self.land_anyway and name == "fitness_log_food":
                self.diary.append({"meal": "Breakfast", "name": "Banane"})
            if self.land_anyway and name == "fitness_quick_add":
                self.diary.append({"meal": "Breakfast", "name": "Quick Add, 1 serving(s)"})
            raise RuntimeError("502 Bad Gateway")
        if name == "fitness_log_food":
            self.diary.append({"meal": "Breakfast", "name": "Banane"})
        if name == "fitness_quick_add":
            self.diary.append({"meal": "Breakfast", "name": "Quick Add, 1 serving(s)"})
        if name == "fitness_delete_food":
            self.diary = [e for e in self.diary if e["name"] != args["query"]]
        return {"ok": True}

    def writes(self):
        return [c for c in self.calls if c[0] != "fitness_get_day"]


def deps(**kw):
    drafts = DraftCache()
    drafts.put(DRAFT)
    return Deps(chat_id=1, call=FakeMfp(), drafts=drafts, today=TODAY, **kw)


@pytest.fixture
def store(tmp_path):
    now = [1_000_000.0]
    s = ChangeStore(tmp_path / "bot.db", clock=lambda: now[0])
    s.now = now
    return s


def make_change(store, **kw):
    change = build_change(deps(), "2026-11-05", [AddItem(draft_id="d1", option=1)], [], None)
    change.created_at = store.now[0]
    store.add(change)
    return change


# --- building cards --------------------------------------------------------


def test_card_numbers_come_from_the_draft():
    change = build_change(deps(), "2026-11-05", [AddItem(draft_id="d1", option=1)], [], None)
    add = change.adds[0]
    assert (add.name, add.kcal, add.quantity, add.meal) == ("Banane", 210.0, 2.0, "breakfast")
    assert "210 kcal" in card_text(change, TODAY)


@pytest.mark.parametrize(
    "date,item,message",
    [
        ("2026-11-05", AddItem(draft_id="nope", option=1), "unknown draft_id"),
        ("2026-11-04", AddItem(draft_id="d1", option=1), "draft again with date=2026-11-04"),
        ("2026-11-05", AddItem(draft_id="d1", option=2), "option must be"),
        ("2026-11-05", AddItem(draft_id="d1", option=1, serving=3), "serving must be"),
        ("2026-11-06", AddItem(draft_id="d1", option=1), "future"),
    ],
)
def test_bad_proposals_go_back_to_the_model(date, item, message):
    with pytest.raises(ModelRetry, match=message):
        build_change(deps(), date, [item], [], None)


def test_remove_uses_the_exact_logged_name():
    change = build_change(deps(), "2026-11-05", [], [RemoveItem(name="magerquark 250 g")], DAY)
    assert change.removes[0].name == "Magerquark 250 g"
    with pytest.raises(ModelRetry, match="Logged that day: Breakfast: Magerquark"):
        build_change(deps(), "2026-11-05", [], [RemoveItem(name="Skyr")], DAY)


def test_old_dates_are_flagged():
    change = build_change(deps(), "2026-11-05", [AddItem(draft_id="d1", option=1)], [], None)
    change.date = "2026-10-01"
    assert "⚠️ 35 days ago" in card_text(change, TODAY)


# --- taps ------------------------------------------------------------------


def test_only_the_first_tap_runs(store):
    change = make_change(store)
    assert store.claim(change.id, 1)[0] == "ok"
    assert store.claim(change.id, 1)[0] == "running"
    store.finish(change.id, {})
    assert store.claim(change.id, 1)[0] == "done"


def test_tap_from_another_chat_is_ignored(store):
    change = make_change(store)
    assert store.claim(change.id, 2) == ("unknown", None)
    assert store.claim(change.id, 1)[0] == "ok"


def test_cards_expire(store):
    change = make_change(store)
    store.now[0] += EXPIRY_SECONDS + 1
    assert store.claim(change.id, 1)[0] == "expired"
    assert store.claim(change.id, 1)[0] == "expired"


def test_cancelled_card_never_runs(store):
    change = make_change(store)
    assert store.cancel(change.id, 1)[0] == "ok"
    assert store.claim(change.id, 1)[0] == "cancelled"


def test_new_card_replaces_pending_one(store):
    first = make_change(store)
    second = make_change(store)
    assert store.claim(first.id, 1)[0] == "superseded"
    assert store.claim(second.id, 1)[0] == "ok"


def test_claims_survive_a_restart(store, tmp_path):
    change = make_change(store)
    assert store.claim(change.id, 1)[0] == "ok"
    reopened = ChangeStore(tmp_path / "bot.db", clock=lambda: store.now[0])
    assert reopened.claim(change.id, 1)[0] == "running"


# --- execution -------------------------------------------------------------


async def test_each_write_is_sent_once_adds_first():
    change = build_change(
        deps(), "2026-11-05", [AddItem(draft_id="d1", option=1)], [RemoveItem(name="Magerquark 250 g")], DAY
    )
    mfp = FakeMfp()
    result = await execute(change, mfp)
    assert [c[0] for c in mfp.writes()] == ["fitness_log_food", "fitness_delete_food"]
    assert mfp.writes()[0][1] == {
        "draft_id": "d1", "option": 1, "serving": 0, "quantity": 2.0, "meal": "breakfast", "date": "2026-11-05",
    }
    assert all(o["ok"] for o in result["outcomes"])
    assert "Σ 150 / 2100 kcal" in result_text(change, result, TODAY)


async def test_failed_write_is_reported_not_retried():
    change = build_change(deps(), "2026-11-05", [AddItem(draft_id="d1", option=1)], [], None)
    mfp = FakeMfp(fail={"fitness_log_food"})
    result = await execute(change, mfp)
    assert len(mfp.writes()) == 1
    assert result["outcomes"][0] == {"item": "+ Banane", "ok": False, "error": "502 Bad Gateway"}
    assert "502 Bad Gateway" in result_text(change, result, TODAY)


async def test_failed_write_that_landed_anyway_says_so():
    change = build_change(deps(), "2026-11-05", [AddItem(draft_id="d1", option=1)], [], None)
    mfp = FakeMfp(fail={"fitness_log_food"}, land_anyway=True)
    result = await execute(change, mfp)
    assert len(mfp.writes()) == 1
    assert result["outcomes"][0]["error"] == "502 Bad Gateway (but it is in the diary now)"


def test_model_gets_no_write_tools():
    from fa_bot.agent import MFP_READ_TOOLS

    assert not [t for t in MFP_READ_TOOLS if any(w in t for w in ("log_", "delete", "modify", "clear", "write"))]


def test_past_foods_groups_filters_and_ranks():
    from fa_bot.agent import past_foods

    days = [
        {"day": "2026-11-01", "diary": [
            {"meal": "Breakfast", "name": "Clever Thunfisch Saft - Thunfisch, 1.5 Dose", "calories": 140},
            {"meal": "Breakfast", "name": "Quick Add, 1 serving(s)", "calories": 700},
            {"meal": "Breakfast", "name": "HSN - HSN Whey, 30 g", "calories": 125},
        ]},
        {"day": "2026-11-03", "diary": [
            {"meal": "Lunch", "name": "Clever Thunfisch Saft - Thunfisch, 1.5 Dose", "calories": 141},
        ]},
    ]
    foods = past_foods(days, None)
    assert [f["name"].split(" ")[0] for f in foods] == ["Clever Thunfisch Saft", "HSN"]
    assert foods[0] | {"name": None} == {
        "name": None, "times": 2, "last_logged": "2026-11-03", "meals": ["Breakfast", "Lunch"],
        "calories": 141, "protein": None, "carbs": None, "fat": None,
    }
    assert [f["name"] for f in past_foods(days, "thunfisch saft")] == [days[1]["diary"][0]["name"]]
    assert past_foods(days, "quick") == []


@pytest.mark.parametrize(
    "quantity,label,expected",
    [(30, "1 g", "30 g"), (250, "1 ml", "250 ml"), (1.5, "1 Dose", "1.5× 1 Dose"), (1, "1 medium", "1 medium"), (2, None, "2×")],
)
def test_amount_text(quantity, label, expected):
    from fa_bot.cards import _amount

    assert _amount(quantity, label) == expected


def test_absurd_amounts_go_back_to_the_model():
    d = deps()
    big = {**DRAFT, "draft_id": "d2", "quantity": 200.0, "options": [{**DRAFT["options"][0], "servings": [
        {"serving": 0, "label": "100 Gramm", "calories": 11801.0, "protein": 1, "carbs": 1, "fat": 1}]}]}
    d.drafts.put(big)
    with pytest.raises(ModelRetry, match="quantity counts servings"):
        build_change(d, "2026-11-05", [AddItem(draft_id="d2", option=1)], [], None)


# --- quick add -------------------------------------------------------------

from fa_bot.agent import QuickAddItem  # noqa: E402

DOENER = QuickAddItem(label="Döner Kebab, groß", calories=700, protein=35, carbs=70, fat=30, meal="lunch")


def test_quick_add_card():
    change = build_change(deps(), "2026-11-05", [], [], None, [DOENER])
    text = card_text(change, TODAY)
    assert "⚡ Quick Add: Döner Kebab, groß (≈ estimate)" in text and "700 kcal" in text and "Σ +700 kcal" in text


@pytest.mark.parametrize(
    "item,message",
    [
        (QuickAddItem(label="x", calories=0), "calories must be"),
        (QuickAddItem(label="x", calories=5000), "calories must be"),
        (QuickAddItem(label="x", calories=700, protein=10, carbs=10, fat=10), "make them consistent"),
        (QuickAddItem(label="x", calories=200, protein=-1), "negative"),
    ],
)
def test_bad_quick_adds_go_back_to_the_model(item, message):
    with pytest.raises(ModelRetry, match=message):
        build_change(deps(), "2026-11-05", [], [], None, [item])


async def test_quick_add_is_sent_once():
    change = build_change(deps(), "2026-11-05", [], [], None, [DOENER])
    mfp = FakeMfp()
    result = await execute(change, mfp)
    assert mfp.writes() == [("fitness_quick_add", {
        "calories": 700, "protein": 35, "carbs": 70, "fat": 30, "meal": "lunch", "date": "2026-11-05"})]
    assert result["outcomes"][0]["ok"]


async def test_failed_quick_add_that_landed_anyway_says_so():
    change = build_change(deps(), "2026-11-05", [], [], None, [DOENER])
    mfp = FakeMfp(fail={"fitness_quick_add"}, land_anyway=True)
    result = await execute(change, mfp)
    assert len(mfp.writes()) == 1
    assert result["outcomes"][0]["error"].endswith("(but it is in the diary now)")


def test_old_cards_without_quick_adds_still_load(store):
    change = make_change(store)
    raw = change.to_json().replace(', "quick_adds": []', "")
    assert ChangeStore.__module__ and "quick_adds" not in raw
    from fa_bot.changes import Change
    assert Change.from_json(raw).quick_adds == []
