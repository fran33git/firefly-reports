"""The clock seam: frozen time is scoped and restores itself."""

from datetime import date, datetime

from firefly_reports import clock


def test_frozen_clock_overrides_now_and_today():
    with clock.frozen(datetime(2026, 1, 15, 12, 0)):
        assert clock.now() == datetime(2026, 1, 15, 12, 0)
        assert clock.today() == date(2026, 1, 15)
    assert clock.today() == date.today()


def test_frozen_clock_restores_after_an_exception():
    try:
        with clock.frozen(datetime(2026, 1, 15)):
            raise RuntimeError
    except RuntimeError:
        pass
    assert clock.today() == date.today()
