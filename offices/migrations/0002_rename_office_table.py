# The table taken over from booking gets this app's name, so the schema says
# where the office lives. Renaming keeps every row and every foreign key
# pointing at it; the names of its index and constraints still start with
# `booking_office`, which is cosmetic.
#
# The office's content type moves with it, so the permissions on offices that
# groups and users were given keep applying. Done only while the new one does
# not exist yet, which is always the case when this runs within `migrate`:
# content types are created after the migrations.

from django.db import migrations


def move_content_type(old_app, new_app):
    def move(apps, schema_editor):
        ContentType = apps.get_model("contenttypes", "ContentType")
        db = schema_editor.connection.alias
        if (
            ContentType.objects.using(db)
            .filter(app_label=new_app, model="office")
            .exists()
        ):
            return
        ContentType.objects.using(db).filter(app_label=old_app, model="office").update(
            app_label=new_app
        )

    return move


class Migration(migrations.Migration):
    dependencies = [
        ("offices", "0001_initial"),
        ("booking", "0004_move_office_to_offices"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.AlterModelTable(name="office", table=None),
        migrations.RunPython(
            move_content_type("booking", "offices"),
            move_content_type("offices", "booking"),
        ),
    ]
