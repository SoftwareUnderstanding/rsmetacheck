FROM python:3.11-slim

# Runtime defaults: no Poetry venv, non-interactive installs, and SoMEF config values.
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    DEBIAN_FRONTEND=noninteractive \
    NLTK_DATA=/usr/local/share/nltk_data \
    SOMEF_CONFIGURATION_FILE=/root/.somef/config.json \
    SOMEF_BASE_URI=https://w3id.org/okn/i/ \
    SOMEF_DOWNLOAD_LIMIT_MB=1000

WORKDIR /app

# System packages needed to install Python packages with native extensions and clone repos.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry globally; dependencies will still go into the container Python.
RUN pip install poetry

# Install project dependencies first to keep Docker layer caching useful.
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root --no-ansi

# Pre-download NLTK resources used by SoMEF so runtime does not configure interactively.
RUN python -m nltk.downloader -d /usr/local/share/nltk_data \
    wordnet omw-1.4 punkt punkt_tab stopwords

# Copy the application and install only the rsmetacheck package itself.
COPY . .
RUN poetry install --only-root --no-ansi \
    && chmod +x /app/docker-somef-config.sh

# Configure SoMEF from environment variables, then run rsmetacheck through Poetry.
ENTRYPOINT ["/app/docker-somef-config.sh"]
CMD ["rsmetacheck", "--help"]
