"""The coach profile: /profile shows it; telling the coach a preference
changes it (update_coach_profile); the model can read it."""

from fakes import reply, tool_call


async def test_profile_starts_empty(coach, outbox):
    await coach.on_message("/profile")

    assert outbox.texts == ["Your coach profile is empty."]


async def test_a_preference_in_chat_updates_the_profile(coach, model, outbox):
    model.script(
        tool_call("update_coach_profile", patch={"quiet hours": "no messages before 9:00"}),
        reply("Profile updated: no messages before 9:00."),
    )

    await coach.on_message("don't message me before 9")
    await coach.on_message("/profile")

    assert outbox.texts == [
        "Profile updated: no messages before 9:00.",
        "Your coach profile:\n- quiet hours: no messages before 9:00",
    ]


async def test_a_profile_entry_can_be_changed_and_removed(coach, model, outbox):
    model.script(
        tool_call("update_coach_profile", patch={"left knee": "sensitive on lunges", "quiet hours": "before 9:00"}),
        reply("Noted."),
        tool_call("update_coach_profile", patch={"left knee": None, "quiet hours": "before 8:00"}),
        reply("Updated."),
    )
    await coach.on_message("my left knee is sensitive on lunges, and no messages before 9")
    await coach.on_message("knee is fine now; 8 is ok")

    outbox.clear()
    await coach.on_message("/profile")

    assert outbox.texts == ["Your coach profile:\n- quiet hours: before 8:00"]


async def test_the_model_reads_the_profile(coach, model):
    model.script(
        tool_call("update_coach_profile", patch={"units": "kg"}),
        reply("ok"),
        tool_call("get_coach_profile"),
        reply("You prefer kg."),
    )
    await coach.on_message("use kg")
    await coach.on_message("what do you know about me?")

    assert model.results(2)[0].content == {"profile": {"units": "kg"}}
    # The profile also travels in every task's state snapshot.
    assert model.requests[-1].state["profile"] == {"units": "kg"}


async def test_an_oversized_profile_entry_is_refused(coach, model, outbox):
    model.script(
        tool_call("update_coach_profile", patch={"notes": "x" * 1000}),
        reply("That's too long for the profile."),
    )

    await coach.on_message("remember this whole essay")

    assert model.results(0)[0].is_error
    outbox.clear()
    await coach.on_message("/profile")
    assert outbox.texts == ["Your coach profile is empty."]
