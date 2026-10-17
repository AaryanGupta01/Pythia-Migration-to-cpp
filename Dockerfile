# PYTHIA Studio image. Build:  docker build -t pythia-studio .      Run:  docker compose up
#
# Stage 1 builds the wheel (the prebuilt UI in studio/web/dist is bundled into it; rebuild it first with
# `cd studio/web && npm ci && npm run build` if you changed the frontend).
# Stage 2 is a slim runtime with a C++ compiler, because PYTHIA compiles your hotspots inside the container.

FROM python:3.12-slim-bookworm AS build
WORKDIR /src
RUN pip install --no-cache-dir build
COPY pyproject.toml README.md LICENSE ./
COPY pythia ./pythia
COPY pythia_studio ./pythia_studio
COPY runtime ./runtime
COPY studio/web/dist ./studio/web/dist
COPY demo ./demo
RUN python -m build --wheel --outdir /dist .

FROM python:3.12-slim-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends g++ git curl \
 && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1000 pythia && mkdir /data /projects && chown pythia /data \
 && ln -s /projects /home/pythia/projects
COPY --from=build /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl
USER pythia
ENV PYTHIA_HOME=/data \
    PYTHIA_HOST=0.0.0.0 \
    PYTHIA_PORT=8765 \
    PYTHONUNBUFFERED=1
VOLUME ["/data"]
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import json,os,urllib.request as u; d=json.load(u.urlopen('http://127.0.0.1:%s/api/doctor' % os.environ['PYTHIA_PORT'], timeout=4)); raise SystemExit(0 if d['ready'] else 1)"
# No browser inside a container, so never try to open one.
ENTRYPOINT ["pythia-studio", "--no-open"]
