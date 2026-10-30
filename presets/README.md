# Presets

Industries and job markets are data, not code. Supporting a new field or a new
country means adding a file here; the API loads and checks every file at
startup, and the tests fail on anything inconsistent.

| File | What it holds |
| --- | --- |
| `industries/<key>.toml` | One industry: its roles, suggested skills, scoring weights and seniority words |
| `markets/<key>.toml` | One job market: currency, countries and common locations |
| `seniority.toml` | The seniority levels, lowest first, and the title words for each |
| `scoring.toml` | The fit-score dimensions and the verdict bands |

The file name is the key a profile stores (`healthcare`, `uk`): lowercase
words joined by hyphens. **Never rename one that's in use** - add a new file
instead.

## An industry

```toml
label = "Healthcare"
description = "Nursing, allied health, medicine, pharmacy, midwifery and care."

# Offered as one-click suggestions in the profile.
skills = ["Patient assessment", "Care planning", "Safeguarding"]

# Weights (percent) for the dimensions in scoring.toml; they add up to 100.
[scoring]
skills = 30
experience = 35
culture = 15
career = 20

# Extra title words for the levels in seniority.toml (optional).
[seniority]
lead = ["band 7", "charge nurse"]

[[roles]]
key = "registered-nurse"              # unique in this file
label = "Registered nurse"
titles = ["registered nurse", "staff nurse", "nurse"]   # a job title containing one is this role
exclude = ["student nurse"]           # ...unless it contains one of these (optional)
search = ["registered nurse", "staff nurse"]            # what job search types into job boards
```

How titles are read:

- Matching is on whole words, ignoring case and punctuation, so `front end
  developer` matches "Front-End Developer" but `nurse` doesn't match
  "Nursery".
- When several roles match, the one with the **longest matching phrase** wins.
  Give a specialist role its full titles ("digital marketing executive") so a
  general role's shorter phrase ("marketing executive") doesn't take it.
- A title's level is the highest level whose words appear. Words inside the
  matched role phrase don't count ("manager" in "Product Manager"), and nor do
  words inside a longer level phrase ("head of" inside "head of year").

The tests check that each role's own titles and search terms land on that
role, so a role can't be hidden by another one.

## A market

```toml
label = "United Kingdom"
currency = "GBP"                       # ISO 4217
salary_period = "year"                 # year, month, day or hour
locations = ["London", "Manchester", "Remote (UK)"]     # suggestions
arrangements = []                      # pre-selected work arrangements (optional)

[countries]                            # ISO 3166-1 alpha-2 code = name
GB = "United Kingdom"
```

A country that appears in several markets must have the same name in each.

## Checking your change

```sh
cd apps/api && .venv/bin/pytest tests/test_presets.py tests/test_titles.py
```

Then try some real job titles under **Settings → Check a job title**.
