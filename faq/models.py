from django.db import models

from pronto.enums import OfficeCode


class Faq(models.Model):
    """A published question and answer pair, filed under one office.

    ``office_code`` is a plain choices field rather than a foreign key to
    ``booking.Office``: the FAQ slice only ever needs to filter by office, and
    a real relation would make the two vertical slices deploy and migrate
    together for no gain. The shared ``OfficeCode`` enum is the contract
    between them.
    """

    office_code = models.CharField(
        max_length=32,
        choices=OfficeCode.choices,
        db_index=True,
        verbose_name="codice ufficio",
    )
    question_it = models.CharField(max_length=255, verbose_name="domanda (italiano)")
    question_en = models.CharField(max_length=255, verbose_name="domanda (inglese)")
    answer_it = models.TextField(verbose_name="risposta (italiano)")
    answer_en = models.TextField(verbose_name="risposta (inglese)")
    is_active = models.BooleanField(
        default=True,
        verbose_name="attiva",
        help_text="Le FAQ non attive restano in archivio ma non vengono mostrate.",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="creata il")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="aggiornata il")

    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQ"
        ordering = ["office_code", "question_it"]
        constraints = [
            # The natural key: seeding the same FAQ twice updates the existing
            # row instead of duplicating it, so the seed script stays idempotent.
            models.UniqueConstraint(
                fields=["office_code", "question_it"],
                name="unique_faq_per_office_and_question",
            )
        ]

    def __str__(self):
        return f"[{self.office_code}] {self.question_it}"
