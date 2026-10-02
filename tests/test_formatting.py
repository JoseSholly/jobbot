from jobbot.domain.models import Profile, ScoreBreakdown, ScoredJob, Slot
from jobbot.services.formatting import TELEGRAM_LIMIT, render_digest, render_profile
from tests.fakes import job


def item(i, **kw):
    j = job("Engineer", f"Acme {i}", **kw)
    j.title = f"Engineer <{i}> & co"  # already-normalized text can still contain HTML chars
    return ScoredJob(job=j, score=87.4, breakdown=ScoreBreakdown(0, 0, 0, 0), reason="Uses <Django>")


def test_digest_escapes_and_has_buttons():
    [msg] = render_digest(Slot.MORNING, [item(1), item(2)])
    assert msg.text.startswith("<b>Morning digest: 2 jobs</b>")
    assert "Engineer &lt;1&gt; &amp; co" in msg.text
    assert "Uses &lt;Django&gt;" in msg.text
    assert "Match 87%" in msg.text
    assert len(msg.buttons) == 2
    assert msg.buttons[0][0].callback_data.startswith("s:")
    assert all(len(b.callback_data.encode()) <= 64 for row in msg.buttons for b in row)


def test_long_digest_is_split_under_limit():
    items = [item(i, description="x") for i in range(10)]
    for it in items:
        it.reason = "y" * 190
        it.job.url = "https://example.com/" + "z" * 600
    messages = render_digest(Slot.EVENING, items)
    assert len(messages) >= 2
    assert all(len(m.text) <= TELEGRAM_LIMIT for m in messages)
    assert sum(len(m.buttons) for m in messages) == 10


def test_location_line_and_profile_render():
    [msg] = render_digest(Slot.MORNING, [item(1, location="Worldwide")])
    assert "Remote - Worldwide" in msg.text
    text = render_profile(Profile(skills=["C++ <x>"])).text
    assert "C++ &lt;x&gt;" in text
