# Job sources

A job source (a "connector") fetches postings from one job board or API.
Job Hunter ships with three:

| Key | Source | Jobs | Cost |
| --- | --- | --- | --- |
| `himalayas` | [Himalayas](https://himalayas.app) | Remote jobs at companies hiring worldwide | Free; key optional |
| `jobicy` | [Jobicy](https://jobicy.com) | Remote jobs posted in the last 7 days | Free, no key |
| `demo` | Sample jobs | Built-in postings with fictional employers, so everything works with no network and no keys | Free |

Both real sources list **remote jobs only**, across every industry they
cover. On-site and hybrid jobs need a source for your country, which isn't
in yet; sources are added one at a time, and only once their terms allow it -
see [third-party.md](third-party.md).

## How a search uses sources

A saved search has terms ("data analyst"), places ("Manchester", "Remote
(UK)") and countries. A run turns them into queries - every term in every
place, with "Remote ..." places becoming remote-only queries, and one more
remote-only query when the search says "Also look for remote jobs"
(`app/search/queries.py`). Each query goes to every enabled source that
covers it: a remote-only source (`remote_only = True`) only gets remote
queries. A profile open to remote work gets "Also look for remote jobs"
ticked on the search made at onboarding.

What comes back is stored once in the shared `jobs` table (unique per
source and source id), then judged against each user's profile
(`app/matching/evaluate.py`). Remote jobs carry the countries they're open
to, so the work-permit check compares those with where the person can work
("Open to people anywhere", "United States and Canada - you'd need a
visa"). A source that fails is recorded on the run and skipped; the others
carry on.

## Himalayas

- Calls the search endpoint for each term and country (up to five countries;
  more than that, one search for anywhere, filtered here), 20 jobs a page,
  two pages at most, most relevant first.
- Answers are kept for six hours (Himalayas refreshes daily), and calls are
  spaced 1.1 s apart. Without a key every caller shares one public
  allowance; a free `HIMALAYAS_API_KEY` gives 60 calls a minute and 10,000
  a day.
- Its terms ([API docs](https://himalayas.app/api), [terms](https://himalayas.app/terms)),
  and how Job Hunter meets them:
  - *Apply buttons use `applicationLink` unchanged* - it's the job's link.
  - *A visible link credits Himalayas* - "via Himalayas" on every job, and
    "Open on Himalayas" in its details.
  - *Jobs shown only on sites and apps you run, never passed to other job
    boards, aggregators, Google Jobs or LinkedIn, including through feeds or
    JobPosting structured data* - Job Hunter has no public job pages, feeds
    or structured data. Don't add any for these jobs.
  - *Expired and closed jobs removed* - jobs past their expiry date leave
    every list, and the worker asks Himalayas daily whether each stored job
    is still open (see below).

## Jobicy

- The whole feed - a thousand or more jobs - is read at most once an hour,
  100 jobs a call, and every search is answered from that copy. Terms match
  whole words in the title, like a job board's title search.
- Its terms ([API docs](https://jobicy.com/jobs-rss-feed)), and how Job
  Hunter meets them:
  - *Credit Jobicy as the source, with a link* - "via Jobicy" on every job.
  - *Apply links go to the original Jobicy job page* - the job's link is the
    Jobicy page the free API gives.
  - *A sync pass at most once an hour; status checks hourly or less, up to
    100 jobs a call* - as above, and see below.
  - *Commercial use, storing and caching are allowed; remove closed jobs. A
    job missing from the feed may still be open* - so jobs are marked closed
    only when Jobicy's status endpoint says so.

## Closed and expired jobs

Sources whose terms say closed jobs must come down set `check_every` and
implement `check()`. Every `RECHECK_SECONDS` (an hour) the worker queues a
`recheck` task that asks each such source about the jobs people have, oldest
check first: Himalayas once a day per job (25 a pass), Jobicy every six
hours (300 a pass). A job that has closed or passed its expiry date leaves
the Matches, Flagged and Filtered lists; in Saved and Hidden it stays,
marked closed, without its posting.

## Which sources run

| Setting | Meaning |
| --- | --- |
| `JOB_SOURCES` | The sources to use, comma-separated keys. `.env.example` sets `himalayas,jobicy`; with no setting at all it's `demo` |
| `COMMERCIAL_ONLY` | `true` leaves out sources whose terms don't allow commercial use - set it on a paid, hosted deployment |
| `HIMALAYAS_API_KEY` | Optional; raises Himalayas' rate limits |
| `RECHECK_SECONDS` | How often the worker checks stored jobs are still open (default 3600) |

A source that needs an API key is skipped until its key setting is set.

## Adding one

1. **Check the terms first.** Read the source's terms of use and API terms:
   is automated access allowed, is commercial use, what attribution is
   required, what rate limits apply, and whether closed jobs must be taken
   down. Record the answer in [third-party.md](third-party.md). Sources that
   forbid scraping or automated access aren't accepted.
2. **Write the source** in `apps/api/app/sources/<key>.py`, subclassing
   `Source` from `app/sources/base.py`. Use `Fetcher` (`app/sources/http.py`)
   for HTTP: it sends a descriptive User-Agent, spaces calls out, caches
   answers and turns failures into readable errors.

   ```python
   class ExampleBoard(Source):
       key = "example"                      # stored with every job; never change it
       label = "Example Board"
       description = "UK jobs across all industries."
       homepage = "https://jobs.example.com"   # linked as "via Example Board"
       countries = ("GB",)                  # where it has jobs; () = anywhere
       commercial = False                   # True only if its terms allow a paid, hosted product
       needs_key = "example_api_key"        # a Settings field; "" if no key
       remote_only = False                  # True if it only lists remote jobs
       check_every = None                   # a timedelta if closed jobs must come down

       def search(self, query: Query) -> list[Posting]:
           ...                              # call the API; raise on failure

       def check(self, jobs):               # only with check_every
           ...                              # {source_id: "open" | "closed" | "unknown"}
   ```

   Map each result to a `Posting`: a stable `source_id`, the posting's URL,
   title, company, location text, ISO country code, `arrangement` (`onsite`,
   `hybrid`, `remote` or `""`), salary with ISO currency and period, the
   posting date, the description as plain text (`html_to_text` in
   `app/sources/text.py`), and for remote jobs the countries it's open to
   (`parse_places` in `app/countries.py`) or `worldwide`.
3. **Register it** in `SOURCES` in `app/sources/__init__.py`, and add its key
   setting (if any) to `app/config.py`, `.env.example` and
   `docker-compose.yml`.
4. **Test it offline** against stand-in answers in the API's shape with
   fictional data (see `tests/test_sources_remote.py`) - don't commit real
   listings. Tests never call the network; add a live test that's skipped
   unless asked for (see `tests/test_sources_live.py`).
5. **Be polite**: respect the source's rate limits and polling guidance, and
   cache what you can.
