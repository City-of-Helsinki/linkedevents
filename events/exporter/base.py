import logging
import os


class Exporter(object):
    def __init__(self, options=None):
        self.options = options
        self.logger = logging.getLogger(__name__)
        self.setup()

    def setup(self):
        pass


exporters = {}


def register_exporter(klass):
    exporters[klass.name] = klass
    return klass


def get_exporters():
    if exporters:
        return exporters
    for fname in os.listdir(os.path.dirname(__file__)):
        module, ext = os.path.splitext(fname)
        if ext.lower() != '.py':
            continue
        if module in ('__init__', 'base'):
            continue
        full_path = "%s.%s" % (__package__, module)
        ret = __import__(full_path, locals(), globals())
    return exporters
