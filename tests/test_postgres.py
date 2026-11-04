"""Checks that the PostgreSQL test run really uses PostgreSQL.

If this is skipped in CI, no `postgres` test runs anywhere.
"""

import pytest
from django.db import connection


@pytest.mark.postgres
@pytest.mark.django_db
def test_the_suite_runs_on_postgres_with_the_languages_the_faqs_are_written_in():
    # Both text search configurations ship with PostgreSQL.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT to_tsvector('italian', 'appelli'), to_tsvector('english', 'exams')"
        )
        italian, english = cursor.fetchone()

    assert connection.vendor == "postgresql"
    assert italian == "'appell':1"
    assert english == "'exam':1"
