"""Tests that the test database works.

This is the reference example for tests that touch the database: mark them with
`@pytest.mark.django_db` and pytest-django will give each test a clean,
transaction-isolated database. It uses the user model only as an example;
real tests should use the models of the app under test.
"""

import pytest
from django.contrib.auth import get_user_model


User = get_user_model()


@pytest.mark.django_db
def test_can_write_and_read_the_database():
    User.objects.create_user(
        email="operatore@unibo.it", password="irrelevant-passphrase"
    )

    assert User.objects.filter(email="operatore@unibo.it").exists()


@pytest.mark.django_db
def test_each_test_gets_a_clean_database():
    # The user created above must not leak into this test.
    assert not User.objects.filter(email="operatore@unibo.it").exists()
