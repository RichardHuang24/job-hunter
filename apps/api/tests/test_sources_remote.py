"""The Himalayas and Jobicy sources, against stand-in HTTP answers shaped like
the real APIs (fictional employers - no real listings are kept here)."""

from __future__ import annotations

import datetime as dt

import httpx2
import pytest

from app.sources.base import Query
from app.sources.himalayas import HimalayasSource, remote_label
from app.sources.himalayas import to_posting as himalayas_posting
from app.sources.http import Fetcher, SourceError
from app.sources.jobicy import Feed, JobicySource
from app.sources.jobicy import to_posting as jobicy_posting

NOW = dt.datetime.now(dt.UTC)


class Board:
    """A stand-in API: answers each request from `reply(request)` and keeps them."""

    def __init__(self, reply):
        self.reply, self.requests = reply, []

    def fetcher(self, ttl: float = 0.0) -> Fetcher:
        def handle(request: httpx2.Request) -> httpx2.Response:
            self.requests.append(request)
            answer = self.reply(request)
            return answer if isinstance(answer, httpx2.Response) else httpx2.Response(200, json=answer)
        return Fetcher(min_interval=0, ttl=ttl, client=httpx2.Client(transport=httpx2.MockTransport(handle)))

    def params(self, i: int = -1) -> dict[str, str]:
        return dict(self.requests[i].url.params)


def him(n: int = 0, **changes) -> dict:
    slug = f"data-scientist-{n}"
    return {
        "title": "Senior Data Scientist", "excerpt": "Build models.", "companyName": "Northwind &amp; Co",
        "companySlug": "northwind", "companyLogo": "", "employmentType": "Full Time",
        "minSalary": 70000, "maxSalary": 90000, "salaryPeriod": "annual", "seniority": ["Senior"], "currency": "GBP",
        "locationRestrictions": ["United Kingdom"], "timezoneRestrictions": [0], "categories": [], "parentCategories": [],
        "description": "<h3>About</h3><p>Build models in&nbsp;<b>Python</b>.</p><ul><li>SQL</li><li>Statistics</li></ul>",
        "pubDate": int((NOW - dt.timedelta(days=2)).timestamp()),
        "expiryDate": int((NOW + dt.timedelta(days=30)).timestamp()),
        "applicationLink": f"https://himalayas.app/companies/northwind/jobs/{slug}?utm_source=api",
        "guid": f"https://himalayas.app/companies/northwind/jobs/{slug}", **changes,
    }


def jobicy(n: int = 1, **changes) -> dict:
    return {
        "id": 1000 + n, "url": f"https://jobicy.com/jobs/{1000 + n}-data-analyst", "jobSlug": f"{1000 + n}-data-analyst",
        "jobTitle": "Senior Data Analyst", "companyName": "Contoso Remote", "companyLogo": "",
        "jobIndustry": ["Data Science &amp; Analytics"], "jobType": ["Full-Time"], "jobGeo": "Canada,  USA",
        "jobLevel": "Senior", "jobExcerpt": "Analyse data.", "jobDescription": "<p>Analyse data with <b>SQL</b>.</p>",
        "pubDate": "2026-10-25T04:10:03+00:00", "salaryMin": 90000, "salaryMax": 110000, "salaryCurrency": "USD",
        "salaryPeriod": "yearly", **changes,
    }


# Himalayas


def test_a_himalayas_job_becomes_a_posting():
    posting = himalayas_posting(him(), NOW)
    assert posting.source_id == "northwind/data-scientist-0"
    assert posting.url == "https://himalayas.app/companies/northwind/jobs/data-scientist-0?utm_source=api"  # unchanged
    assert (posting.title, posting.company) == ("Senior Data Scientist", "Northwind & Co")
    assert (posting.location, posting.country, posting.arrangement) == ("Remote (United Kingdom)", "GB", "remote")
    assert (posting.countries, posting.worldwide) == (("GB",), False)
    assert (posting.salary_min, posting.salary_max, posting.salary_currency, posting.salary_period) == (70000, 90000, "GBP", "year")
    assert posting.description == "About\n\nBuild models in Python.\n\n- SQL\n- Statistics"
    assert posting.posted_at < NOW < posting.expires_at


