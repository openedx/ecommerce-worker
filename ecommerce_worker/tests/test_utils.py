""" Test coverage for ecommerce_worker/utils.py """
from unittest import TestCase, mock

import ddt
from requests.exceptions import HTTPError, RequestException

from ecommerce_worker.configuration.test import ECOMMERCE_API_ROOT
from ecommerce_worker.utils import get_access_token, get_configuration


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


@ddt.ddt
class GetAccessTokenTests(TestCase):
    """
    Tests covering the get_access_token operation.
    """

    @ddt.data(KeyError, HTTPError)
    @mock.patch('ecommerce_worker.utils.requests.post')
    def test_get_access_token_with_exception(self, expected_exception, mock_request_post):
        """
        Confirm that get_access_token raise an error correctly
        """
        mock_response = mock.MagicMock()
        mock_response.raise_for_status.side_effect = expected_exception
        mock_request_post.return_value = mock_response

        with self.assertRaises(RequestException):
            get_access_token()
