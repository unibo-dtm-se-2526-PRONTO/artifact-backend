"""Create the missing bundled FAQs, published. Safe to run at every start.

A FAQ is there when its office has one with the same Italian question, the key
of ``import_faqs``; FAQs already there are left as they are.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from faq import vector_index
from faq.models import Faq
from faq.seed import load_faqs
from offices.models import Office
from offices.seed import seed_office


class Command(BaseCommand):
    help = (
        "Create the FAQs bundled with PRONTO that do not exist yet, published, "
        "and index them. FAQs already there are left as they are."
    )

    def handle(self, *args, **options):
        faqs = load_faqs()
        with transaction.atomic():
            offices = {
                code: seed_office(Office, code)[0]
                for code in {faq["office"] for faq in faqs}
            }
            existing = set(Faq.objects.values_list("office__code", "question_it"))
            new = [
                Faq(**{**faq, "office": offices[faq["office"]]}, is_active=True)
                for faq in faqs
                if (faq["office"], faq["question_it"]) not in existing
            ]
            # No signals: the index is rebuilt once below.
            Faq.objects.bulk_create(new)
        self.stdout.write(f"Created: {len(new)}")
        self.stdout.write(f"Already there: {len(faqs) - len(new)}")
        if new:
            self.index()

    def index(self):
        try:
            if vector_index.get_collection() is None:
                return
            count = vector_index.rebuild()
        # Chroma unreachable, or the embedding model not downloadable. Never
        # stop the start-up: the FAQs are saved and full-text search works.
        except (ValueError, OSError) as error:
            self.stdout.write(
                f"FAQ index not updated ({error}): run rebuild_faq_index."
            )
            return
        self.stdout.write(f"Indexed: {count} FAQs")
