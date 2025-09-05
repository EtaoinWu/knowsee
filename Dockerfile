# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

RUN apt-get update && apt-get install -y locales locales-all openssl curl && rm -rf /var/lib/apt/lists/* \
    && (curl https://ca.i.3t.al/roots.pem --insecure | tee /usr/local/share/ca-certificates/3t-al.pem) && update-ca-certificates

# Set workdir
WORKDIR /app

# Copy project files
ADD . /app

# Install dependencies with uv
RUN uv sync --locked

ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

# Set entrypoint (adjust as needed)
CMD ["uv", "run", "main.py"]
