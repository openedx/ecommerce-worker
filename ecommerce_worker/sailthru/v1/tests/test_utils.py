""" Tests for utility functions. """

from __future__ import absolute_import
from unittest import TestCase

import ddt
import mock

from ecommerce_worker.sailthru.v1.exceptions import SailthruNotEnabled, ConfigurationError
from ecommerce_worker.sailthru.v1.utils import get_sailthru_client


@ddt.ddt
class SailthruUtilsTests(TestCase):
    """ Tests for Sailthru utility functions. """
    SITE_CODE = 'test'
    SITE_OVERRIDES_MODULE = 'ecommerce_worker.configuration.test.SITE_OVERRIDES'

    def assert_get_sailthru_client_raises(self, exc_class, config):
        """ Asserts an error is raised by a call to get_sailthru_client. """
        overrides = {
            self.SITE_CODE: {
                'SAILTHRU': config
            }
        }
        with mock.patch.dict(self.SITE_OVERRIDES_MODULE, overrides):
            with self.assertRaises(exc_class):
                get_sailthru_client(self.SITE_CODE)

    def test_get_sailthru_client_with_sailthru_disabled(self):
        """ Verify the method raises a SailthruNotEnabled if Sailthru is not enabled for the site. """

        with mock.patch('ecommerce_worker.sailthru.v1.utils.log.debug') as mock_log:
            self.assert_get_sailthru_client_raises(SailthruNotEnabled, {'SAILTHRU_ENABLE': False})

        mock_log.assert_called_once_with('Sailthru is not enabled for site {}'.format(self.SITE_CODE))

    @ddt.data(
        {},
        {'SAILTHRU_KEY': None, 'SAILTHRU_SECRET': None},
        {'SAILTHRU_KEY': 'test', 'SAILTHRU_SECRET': None},
        {'SAILTHRU_KEY': None, 'SAILTHRU_SECRET': 'test'},
    )
    def test_get_sailthru_client_without_credentials(self, sailthru_config):
        """ Verify the method raises a ConfigurationError if Sailthru is not configured properly. """
        sailthru_config['SAILTHRU_ENABLE'] = True

        with mock.patch('ecommerce_worker.sailthru.v1.utils.log.error') as mock_log:
            self.assert_get_sailthru_client_raises(ConfigurationError, sailthru_config)

        mock_log.assert_called_once_with('Both key and secret are required for site {}'.format(self.SITE_CODE))

    def test_get_sailthru_client(self):
        """ Verify the method returns an authenticated SailthruClient. """
        key = 'key'
        secret = 'secret'
        overrides = {
            self.SITE_CODE: {
                'SAILTHRU': {
                    'SAILTHRU_ENABLE': True,
                    'SAILTHRU_KEY': key,
                    'SAILTHRU_SECRET': secret
                }
            }
        }
        with mock.patch.dict(self.SITE_OVERRIDES_MODULE, overrides):
            client = get_sailthru_client(self.SITE_CODE)
            self.assertEqual(client.api_key, key)
            self.assertEqual(client.secret, secret)
