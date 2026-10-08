FROM python:3.12-slim AS tectonic-binary

ARG TECTONIC_VERSION=0.17.0
ARG TECTONIC_SHA256=8533d07f9ccbd7a65824b9e0459041bca34af1eb33daba48f59215593753a3b7

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL \
      "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz" \
      -o /tmp/tectonic.tar.gz \
    && echo "${TECTONIC_SHA256}  /tmp/tectonic.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/tectonic.tar.gz -C /usr/local/bin tectonic \
    && chmod 0755 /usr/local/bin/tectonic \
    && rm /tmp/tectonic.tar.gz

FROM python:3.12-slim

RUN useradd --create-home --uid 10001 tectonic \
    && mkdir -p /var/lib/internhub/compile/inbox \
       /var/lib/internhub/compile/responses \
       /var/lib/internhub/compile/tmp \
       /var/lib/internhub/artifacts \
    && chmod -R 0777 /var/lib/internhub
COPY --from=tectonic-binary /usr/local/bin/tectonic /usr/local/bin/tectonic
COPY backend/services/tectonic_compile_service.py /app/tectonic_compile_service.py
COPY deploy/tectonic/worker.py /app/worker.py

ENV HOME=/home/tectonic \
    RESUME_COMPILE_DIR=/var/lib/internhub/compile \
    RESUME_ARTIFACT_DIR=/var/lib/internhub/artifacts
USER 10001:10001

RUN printf '%s\n' '\documentclass{article}' \
      '\begin{document}warmup\end{document}' > /tmp/warmup.tex \
    && tectonic --untrusted --outdir /tmp /tmp/warmup.tex \
    && rm -f /tmp/warmup.tex /tmp/warmup.pdf

ENTRYPOINT ["python", "/app/worker.py"]
