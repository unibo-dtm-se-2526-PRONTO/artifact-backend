# The second half of moving the office to the `offices` app (see offices
# 0001): the foreign keys of profiles and appointments now point at
# `offices.Office`, and booking forgets its own. State only: the columns and
# their constraints already reference the right table, whatever it is called.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0003_appointment_suggested_faq"),
        ("offices", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="employeeprofile",
                    name="office",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employees",
                        to="offices.office",
                        verbose_name="ufficio",
                    ),
                ),
                migrations.AlterField(
                    model_name="appointment",
                    name="office",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="appointments",
                        to="offices.office",
                        verbose_name="ufficio",
                    ),
                ),
                migrations.DeleteModel(name="Office"),
            ],
            database_operations=[],
        ),
    ]
