# The API, the worker and the database migrations: one image, three commands
# (docker-compose.yml). Build from the repo root. Runs on amd64 and arm64.
FROM python:3.12-slim

# TEXMFVAR: LuaLaTeX's font cache, built below as the app user.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TEXMFVAR=/app/.texmf-var

# LuaLaTeX and two fonts, for CV PDFs (app/cv): only the packages the CV
# template uses - fontspec, geometry, xcolor, enumitem, hyperref.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      texlive-luatex texlive-latex-recommended fonts-lato fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/* /usr/share/man/* /usr/share/info/* \
 && find /usr/share/doc -depth -type f ! -name copyright -delete \
 && find /usr/share/doc -depth -type d -empty -delete

WORKDIR /app
COPY apps/api/requirements.txt ./
RUN pip install -r requirements.txt

COPY apps/api/alembic.ini ./
COPY apps/api/alembic ./alembic
COPY apps/api/app ./app
# Industry and market presets; the API finds them at /app/presets.
COPY presets ./presets

RUN useradd --system --uid 10001 --home-dir /app --no-create-home app \
 && mkdir -p "$TEXMFVAR" && chown app "$TEXMFVAR"
USER app

# Build one CV now: it fills the font cache, so the first real PDF is quick,
# and a broken TeX setup fails the image build rather than someone's PDF.
RUN python -c "from app.cv.build import build_pdf; from app.cv.latex import render; from app.cv.schema import CvContent; \
pdf = build_pdf(render(CvContent(name='Image check', summary='Lato and DejaVu: ✓ Ελληνικά Русский'))); \
assert pdf.data.startswith(b'%PDF') and pdf.pages == 1, pdf.pages; print('A CV PDF builds:', len(pdf.data), 'bytes')"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
