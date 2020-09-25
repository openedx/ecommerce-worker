""" Test coverage for ecommerce_worker/utils.py """
from __future__ import absolute_import
from unittest import TestCase

import ddt
import mock

from ecommerce_worker.configuration.test import ECOMMERCE_API_ROOT
from ecommerce_worker.utils import get_configuration


@ddt.ddt
class GetConfigurationTests(TestCase):
    """Tests covering the get_configuration operation."""

    SITE_OVERRIDES_MODULE = 'ecommerce_worker.configuration.test.SITE_OVERRIDES'
    TEST_SETTING = 'ECOMMERCE_API_ROOT'

    OVERRIDES_DICT = {
        'openedx': {'ECOMMERCE_API_ROOT': 'http://openedx.org'},
        'test': {'ECOMMERCE_API_ROOT': 'http://example.com'},
        'novalue': {'ECOMMERCE_API_ROOT': None},
        'emptydict': {}
    }

    def test_configuration_no_site_overrides(self):
        test_setting = get_configuration(self.TEST_SETTING)
        self.assertEqual(test_setting, ECOMMERCE_API_ROOT)

    def test_configuration_no_site_code_specified(self):
        with mock.patch.dict(self.SITE_OVERRIDES_MODULE, self.OVERRIDES_DICT):
            test_setting = get_configuration(self.TEST_SETTING)
            self.assertEqual(test_setting, ECOMMERCE_API_ROOT)

    @ddt.data('openedx', 'test')
    def test_configuration_valid_site_code_dict_value(self, site_code):
        """
        Confirm that valid SITE_OVERRIDES parameters are correctly returned
        """
        with mock.patch.dict(self.SITE_OVERRIDES_MODULE, self.OVERRIDES_DICT):
            test_setting = get_configuration(self.TEST_SETTING, site_code=site_code)
            self.assertEqual(test_setting, self.OVERRIDES_DICT[site_code][self.TEST_SETTING])

    @ddt.data(None, 'invalid', 'emptydict', 'novalue')
    def test_configuration_no_site_code_matched(self, site_code):
        """
        Test various states of SITE_OVERRIDES to ensure all branches (ie, use cases) are covered
        """
        with mock.patch.dict(self.SITE_OVERRIDES_MODULE, self.OVERRIDES_DICT):
            test_setting = get_configuration(self.TEST_SETTING, site_code=site_code)
            self.assertEqual(test_setting, ECOMMERCE_API_ROOT)
