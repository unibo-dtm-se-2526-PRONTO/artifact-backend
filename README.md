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
poetry run python manage.py seed_offices   # once per database, see Offices
poetry run python manage.py import_faqs export.xlsx   # optional, see Importing FAQs
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

On a new database, create the offices once the backend is up:
`docker compose exec backend python manage.py seed_offices`.

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

`tests/conftest.py` holds what more than one test file needs. For the booking
tests, two offices, their staff, a student, their authenticated clients, and a
`day` that is always a Monday in the future; every employee it makes works
Monday to Friday, 9 to 17, unless a test passes other `shifts` to
`make_employee`. For the accounts and FAQ tests, an anonymous `client` (DRF's
`APIClient`, replacing pytest-django's fixture of the same name), the
`PASSWORD` every test user is given, `make_user`, which names every user it
makes and gives a student the student profile registration would,
`authenticate(user)`, which returns a client carrying that user's token, and `office_for(code)`, the office a FAQ or
a question is filed under, created as `seed_offices` would if missing. Fixtures stay local to a file while one file
owns them; they move to `conftest.py` once a second file needs them.

## Continuous integration

`.github/workflows/check.yml` runs on every push and pull request, on
`ubuntu-latest` and Python 3.12 — the Python of the `Dockerfile`, which is what
the backend runs on in production:

1. **Preliminary Checks** — `poe compile`, `poe static-checks`,
   `poe format-check`, then the suite on SQLite.
2. **Test on PostgreSQL** — the suite again, with coverage, against a
   `postgres:16` service container with the same credentials as the compose
   `db`, selected through `TEST_DATABASE_URL`. This is where the `postgres`
   tests run, and so the only run that reaches the FAQ matching: coverage is
   measured here for that reason. The HTML report is uploaded as a build
   artifact.
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
| POST   | `/api/auth/register/`                   | public  | Create an account, inactive until verified; `role` is derived from the email domain. Payload in [Accounts](#accounts) |
| GET    | `/api/auth/verify/<uidb64>/<token>/`    | public  | The link e-mailed at registration; activates the account |
| POST   | `/api/auth/login/`                      | public  | Exchange email and password for a token          |
| POST   | `/api/auth/logout/`                     | token   | Delete the caller's token                        |
| GET    | `/api/auth/me/`                         | token   | The authenticated user's own data, same shape as the registration response |
| GET    | `/api/faqs/`                            | public  | Published FAQs; filter with `?office=<code>`     |
| GET    | `/api/faqs/<id>/`                       | public  | A single published FAQ                           |
| POST   | `/api/questions/`                       | student | Ask about an office: `{"office": "<code>", "question": "<text>"}`; returns the best-matching FAQ, if any. `?lang` is the language of the question |
| POST   | `/api/questions/<uuid>/resolve/`        | student | The suggested FAQ answered the question; `400` if none was suggested |
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
of exposing the `_it` / `_en` columns. An unsupported code is a `400`. The
questions endpoints are the one twist: there `lang` is the language the
question is written in, and an inquiry is always read back in that language.

## Apps

| App | What it owns |
|-----|--------------|
| `accounts` | the user model and the student profiles, registration, login and e-mail verification |
| `offices` | the helpdesk offices and `seed_offices` |
| `faq` | the FAQs, the questions students ask (`Inquiry`), matching and the import |
| `booking` | employee profiles, shifts and appointments, and the office endpoints |
| `pronto` | the project: settings, URLs, and what every app shares — the enums, the `?lang` handling and the role permissions |

The dependencies run one way. `faq` and `booking` both file their rows under
an office, so both depend on `offices`, which depends on neither; `booking`
also depends on `faq`, since an appointment records the FAQ that did not help,
and `faq` never imports from `booking`. What two apps that do not depend on
each other both need lives in `pronto` instead.

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
appointment legitimately — so `IsEmployee` guards it explicitly. `IsStudent`
and `IsEmployee` live in `pronto/permissions.py`, because `faq` needs
`IsStudent` too and cannot import from `booking`.

### Offices

An office is `offices.Office`, in an app of its own because appointments,
employee profiles, FAQs and students' questions all point to it with a foreign
key. `OfficeCode` in `pronto/enums.py` is the set of valid codes, and the code
is how the API names an office, in requests and responses alike.

The offices are data, not schema, so a fresh database has none: no employee
can choose one, nothing can be booked, and no question can be asked.
`seed_offices` creates one per `OfficeCode`, active, with 30-minute slots, the
Italian name of the code and the English one of the helpdesk spreadsheet:

```bash
poetry run python manage.py seed_offices
```

It only creates the offices that are missing, so running it again is safe and
never undoes a change made in the admin since. The contact addresses it writes
(`orientamento@unibo.it`, ...) follow the university's style but are made up:
correct them in the admin before going live. What a new office looks like is
written once, in `offices/seed.py`: the FAQ import and the migration that
linked the FAQs to their office create a missing office from the same data.
Covered by `tests/test_offices_seed.py`.

The model used to be `booking.Office`. Its table was taken over and renamed to
`offices_office` by the migrations, not copied, so existing databases keep
their offices, with the same ids; only the names of the table's index and
constraints still begin with `booking_office`.

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

Both rules hold under simultaneous requests too. Declaring, withdrawing and
booking lock the employee's row first, so a withdrawal and a booking with the
same employee run one after the other: the booking checks again, under the
lock, that a shift still covers the slot, and the withdrawal sees a booking
that committed while it waited. `tests/test_booking_concurrency.py` runs these
races, and the one between simultaneous bookings, on PostgreSQL only: SQLite
serialises every write, so there would be no race to observe.

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

Each FAQ, and each question a student asks, is filed under an office with a
foreign key to `offices.Office`, protected: an office with FAQs or questions
cannot be deleted, only made inactive. The API still names offices by their
code, as `office` in requests and `office_code` in the FAQs it returns.

### Asking a question

Before booking, a student picks an office and writes their question
(`POST /api/questions/?lang=it|en`). The answer, `201`:

```json
{
  "id": "5b0e6a0e-3f0c-4d7e-9d3a-0c5e8f1b2a47",
  "office": "ADMIN_OFFICE",
  "language": "it",
  "match": {
    "faq": {"id": 3, "question": "Come attivo un tirocinio?", "answer": "..."},
    "office": "INTERNSHIPS",
    "score": 0.61
  },
  "office_reassigned": true,
  "resolved": false
}
```

`match` is `null` when no FAQ is relevant enough. `office` is the office the
student asked; `match.office` the one the answer belongs to, and
`office_reassigned` says they differ, so the client can offer to book with the
right office. If the answer helps, the client calls
`POST /api/questions/<id>/resolve/` and the flow ends there; if not, it books
through `POST /api/appointments/` as usual, passing `match.faq.id` as `faq_id`.
Resolving an inquiry that is already resolved answers `200` again, so a retry
is harmless; one with no suggested FAQ is a `400`. Both endpoints return the
same shape, with texts in the language the question was asked in. Only
students ask and resolve.

Each question is stored as a `faq.Inquiry`, to see what students need that the
FAQs do not cover. It records the office, the text, the language, the FAQ
suggested and its score, and whether it resolved the question — and on purpose
nothing else:

- **no user**: what was asked is what the knowledge base needs, not who asked
  it, so the questions stay anonymous from the start;
- **no appointment**: when the answer does not help, the appointment records
  the FAQ that was shown (`suggested_faq`), so `booking` depends on `faq` and
  never the other way round;
- **a UUID primary key**: the id is handed to the client to resolve the
  question later, and with no user to scope by, an id nobody can guess or
  count is what keeps one student from closing another's question.

The inquiries are listed, read-only, in the admin.

### FAQ matching

The matching lives in `faq/matching.py`; `faq/services.py` stores the result.
It is PostgreSQL full-text search, from `django.contrib.postgres.search`:

- only published FAQs are searched, in the language of the question: its
  question and answer columns, with the `italian` or `english` text search
  configuration, which does the stemming (`certificati` finds `certificato`)
  and drops the stop words (`come`, `il`, `dove`, ...);
- the FAQ's question is weighted `A` and its answer `B`, so a word the FAQ is
  about counts more than one its answer mentions;
- the words of the question are OR-ed (a `websearch` query): a student writes
  a sentence, and requiring every word of it would match almost nothing.
  `ts_rank` averages over the words of the question, so a FAQ scores by how
  much of the question it covers, and short and long questions are comparable;
- a FAQ is suggested only if its score reaches `FAQ_MATCH_MIN_RANK`, `0.1` by
  default, in `pronto/settings.py`. On the examples in
  `tests/test_faq_matching.py`, questions a FAQ answers score 0.15 to 0.65,
  while one that only shares a word with an answer (the "online" of "Studenti
  Online") scores 0.04. The comment on the setting explains the choice;
- the office the student chose is searched first. Only if nothing there
  reaches the threshold are all offices searched, and the best of those is
  returned with its own office.

The vectors are computed at query time, with no stored column and no GIN
index: the knowledge base is a few hundred rows at most, where an index would
not pay for itself. That is the first thing to revisit if it grows by orders
of magnitude.

The search only exists on PostgreSQL. On any other database the service raises
`MatchingUnavailable` instead of reporting "no match", which would look exactly
like a knowledge base with no answer; the tests that reach it are marked
`postgres`.

Semantic search over embeddings (Chroma, IR4) is a planned extension and is
not implemented. The service is split for it: a matcher (`FullTextMatcher`)
only finds the best candidate among a set of FAQs, with its own score and
threshold, while `find_best_match` applies the office-first policy on top. A
vector matcher would implement the same `Matcher` protocol and be passed in.

### Importing FAQs

The knowledge base is seeded from the helpdesk's spreadsheet, with columns
`Ufficio | Office | Domanda | Question | Risposta`:

```bash
poetry run python manage.py import_faqs path/to/export.xlsx [--sheet NAME] [--publish]
```

The export holds real personal data: keep it out of the repository (`*.xlsx`
is git-ignored) and delete it once imported. The command, covered by
`tests/test_faq_import.py`:

- maps the office by its Italian name, then its English one, to `OfficeCode`.
  Rows with an unknown office, no question or no answer are skipped and
  counted by reason, never fatal. Questions are stored whole, however long
- creates the offices it needs that are not in the database yet, as
  `seed_offices` would, and says which; so it can run before `seed_offices`,
  which then only creates the rest. Offices already there are used as they are
- anonymises every question and answer, in both languages, before storing it
- fills the English answer, which the sheet does not have, with the Italian
  one, so English readers get an answer rather than an empty page; a missing
  English question falls back to the Italian one the same way. Translations
  are done in the admin
- creates FAQs **unpublished**: the text is about to go on a public endpoint
  and name detection is heuristic, so someone reads it in the admin first.
  `--publish` skips that review
- is idempotent: `(office, question_it)` is the natural key, so a re-run
  updates the FAQs it finds instead of duplicating them. The Italian answer and
  the English question follow the sheet; an English answer is replaced only
  while it is still the untranslated copy; publication is never touched
- runs in one transaction, and prints how many FAQs were created, updated,
  left unchanged and skipped

Most rows of the current export have no answer yet, so they are skipped: fill
the `Risposta` column and run the command again.

### Anonymisation

NFR4 requires the requester to be unidentifiable. `faq/anonymisation.py`
replaces, covered by `tests/test_faq_anonymisation.py`:

| What | Recognised as | Placeholder |
|------|---------------|-------------|
| e-mail addresses | any address, except the institutional `@unibo.it` | `[EMAIL]` |
| phone numbers | Italian mobiles and landlines, with or without `+39`/`0039`, grouped by spaces, dots or dashes; any `+`-prefixed international number | `[PHONE]` |
| student IDs | a ten-digit Unibo matricola (`00…`), or 5–10 digits after `matricola`, `matr.`, `student ID`… | `[STUDENT_ID]` |
| tax codes | the codice fiscale format | `[TAX_CODE]` |
| names | capitalised words after an honorific (`Prof.`, `dott.ssa`, `Sig.ra`, `Mr`…), a self-introduction (`mi chiamo`, `my name is`; `sono` / `I am` only with first and last name), or a sign-off closing the text (`Grazie, Mario Rossi`) | `[NAME]` |

Institutional contacts: `@unibo.it` addresses are kept because students write
from `@studio.unibo.it`, so such an address is the university's — usually the
office an answer points to — and never the requester's. Phone numbers get no
exception: a student's and an office's look alike, and office numbers are
published elsewhere. Links are left whole.

The limits, which is why imports are unpublished by default:

- names are found only after a cue. A bare "Mario Rossi" mid-sentence, a lone
  first name after `sono`, or a lowercase name is missed; a bare capitalised
  pair is not treated as a name because in this data it is almost always a
  degree course ("Ingegneria Biomedica")
- the cues can over-match: "I am Computer Engineering…" loses the course name.
  `Ing.` is not a cue, since here it abbreviates "Ingegneria"
- matricole shorter than ten digits without a cue, addresses, and other
  indirect details (a rare combination of course and hometown) are not
  recognised

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

### Personal data

Registration asks for different data depending on the role the email domain
grants (FR1, FR2). `RegisterSerializer` derives the role first and then
applies the rules below; the admin applies the same ones.

| Field | Student | Employee |
|-------|---------|----------|
| `first_name`, `last_name` | required | required |
| `matricola` | required, unique | refused |
| `degree_programme` | required, up to 200 characters | refused |

- **Matricola**: digits only, 6 to 10 of them. Current Unibo matricole have
  ten digits, zero-padded (`0001012345`); older ones are shorter. It is stored
  as text, exactly as given: leading zeros are kept and nothing is padded, so
  `123456` and `0000123456` are two different values. Unique among students.
- **Degree programme** (corso di studi): free text. There is no list of
  degree programmes in the project to validate it against.
- **Employees** sending a non-empty `matricola` or `degree_programme` get a
  `400` naming the field, rather than having it silently dropped: an employee
  sending a matricola has most likely typed the wrong address. Empty strings
  are accepted. The employee's office is not part of registration: it is
  chosen afterwards through `POST /api/employee-profile/` (see
  [Shifts](#shifts)).
- **Admins**, created with `createsuperuser`, have no student data, but need a
  first and a last name like everybody else: the command asks for them
  (`--first_name` and `--last_name` with `--noinput`).

`POST /api/auth/register/`, a student:

```json
{
  "email": "mario.rossi@studio.unibo.it",
  "password": "…",
  "first_name": "Mario",
  "last_name": "Rossi",
  "matricola": "0001012345",
  "degree_programme": "Ingegneria e scienze informatiche"
}
```

An employee sends the same without `matricola` and `degree_programme`. The
`201` response, and `GET /api/auth/me/`, return the account without the
password:

```json
{
  "id": 7,
  "email": "mario.rossi@studio.unibo.it",
  "role": "STUDENT",
  "first_name": "Mario",
  "last_name": "Rossi",
  "matricola": "0001012345",
  "degree_programme": "Ingegneria e scienze informatiche"
}
```

For an employee, `matricola` and `degree_programme` are `""`. A validation
error is a `400` keyed by field, e.g. `{"matricola": ["A matricola is a number
of 6 to 10 digits."]}`.

### Data model

The user table holds what every user has, and nothing that is empty for a
whole role: every column is `NOT NULL`, and the names cannot be `""` either,
which a check constraint enforces on top of the forms and the API. The one
exception is `last_login`, `NULL` until the user first logs in (see below).

What only some users have lives in a profile, one-to-one with the user:

| Table | Who has one | Holds | App |
|-------|-------------|-------|-----|
| `accounts_studentprofile` | every student, nobody else | `matricola` (unique), `degree_programme` | `accounts` |
| `booking_employeeprofile` | employees, once they choose an office | `office` | `booking` |

`StudentProfile` follows the pattern of `EmployeeProfile`, with two
differences. Its primary key is the user's own, since a profile is part of
the user and never moves to another one. And it belongs to `accounts`, being
personal data given at registration, while the office an employee works for
is the booking slice's business. Both columns are required and refuse `""`
in the database too; the matricola is unique.

"A student has a student profile, and nobody else does" is the invariant the
schema cannot express: a constraint would have to span both tables. It is
upheld where users are written:

- registration creates the user and the profile in one transaction, so a
  profile that fails to save takes the user with it
- the admin edits the profile inline on the user's page, asks a student for
  one, and refuses one to anybody else
- anything else writing users — a migration, a fixture, the shell — has to
  uphold it itself, as for the invariant of `Appointment`

The API does not show the split: registration takes `matricola` and
`degree_programme` alongside the rest, and `/api/auth/me/` returns them, `""`
for anybody without a profile.

The student data used to be two blank-able columns of the user table. The
migrations `accounts.0004`–`0006` moved each student's values to a profile and
dropped the columns; they stop, listing the accounts, if a student lacks
either value or someone else has one, rather than inventing or losing data.
`0007` likewise stops on users without a name before adding the constraints.
Both can be reversed.

In the admin, users can still be searched by matricola.

### Passwords and tokens

- Passwords are stored only as salted hashes, by Django's default hasher
  (PBKDF2), through `set_password`. No serializer has a readable `password`
  field, and `tests/test_accounts_auth.py` checks that neither the password
  nor its hash appears in any response of the sign-up flow.
- Registration runs every validator in `AUTH_PASSWORD_VALIDATORS` — minimum
  length, common passwords, entirely numeric passwords, and similarity to the
  email and the names — against the candidate user.
- Sessions use DRF's `TokenAuthentication`: `POST /api/auth/login/` returns a
  random 40-character key, stored server-side in `authtoken_token`, one per
  user. The key is not signed and does not expire; it stops working only when
  the user logs out, which deletes it. Only the e-mail verification link is a
  signed token with a lifetime (Django's `default_token_generator`, valid for
  `PASSWORD_RESET_TIMEOUT`, three days by default).
- A login through `POST /api/auth/login/` records `last_login`. The view sends
  Django's `user_logged_in` signal, as a session login would, and Django's own
  receiver updates the column; a `NULL` means the user has never logged in.
  Since the verification token is derived from `last_login`, a verification
  link stops working once its account has logged in, which it can only do
  after the link was opened.
