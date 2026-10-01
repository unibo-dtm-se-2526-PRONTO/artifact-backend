"""Create the helpdesk's offices, one per ``OfficeCode``.

Nothing else creates them: an office is data, not schema, and a fresh database
has none, so no employee can choose one and nothing can be booked. This is run
once per database, after ``migrate``.

It only fills in what is missing. An office that already exists is left as it
is, since its names, address or slot length may have been changed in the admin
since, and running the command again must not undo that.

The Italian names are the labels of ``OfficeCode``; the English ones are those
of the helpdesk spreadsheet the FAQs come from. The contact addresses follow
the university's style but are made up: check them before going live, and
correct them in the admin.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from booking.models import Office
from pronto.enums import OfficeCode

SLOT_DURATION_MINUTES = 30

# English name and contact address of each office.
OFFICES = {
    OfficeCode.GUIDANCE: ("Guidance and Admissions", "orientamento@unibo.it"),
    OfficeCode.ADMIN_OFFICE: ("Student Administration Office", "segreteria@unibo.it"),
    OfficeCode.INTERNATIONAL: (
        "International Relations",
        "relazioni.internazionali@unibo.it",
    ),
    OfficeCode.INTERNSHIPS: ("Internships", "tirocini@unibo.it"),
}


class Command(BaseCommand):
    help = (
        "Create the helpdesk offices that do not exist yet. "
        "Offices already there are left as they are."
    )

    def handle(self, *args, **options):
        created = []
        with transaction.atomic():
            for code, (name_en, contact_email) in OFFICES.items():
                _office, was_created = Office.objects.get_or_create(
                    code=code,
                    defaults={
                        "name_it": code.label,
                        "name_en": name_en,
                        "contact_email": contact_email,
                        "slot_duration_minutes": SLOT_DURATION_MINUTES,
                    },
                )
                if was_created:
                    created.append(code)
        self.stdout.write(f"Created: {len(created)}")
        for code in created:
            self.stdout.write(f"  {code}")
        self.stdout.write(f"Already there: {len(OFFICES) - len(created)}")
