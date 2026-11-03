from django.db import models

from pronto.enums import OfficeCode


class Office(models.Model):
    """A helpdesk office; ``code`` is the identifier the API uses."""

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
