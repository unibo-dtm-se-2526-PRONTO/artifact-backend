"""Create the missing helpdesk offices. Run once per database after ``migrate``."""

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
