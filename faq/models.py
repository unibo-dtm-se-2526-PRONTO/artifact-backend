import uuid

from django.db import models

from offices.models import Office


class Faq(models.Model):
    """A published question and answer pair, filed under one office."""

    # PROTECT: an office with FAQs filed under it must be emptied deliberately,
    # never by deleting the office. An office that stops working is made
    # inactive instead, which keeps its FAQs searchable.
    office = models.ForeignKey(
        Office,
        on_delete=models.PROTECT,
        related_name="faqs",
        verbose_name="ufficio",
    )
    # Text rather than a 255-character column: the helpdesk's questions are
    # sometimes a paragraph of context, and they are stored as asked. The
    # unique constraint below indexes the Italian one, which PostgreSQL allows
    # up to about 2,700 bytes — far beyond any question in the knowledge base.
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
            # The natural key: seeding the same FAQ twice updates the existing
            # row instead of duplicating it, so the seed script stays idempotent.
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
    """A question a student asked about an office, and the FAQ it was matched to.

    Two links are missing on purpose. There is no user: the questions are kept
    to learn what the knowledge base lacks, and that needs the text, not who
    wrote it. There is no appointment either: if the answer does not help, the
    student books through the booking API, which records the suggested FAQ on
    the appointment itself, so the dependency keeps running from `booking` to
    `faq` and never back.

    The primary key is a UUID because it is handed to the client, which quotes
    it back to mark the question resolved: a sequential id would let anyone
    resolve, or count, the questions of everybody else.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # PROTECT, as for a FAQ: the questions are the record of what students
    # needed from an office, and deleting the office must not erase it.
    # Nullable because a student need not choose an office: the question is
    # then filed under the office of the suggested FAQ, or under none.
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
        choices=[("it", "Italiano"), ("en", "Inglese")],
        verbose_name="lingua",
    )
    # SET_NULL: retiring a FAQ must not erase the record of what was asked.
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
    # Not in the API: the student needs the answer, not how it was found. It
    # is here to read the score, whose scale depends on the method.
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
