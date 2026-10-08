"""What a newly created office looks like, one per ``OfficeCode``.

The one place that knows it: the ``seed_offices`` command, the FAQ import and
the migration that linked the FAQs to their office all create offices through
`seed_office`, so an office made by any of them is the same office.

Plain data and no model import, so a migration can use it with its historical
model: `seed_office` takes the model to create with.

The Italian names are the labels of ``OfficeCode``; the English ones are those
of the helpdesk spreadsheet the FAQs come from. The contact addresses follow
the university's style but are made up: check them before going live, and
correct them in the admin.
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
    """The office with `code`, created active if missing: ``(office, created)``.

    An office that already exists is returned as it is, since its names,
    address or slot length may have been changed in the admin since.
    """
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
