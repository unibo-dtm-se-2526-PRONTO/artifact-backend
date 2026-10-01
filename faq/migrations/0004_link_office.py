# Each FAQ and inquiry is linked to the office with its code. An office that
# does not exist yet — a database where FAQs were imported but `seed_offices`
# never ran — is created as `seed_offices` would create it.
#
# Going back writes each row's office code again. Offices created here stay:
# by then they may have staff and appointments.

from django.db import migrations

from offices.seed import seed_office
from pronto.enums import OfficeCode

MODELS = ("Faq", "Inquiry")


def link_office(apps, schema_editor):
    Office = apps.get_model("offices", "Office")
    for name in MODELS:
        model = apps.get_model("faq", name)
        codes = model.objects.values_list("office_code", flat=True).distinct()
        for code in codes:
            if code not in OfficeCode.values:
                # Only full_clean() checked the code, so a bad one may have
                # been stored. Better stop here than invent an office for it.
                raise RuntimeError(
                    f"faq.{name} rows have the unknown office code {code!r}: "
                    "correct them, then migrate again."
                )
            office, _created = seed_office(Office, code)
            model.objects.filter(office_code=code).update(office=office)


def unlink_office(apps, schema_editor):
    Office = apps.get_model("offices", "Office")
    for name in MODELS:
        model = apps.get_model("faq", name)
        for office in Office.objects.all():
            model.objects.filter(office=office).update(office_code=office.code)


class Migration(migrations.Migration):
    dependencies = [
        ("faq", "0003_faq_office_inquiry_office"),
    ]

    operations = [
        migrations.RunPython(link_office, unlink_office),
    ]
