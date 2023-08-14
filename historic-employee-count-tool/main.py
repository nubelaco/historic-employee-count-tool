import asyncio
import calendar
import logging
import sys
from datetime import date, timedelta
from random import shuffle
from typing import Dict, List, Optional, Callable, TypeVar
from typing_extensions import ParamSpec

import backoff as backoff
import requests
from proxycurl_py.asyncio import do_bulk, Proxycurl
from proxycurl_py.asyncio.base import Result, ProxycurlException
from requests import HTTPError, Response

from errors import NoCurrentDataException

try:
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
except AttributeError:
    pass

# By default, the proxycurl library logs an error on 404s. We're expecting this, though, so we'll silence
# exception-level logging for this script.
logger = logging.getLogger()
logger.setLevel(logging.CRITICAL)


class EmployeeCount:
    count_endpoint = 'https://nubela.co/proxycurl/api/linkedin/company/employees/count'
    listing_endpoint = 'https://nubela.co/proxycurl/api/linkedin/company/employees/'
    person_endpoint = 'https://nubela.co/proxycurl/api/v2/linkedin'
    DEFAULT_MONTH_COUNT = 36
    DEFAULT_LIMIT = 3000

    # Set this flag for testing; it won't paginate past the limit, so you can test on a fast query.
    # Use in conjunction with the `page_size` parameter in `query_past_employee_urls`
    should_run_full_query = False

    def __init__(self, key: str, url: str, months: Optional[int], limit: Optional[int]):
        self.key = key
        self.url = url
        self.proxycurl = Proxycurl(api_key=key)
        # month_ranges has a length of months+1 because we include the current month in our offset.
        # So we won't store months for later access, since it won't give us an accurante size.
        self.month_ranges = self.get_month_ranges(months if months is not None else self.DEFAULT_MONTH_COUNT)
        self.limit = limit if limit is not None else self.DEFAULT_LIMIT

    async def main(self):
        current_employee_count = self.query_current_employee_count()
        if current_employee_count == 0:
            raise NoCurrentDataException
        past_employee_urls = self.query_past_employee_urls()
        past_employee_profiles = await self.query_past_counts(past_employee_urls)
        past_employee_counts = self.get_past_employee_counts(past_employee_profiles)
        adjusted_employee_accounts = self.get_adjusted_employee_counts(past_employee_counts, current_employee_count)
        self.print_output(adjusted_employee_accounts)

    def query_current_employee_count(self) -> int:
        # Retrieve the total count of employees on linkedin, including those we cannot scrape.
        # We'll scale our tenure trend data by this number, since tenures can only include
        # scrapable profiles.
        params = {
            'use_cache': 'if-recent',
            'linkedin_employee_count': 'include',
            'employment_status': 'current',
            'url': self.url,
        }
        response = requests.get(self.count_endpoint,
                                params=params,
                                headers=self.headers)
        result = response.json()
        return int(result['linkedin_employee_count'])

    def query_past_employee_urls(self) -> List[str]:
        params = {
            'employment_status': 'all',  # current, past, all
            # 'page_size': '100',  # max 100 when enrich is "enrich"
            'url': self.url,
        }
        response = requests.get(self.listing_endpoint,
                                params=params,
                                headers=self.headers)
        code = response.status_code
        if code != 200:
            raise HTTPError
        result = response.json()
        combined_result = result['employees']
        while result['next_page'] is not None and self.should_run_full_query:
            response = self.run_query_string(result['next_page'])
            result = response.json()
            combined_result += result['employees']
        return [empl['profile_url'] for empl in combined_result]

    @backoff.on_exception(backoff.expo, Exception, max_time=512)
    def run_query_string(self, query: str) -> Response:
        # Max time slightly more than 512 since that's the power of 2 bigger than 300 and rate limit is
        # applied in 5-minute bursts
        return requests.get(query, headers=self.headers)

    @property
    def headers(self) -> Dict[str, str]:
        return {
            'Authorization': 'Bearer ' + self.key,
        }

    @staticmethod
    def get_month_ranges(months: int) -> List[Dict[str, date]]:
        # We need to get the current date as our first data point to calculate the ratio.
        # This will not be returned to the user, but it will be the starting point for our proportion.
        time_ranges = [{
            "end": date.today(),
            "start": date(year=date.today().year, month=date.today().month, day=1)
        }]
        for i in range(months - 1):
            # It's a little tricky to know how long a month is, so we will build this list in an
            # iterative manner, relying on the fact that the last day of a month is one day before
            # the first day of the month after it.
            if i == 0:
                current_month = date(year=date.today().year, month=date.today().month, day=1)
                time_ranges.append(EmployeeCount.get_month_range(current_month))
            time_ranges.append(EmployeeCount.get_month_range(time_ranges[-1]['start']))
        return time_ranges

    @staticmethod
    def get_month_range(first_of_next_month: date) -> Dict[str, date]:
        prev_month_end = first_of_next_month - timedelta(days=1)
        return {
            "end": prev_month_end,
            "start": first_of_next_month - timedelta(
                days=calendar.monthrange(prev_month_end.year, prev_month_end.month)[1])
        }

    async def query_past_counts(self, past_employee_urls: List[str]) -> List[Result]:

        P = ParamSpec('P')
        T = TypeVar('T')

        def ignore_404(f: Callable[P, T]) -> Callable[P, Optional[T]]:
            def inner(*args: P.args, **kwargs: P.kwargs) -> Optional[T]:
                try:
                    return f(*args, **kwargs)
                except ProxycurlException:
                    return None

            return inner

        results = await do_bulk([
            (ignore_404(self.proxycurl.linkedin.person.get), {'url': u})
            # pass limit as a parameter to make this method easily testable
            for u in self.get_limited_sample_of_urls(past_employee_urls, self.limit)
        ])
        return results

    @staticmethod
    def get_limited_sample_of_urls(past_employee_urls: List[str], limit: int) -> List[str]:
        if limit == -1 or limit >= len(past_employee_urls):
            return past_employee_urls
        ret = []
        ordering = list(range(len(past_employee_urls)))
        shuffle(ordering)
        for i in range(limit):
            ret.append(past_employee_urls[ordering[i]])
        return ret

    def get_past_employee_counts(self, employees: List[Result]) -> List[int]:
        company_identifier = self.identifier(self.url)
        total_employee_ranges = [0] * len(self.month_ranges)

        for employee in employees:
            if employee is None:
                continue
            if employee.value is None:
                continue
            employee_ranges = self.get_employee_ranges_from_experiences(
                employee.value, len(self.month_ranges), company_identifier
            )
            for i, new_range in enumerate(employee_ranges):
                total_employee_ranges[i] = total_employee_ranges[i] + new_range
        return total_employee_ranges

    def get_employee_ranges_from_experiences(self, employee: Dict[str, any],
                                             months: int, company_identifier) -> List[int]:
        # Given a single employee, parse their experiences section & determine during which dates
        # they worked for the target company.
        # Return a vector containing 1s in the correct ranges, 0s elsewhere.
        employee_ranges = [0] * months
        for exp in employee['experiences']:
            if exp['company_linkedin_profile_url'] is None:
                continue
            if self.identifier(exp['company_linkedin_profile_url']) == company_identifier:
                ends_at = exp['ends_at']
                starts_at = exp['starts_at']
                if starts_at is None:
                    # In this case there is nothing we can do, the line is useless
                    continue
                # Current employees are tenured until "today"
                ends_at_date = date(year=ends_at['year'], month=ends_at['month'],
                                    day=ends_at['day']) if ends_at is not None else date.today()
                starts_at_date = date(year=starts_at['year'], month=starts_at['month'], day=starts_at['day'])
                for i, date_range in enumerate(self.month_ranges):
                    if self.active_during(date_range, starts_at_date, ends_at_date):
                        employee_ranges[i] = 1
        return employee_ranges

    @staticmethod
    def identifier(url: str) -> str:
        arr = url.split('/')
        return arr[-2] if arr[-1] == '' else arr[-1]

    @staticmethod
    def active_during(date_range: Dict[str, date], starts_at_date: [date], ends_at_date: date) -> bool:
        # We want the employment date to intersect with the month range.
        # So the month must begin (Start) before the employment ends, i.e. ends_at_date > date_range["start"]
        # Also, the month must end after the employment has started, i.e. date_range["end"] > starts_at_date
        return ends_at_date >= date_range['start'] and date_range["end"] >= starts_at_date

    @staticmethod
    def get_adjusted_employee_counts(past_employee_counts: List[int], current_employee_count: int) -> List[int]:
        # The "estimate" is the number of people with public linkedin profiles, i.e. the number of
        # people who we have been able to scrape who were active in the company this month
        # That forms month 0 for our trend line, and we will use it to extrapolate backwards.
        current_employee_estimate = past_employee_counts[0]
        adjusted_employee_counts = []
        for item in past_employee_counts:
            # The ratio is (public old count / Estimation we want) = (current "estimate" / Current total)
            # Factor to solve for "Estimate we want" and we have:
            # public old count * Current total (on linkedin) / current "estimate" = X
            if current_employee_estimate == 0:
                # This can happen during debugging if we aren't enriching profiles
                adjusted_employee_counts.append(0)
                continue
            adjusted_employee_counts.append(int(item * current_employee_count / current_employee_estimate))
        return adjusted_employee_counts

    def print_output(self, adjusted_employee_accounts: List[int]) -> None:
        o = ['date,total_employees']
        for i, month in enumerate(self.month_ranges):
            if i == 0:
                # Recall we used the first slot for current information, and not for a full month of data.
                continue
            o.append(f"{month['end'].strftime('%Y-%m-%d')},{adjusted_employee_accounts[i]}")
        print('\n'.join(o))


if __name__ == "__main__":
    key_arg = sys.argv[1]
    url_arg = sys.argv[2]
    months_arg = int(sys.argv[3]) if len(sys.argv) > 3 else None
    limit_arg = int(sys.argv[4]) if len(sys.argv) > 4 else None
    asyncio.run(EmployeeCount(key_arg, url_arg, months_arg, limit_arg).main())
