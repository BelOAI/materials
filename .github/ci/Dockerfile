FROM node:24-bookworm-slim AS node
FROM python:3.14-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash make texlive-latex-base texlive-latex-recommended texlive-latex-extra \
    texlive-fonts-recommended texlive-lang-cyrillic texlive-pictures texlive-science \
    poppler-utils \
 && rm -rf /var/lib/apt/lists/*
COPY handbook/start/requirements.txt /opt/ci/handbook-requirements.txt
RUN python -m pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu \
 && python -m pip install --no-cache-dir -r /opt/ci/handbook-requirements.txt
COPY .github/ci/requirements.txt /opt/ci/requirements.txt
RUN python -m pip install --no-cache-dir -r /opt/ci/requirements.txt
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
WORKDIR /work
