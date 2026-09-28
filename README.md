# PRONTO — backend

The backend of PRONTO, the web application that automates the phone helpdesk
of the Campus of Cesena: students look for an answer among the FAQs of each
office and, when none helps, book an appointment with the office's staff.

It is a Django and Django REST Framework project on PostgreSQL. The frontend
lives in its own repository.

## Getting started

The project uses **Poetry 2.2.1**. That version is written in one place, the
`ARG POETRY_VERSION` line of the `Dockerfile`: the image installs it from
there, and so does CI. Install the same one locally, for example with
`pipx install poetry==2.2.1`, then:

```bash
poetry install                   # creates .venv/ inside the project
cp .env.example .env             # then fill in the keys, see Configuration
poetry run python manage.py migrate
poetry run python manage.py runserver
```

### With Docker Compose

```bash
docker compose up --build
```

starts two containers: `db`, a PostgreSQL 16, and `backend`, which applies the
migrations and serves the API on <http://localhost:8000>. The backend waits
until `pg_isready` reports the database healthy, so it never starts migrating
against a server that is still booting.

In compose the backend always talks to the `db` container: `docker-compose.yml`
overrides the `DB_*` keys, whatever `.env` says, and turns SSL off, because the
local server has no certificate. Everything else — `SECRET_KEY` first of all —
still comes from `.env`. The database lives in the `pgdata` volume;
`docker compose down -v` throws it away.

`db` is published on `localhost:5432`, and on localhost only. If that port is
taken by a PostgreSQL of your own, set `POSTGRES_HOST_PORT` (in the shell or in
`.env`) to publish it elsewhere.

## Running the tests

```bash
poetry install
poetry run poe test              # run the suite
poetry run poe coverage          # run with coverage
poetry run poe coverage-report   # print the coverage report
poetry run poe static-checks     # ruff + mypy
poetry run poe format            # apply formatting (CI checks it)
```

## Test database

By default tests run against an **in-memory SQLite** database, configured in
`pronto/settings.py`. They need neither credentials nor network access, so
`poe test` works on a fresh clone with no `.env` and no database server.

SQLite is not PostgreSQL, though. There is no full-text search, which the FAQ
matching relies on, and SQLite locks the whole database on a write rather than
a row, so two bookings racing for the same slot never really race. Setting
`TEST_DATABASE_URL` runs the same suite against PostgreSQL instead:

```bash
docker compose up -d --wait db
TEST_DATABASE_URL=postgres://pronto:pronto@localhost:5432/pronto?sslmode=disable \
    poetry run poe test
```

Django creates its own `test_pronto` database on that server and drops it at
the end, so the `pronto` database the backend container uses is left alone.
The variable can also go in `.env`, to make PostgreSQL your default; leave it
empty to go back to SQLite. The URL is deliberately a separate key rather than
the `DB_*` ones, so a test run never ends up on the hosted development database.

### Tests that only make sense on PostgreSQL

Mark them with `@pytest.mark.postgres`:

```python
@pytest.mark.postgres
@pytest.mark.django_db
def test_a_faq_is_found_by_the_stem_of_a_word():
    ...
```

On SQLite they are skipped, with `needs PostgreSQL: set TEST_DATABASE_URL` as
the reason (`poe test -rs` lists them); on PostgreSQL they run like any other.
The marker is registered in `pyproject.toml` and the skipping is done by a hook
in `tests/conftest.py`. `tests/test_postgres.py` is the example to copy from,
and a check in its own right: if it is skipped on CI, nothing marked
`postgres` is running anywhere.

Use the marker only when SQLite cannot express the behaviour at all. Anything
that can run on both should, so it is also covered by the fast default run.

## How we write tests (TDD)

We follow test-driven development where it pays off, not dogmatically.

**Write the test first for:**
- domain logic (booking rules, validation, slot availability, conflicts)
- API endpoint behaviour — given this request, expect this status and this JSON

**Do not write tests for:**
- migrations, `settings`, admin registrations, purely declarative serializers

Testing those means testing Django, not our code, and produces brittle tests
that break on every refactor.

The cycle: write a failing test → minimal code to make it pass → refactor.

## Test layout

All tests live in `tests/`, never in an app's own `tests.py`. CI points at
`tests/`, so a test file anywhere else simply never runs.

Two reference examples to copy from:
- `tests/test_health.py` — endpoint test using DRF's `APIClient`
- `tests/test_faq_models.py` — database tests using the `@pytest.mark.django_db`
  marker, which gives each test a clean, isolated database

`tests/conftest.py` holds the fixtures the booking test files share — two
offices, their staff, a student, their authenticated clients, and a `day` that
is always a Monday in the future. Every employee it makes works Monday to
Friday, 9 to 17, unless a test passes other `shifts` to `make_employee`. Fixtures stay local to a file while one file
owns them, as the accounts tests do; they move to `conftest.py` once a second
file needs the same cast.

## Continuous integration

`.github/workflows/check.yml` runs on every push and pull request, on
`ubuntu-latest` and Python 3.12 — the Python of the `Dockerfile`, which is what
the backend runs on in production:

