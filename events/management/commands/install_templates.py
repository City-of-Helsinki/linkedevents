import os
import shutil

from django.core.management.base import BaseCommand

from django.conf import settings


class Command(BaseCommand):
    help = "Install a city specific HTML template"

    def add_arguments(self, parser):
        parser.add_argument('city_directory', nargs=1, type=str)

    def handle(self, *args, **options):
        city_template_dir = os.path.join(settings.BASE_DIR, options['city_directory'][0], 'templates/rest_framework/')
        project_template_dir = os.path.join(settings.BASE_DIR, 'templates/rest_framework/')
        print(city_template_dir)
        for file in os.listdir(city_template_dir):
            print(file)
            shutil.copyfile(os.path.join(city_template_dir, file),
                            os.path.join(project_template_dir, file))
        self.stdout.write(self.style.SUCCESS('Successfully installed the template from ' + options['city_directory'][0]))
