import os
from datetime import time

import pytest
from django.test import TestCase

from events.importer.kulke import KulkeImporter, parse_age_range, parse_course_time


@pytest.mark.django_db
@pytest.mark.parametrize("test_input,expected", [
    ('Pölyt pois taidehistoriasta! Rooman ylväät pylväät', (None, None)),
    ('(3 kk–4 v) klo 9.30–10.15 kevään mittainen lyhytkurssi', (None, None)),
    ('4-6 vuotiaille (yhdessä aikuisen kanssa) ma klo 10-11.30', (4, 6)),
    ('Työpaja ja esitys 9-12-vuotiaille', (9, 12)),
    ('(3–5 v) klo 13-15', (3, 5)),
    ('5–6 v klo 15.45–17.15', (5, 6)),
    ('13–18 v klo 14.00–15.30', (13, 18)),
    ('8–12 år kl 15.30–17.00', (8, 12)),
    ('11–18 år kl 17.15–19.30', (11, 18)),
])
def test_parse_age_range_returns_correct_result(test_input, expected):
    assert parse_age_range(test_input) == expected


@pytest.mark.django_db
@pytest.mark.parametrize("test_input,expected", [
    ('Pölyt pois taidehistoriasta! Rooman ylväät pylväät', (None, None)),
    ('Työpaja ja esitys 9-12-vuotiaille', (None, None)),
    ('(3–5 v) klo 13-15', (time(hour=13), time(hour=15))),
    ('7–9 v klo 10.30–12', (time(hour=10, minute=30), time(hour=12))),
    ('(3–5 v) klo 10.30–12.30', (time(hour=10, minute=30), time(hour=12, minute=30))),
    ('11-13 v klo 16-17.30 lukuvuoden mittainen kurssi', (time(hour=16), time(hour=17, minute=30))),
    ('8–12 v klo 15.30–17.00', (time(hour=15, minute=30), time(hour=17))),
    ('11–18 år kl 17.15–19.30', (time(hour=17, minute=15), time(hour=19, minute=30))),
    ('8–12 år kl 15.30–17.00', (time(hour=15, minute=30), time(hour=17))),
    ('4-6 vuotiaille (yhdessä aikuisen kanssa) ma klo 10-11.30', (time(hour=10), time(hour=11, minute=30))),
])
def test_parse_course_time_returns_correct_result(test_input, expected):
    assert parse_course_time(test_input) == expected


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
