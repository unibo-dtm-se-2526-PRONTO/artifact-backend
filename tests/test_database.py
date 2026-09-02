"""Tests that the test database works.

This is the reference example for tests that touch the database: mark them with
`@pytest.mark.django_db` and pytest-django will give each test a clean,
transaction-isolated database. It uses `User` only because no domain model
exists yet; real tests should use the models in `booking`.
"""

import pytest
from django.contrib.auth.models import User


@pytest.mark.django_db
def test_can_write_and_read_the_database():
    User.objects.create_user(username="operatore", password="irrelevant")

    assert User.objects.filter(username="operatore").exists()


@pytest.mark.django_db
def test_each_test_gets_a_clean_database():
    # The user created above must not leak into this test.
    assert not User.objects.filter(username="operatore").exists()
