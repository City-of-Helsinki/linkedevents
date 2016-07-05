import shutil
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Install a city specific HTML template"

    def add_arguments(self, parser):
        parser.add_argument('city_name', nargs=1, type=str)

    def handle(self, *args, **options):
        shutil.copyfile('templates/rest_framework/api.html.'+options['city_name'][0],
                        'events/templates/rest_framework/api.html')
        self.stdout.write(self.style.SUCCESS('Successfully installed the template for '+options['city_name'][0]))
