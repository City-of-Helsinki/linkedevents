# Generated by Django 1.9.10 on 2016-11-16 13:46

from django.db import migrations, models
import mptt
import mptt.managers


def _add_mptt_manager(cls):
    manager = mptt.managers.TreeManager()
    manager.model = cls
    mptt.register(cls, parent_attr="super_event")
    manager.contribute_to_class(cls, "objects")


def populate_super_event_type(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    _add_mptt_manager(Event)

    Event.objects.filter(is_recurring_super=True).update(super_event_type="recurring")


def populate_is_recurring_super(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    _add_mptt_manager(Event)

    Event.objects.filter(super_event_type="recurring").update(is_recurring_super=True)


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0031_add_place_divisions"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="super_event_type",
            field=models.CharField(
                blank=True,
                choices=[("recurring", "Recurring")],
                default=None,
                max_length=255,
                null=True,
            ),
        ),
        migrations.RunPython(populate_super_event_type, populate_is_recurring_super),
        migrations.RemoveField(
            model_name="event",
            name="is_recurring_super",
        ),
    ]
