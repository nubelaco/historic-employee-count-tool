from datetime import date

from main import EmployeeCount


def test_time_ranges():
    time_ranges = EmployeeCount.get_month_ranges(12)
    assert time_ranges[3]['start'].month == 12
    # We add 1 to the length of time_ranges because we first push one to the start
    # for the current month. This was a change in logic after the script was first
    # written to correct an off-by-one error.
    assert len(time_ranges) == len(range(12)) + 1 == 12 + 1


def test_identifier():
    assert EmployeeCount.identifier("https://www.linkedin.com/company/fandomwikia") == 'fandomwikia'
    assert EmployeeCount.identifier("https://www.linkedin.com/company/fandomwikia/") == 'fandomwikia'


def test_active_during():
    january = {
        "start": date(year=2023, month=1, day=1),
        "end": date(year=2023, month=1, day=31)
    }
    december = {
        "start": date(year=2022, month=12, day=1),
        "end": date(year=2022, month=12, day=31)
    }
    assert EmployeeCount.active_during(january, date(year=2022, month=10, day=15), date(year=2022, month=12, day=31)) is False
    assert EmployeeCount.active_during(january, date(year=2023, month=2, day=1), date(year=2023, month=2, day=5)) is False
    assert EmployeeCount.active_during(january, date(year=2022, month=10, day=15), date(year=2023, month=12, day=31)) is True

    assert EmployeeCount.active_during(december, date(year=2022, month=10, day=15), date(year=2022, month=11, day=30)) is False
    assert EmployeeCount.active_during(december, date(year=2023, month=11, day=1), date(year=2023, month=11, day=30)) is False
    assert EmployeeCount.active_during(december, date(year=2022, month=10, day=15), date(year=2023, month=12, day=31)) is True
    # We want the equality test to succeed because the intervals are non-overlapping
    assert EmployeeCount.active_during(december, date(year=2022, month=12, day=31), date(year=2023, month=12, day=31)) is True


def test_get_limited_sample_of_urls():
    test_data = ["hello"] * 50
    limit = 20
    assert len(EmployeeCount.get_limited_sample_of_urls(test_data, limit)) == 20
