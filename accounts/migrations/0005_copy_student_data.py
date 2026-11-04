# Moves each student's matricola and degree programme to a student profile.
# Data a profile cannot hold stops the migration. A separate migration because
# PostgreSQL cannot alter a table in the transaction that wrote rows to it.

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
