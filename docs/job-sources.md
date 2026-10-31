# Job sources

A job source (a "connector") fetches postings from one job board or API.
Job Hunter ships with one: **Sample jobs** (`demo`), built-in postings with
fictional employers so everything works on the first run, with no keys.

Real sources are added one at a time, and only once the source's terms allow
it - see [third-party.md](third-party.md).

## How a search uses sources

A saved search has terms ("staff nurse"), places ("Manchester", "Remote
(UK)") and countries. A run turns them into queries - every term in every
place, with "Remote ..." places becoming remote-only queries
(`app/search/queries.py`) - and sends each query to every enabled source that
covers its countries. What comes back is stored once in the shared `jobs`
table (unique per source and source id), then judged against the user's
profile (`app/matching/evaluate.py`). A source that fails is recorded on the
run and skipped; the others carry on.

## Which sources run

| Setting | Meaning |
| --- | --- |
| `JOB_SOURCES` | The sources to use, comma-separated keys (default `demo`) |
| `COMMERCIAL_ONLY` | `true` leaves out sources whose terms don't allow commercial use - set it on a paid, hosted deployment |

A source that needs an API key is skipped until its key setting is set.

## Adding one

1. **Check the terms first.** Read the source's terms of use and API terms:
   is automated access allowed, is commercial use, what attribution is
   required, and what rate limits apply. Record the answer in
   [third-party.md](third-party.md). Sources that forbid scraping or
   automated access aren't accepted.
2. **Write the source** in `apps/api/app/sources/<key>.py`, subclassing
   `Source` from `app/sources/base.py`:

   ```python
   class ExampleBoard(Source):
       key = "example"                      # stored with every job; never change it
       label = "Example Board"
       description = "UK jobs across all industries."
       homepage = "https://jobs.example.com"
       countries = ("GB",)                  # where it has jobs; () = anywhere
       commercial = False                   # True only if its terms allow a paid, hosted product
       needs_key = "example_api_key"        # a Settings field; "" if no key

       def search(self, query: Query) -> list[Posting]:
           ...                              # call the API; raise on failure
   ```

   Map each result to a `Posting`: a stable `source_id`, the posting's URL,
   title, company, location text, ISO country code, `arrangement` (`onsite`,
   `hybrid`, `remote` or `""`), salary with ISO currency and period, the
   posting date, and the description as plain text.
3. **Register it** in `SOURCES` in `app/sources/__init__.py`, and add its key
   setting (if any) to `app/config.py` and `.env.example`.
4. **Test it offline**: record a real response as a fixture under
   `apps/api/tests/fixtures/` and test the mapping against it. Tests never
   call the network.
5. **Be polite**: set a timeout on every request, respect the source's rate
   limits, and send a descriptive User-Agent.
