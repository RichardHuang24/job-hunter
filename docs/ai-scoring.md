# AI scoring

Job Hunter scores how well each job fits you, from 0 to 100, with the
reasons. Scores are made in the background by the worker: new matches and
flagged jobs after every search, and any job when you press **Score this
job**. Filtered-out jobs aren't scored unless you ask.

## Two scorers

| | Claude (Anthropic API) | Simulated |
| --- | --- | --- |
| When | `ANTHROPIC_API_KEY` is set | No key (the default) |
| What it does | Reads your profile and the whole posting, and judges the fit | Counts which of your skills appear in the posting and reads the deal-breaker checks - it understands nothing |
| Cost | Per token (below) | Free, runs locally |
| Labelled | Model name and cost on each score | "Simulated" on every score and reason |

The simulator is there so every screen works on a fresh install with no
keys. Don't make decisions on its numbers.

## How a score is made

1. The **system prompt** holds the instructions and your profile (headline,
   roles, levels, years, skills, languages, your own words) and the scoring
   dimensions with your industry's weights. It's the same for every job you
   score, so it's cached between calls.
2. The **user turn** holds the posting - marked as untrusted text, never to
   be followed - and the deal-breaker checks code already decided.
3. Claude answers in a fixed JSON schema (structured outputs): a score and a
   one-sentence reason for each of the four dimensions, requirements it
   quotes from the posting (matched and missing), risks, and what the
   posting doesn't say.
4. Every quoted requirement is looked up in the posting. One that isn't
   there is kept but shown struck through as "not found in the posting",
   never as evidence.
5. The overall score is the dimension scores weighted by the industry
   preset (`presets/industries/*.toml`, `[scoring]`) - worked out in code,
   never a number from the model - and turned into a verdict by the bands in
   `presets/scoring.toml`.

A score goes **out of date** when your profile, your roles, the checks or the
posting change; it's shown faded until you score it again.

The code: `apps/api/app/scoring/` - `prompt.py` (the request and answer,
pure), `providers.py` (Claude and the simulator), `service.py` (queueing,
limits, the worker task).

## Turning on Claude

Add your key to `.env` and restart:

```sh
ANTHROPIC_API_KEY=sk-ant-...
```

`AI_PROVIDER=auto` (the default) uses Claude when a key is set. To check the
key works without a search, run the one live test - it makes one real call:

```sh
cd apps/api
RUN_LIVE_AI=1 ANTHROPIC_API_KEY=sk-ant-... .venv/bin/pytest tests/test_scoring_live.py -s
```

## Settings

| Setting | Default | Meaning |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | empty | Your Anthropic API key. Never logged or shown. |
| `AI_PROVIDER` | `auto` | `auto`, `anthropic` or `simulated` |
| `AI_MODEL` | `claude-haiku-5-5` | Any current Claude model, e.g. `claude-sonnet-5-5` or `claude-opus-5-5` |
| `AI_EFFORT` | `low` | How much effort the model puts in: `low`, `medium`, `high`, `xhigh`, `max` |
| `AI_THINKING` | `false` | `false` turns the model's thinking off where it allows that (Haiku 5.5, Sonnet 5.5, Opus 5 at effort `high` or lower); `true` leaves it on |
| `AI_AUTO_SCORE` | `true` | Score new matches and flagged jobs after each search |
| `AI_SCORES_PER_MONTH` | `300` | Per user |
| `AI_BUDGET_USD_PER_MONTH` | `5.0` | Per user; scoring stops for the month when it's spent |
| `AI_TIMEOUT_SECONDS` | `120` | Per call; the SDK retries twice on rate limits, server errors and timeouts |

## Cost

Scoring is reading a posting and comparing it with a profile - no
multi-step reasoning - so the default is the cheapest Claude model, Haiku
5.5, at low effort with thinking off. Each score is one API call: roughly
1,000-3,000 tokens in (the instructions and profile are cached after the
first job) and 600-1,000 out. Rough estimates per score at October 2026
list prices - measure your own from the cost shown on each score and on the
AI scoring card:

| Model | Input / output per million tokens | About per score | 300 scores |
| --- | --- | --- | --- |
| `claude-haiku-5-5` (default, thinking off) | $0.10 / $0.50 | under $0.001 | about $0.20-0.30 |
| `claude-sonnet-5-5` | $2 / $10 | $0.01-0.02 | $3-6 |
| `claude-opus-5-5` (always thinks) | $4 / $20 | $0.02-0.04 | $6-12 |

There is no free Claude model. With no API key the simulated scorer runs
instead: free, but it only counts skills and reads the deal-breaker checks.

## Safety, errors and privacy

- On models that support it (Opus 5.5, Sonnet 5.5 and others, not Haiku
  5.5), if Claude declines a request for safety reasons, the API re-runs it
  on the model Anthropic recommends, in the same call (server-side
  fallback). The cost of each attempt is recorded. On Haiku 5.5 a refusal
  fails just that job.
- A rejected key, rate limits or an unreachable API stop the batch and mark
  its scores failed with the reason; nothing is retried in a loop. A refusal
  or an unusable answer fails just that job. **Try again** queues it again.
- What's sent to Anthropic: your profile as listed above and the job
  posting. Nothing else - no email address, no other users' data. See
  Anthropic's commercial terms and privacy policy before running a hosted
  version.
