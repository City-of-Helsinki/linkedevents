from django.core.management.base import BaseCommand

from events.models import Language

LANGUAGES = [
    {
        "id": "ru",
        "name_fi": "venäjä",
        "name_sv": "ryska",
        "name_en": "Russian",
    },
    {
        "id": "et",
        "name_fi": "viro",
        "name_sv": "estniska",
        "name_en": "Estonian",
    },
    {
        "id": "fr",
        "name_fi": "ranska",
        "name_sv": "franska",
        "name_en": "French",
    },
    {
        "id": "so",
        "name_fi": "somali",
        "name_sv": "somaliska",
        "name_en": "Somali",
    },
    {
        "id": "es",
        "name_fi": "espanja",
        "name_sv": "spanska",
        "name_en": "Spanish",
    },
    {
        "id": "tr",
        "name_fi": "turkki",
        "name_sv": "turkiska",
        "name_en": "Turkish",
    },
    {
        "id": "fa",
        "name_fi": "persia",
        "name_sv": "persiska",
        "name_en": "Persian",
    },
    {
        "id": "ar",
        "name_fi": "arabia",
        "name_sv": "arabiska",
        "name_en": "Arabic",
    },
    {
        "id": "zh_hans",
        "name_fi": "kiina",
        "name_sv": "kinesiska",
        "name_en": "Chinese",
    },
    {
        "id": "en",
        "name_fi": "englanti",
        "name_sv": "engelska",
        "name_en": "English",
    },
    {
        "id": "fi",
        "name_fi": "suomi",
        "name_sv": "finska",
        "name_en": "Finnish",
    },
    {
        "id": "sv",
        "name_fi": "ruotsi",
        "name_sv": "svenska",
        "name_en": "Swedish",
    },
]


class Command(BaseCommand):
    help = "Create language objects with correct translations."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            dest="force",
            help="Forcefully update all languages with translations.",
        )

    def handle(self, *args, **options):
        if options["force"]:
            method = Language.objects.update_or_create
        else:
            method = Language.objects.get_or_create

        language_ids = [language_data["id"] for language_data in LANGUAGES]
        should_run = options["force"] or Language.objects.filter(
            id__in=language_ids
        ).count() < len(language_ids)

        if should_run:
            for language_data in LANGUAGES:
                language, created = method(
                    id=language_data["id"], defaults=language_data
                )
                if created:
                    self.stdout.write(f"Created language {language_data['id']}.")
                else:
                    self.stdout.write(f"Language {language_data['id']} already exist.")
        else:
            self.stdout.write("All language objects are in order.")
