# Generated by Django 1.11.11 on 2018-06-01 09:56

from django.db import migrations


def _fix_chinese_language_object(apps, schema_editor, old_lang_code, new_lang_code):
    Language = apps.get_model("events", "Language")
    KeywordLabel = apps.get_model("events", "KeywordLabel")
    Event = apps.get_model("events", "Event")
    EventLink = apps.get_model("events", "EventLink")

    try:
        # Create a new language object with identical fields as the old one
        chinese_lang = Language.objects.get(id=old_lang_code)
        chinese_lang.id = new_lang_code
        chinese_lang.save()

        # Update ForeignKey links
        KeywordLabel.objects.filter(language=old_lang_code).update(
            language=chinese_lang.id
        )
        EventLink.objects.filter(language=old_lang_code).update(
            language=chinese_lang.id
        )
        # Update ManyToMany link
        relevant_events = Event.objects.filter(in_language=old_lang_code)
        for event in relevant_events:
            event.in_language.remove(old_lang_code)
            event.in_language.add(chinese_lang)

        # Delete the old language object
        Language.objects.get(id=old_lang_code).delete()
    except Language.DoesNotExist:
        pass


def delete_zh_lang_code(apps, schema_editor):
    _fix_chinese_language_object(apps, schema_editor, "zh", "zh_hans")


def delete_zh_hans_lang_code(apps, schema_editor):
    _fix_chinese_language_object(apps, schema_editor, "zh_hans", "zh")


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0055_fix_chinese_language_code"),
    ]

    operations = [
        migrations.RunPython(delete_zh_lang_code, delete_zh_hans_lang_code),
    ]
