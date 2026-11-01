# Questions

**Is it free?**
Running it yourself is free: it's open source under the AGPL-3.0. A hosted
version, where you sign up and pay for convenience, is planned
([roadmap.md](roadmap.md)).

**Which jobs and countries does it cover?**
Profiles, roles and checks work for twelve industries and seven job markets
(the UK, Ireland, the US, Canada, the EU, Australia, and remote anywhere),
and anyone can add more as data files ([presets/](../presets/README.md)).
Real jobs come from Himalayas and Jobicy today - remote jobs, across
industries. Job boards for on-site work in each country come next, each
added once its terms allow it ([job-sources.md](job-sources.md)).

**Why not LinkedIn or Indeed?**
Their terms don't allow it: LinkedIn forbids automated access, and Indeed
closed its job search API. Job Hunter only uses sources whose terms permit
it ([third-party.md](third-party.md)).

**Does it apply to jobs for me?**
No. It finds and sorts jobs and tracks what you've applied for; you apply
on the employer's or job board's own page.

**Do I need an Anthropic API key?**
No. Without one, a free simulated scorer gives rough, clearly labelled fit
scores. With one, Claude reads each posting against your profile and
explains its score - under a tenth of a US cent per job with the default
model ([ai-scoring.md](ai-scoring.md)).

**Where's my data, and who sees it?**
On the server running Job Hunter. You can download all of it or delete your
account from Settings → Your data; the privacy page (`/privacy`) says what
this server sends where ([privacy.md](privacy.md)).

**Can I use it on my phone?**
Yes - every page is built and tested for phone screens, light and dark.

**Can I change how my CV looks?**
Not yet: there's one clean template, A4 or US Letter. Its text supports
Latin, Greek and Cyrillic; Chinese, Japanese, Korean and right-to-left
scripts aren't in the PDF fonts yet ([cv.md](cv.md)).

**How do I add a job board?**
Write a source - one Python file - after checking the board's terms
([job-sources.md](job-sources.md)).

**How do I make myself an admin?**
Put your email address in `ADMIN_EMAILS` in `.env` and restart; an
**Admin** link appears ([admin.md](admin.md)).

**How do I update it?**
`git pull`, `./scripts/setup-env.sh` (it adds any new secrets and changes
nothing else), then `docker compose ... up -d --build`
([self-hosting.md](self-hosting.md#update)).

**Is there an API?**
Everything the web app does goes through the API. Running it locally, its
OpenAPI documentation is at <http://localhost:8420/docs>. In production the
API isn't reachable from outside; the web app calls it for each signed-in
person ([architecture.md](architecture.md)).

**Can I try it without installing anything?**
Yes, if someone runs a demo site ([demo.md](demo.md)) - three fictional
people to try it as, each a fresh account of your own.
