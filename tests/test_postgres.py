"""Tests that the PostgreSQL test run is really a PostgreSQL test run.

This is the reference example for tests marked `@pytest.mark.postgres`: they
are skipped on the default SQLite database and run when TEST_DATABASE_URL is
set, as it is on CI. If this test is skipped on CI, the tests that need
PostgreSQL are silently not running anywhere.
"""

import pytest
from django.db import connection


@pytest.mark.postgres
@pytest.mark.django_db
def test_the_suite_runs_on_postgres_with_the_languages_the_faqs_are_written_in():
    # FAQs are searched in Italian and in English; both text search
    # configurations ship with PostgreSQL, and this makes sure of it.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT to_tsvector('italian', 'appelli'), to_tsvector('english', 'exams')"
        )
        italian, english = cursor.fetchone()

    assert connection.vendor == "postgresql"
    assert italian == "'appell':1"
    assert english == "'exam':1"
