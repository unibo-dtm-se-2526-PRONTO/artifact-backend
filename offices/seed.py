"""The default data of each office, used by seeding, FAQ import and migrations.

The contact addresses are placeholders: correct them in the admin.
"""

from pronto.enums import OfficeCode

SLOT_DURATION_MINUTES = 30

# English name and contact address of each office.
OFFICES = {
    OfficeCode.GUIDANCE: ("Guidance and Admissions", "orientamento@unibo.it"),
    OfficeCode.ADMIN_OFFICE: ("Student Administration Office", "segreteria@unibo.it"),
    OfficeCode.INTERNATIONAL: (
        "International Relations",
        "relazioni.internazionali@unibo.it",
    ),
    OfficeCode.INTERNSHIPS: ("Internships", "tirocini@unibo.it"),
}


def seed_office(model, code):
    """``(office, created)``; an existing office is left as it is."""
    code = OfficeCode(code)
    name_en, contact_email = OFFICES[code]
    return model.objects.get_or_create(
        code=code,
        defaults={
            "name_it": code.label,
            "name_en": name_en,
            "contact_email": contact_email,
            "slot_duration_minutes": SLOT_DURATION_MINUTES,
        },
    )
