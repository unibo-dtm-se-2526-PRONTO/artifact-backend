# FAQs and inquiries move from an office code to a foreign key to the office,
# in three steps, each its own transaction: PostgreSQL refuses to alter a
# table whose rows have just been updated in the same transaction while their
# foreign keys are still to be checked. Here the key is added, nullable; 0004
# fills it in and 0005 makes it required and drops the code.
#
# The code becomes nullable on its way out and its unique constraint goes
# first: going back, the code column is restored empty, 0004 fills it in, and
# only then are its constraints put back.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("faq", "0002_inquiry"),
        ("offices", "0002_rename_office_table"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="faq",
            name="unique_faq_per_office_and_question",
        ),
        migrations.AlterField(
            model_name="faq",
            name="office_code",
            field=models.CharField(
                choices=[
                    ("GUIDANCE", "Orientamento"),
                    ("ADMIN_OFFICE", "Segreteria studenti"),
                    ("INTERNATIONAL", "Relazioni internazionali"),
                    ("INTERNSHIPS", "Tirocini"),
                ],
                db_index=True,
                max_length=32,
                null=True,
                verbose_name="codice ufficio",
            ),
        ),
        migrations.AlterField(
            model_name="inquiry",
            name="office_code",
            field=models.CharField(
                choices=[
                    ("GUIDANCE", "Orientamento"),
                    ("ADMIN_OFFICE", "Segreteria studenti"),
                    ("INTERNATIONAL", "Relazioni internazionali"),
                    ("INTERNSHIPS", "Tirocini"),
                ],
                help_text="L'ufficio scelto dallo studente, anche se la risposta è di un altro.",
                max_length=32,
                null=True,
                verbose_name="codice ufficio",
            ),
        ),
        migrations.AddField(
            model_name="faq",
            name="office",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="faqs",
                to="offices.office",
                verbose_name="ufficio",
            ),
        ),
        migrations.AddField(
            model_name="inquiry",
            name="office",
            field=models.ForeignKey(
                help_text="L'ufficio scelto dallo studente, anche se la risposta è di un altro.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="inquiries",
                to="offices.office",
                verbose_name="ufficio",
            ),
        ),
    ]
