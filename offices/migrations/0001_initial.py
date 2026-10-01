# The office used to be `booking.Office`. Moving a model between apps is done
# in state only, so not a row is copied: this migration takes over the table
# booking created (hence the dependency, and `db_table`), booking 0004 lets go
# of it, and 0002 then renames the table to this app's own name.

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("booking", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Office",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        (
                            "code",
                            models.CharField(
                                choices=[
                                    ("GUIDANCE", "Orientamento"),
                                    ("ADMIN_OFFICE", "Segreteria studenti"),
                                    ("INTERNATIONAL", "Relazioni internazionali"),
                                    ("INTERNSHIPS", "Tirocini"),
                                ],
                                max_length=32,
                                unique=True,
                                verbose_name="codice ufficio",
                            ),
                        ),
                        (
                            "name_it",
                            models.CharField(
                                max_length=128, verbose_name="nome (italiano)"
                            ),
                        ),
                        (
                            "name_en",
                            models.CharField(
                                max_length=128, verbose_name="nome (inglese)"
                            ),
                        ),
                        (
                            "contact_email",
                            models.EmailField(
                                max_length=254, verbose_name="email di contatto"
                            ),
                        ),
                        (
                            "slot_duration_minutes",
                            models.PositiveIntegerField(
                                default=30,
                                help_text="Lunghezza di un appuntamento presso questo ufficio.",
                                verbose_name="durata dello slot (minuti)",
                            ),
                        ),
                        (
                            "is_active",
                            models.BooleanField(
                                default=True,
                                help_text="Gli uffici non attivi non accettano nuove prenotazioni.",
                                verbose_name="attivo",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "ufficio",
                        "verbose_name_plural": "uffici",
                        "ordering": ["code"],
                        "db_table": "booking_office",
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
