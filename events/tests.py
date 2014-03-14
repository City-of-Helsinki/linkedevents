#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

from django.test import SimpleTestCase
from events.serializers.serializers import LinkedEventsSerializer


class LinkedEventsSerializerTestCase(SimpleTestCase):

    def test_from_camelcase_conversions(self):
        self.assertEquals(LinkedEventsSerializer.convert_from_camelcase('LoremIpsumIndaHouse'), 'lorem_ipsum_inda_house')
        self.assertEquals(LinkedEventsSerializer.convert_from_camelcase('startsWithSmall'), 'starts_with_small')

    def test_to_camelcase_conversions(self):
        self.assertEquals(LinkedEventsSerializer.convert_to_camelcase('lorem_ipsum_inda_house'), 'loremIpsumIndaHouse')

    def test_dict_structure_conversions(self):
        obj1 = {
            "idField": 1,
            "valueField": "blahblah",
            "boolFieldHere": True,
            "nestedArray": [1, {"valValOne": 1}, {"valValTwo": 2}, {"nestedNestedArray": ["lorem", "ipsum"]}]
        }

        obj2 = {
            "id_field": 1,
            "value_field": "blahblah",
            "bool_field_here": True,
            "nested_array": [1, {"val_val_one": 1}, {"val_val_two": 2}, {"nested_nested_array": ["lorem", "ipsum"]}]
        }

        self.assertTrue(LinkedEventsSerializer.rename_fields(obj1) == obj2)