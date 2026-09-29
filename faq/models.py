import uuid

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
    office_code = models.CharField(
        max_length=32,
        choices=OfficeCode.choices,
        verbose_name="codice ufficio",
        help_text="L'ufficio scelto dallo studente, anche se la risposta è di un altro.",
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
        return f"[{self.office_code}] {self.text[:60]}"
