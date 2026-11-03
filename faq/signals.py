"""Update the vector store after a FAQ is saved or deleted.

Errors are logged; `rebuild_faq_index` catches up, also after bulk updates.
"""

import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from . import vector_index
from .models import Faq

logger = logging.getLogger(__name__)


def sync_after_commit(faq_id):
    def sync():
        try:
            vector_index.sync_faq(faq_id)
        except Exception:
            logger.exception("Could not update FAQ %s in the vector store.", faq_id)

    transaction.on_commit(sync)


@receiver(post_save, sender=Faq)
def faq_saved(sender, instance, raw=False, **kwargs):
    # Skipped for fixtures (loaddata).
    if not raw:
        sync_after_commit(instance.pk)


@receiver(post_delete, sender=Faq)
def faq_deleted(sender, instance, **kwargs):
    sync_after_commit(instance.pk)
