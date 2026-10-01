from django.db import models

from pronto.enums import OfficeCode


class Office(models.Model):
    """A helpdesk office: what students ask about and book appointments with.

    An app of its own because both `faq` and `booking` file their rows under an
    office, and neither should have to depend on the other for it. It depends
    on neither in turn: everything here is about the office itself.

    ``code`` is the stable identifier the API and the frontend use; the display
    names are stored per language so the API can answer in the language the
    student asked in.
    """

    code = models.CharField(
        max_length=32,
        unique=True,
        choices=OfficeCode.choices,
        verbose_name="codice ufficio",
    )
    name_it = models.CharField(max_length=128, verbose_name="nome (italiano)")
    name_en = models.CharField(max_length=128, verbose_name="nome (inglese)")
    contact_email = models.EmailField(verbose_name="email di contatto")
    slot_duration_minutes = models.PositiveIntegerField(
        default=30,
        verbose_name="durata dello slot (minuti)",
        help_text="Lunghezza di un appuntamento presso questo ufficio.",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="attivo",
        help_text="Gli uffici non attivi non accettano nuove prenotazioni.",
    )

    class Meta:
        verbose_name = "ufficio"
        verbose_name_plural = "uffici"
        ordering = ["code"]

    def __str__(self):
        return self.name_it