1. **Preliminary Checks** — `poe compile`, `poe static-checks`,
   `poe format-check`, then the suite with coverage on SQLite. The HTML
   coverage report is uploaded as a build artifact.
2. **Test on PostgreSQL** — the suite again, against a `postgres:16` service
   container with the same credentials as the compose `db`, selected through
   `TEST_DATABASE_URL`. This is where the `postgres` tests run.
3. **Deploy** — semantic-release, which only releases from `master` (see
   below).

A change is green only when both runs pass.

## Releases

`.github/workflows/deploy.yml` runs [semantic-release](https://semantic-release.gitbook.io)
after CI. It reads the commit messages, which therefore follow
[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/): `feat`
makes a minor release, `fix` and `docs` a patch, a `!` a major one, while
`chore`, `ci`, `test` and `refactor` make none, dependency updates aside. A
release is a git tag, a GitHub release, the new version in `pyproject.toml`
(written by `poetry version`) and an entry in `CHANGELOG.md`, committed back
as `chore(release): …`.

Nothing is published to PyPI: `pyproject.toml` sets `package-mode = false`, as
this is an application to deploy, not a library to install. The workflow needs
one secret, `RELEASE_TOKEN`, a GitHub token allowed to push to the repository.

Dependency updates are proposed by [Renovate](https://docs.renovatebot.com/),
configured in `renovate.json`, and merged automatically once CI passes.

## Configuration

`.env` is not versioned; `.env.example` lists every key. Three of them decide
how the app behaves outside tests:

| Key | Default | Meaning |
|-----|---------|---------|
| `SECRET_KEY` | — | Required. Missing outside tests, Django refuses to start |
| `DEBUG` | `False` | Accepts `1`, `true`, `yes`, `on`. Off unless asked for, so a deployment that forgets it does not serve tracebacks |
| `ALLOWED_HOSTS` | empty | Comma-separated. Required once `DEBUG` is off; in debug it defaults to localhost |

The database is read from `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` and
`DB_PORT`. `DB_SSLMODE` defaults to `require`, because the hosted database
only accepts encrypted connections; set it to `disable` for a local PostgreSQL
without SSL, as `docker-compose.yml` does for its `db`. Two more keys concern
only a developer's machine: `TEST_DATABASE_URL` (empty: tests on SQLite, see
[Test database](#test-database)) and `POSTGRES_HOST_PORT` (default `5432`, the
host port of the compose `db`).

E-mails are printed to the console unless `EMAIL_BACKEND` is set to
`django.core.mail.backends.smtp.EmailBackend`; the SMTP server is then read
from `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` and
`EMAIL_USE_TLS`, all listed in `.env.example`.

`TIME_ZONE` is `Europe/Rome`, and this is load-bearing rather than cosmetic:
the booking grid builds its slots in the active timezone, so a shift declared
9-17 means the office's nine to five. Under UTC the same shift would offer
students 11:00-19:00 local time.

## Endpoints

All endpoints require a token (`Authorization: Token <key>`) except where the
Auth column says "public". The project-wide defaults are `TokenAuthentication`
and `IsAuthenticated`, set in `pronto/settings.py`.

| Method | Path                                    | Auth    | Description                                      |
|--------|-----------------------------------------|---------|--------------------------------------------------|
| GET    | `/api/health/`                          | public  | Health check, returns `{"status": "ok"}`         |
| POST   | `/api/auth/register/`                   | public  | Create an account; `role` is derived from the email domain |
| POST   | `/api/auth/login/`                      | public  | Exchange email and password for a token          |
| POST   | `/api/auth/logout/`                     | token   | Delete the caller's token                        |
| GET    | `/api/auth/me/`                         | token   | The authenticated user's own data                |
| GET    | `/api/faqs/`                            | public  | Published FAQs; filter with `?office=<code>`     |
| GET    | `/api/faqs/<id>/`                       | public  | A single published FAQ                           |
| GET    | `/api/offices/`                         | token   | The offices currently taking bookings            |
| GET    | `/api/offices/<code>/availability/`     | token   | Free slots on `?date=YYYY-MM-DD` (required)      |
| GET    | `/api/appointments/`                    | token   | The caller's own appointments                    |
| POST   | `/api/appointments/`                    | student | Book a slot; the employee is assigned server-side. Optional `faq_id`: the FAQ the student was shown and did not find helpful |
| POST   | `/api/appointments/<id>/cancel/`        | student / employee | Cancel one of the caller's appointments |
| POST   | `/api/appointments/<id>/complete/`      | employee | Record that an appointment assigned to the caller took place |
| GET    | `/api/employee-profile/`                | employee | The caller's office; `404` until one is chosen   |
| POST   | `/api/employee-profile/`                | employee | Choose the caller's office, once: `{"office": "<code>"}` |
| GET    | `/api/shifts/`                          | employee | The caller's weekly shifts                       |
| POST   | `/api/shifts/`                          | employee | Declare a shift: `{"weekday": 0-6, "start_time": "HH:MM", "end_time": "HH:MM"}`, `0` is Monday |
| DELETE | `/api/shifts/<id>/`                     | employee | Withdraw a shift; `400` listing the `appointments` it still covers |

Every endpoint that returns stored text accepts `?lang=it|en` (`it` by
default) and answers with neutral keys — `name`, `question`, `answer` — instead
of exposing the `_it` / `_en` columns. An unsupported code is a `400`.

## Booking

Appointments are never created directly from a view. Every booking goes through
`booking/services.py`, which is where the one invariant the schema cannot
express is upheld: an appointment's employee must work for the appointment's
office (see the docstring of `Appointment`). The service picks the employee
from `office.employees`, so the client neither chooses nor sees a way to
choose one.

The rules, all covered by `tests/test_booking_services.py`:

- a slot lasts `office.slot_duration_minutes`; an office's day is a grid that
  starts at midnight and steps by that length, read in `TIME_ZONE`
  (`Europe/Rome`) — the office's local time, not the server's
- availability is derived from the employees' weekly shifts and never stored:
  a slot on the grid is open when some employee has a shift covering the whole
  of it, and stays bookable while one of those employees is free
- among the employees on duty and free in a slot, the booking goes to whoever
  holds the fewest appointments still `BOOKED`, ties broken by primary key. The
  balance is best-effort under simultaneous requests: the counts are read
  before the insert, so what is guaranteed is only that nobody is double-booked
- if a simultaneous request takes the chosen employee first, the booking is
  retried with the next colleague free in that slot; the student is told the
  slot is gone only when nobody on duty is left
- cancelling frees the slot again, which is why the uniqueness constraint on
  `(employee, slot)` only applies to appointments still in `BOOKED`
- slots in the past, inactive offices and slots nobody is on duty for are
  refused
- an appointment is completed by the employee handling it, and only once it
  has started: "completed" means the question was answered, which cannot have
  happened at a meeting still in the future. It is the mirror of the rule that
  refuses to cancel a meeting already under way

Students book; employees answer, and close the appointment when they have.
A student sees only their own appointments, an employee only those assigned to
them, an admin all of them. Asking for someone else's appointment returns
`404`, not `403`: whether it exists is not the caller's business. Completing
is the one action scoping alone does not protect — a student reaches their own
appointment legitimately — so `IsEmployee` guards it explicitly.

### Shifts

Employees set up their own availability. After registering, an employee
chooses their office once (`POST /api/employee-profile/`); from then on only an
admin can move them, because changing office would leave their booked
appointments with an office they no longer work for. Shifts are then declared
and withdrawn through `booking/services.py`, covered by
`tests/test_booking_shifts.py`:

- a shift repeats every week on one weekday; an employee can have several on
  the same day (a morning and an afternoon) but they cannot overlap
- a shift starts and ends on the office's slot grid: at a 30-minute office,
  9:15 is refused, because the quarter of an hour before 9:30 could never be
  booked. If the office's slot length changes later, existing shifts are left
  as they are and offer the slots they still cover whole
- a shift cannot be withdrawn while the employee's own future `BOOKED`
  appointments fall inside it; the refusal lists them, so the employee cancels
  them first. There is no edit: changing a shift is withdrawing it and
  declaring another, so both rules apply to every change
- shifts written from the admin skip these checks, as appointments do

### Notifications

Every booking and cancellation sends e-mails, from `booking/notifications.py`,
covered by `tests/test_booking_notifications.py`:

| Event | Who is told | Language |
|-------|-------------|----------|
| booked | the student, as a confirmation | the language of the question |
| booked | the assigned employee, with the question and the FAQ that did not help | Italian |
| cancelled by the student | the employee | Italian |
| cancelled by the employee | the student | the language of the question |
| cancelled by an admin | both | as above |

Completing an appointment sends nothing. Each e-mail carries the office, the
date and time in the helpdesk's local time, and the question, so it can be
acted on without opening the app.

The service registers the e-mails inside the transaction that changes the
appointment, and they are sent only once it commits: a booking that is rolled
back, or lost to a simultaneous request, tells nobody. Delivery is
best-effort. A failed e-mail is logged and the booking stands, and each e-mail
goes out on its own, so one bounced address does not silence the other. The
texts are plain-text templates in `booking/templates/booking/email/`, one per
e-mail and language, with the subject on the first line.

## FAQ

The FAQ endpoints are public, unlike the rest of the API. They exist to spare a
phone call, so requiring an account first would defeat their purpose. Writing
is not exposed over HTTP at all — FAQs are maintained in the Django admin.

`faq.Faq` stores `office_code` as a plain choices field rather than a foreign
key to `booking.Office`: the two slices share the `OfficeCode` enum in
`pronto/enums.py` and nothing else, so neither has to migrate or deploy with
the other.

## Accounts

The user model is `accounts.User`; always reference it as
`settings.AUTH_USER_MODEL` in foreign keys, never by importing it directly.

Users log in with their institutional email, which also determines their role
and cannot be chosen by the client:

| Email domain        | Role       |
|---------------------|------------|
| `@studio.unibo.it`  | `STUDENT`  |
| `@unibo.it`         | `EMPLOYEE` |

Any other domain is rejected with `400`.
