import pytest

from jobbot.domain.regions import is_nigerian, location_allows

OK = ["Nigeria", "Worldwide", "Africa", "EMEA"]


@pytest.mark.parametrize("loc", ["Lagos", "Abuja, FCT", "Port Harcourt, Rivers", "Nigeria"])
def test_is_nigerian(loc):
    assert is_nigerian(loc)


@pytest.mark.parametrize("loc", ["Berlin", "Remote - USA", "Johannesburg"])
def test_not_nigerian(loc):
    assert not is_nigerian(loc)


@pytest.mark.parametrize(
    "loc",
    [
        "",
        "Worldwide",
        "Remote",
        "Anywhere in the World",
        "EMEA",
        "Africa",
        "Remote, EMEA",
        "Nigeria, Kenya",
        "Fully remote",
    ],
)
def test_location_allows(loc):
    assert location_allows(loc, OK)


@pytest.mark.parametrize("loc", ["USA Only", "Remote - US", "Europe", "Berlin", "LATAM"])
def test_location_rejects(loc):
    assert not location_allows(loc, OK)


def test_location_rejects_bare_remote_when_user_does_not_accept_worldwide():
    assert not location_allows("Remote", ["Nigeria"])
    assert location_allows("Remote, Africa", ["Nigeria"])
