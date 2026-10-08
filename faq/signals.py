"""Keeping the vector store in step with the FAQs (see `faq.vector_index`).

Every save and delete of a FAQ updates its entries after the transaction
commits, so a rolled-back change never reaches Chroma. The update is
best-effort, like the booking e-mails: a vector store that is down must not
stop anyone from editing a FAQ. The error is logged, and `rebuild_faq_index`
catches up afterwards. Bulk `QuerySet.update` sends no signal at all, which is
the other reason that command exists.
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
    # raw: a fixture being loaded by loaddata, stored as it is in the file;
    # rebuild_faq_index indexes it afterwards.
    if not raw:
        sync_after_commit(instance.pk)


@receiver(post_delete, sender=Faq)
def faq_deleted(sender, instance, **kwargs):
    sync_after_commit(instance.pk)
