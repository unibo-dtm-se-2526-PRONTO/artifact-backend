"""Rebuild the vector store of semantic FAQ matching from the database.

Saving or deleting a FAQ updates its entries on its own (`faq.signals`), but
not when the vector store was down at that moment, nor after a bulk change
that sends no signal, nor on a fresh, empty store. This catches up: it drops
every entry and indexes each published FAQ again, so it is safe to run at any
time, as often as needed.
"""

from django.core.management.base import BaseCommand, CommandError

from faq import vector_index


class Command(BaseCommand):
    help = "Index every published FAQ again in the vector store (Chroma)."

    def handle(self, *args, **options):
        try:
            if vector_index.get_collection() is None:
                raise CommandError(
                    "Semantic matching is off: set CHROMA_HOST to the Chroma server."
                )
            count = vector_index.rebuild()
        except ValueError as error:
            # What chromadb raises when the server cannot be reached.
            raise CommandError(f"Chroma is not reachable: {error}") from None
        self.stdout.write(f"Indexed: {count} FAQs")
