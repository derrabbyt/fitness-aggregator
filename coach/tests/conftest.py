import pytest

from fa_coach.core import Coach
from fakes import FakeApi, FakeClock, FakeModel, FakeOutbox


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def api() -> FakeApi:
    return FakeApi()


@pytest.fixture
def model() -> FakeModel:
    return FakeModel()


@pytest.fixture
def outbox() -> FakeOutbox:
    return FakeOutbox()


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "coach.db"


@pytest.fixture
def make_coach(db_path, api, model, clock, outbox):
    """A Coach with the real features (or a given registry) over one database file.
    Calling it again opens the same database, like a restart."""

    def make(**overrides) -> Coach:
        kwargs = dict(api=api, model=model, clock=clock, outbox=outbox)
        kwargs.update(overrides)
        return Coach(db_path, **kwargs)

    return make


@pytest.fixture
def coach(make_coach) -> Coach:
    return make_coach()
