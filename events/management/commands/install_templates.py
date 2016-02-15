# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import os
import shutil


def install_templates(self, startpath, reinstall):
    """
    Copy all files templates with .example suffix to name without it
    :param self: a Command object
    :param startpath: path to start searching for templates
    :param bool reinstall: overwrite existing files
    :return: None
    """
    for root, dirs, files in os.walk(startpath):
        for f in files:
            fpath = os.path.join(startpath, root, f)
            if os.path.isfile(fpath) and fpath.endswith('.example'):
                newname = f.replace('.example', '')
                newfpath = os.path.join(startpath, root, newname)
                if os.path.isfile(newfpath) and reinstall is False:
                    self.stdout.write(self.style.WARNING(
                        'Not overwriting {} --> {}. Use --reinstall to '
                        'overwrite'.format(f, newname)))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        'Copying {} --> {}'.format(f, newname)))
                    shutil.copy(fpath, newfpath)


class Command(BaseCommand):

    help = 'Install customizable rest_framework templates'

    def add_arguments(self, parser):
        parser.add_argument(
            '-r', '--reinstall',
            action='store_true',
            dest='reinstall',
            default=False,
            help=u'Reinstall all templates (overwrite existing ones)')

    def handle(self, *args, **options):
        reinstall = options.get('reinstall')
        template_dir = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', '..',
            'templates', 'rest_framework'))
        install_templates(self, template_dir, reinstall)

