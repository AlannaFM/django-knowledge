from django.test import TestCase

from knowledge.utils import paginate, get_module


class UtilsTestCase(TestCase):
    def test_paginate_invalid_page_number(self):
        paginator, page = paginate(range(0, 1000), 100, 'xcvb')
        self.assertEqual(page.number, 1)  # retorna para a primeira página

    def test_paginate_overflow_page_number(self):
        paginator, page = paginate(range(0, 1000), 100, 154543)
        self.assertEqual(page.number, 10)  # retorna para a última página

    def test_paginate_valid_page(self):
        paginator, page = paginate(range(0, 1000), 100, 1)
        self.assertEqual(len(page.object_list), 100)
        self.assertEqual(paginator.count, 1000)
        self.assertEqual(paginator.num_pages, 10)

    def test_get_module_success(self):
        from django.template.defaultfilters import slugify
        loaded_slugify = get_module('django.template.defaultfilters.slugify')
        self.assertIs(loaded_slugify, slugify)

    def test_get_module_nonexistent_module(self):
        with self.assertRaises(ImportError):
            get_module('django.notreal.america')

    def test_get_module_nonexistent_attribute(self):
        with self.assertRaises(ImportError):
            get_module('django.template.defaultfilters.slugbug')
