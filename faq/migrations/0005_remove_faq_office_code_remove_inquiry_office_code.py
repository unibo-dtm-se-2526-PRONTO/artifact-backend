# Every row has its office now (0004): the key becomes required, the code
# goes, and the natural key of a FAQ is its office and Italian question again.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("faq", "0004_link_office"),
    ]

    operations = [
        migrations.AlterField(
            model_name="faq",
            name="office",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="faqs",
                to="offices.office",
                verbose_name="ufficio",
            ),
        ),
        migrations.AlterField(
            model_name="inquiry",
            name="office",
            field=models.ForeignKey(
                help_text="L'ufficio scelto dallo studente, anche se la risposta è di un altro.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="inquiries",
                to="offices.office",
                verbose_name="ufficio",
            ),
        ),
        migrations.RemoveField(
            model_name="faq",
            name="office_code",
        ),
        migrations.RemoveField(
            model_name="inquiry",
            name="office_code",
        ),
        migrations.AlterModelOptions(
            name="faq",
            options={
                "ordering": ["office__code", "question_it"],
                "verbose_name": "FAQ",
                "verbose_name_plural": "FAQ",
            },
        ),
        migrations.AddConstraint(
            model_name="faq",
            constraint=models.UniqueConstraint(
                fields=("office", "question_it"),
                name="unique_faq_per_office_and_question",
            ),
        ),
    ]
