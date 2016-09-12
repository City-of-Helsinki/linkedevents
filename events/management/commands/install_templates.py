import shutil
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Install a city specific HTML template"

    def add_arguments(self, parser):
        parser.add_argument('city_directory', nargs=1, type=str)

    def handle(self, *args, **options):
        shutil.copyfile(options['city_directory'][0]+'/templates/rest_framework/api.html',
                        'templates/rest_framework/api.html')
        self.stdout.write(self.style.SUCCESS('Successfully installed the template from '+options['city_directory'][0]))
