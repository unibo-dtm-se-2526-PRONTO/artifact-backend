# Each student's matricola and degree programme move from the user row to a
# new student profile. Nobody else gets one: an employee or an admin had both
# columns empty.
#
# Data the old columns allowed but a profile cannot hold — a student missing
# either value, or someone else with one — stops the migration rather than
# being dropped or invented. Going back writes the values onto the user again.
#
# A migration of its own, between the one creating the table and the one
# dropping the columns: on PostgreSQL, a table cannot be altered in the same
# transaction that has just written rows pointing to it.

from django.db import migrations

from pronto.enums import Role


def copy_to_profiles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    StudentProfile = apps.get_model("accounts", "StudentProfile")
    profiles = []
    invalid = []
    for user in User.objects.order_by("pk"):
        given = [
            bool(value.strip()) for value in (user.matricola, user.degree_programme)
        ]
        if user.role == Role.STUDENT and all(given):
            profiles.append(
                StudentProfile(
                    user=user,
                    matricola=user.matricola,
                    degree_programme=user.degree_programme,
                )
            )
        elif user.role == Role.STUDENT or any(given):
            invalid.append(user.email)
    if invalid:
        raise RuntimeError(
            "These users' matricola and degree programme do not match their "
            f"role (both required of a student, refused from anyone else): "
            f"{', '.join(invalid)}. Correct them, then migrate again."
        )
    StudentProfile.objects.bulk_create(profiles)


def copy_to_users(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    StudentProfile = apps.get_model("accounts", "StudentProfile")
    for profile in StudentProfile.objects.all():
        User.objects.filter(pk=profile.pk).update(
            matricola=profile.matricola, degree_programme=profile.degree_programme
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_studentprofile"),
    ]

    operations = [
        migrations.RunPython(copy_to_profiles, copy_to_users),
    ]
