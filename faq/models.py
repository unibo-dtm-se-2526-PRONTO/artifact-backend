import uuid

from django.db import models

from offices.models import Office
from pronto.enums import Language


class Faq(models.Model):
    """A published question and answer pair, filed under one office."""

    office = models.ForeignKey(
        Office,
        on_delete=models.PROTECT,
        related_name="faqs",
        verbose_name="ufficio",
    )
    question_it = models.TextField(verbose_name="domanda (italiano)")
    question_en = models.TextField(verbose_name="domanda (inglese)")
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
        ordering = ["office__code", "question_it"]
        constraints = [
            # The natural key used by import_faqs.
            models.UniqueConstraint(
                fields=["office", "question_it"],
                name="unique_faq_per_office_and_question",
            )
        ]

    def __str__(self):
        return f"[{self.office.code}] {self.question_it}"


class MatchMethod(models.TextChoices):
    """How a suggested FAQ was found, which says what its score measures."""

    FULL_TEXT = "fulltext", "ricerca full-text"
    SEMANTIC = "semantic", "similarità semantica"


class Inquiry(models.Model):
    """A question a student asked, and the FAQ it was matched to.

    No link to the user, by design. The UUID key is given to the client to mark
    the question resolved, so it must not be guessable.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    office = models.ForeignKey(
        Office,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inquiries",
        verbose_name="ufficio",
        help_text=(
            "L'ufficio scelto dallo studente, anche se la risposta è di un altro. "
            "Se non ne ha scelto uno, quello della FAQ proposta; vuoto se non ne "
            "è stata trovata una."
        ),
    )
    text = models.TextField(verbose_name="domanda")
    language = models.CharField(
        max_length=2,
        choices=Language.choices,
        verbose_name="lingua",
    )
    matched_faq = models.ForeignKey(
        Faq,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inquiries",
        verbose_name="FAQ proposta",
    )
    score = models.FloatField(
        null=True,
        blank=True,
        verbose_name="punteggio",
        help_text="La pertinenza della FAQ proposta; vuoto se non ne è stata trovata una.",
    )
    # Admin only: says which scale the score is on.
    matched_by = models.CharField(
        max_length=16,
        choices=MatchMethod.choices,
        blank=True,
        verbose_name="trovata con",
        help_text="Il metodo che ha trovato la FAQ proposta, e quindi la scala del punteggio.",
    )
    resolved = models.BooleanField(
        default=False,
        verbose_name="risolta",
        help_text="Lo studente ha indicato che la FAQ proposta risponde alla domanda.",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="posta il")

    class Meta:
        verbose_name = "domanda"
        verbose_name_plural = "domande"
        ordering = ["-created_at"]

    def __str__(self):
        code = self.office.code if self.office else "-"
        return f"[{code}] {self.text[:60]}"
