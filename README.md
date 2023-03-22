# Proxycurl Historic Employee Count Generator

## Overview

Welcome to the Proxycurl Historic Employee Count Generator! Using the Proxycurl API to fetch LinkedIn data about people's historical employment records, we can approximate the number of employees in a company over time. We can use this to extrapolate trends in hiring and firing at companies like Stripe, People Data Labs, and Apple. Finally, we will compare these trends to news stories and investment reports.

## Usage

1. Sign up for a [Proxycurl account](https://nubela.co/proxycurl/) and purchase credits.
2. Download the Docker container from Github with the following command:
     ```
   docker pull ghcr.io/nubelaco/historic-employee-count-tool:master
   ```
3. Run the container, replacing `<PROXYCURL_API_KEY>`and `<TARGET_COMPANY_LI_URL` with their respective values (you may wish to change the output file name if running multiple scripts):
     ```
    docker run -it ghcr.io/nubelaco/historic-employee-count-tool:master PROXYCURL_API_KEY TARGET_COMPANY_LI_URL > employee_count_history.csv
    ```
4. You can optionally specify two additional parameters: the number of months to look back and the limit on the number of employees to query. These will default to 36 & 3000, respectively. A query with these additional optional parameters included might look like this:
     ```
    docker run -it ghcr.io/nubelaco/historic-employee-count-tool:master YOUR_KEY_HERE https://www.linkedin.com/company/stripe 48 5000 > employee_count_history.csv
    ```
5. Alternatively you can clone this repo, use `pip install -r requirements.txt` and run from a command line or your IDE. The project was coded in Python 3.8 but it should be able to run in any higher version; eventually, you might have to move `ParamSpec` to `typing`.
6. If you're inspired by what you've seen, build your own projects using the Proxycurl API! If you build something cool, let us know about it at hello@nubela.co & maybe we'll feature a blog post about it!

## Limitations

Sometimes, by understanding what a tool cannot do, we can best understand what it's capable of. Let's first discuss the limitations of this script.

1. It's an approximation: We don't have any data about employees who aren't on LinkedIn, and we don't have historical data about employees with private (non-public) profiles.
2. It can only go so far back: As soon as "people's willingness to sign up for LinkedIn or broadcast their status working for this company" is a confounding factor, it won't be accurate. This could be LinkedIn's ubiquity as a social media platform (if we're going very far back) or the company being in stealth and people not wanting to list it.
3. Is the company in a sector and demographic that correlates well to LinkedIn usage? For example, this will not help you track Apple moving its manufacturing plants out of China.
4. We also need a meaningful sample size. If you scrape 5 people, you will have a projection where the company's size suddenly doubled 2 years ago, because one person quit and so isn't in the current employee pool.

Now that we've narrowed our focus to a specific window, we can see that this method can be extremely powerful for identifying and analyzing recent hiring/firing trends among companies whose employees tend to be active on LinkedIn - which is exactly our goal.

## How it works

### High-level
We will do three things, two LinkedIn queries and one calculation:

1. Query the current number of people on LinkedIn at the company (LinkedIn provides this as a total number, including non-public profiles).
2. Query snapshots in one-month intervals going back N months in time of how many people (public profiles only) who worked at the company. Note that these numbers are limited not only to "employees on LinkedIn" but even to "employees with public profiles on LinkedIn." Therefore, we will do a calculation in step 3.
3. With some super-advanced math that we haven't used since middle school, we can use the ratios of `previous snapshot` : `X` = `current month's snapshot count` : `current month's total told us by LinkedIn` to arrive at better numbers than what we got from step 2.

### Proxycurl API details

Of course, this would still be nearly impossible without the help of the Proxycurl API, as [scraping LinkedIn is not an easy thing to do on your own](https://nubela.co/blog/tutorial-how-to-build-your-own-linkedin-profile-scraper-2020/). But with the help of the Proxycurl API, we can use three endpoints to do this relatively painlessly (although you *do* have to deal with `datetime`):

* [Employee Listing Endpoint](https://nubela.co/proxycurl/docs#company-api-employee-listing-endpoint) - One of the company endpoints, this lists every employee in a company and gives links to their profile URLs. In the Proxycurl API, **a LinkedIn URL is always the unique identifier of an entity**, be it company, person, job, or anything else.
* [Employee Count Endpoint](https://nubela.co/proxycurl/docs#company-api-employee-count-endpoint) - Another one of the company endpoints, this does exactly what it says: It gives us a count of the employees employed by the company. You can get both cached information from Proxycurl in the form of a `linkdb_employee_count`, which can be either `past`, `current`, or `all` employees. For this tool, we're more interested in the `linkedin_employee_count`, which is scraped directly from LinkedIn and includes private profiles.
* [Person Profile Endpoint](https://nubela.co/proxycurl/docs#people-api-person-profile-endpoint) - this endpoint is optional and is a performance enhancement and cache invalidator. We could, if we wanted, use the first endpoint with the `enrich_profiles=enrich` option instead. That endpoint would then enrich our first query with the person endpoint profile results. But for performance, we can batch our queries here & use the async [Proxycurl Python client library](https://pypi.org/project/proxycurl-py/) to run the script a bit faster - and with the `use_cache=if-recent` flag, which lets us ensure our data is never more than 29 days out of date.

### AAQ (Answers to Anticipated Questions)

**Q: Why does the first number in the result differ from the result I get if I look at `linkedin_employee_count` from the Employee Listing Endpoint? Isn't that supposed to be the total number of employees in the company?**  
A: There are two hard problems in programming: Cache invalidation, naming things, and off-by-one errors. This case is an off-by-one error. The current count is for the *current* month, and we're discarding this number from the result set before we print anything. It looks a bit cleaner this way, but you're right that you do get this slightly-off result if the number has changed since the month started.

**Q: How long will this take to run?**  
A: It all depends on the size of the company that you want to scrape. We're using proxycurl-py to make our queries concurrently, but there's still a [rate limit of 300 queries per minute](https://nubela.co/proxycurl/docs#overview-rate-limit) (though bursting up to 1500 within 5 minutes is allowed). Thus, [People Data Labs](https://www.linkedin.com/company/peopledatalabs/) takes under a minute, Stripe with a limit of 3000 takes just under 6 minutes, and if you wanted to run the entireity of [Stripe](https://www.linkedin.com/company/stripe/) without any limit (set it to -1) it can be done in under an hour, but we don't recommend Apple without a limit.