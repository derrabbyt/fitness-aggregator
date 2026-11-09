"""The Coach core's dispatch: commands, free text, buttons, jobs and sync
reach the features registered for them, and nothing else happens."""

import datetime

from fa_coach.ports import Button, Edit, Send
from fa_coach.registry import Registry


async def test_unknown_command_lists_the_commands(coach, outbox):
    await coach.on_message("/start")

    assert len(outbox.texts) == 1
    assert "/profile" in outbox.texts[0]


async def test_free_text_without_a_chat_handler_lists_the_commands(coach, outbox):
    await coach.on_message("how am I doing?")

    assert len(outbox.texts) == 1
    assert "/profile" in outbox.texts[0]


async def test_a_tap_reaches_its_button_handler(make_coach, outbox):
    registry = Registry()

    @registry.command("card", "Show a card")
    async def card(coach, args, now):
        coach.say("Raise by 100 kcal?", buttons=((Button("Approve", "approve", "p1"),),), ref="proposal:p1")

    @registry.button("approve")
    async def approve(coach, ref_id, now):
        coach.edit(f"proposal:{ref_id}", "Approved.")

    coach = make_coach(registry=registry)
    await coach.on_message("/card")
    await coach.on_button("approve", "p1")

    assert outbox.items == [
        Send("Raise by 100 kcal?", ((Button("Approve", "approve", "p1"),),), "proposal:p1"),
        Edit("proposal:p1", "Approved."),
    ]


async def test_a_tap_on_an_unknown_button_does_nothing(coach, outbox):
    await coach.on_button("approve", "gone")

    assert outbox.items == []


def daily_hello(registry: Registry) -> None:
    @registry.job("hello")
    async def hello(coach, now):
        if coach.db.once(f"hello:{now.date()}", now):
            coach.say(f"Good morning, {now.date()}")


async def test_a_job_runs_once_per_day_even_across_restarts(make_coach, clock, outbox):
    registry = Registry()
    daily_hello(registry)

    await make_coach(registry=registry).run_due_jobs()
    await make_coach(registry=registry).run_due_jobs(clock.advance(hours=3))
    await make_coach(registry=registry).run_due_jobs(clock.advance(days=1))

    assert outbox.texts == ["Good morning, 2026-11-09", "Good morning, 2026-11-10"]


async def test_a_failing_job_does_not_stop_the_others(make_coach, outbox):
    registry = Registry()

    @registry.job("broken", order=1)
    async def broken(coach, now):
        raise RuntimeError("boom")

    daily_hello(registry)

    await make_coach(registry=registry).run_due_jobs()

    assert outbox.texts == ["Good morning, 2026-11-09"]


async def test_sync_runs_every_source_even_if_one_fails(make_coach, clock):
    registry = Registry()
    seen: list[tuple[str, datetime.datetime]] = []

    @registry.syncer("mfp", order=1)
    async def mfp(coach, now):
        raise RuntimeError("502 Bad Gateway")

    @registry.syncer("hevy", order=2)
    async def hevy(coach, now):
        seen.append(("hevy", now))

    await make_coach(registry=registry).sync()

    assert seen == [("hevy", clock.now())]
