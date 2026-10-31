# CVs and PDFs

The **CV** page keeps your CV as plain facts - who you are, a short profile,
jobs with what you did in each, education, skills and languages - and makes
a PDF from it whenever you ask. Until you save it, the page starts from your
profile (name, headline, email, summary, skills, languages); after that, the
two are separate.

## How a PDF is made

1. **Make PDF** saves the CV and queues a `cv_pdf` task
   (`app/cv/service.py`). One is made at a time per person.
2. The worker turns the CV into LaTeX (`app/cv/latex.py`) using the template
   `app/cv/cv.tex`: Lato, with DejaVu Sans for characters Lato lacks; A4,
   or US Letter when your job market is the US or Canada.
3. LuaLaTeX builds it (`app/cv/build.py`), usually in two to five seconds.
4. The PDF goes into storage (`app/storage.py`) and appears on the page to
   download. The newest ten are kept (`CV_FILES_KEPT`); older ones are
   deleted, file and all.

If a build fails, the PDF is marked failed with LaTeX's own error line, and
**Make PDF** tries again.

## Safety

Nothing typed into a CV can run as LaTeX:

- Every piece of text is escaped - `\`, `{`, `}`, `$`, `&`, `#`, `^`, `_`, `%`
  and `~` print as themselves, control characters are dropped - and links
  are percent-encoded. Only the template's own commands are LaTeX.
- LuaLaTeX runs with shell commands off (`-no-shell-escape`,
  `shell_escape=f`), may only read and write inside its own throwaway folder
  (`openin_any=p`, `openout_any=p`), stops at the first error, and is killed
  after `CV_TIMEOUT_SECONDS` (90).
- It runs in the worker container as an unprivileged user.

Tests cover the escaping with every special character, and a real build with
awkward text, including `\input{/etc/passwd}` and `\write18{...}`, which
print as text (`apps/api/tests/test_cv.py`).

## Languages and scripts

Latin, Greek and Cyrillic text prints as typed. Chinese, Japanese, Korean
and right-to-left scripts such as Arabic and Hebrew aren't supported yet:
their characters print as empty boxes. Supporting them means adding fonts
for them to the image (tens of megabytes) and a fallback in the template.

## Running it

The Docker image has everything: LuaLaTeX (`texlive-luatex`,
`texlive-latex-recommended`) and the fonts (`fonts-lato`,
`fonts-dejavu-core`), and it builds a sample CV while the image is built, so
a broken TeX setup fails the build, not someone's PDF. Running the worker
outside Docker needs the same packages; without them, a build fails with
"lualatex isn't installed here".

| Setting | Default | Meaning |
| --- | --- | --- |
| `CV_LATEX` | `lualatex` | The LaTeX program |
| `CV_TIMEOUT_SECONDS` | `90` | How long one build may take |
| `CV_FILES_KEPT` | `10` | PDFs kept per person |

Where the files go is set by the storage settings - see
[self-hosting.md](self-hosting.md#files).

## Next

A version of your CV for each job, built from the posting - see
[roadmap.md](roadmap.md).
