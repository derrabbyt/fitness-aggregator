"""/profile shows the coach profile (empty until the chat can change it)."""


async def test_profile_starts_empty(coach, outbox):
    await coach.on_message("/profile")

    assert outbox.texts == ["Your coach profile is empty."]