def test_himalayas_edge_cases():
    anywhere = himalayas_posting(him(locationRestrictions=[]), NOW)
    assert anywhere.worldwide and anywhere.countries == () and anywhere.location == "Remote (anywhere)"
    many = himalayas_posting(him(locationRestrictions=["Germany", "Spain", "Congo, The Democratic Republic of the", "Atlantis"]), NOW)
    assert many.countries == ("DE", "ES", "CD") and many.country == "" and many.location == "Remote (Germany, Spain and 2 more)"
    assert himalayas_posting(him(expiryDate=int((NOW - dt.timedelta(hours=1)).timestamp())), NOW) is None
    weekly = himalayas_posting(him(salaryPeriod="weekly"), NOW)
    assert weekly.salary_min is None and weekly.salary_currency == ""  # not comparable, so left out
    hourly = himalayas_posting(him(minSalary=45, maxSalary=None, salaryPeriod="hourly", currency="usd"), NOW)
    assert (hourly.salary_min, hourly.salary_max, hourly.salary_currency, hourly.salary_period) == (45, None, "USD", "hour")
    assert himalayas_posting(him(currency=None), NOW).salary_min is None
    assert himalayas_posting(him(title=""), NOW) is None
    assert himalayas_posting(him(applicationLink="javascript:alert(1)", guid=""), NOW) is None
    assert remote_label(["A", "B", "C"], False) == "Remote (A, B, C)"


def test_himalayas_search_pages_and_caches():
    def reply(request):
        page = int(request.url.params["page"])
        return {"jobs": [him(n) for n in range(20)] if page == 1 else [him(n) for n in range(18, 23)], "totalCount": 23}
    board = Board(reply)
    source = HimalayasSource(board.fetcher(ttl=3600), api_key="hk-test")
    found = source.search(Query("data scientist", countries=("GB",), remote=True))
    assert len(found) == 23 and len({p.source_id for p in found}) == 23  # repeats across pages dropped
    assert [board.params(i) for i in range(2)] == [{"q": "data scientist", "page": "1", "country": "GB"},
                                                   {"q": "data scientist", "page": "2", "country": "GB"}]
    assert board.requests[0].headers["authorization"] == "Bearer hk-test"
    assert board.requests[0].headers["user-agent"].startswith("JobHunter/")
    source.search(Query("data scientist", countries=("GB",), remote=True))
    assert len(board.requests) == 2  # the same search again comes from the cache
    assert len(source.search(Query("data scientist", countries=("GB",), remote=True, limit=5))) == 5


def test_himalayas_searches_each_country_or_anywhere():
    board = Board(lambda request: {"jobs": [him(hash(request.url.params.get("country", "")) % 1000)]})
    source = HimalayasSource(board.fetcher(), api_key="")
    source.search(Query("nurse", countries=("GB", "IE"), remote=True))
    assert [board.params(i).get("country") for i in range(2)] == ["GB", "IE"]
    assert "authorization" not in board.requests[0].headers
    board.requests.clear()
    source.search(Query("nurse", remote=True))
    assert "country" not in board.params()

    eu = ("AT", "BE", "DE", "ES", "FR", "IT")  # more than five: one search for anywhere, filtered here
    board = Board(lambda request: {"jobs": [him(1, locationRestrictions=["Germany"]), him(2, locationRestrictions=["Japan"]),
                                            him(3, locationRestrictions=[])]})
    found = HimalayasSource(board.fetcher(), api_key="").search(Query("nurse", countries=eu, remote=True))
    assert len(board.requests) == 1 and "country" not in board.params()
    assert sorted(p.source_id for p in found) == ["northwind/data-scientist-1", "northwind/data-scientist-3"]


@pytest.mark.parametrize("answer, message", [
    (httpx2.Response(429, headers={"Retry-After": "30"}), "himalayas.app is rate-limiting us - try again in 30 s"),
    (httpx2.Response(503), "himalayas.app answered 503"),
    (httpx2.Response(200, text="<html>"), "himalayas.app sent something that isn't JSON"),
    (httpx2.Response(200, json={"error": "no"}), "Himalayas sent an answer without jobs"),
])
def test_himalayas_errors_say_what_happened(answer, message):
    with pytest.raises(SourceError, match=message):
        HimalayasSource(Board(lambda request: answer).fetcher(), api_key="").search(Query("x", remote=True))


def test_himalayas_unreachable():
    def down(request):
        raise httpx2.ConnectError("refused", request=request)
    fetcher = Fetcher(min_interval=0, client=httpx2.Client(transport=httpx2.MockTransport(down)))
    with pytest.raises(SourceError, match="Couldn't reach himalayas.app"):
        HimalayasSource(fetcher, api_key="").search(Query("x", remote=True))


def test_himalayas_checks_jobs_one_by_one():
    codes = {"open": 200, "gone": 410, "missing": 404, "odd": 500}
    board = Board(lambda request: httpx2.Response(codes[request.url.path.rsplit("/", 1)[-1]]))
    statuses = HimalayasSource(board.fetcher(), api_key="").check(
        [("acme/open", ""), ("acme/gone", ""), ("acme/missing", ""), ("acme/odd", ""), ("not-a-path", "")])
    assert statuses == {"acme/open": "open", "acme/gone": "closed", "acme/missing": "closed", "acme/odd": "unknown",
                        "not-a-path": "unknown"}
    assert board.requests[0].url.path == "/jobs/api/companies/acme/jobs/open"
    limited = Board(lambda request: httpx2.Response(429))
    assert HimalayasSource(limited.fetcher(), api_key="").check([("a/b", ""), ("c/d", "")]) == {}  # the rest wait
    assert len(limited.requests) == 1


