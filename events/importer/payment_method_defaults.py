# -*- coding: utf-8 -*-

# Dependencies.

# Logging:
import time
import logging
from os import mkdir
from os.path import abspath, join, dirname, exists, basename, splitext

# Django:
from django_orghierarchy.models import Organization
from django_orghierarchy.models import OrganizationClass
from events.models import BaseModel, PaymentMethod

# Importer specific:
from .base import Importer, register_importer

# Type checking:
from typing import Any

# Setup Logging:
if not exists(join(dirname(__file__), 'logs')):
    mkdir(join(dirname(__file__), 'logs'))

logger = logging.getLogger(__name__)  # Per module logger
curFileExt = basename(__file__)
curFile = splitext(curFileExt)[0]
logFile = \
    logging.FileHandler(
        '%s' % (join(dirname(__file__), 'logs', curFile+'.logs'))
    )
logFile.setFormatter(
    logging.Formatter(
        '[%(asctime)s] <%(name)s> (%(lineno)d): %(message)s'
    )
)
logFile.setLevel(logging.DEBUG)
logger.addHandler(
    logFile
)


@register_importer
class PMDImporter(Importer):
    # Required super 'base' class dependencies...
    name = "payment_method_defaults"  # Command calling name.
    supported_languages = ['fi', 'sv', 'en']  # Language requirement.
    data_source = None  # Base data_source requirement.
    organization = None  # Base organization requirement.

    def setup(self: 'events.importer.payment_method_defaults.PMDImporter') -> None:
        data = [
            'Käteinen',
            'Maksukortti',
            'Virikeseteli',
            'Tyky-ranneke',
            'Verkkomaksu',
            'Mobile Pay',
            'Museokortti',
            'Lasku',
        ]

        for idx, word in enumerate(data, start=1):
            try:
                pm = PaymentMethod()
                pm.id = str(idx)
                pm.name = word
                pm.save()
            except Exception as e:
                logger.error(e)
