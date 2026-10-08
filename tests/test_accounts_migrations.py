"""Tests for the data migrations of the accounts app.

The migration's function is called on the current models rather than by
migrating a database back and forth: what is tested is which rows it picks.
"""

from importlib import import_module

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone

from tests.conftest import make_user

User = get_user_model()

activate_unverified = import_module(
    "accounts.migrations.0008_activate_accounts"
).activate_unverified


@pytest.mark.django_db
def test_activates_the_inactive_users_who_never_logged_in():
    unverified = make_user("mario.rossi@studio.unibo.it", User.Role.STUDENT)
    User.objects.filter(pk=unverified.pk).update(is_active=False)

    activate_unverified(apps, None)

    unverified.refresh_from_db()
    assert unverified.is_active


@pytest.mark.django_db
def test_leaves_an_inactive_user_who_has_logged_in_inactive():
    # Deactivated by an admin after using the account.
    deactivated = make_user("anna.bianchi@unibo.it", User.Role.EMPLOYEE)
    User.objects.filter(pk=deactivated.pk).update(
        is_active=False, last_login=timezone.now()
    )

    activate_unverified(apps, None)

    deactivated.refresh_from_db()
    assert not deactivated.is_active


@pytest.mark.django_db
def test_leaves_active_users_as_they_are():
    active = make_user("mario.rossi@studio.unibo.it", User.Role.STUDENT)

    activate_unverified(apps, None)

    active.refresh_from_db()
    assert active.is_active