def test_remote_only_sources_answer_remote_searches_only():
    source = HimalayasSource(Board(lambda request: {"jobs": []}).fetcher(), api_key="")
    assert source.covers(Query("x", remote=True, countries=("GB",)))
    assert not source.covers(Query("x", location="Leeds", countries=("GB",)))


# Jobicy


def test_a_jobicy_job_becomes_a_posting():
    posting = jobicy_posting(jobicy())
    assert (posting.source_id, posting.url) == ("1001", "https://jobicy.com/jobs/1001-data-analyst")
    assert (posting.location, posting.countries, posting.country) == ("Remote (Canada, USA)", ("CA", "US"), "")
    assert (posting.salary_min, posting.salary_max, posting.salary_currency, posting.salary_period) == (90000, 110000, "USD", "year")
    assert posting.description == "Analyse data with SQL."
    assert posting.posted_at == dt.datetime(2026, 10, 25, 4, 10, 3, tzinfo=dt.UTC)
    anywhere = jobicy_posting(jobicy(jobGeo="Anywhere"))
    assert anywhere.worldwide and anywhere.location == "Remote (anywhere)"
    emea = jobicy_posting(jobicy(jobGeo="EMEA"))
    assert {"GB", "DE", "AE", "NG"} <= set(emea.countries) and "US" not in emea.countries
    assert jobicy_posting(jobicy(jobGeo="UK")).country == "GB"
    assert jobicy_posting(jobicy(salaryMin=None, salaryMax=None, salaryCurrency=None, salaryPeriod=None)).salary_currency == ""
    assert jobicy_posting(jobicy(id=None)) is None


def feed_board(pages: list[list[dict]]) -> Board:
    def reply(request):
        cursor = request.url.params.get("cursor", "")
        index = int(cursor or 0)
        more = index + 1 < len(pages)
        return {"jobs": pages[index], "hasMore": more, "nextCursor": str(index + 1) if more else None, "success": True}
    return Board(reply)


def test_jobicy_reads_the_whole_feed_once_an_hour():
    board = feed_board([[jobicy(1), jobicy(2, jobTitle="Account Executive")], [jobicy(3, jobGeo="Japan")]])
    source = JobicySource(Feed(board.fetcher()))
    found = source.search(Query("data analyst", countries=("US",), remote=True))
    assert [p.source_id for p in found] == ["1001"]  # title words must match; 1003 is Japan-only
    assert [board.params(i) for i in range(2)] == [{"count": "100"}, {"count": "100", "cursor": "1"}]
    assert {p.source_id for p in source.search(Query("data analyst", remote=True))} == {"1001", "1003"}
    assert {p.source_id for p in source.search(Query("account executive", remote=True))} == {"1002"}
    assert len(board.requests) == 2  # every search answered from the same copy


def test_jobicy_keeps_jobs_whose_places_are_unknown():
    board = feed_board([[jobicy(1, jobGeo="Somewhere Nice")]])
    [posting] = JobicySource(Feed(board.fetcher())).search(Query("data analyst", countries=("GB",), remote=True))
    assert posting.countries == () and not posting.worldwide  # the permit check will say "not stated"


def test_jobicy_failures_back_off():
    board = Board(lambda request: httpx2.Response(500))
    source = JobicySource(Feed(board.fetcher()))
    for _ in range(3):
        with pytest.raises(SourceError, match="jobicy.com answered 500"):
            source.search(Query("data analyst", remote=True))
    assert len(board.requests) == 1  # not asked again for ten minutes


def test_jobicy_checks_jobs_in_batches():
    def reply(request):
        ids = request.url.params["ids"].split(",")
        return {"jobs": [{"id": int(i), "status": "closed" if int(i) % 2 else "active"} for i in ids], "success": True}
    board = Board(reply)
    jobs = [(str(i), "") for i in range(1, 251)] + [("abc", "")]
    statuses = JobicySource(Feed(board.fetcher())).check(jobs)
    assert len(board.requests) == 3 and len(board.params(0)["ids"].split(",")) == 100
    assert statuses["1"] == "closed" and statuses["2"] == "open" and statuses["abc"] == "unknown" and len(statuses) == 251


def test_the_sources_say_what_their_terms_are():
    for source in (HimalayasSource, JobicySource):
        assert source.commercial and source.remote_only and source.check_every
        assert source.homepage.startswith("https://")
