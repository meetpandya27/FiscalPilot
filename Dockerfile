FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install FiscalPilot
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir -e ".[all]"

# Create non-root user
RUN useradd --create-home fiscalpilot
USER fiscalpilot

ENTRYPOINT ["fiscalpilot"]
CMD ["--help"]
