# PRONTO backend

PRONTO automates the phone helpdesk of the Campus of Cesena. Students look for
an answer among the FAQs of each office and, when none helps, book an
appointment with the office's staff.

This repository is the backend, a Django REST API on PostgreSQL. The web app is
in [artifact-frontend](https://github.com/unibo-dtm-se-2526-PRONTO/artifact-frontend).

## Run PRONTO

The whole application runs from the Docker images published on GHCR. You need
only [Docker](https://docs.docker.com/get-docker/) with Docker Compose.

**1. Download the compose file** into an empty folder:

```bash
mkdir pronto && cd pronto
curl -O https://raw.githubusercontent.com/unibo-dtm-se-2526-PRONTO/artifact-backend/master/docker-compose.release.yml
```

**2. Start PRONTO:**

```bash
docker compose -f docker-compose.release.yml up -d
```

The first start downloads the images and takes a few minutes. It starts
PostgreSQL, Chroma, the backend and the web app, applies the migrations and
loads the offices and the helpdesk FAQs.

**3. Create the administrator account:**

```bash
docker compose -f docker-compose.release.yml exec backend python manage.py createsuperuser
```

It asks for an e-mail address, a first and last name and a password.

**4. Open <http://localhost:8080>.**

- The admin site is <http://localhost:8080/admin/>: log in with the account
  of step 3 to edit the FAQs, the offices and the users.
- Register as a student with an `@studio.unibo.it` address, or as an employee
  with an `@unibo.it` address. Employees choose their office and add their
  weekly shifts before students can book them.
- E-mails are not sent: they are printed in the backend log,
  `docker compose -f docker-compose.release.yml logs backend`.

**5. Stop PRONTO** with `docker compose -f docker-compose.release.yml down`.
Add `-v` to delete its data as well.

To pin a version instead of `latest`, set `BACKEND_TAG` and `FRONTEND_TAG`
(e.g. `BACKEND_TAG=1.2.0`); `FRONTEND_HOST_PORT` changes the port `8080`.

## Other ways to run it

### From PyPI

The `pronto-helpdesk` package contains the API and the admin site, without the
web app. It needs Python 3.10 or later and a PostgreSQL database.

```bash
pip install pronto-helpdesk
```

Create a `.env` in the folder you run it from, with at least `SECRET_KEY`,
`DEBUG=True` and the `DB_*` keys of your database (see
[Configuration](#configuration)). Then:

```bash
pronto-helpdesk migrate
pronto-helpdesk seed_offices
pronto-helpdesk seed_faqs
pronto-helpdesk createsuperuser
pronto-helpdesk runserver
```

The API is on <http://localhost:8000/api/> and the admin site on
<http://localhost:8000/admin/>.

### From source

For development. You need Docker and
[Poetry](https://python-poetry.org/) 2.2.1. Clone the backend and the frontend
side by side:

```bash
git clone https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend.git
git clone https://github.com/unibo-dtm-se-2526-PRONTO/artifact-frontend.git
cd artifact-backend
cp .env.example .env              # set SECRET_KEY and DEBUG=True
docker compose up --build
```

This builds the sources and starts the API on <http://localhost:8000> and the
web app on <http://localhost:5173>. On a new database, in a second terminal:

```bash
docker compose exec backend python manage.py seed_offices
docker compose exec backend python manage.py seed_faqs
docker compose exec backend python manage.py createsuperuser
```

Tests and checks:

```bash
poetry install
poetry run poe test               # on in-memory SQLite
poetry run poe static-checks      # ruff and mypy
poetry run poe format-check
```

The full-text and concurrency tests need PostgreSQL and are skipped on SQLite.
To run them on the `db` container:

```bash
docker compose up -d --wait db
TEST_DATABASE_URL=postgres://pronto:pronto@localhost:5432/pronto?sslmode=disable \
    poetry run poe test
```

## Configuration

The backend reads these keys from the environment or from a `.env` file.
`.env.example` lists them all.

| Key | Default | Meaning |
|-----|---------|---------|
| `SECRET_KEY` | none | Required |
| `DEBUG` | `False` | Debug mode; `True` also serves the admin's static files |
| `ALLOWED_HOSTS` | empty | Comma-separated, required when `DEBUG` is off |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | | PostgreSQL connection |
| `DB_SSLMODE` | `require` | `disable` for a local server without SSL |
| `CHROMA_HOST`, `CHROMA_PORT` | empty, `8000` | Semantic FAQ search; off when `CHROMA_HOST` is empty |
| `EMAIL_BACKEND` | console | The SMTP backend sends real e-mails (`EMAIL_HOST`, `EMAIL_PORT`, ...) |

## License

Apache 2.0
