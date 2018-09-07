import os

from django.test import TestCase

from events.importer.kulke import KulkeImporter


class TestKulkeImporter(TestCase):

    def test_html_format(self):
        text = (
            'Lorem ipsum dolor sit amet, consectetur adipiscing elit.{0}'
            '{0}'
            'Nam quam urna.{0}'
            'Etiam maximus ex tellus, elementum fermentum tellus bibendum id.{0}'
            'Praesent sodales purus libero.{0}'
            '{0}'
            'Vestibulum lacinia interdum nisi eu vehicula.'
        ).format(os.linesep)

        html_text = KulkeImporter._html_format(text)
        expected_text = (
            '<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>'
            '<p>Nam quam urna.<br>'
            'Etiam maximus ex tellus, elementum fermentum tellus bibendum id.<br>'
            'Praesent sodales purus libero.</p>'
            '<p>Vestibulum lacinia interdum nisi eu vehicula.</p>'
        )
        self.assertEqual(html_text, expected_text)
