"""Rebuild the semantic FAQ index from the database. Safe to run any time."""

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
