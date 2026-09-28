FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

# The one Poetry version of the project: CI reads it from this line, so bump
# it here and nowhere else.
ARG POETRY_VERSION=2.2.1
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]
