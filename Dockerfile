# Base image with Python 3.12
FROM python:3.12-slim

# Install Postgres client deps and Fortran toolchain needed by pyslalib
RUN apt-get update \
  && apt-get install -y \
      build-essential \
      curl \
      gfortran \
      ninja-build \
      libpq-dev \
      postgresql-client \
      gdal-bin \
      libgdal-dev \
      libproj-dev \
  && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Poetry
ENV POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    PATH="/opt/poetry/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | python3 - && poetry --version

# Copy only pyproject/lock first (cache deps)
COPY pyproject.toml poetry.lock README.md ./

# Install Python deps into .venv
RUN poetry install --no-interaction --no-ansi --no-root \
  \
  && poetry run pip install gunicorn

# Copy rest of the code
COPY . .

# Copy the DB-wait helper and make it executable
COPY wait-for-db.sh /usr/local/bin/wait-for-db.sh
RUN chmod +x /usr/local/bin/wait-for-db.sh

# Set environment variable
ENV DJANGO_SETTINGS_MODULE=heroic_base.settings

# Expose port and define default entrypoint
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/wait-for-db.sh"]
CMD poetry run gunicorn \
     --workers $GUNICORN_WORKERS \
     --bind 0.0.0.0:8000 \
     heroic_base.wsgi:application
