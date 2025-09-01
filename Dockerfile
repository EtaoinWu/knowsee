# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

RUN apt-get update
RUN apt-get install -y locales locales-all openssl

# Set workdir
WORKDIR /app

# Copy project files
ADD . /app

# Install dependencies with uv
RUN uv sync --locked

# Set entrypoint (adjust as needed)
CMD ["uv", "run", "main.py"]
