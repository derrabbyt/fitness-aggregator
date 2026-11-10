"""Free text in the coach chat goes to the model (coach-chat + context-log on
top of coach-core); tool calls the model makes are executed by code, and
their results go back to the model before it writes the reply."""

from fa_coach.ports import ModelError
from fakes import reply, tool_call


async def test_free_text_goes_to_the_model_and_its_reply_to_the_user(coach, model, outbox):
    model.script(reply("Your weight is trending up as planned."))

    await coach.on_message("how am I doing?")

    request = model.requests[0]
    assert request.prefix_skills[0] == "coach-core"
    assert request.task_skills == ("coach-chat", "context-log")
    assert request.input == {"message": "how am I doing?"}
    assert outbox.texts == ["Your weight is trending up as planned."]


async def test_scope_and_language_rules_come_with_every_chat_message(coach, model):
    model.script(reply("That's outside what this coach does."))

    await coach.on_message("should I take creatine?")

    assert model.requests[0].prefix_skills == ("coach-core",)  # no phase yet
    core = coach.skills.skill("coach-core")
    assert "Language: always English" in core
    assert "Medical" in core and "supplement recommendations" in core and "Technique" in core
    chat = coach.skills.skill("coach-chat")
    assert "CC-OUT-OF-SCOPE" in chat and "one line" in chat


async def test_the_chat_offers_the_context_and_profile_tools(coach, model):
    model.script(reply("ok"))

    await coach.on_message("hi")

    names = {t["name"] for t in model.requests[0].tools}
    assert {"add_context_note", "get_context_notes", "update_coach_profile", "get_coach_profile"} <= names
    assert "set_week_sport_load" not in names


async def test_the_chat_keeps_a_short_recent_history(coach, model, clock):
    for i in range(5):
        model.script(reply(f"answer {i}"))
        await coach.on_message(f"question {i}")

    history = model.requests[-1].history
    assert [(t.role, t.text) for t in history] == [
        ("user", "question 1"),
        ("assistant", "answer 1"),
        ("user", "question 2"),
        ("assistant", "answer 2"),
        ("user", "question 3"),
        ("assistant", "answer 3"),
    ]

    clock.advance(days=1)
    model.script(reply("fresh"))
    await coach.on_message("new day")

    assert model.requests[-1].history == ()


async def test_tool_traffic_stays_out_of_the_history(coach, model):
    model.script(
        tool_call("add_context_note", applies_from="2026-11-09", applies_to="2026-11-09", tags=["alcohol"], suggest_unusable="no"),
        reply("Noted: drinks tonight."),
        reply("ok"),
    )
    await coach.on_message("a few drinks tonight")
    await coach.on_message("thanks")

    assert [(t.role, t.text) for t in model.requests[-1].history] == [
        ("user", "a few drinks tonight"),
        ("assistant", "Noted: drinks tonight."),
    ]


async def test_an_unreachable_model_gets_one_line(coach, model, outbox):
    model.script(ModelError("connection failed"))

    await coach.on_message("how am I doing?")

    assert len(outbox.texts) == 1
    assert "\n" not in outbox.texts[0]
    assert "connection failed" in outbox.texts[0]


async def test_commands_never_reach_the_model(coach, model, outbox):
    await coach.on_message("/profile")

    assert model.requests == []
