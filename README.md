# PRONTO backend

PRONTO automates the phone helpdesk of the Campus of Cesena. Students look for
an answer among the FAQs of each office and, when none helps, book an
appointment with the office's staff.

This is the backend: a Django and Django REST Framework API on PostgreSQL. The
frontend is a separate Vue repository.

## Getting started

You need Poetry 2.2.1 (the version pinned in the `Dockerfile`).

```bash
poetry install
cp .env.example .env                  # then fill in the values
poetry run python manage.py migrate
poetry run python manage.py seed_offices
poetry run python manage.py import_faqs export.xlsx   # optional
poetry run python manage.py runserver
```

### With Docker Compose

```bash
docker compose up --build
```

This starts PostgreSQL (`db`), Chroma (`chroma`), the API on
<http://localhost:8000> and the frontend on <http://localhost:5173>. The
frontend is built from `../artifact-frontend`, so clone it next to this
repository.

On a new database, create the offices and index the FAQs:

```bash
docker compose exec backend python manage.py seed_offices
docker compose exec backend python manage.py rebuild_faq_index
```

`docker compose down -v` deletes the database volume.

## Tests

```bash
poetry run poe test              # test suite
poetry run poe coverage          # suite with coverage
poetry run poe coverage-report
poetry run poe static-checks     # ruff and mypy
poetry run poe format
```

Tests run on an in-memory SQLite database by default. Full-text search and the
booking concurrency tests need PostgreSQL: they are marked
`@pytest.mark.postgres` and skipped on SQLite. To run them:

```bash
docker compose up -d --wait db
TEST_DATABASE_URL=postgres://pronto:pronto@localhost:5432/pronto?sslmode=disable \
    poetry run poe test
```

All tests live in `tests/`.

## Configuration

`.env.example` lists every key.

| Key | Default | Meaning |
|-----|---------|---------|
| `SECRET_KEY` | none | Required outside tests |
| `DEBUG` | `False` | Debug mode |
| `ALLOWED_HOSTS` | empty | Comma-separated, required when `DEBUG` is off |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | | PostgreSQL connection |
| `DB_SSLMODE` | `require` | `disable` for a local server without SSL |
| `TEST_DATABASE_URL` | empty | Run the tests on PostgreSQL instead of SQLite |
| `CHROMA_HOST`, `CHROMA_PORT` | empty, `8000` | Semantic FAQ search; off when `CHROMA_HOST` is empty |
| `EMAIL_BACKEND` | console | Set to the SMTP backend to send real e-mails (`EMAIL_HOST`, `EMAIL_PORT`, ...) |

## API

Every endpoint needs a token (`Authorization: Token <key>`) unless marked
public. Endpoints that return stored text accept `?lang=it|en`.

| Method | Path | Who | Description |
|--------|------|-----|-------------|
| GET | `/api/health/` | public | Status and version |
| POST | `/api/auth/register/` | public | Create an account; the role comes from the e-mail domain |
| POST | `/api/auth/login/` | public | Get a token |
| POST | `/api/auth/logout/` | token | Delete the token |
| GET | `/api/auth/me/` | token | Current user |
| GET | `/api/faqs/` | public | Published FAQs, `?office=<code>` to filter |
| GET | `/api/faqs/<id>/` | public | One FAQ |
| POST | `/api/questions/` | student | Ask a question, get the best matching FAQ |
| POST | `/api/questions/<uuid>/resolve/` | student | Mark the suggested FAQ as helpful |
| GET | `/api/offices/` | token | Offices taking bookings |
| GET | `/api/offices/<code>/availability/` | token | Free slots on `?date=YYYY-MM-DD` |
| GET | `/api/appointments/` | token | The caller's appointments |
| POST | `/api/appointments/` | student | Book a slot |
| POST | `/api/appointments/<id>/cancel/` | student, employee | Cancel an appointment |
| POST | `/api/appointments/<id>/complete/` | employee | Mark an appointment as done |
| GET, POST | `/api/employee-profile/` | employee | Read or choose the employee's office |
| GET, POST | `/api/shifts/` | employee | List or add weekly shifts |
| DELETE | `/api/shifts/<id>/` | employee | Remove a shift |

`@studio.unibo.it` addresses register as students, `@unibo.it` addresses as
employees. Other domains are refused.

## Project structure

| App | Contents |
|-----|----------|
| `pronto` | Settings, URLs, shared enums and permissions |
| `accounts` | Users, student profiles, registration and login |
| `offices` | Offices and the `seed_offices` command |
| `faq` | FAQs, student questions, matching, import and anonymisation |
| `booking` | Employee profiles, shifts, appointments and e-mail notifications |

FAQ matching tries PostgreSQL full-text search first and falls back to
semantic search with Chroma. FAQs are managed in the Django admin or imported
from the helpdesk spreadsheet with `import_faqs`, which anonymises the text and
leaves the FAQs unpublished.

## CI and releases

GitHub Actions runs the checks and the test suite, on SQLite and on
PostgreSQL, for every push and pull request. A merge into `develop` also
applies the migrations to the shared Neon database.

Releases are made by semantic-release from `master`, based on
[Conventional Commits](https://www.conventionalcommits.org/). Each release
creates a tag, a GitHub release, an entry in `CHANGELOG.md`, and publishes the
`pronto-helpdesk` package to TestPyPI, or to PyPI when the repository variable
`PUBLISH_TO_PYPI` is `true`. The package index token is the `PYPI_TOKEN`
secret.

## License

Apache 2.0
