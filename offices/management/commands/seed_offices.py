"""Create the helpdesk's offices, one per ``OfficeCode``.

Nothing else creates them up front: an office is data, not schema, and a fresh
database has none, so no employee can choose one and nothing can be booked.
This is run once per database, after ``migrate``.

It only fills in what is missing. An office that already exists is left as it
is, since its names, address or slot length may have been changed in the admin
since, and running the command again must not undo that. What a new office
looks like is decided in `offices.seed`.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from offices.models import Office
from offices.seed import OFFICES, seed_office


class Command(BaseCommand):
    help = (
        "Create the helpdesk offices that do not exist yet. "
        "Offices already there are left as they are."
    )

    def handle(self, *args, **options):
        created = []
        with transaction.atomic():
            for code in OFFICES:
                _office, was_created = seed_office(Office, code)
                if was_created:
                    created.append(code)
        self.stdout.write(f"Created: {len(created)}")
        for code in created:
            self.stdout.write(f"  {code}")
        self.stdout.write(f"Already there: {len(OFFICES) - len(created)}")
