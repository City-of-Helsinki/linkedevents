from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    def handle(self, *args, **options):
        if settings.DEBUG is not True:
            raise CommandError('This command can be run only in DEBUG mode')

        admin_user_exists = get_user_model().objects.filter(username='admin').exists()
        if admin_user_exists:
            self.stdout.write('Superuser "admin" already exists')
            return

        get_user_model().objects.create_superuser('admin', 'admin@admin.com', 'admin')
        self.stdout.write('Superuser "admin" with admin:admin credentials created')
