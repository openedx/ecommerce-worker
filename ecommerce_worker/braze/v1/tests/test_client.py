"""
Tests for Braze client.
"""

from __future__ import absolute_import
from unittest import TestCase
import ddt

import mock
import responses

from ecommerce_worker.braze.v1.client import get_braze_client
from ecommerce_worker.braze.v1.exceptions import (
    BrazeClientError,
    BrazeNotEnabled,
    BrazeRateLimitError,
    BrazeInternalServerError,
    ConfigurationError
)


@ddt.ddt
class BrazeClientTests(TestCase):
    """
    Tests for Braze Client.
    """
    SITE_CODE = 'test'
    SITE_OVERRIDES_MODULE = 'ecommerce_worker.configuration.test.SITE_OVERRIDES'

    def assert_get_braze_client_raises(self, exc_class, config):
        """
        Asserts an error is raised by a call to get_braze_client.
        """
        overrides = {
            self.SITE_CODE: {
                'BRAZE': config
            }
        }
        with mock.patch.dict(self.SITE_OVERRIDES_MODULE, overrides):
            with self.assertRaises(exc_class):
                get_braze_client(self.SITE_CODE)

    def test_get_braze_client_with_braze_disabled(self):
        """
        Verify the method raises a BrazeNotEnabled if Braze is not enabled for the site.
        """

        with mock.patch('ecommerce_worker.braze.v1.client.log.debug') as mock_log:
            self.assert_get_braze_client_raises(BrazeNotEnabled, {'BRAZE_ENABLE': False})

        mock_log.assert_called_once_with('Braze is not enabled for site {}'.format(self.SITE_CODE))

    @ddt.data(
        {},
        {'BRAZE_REST_API_KEY': None, 'BRAZE_WEBAPP_API_KEY': None,
         'REST_API_URL': None, 'MESSAGES_SEND_ENDPOINT': None, 'FROM_EMAIL': None},
        {'BRAZE_REST_API_KEY': 'test', 'BRAZE_WEBAPP_API_KEY': None,
         'REST_API_URL': 'test', 'MESSAGES_SEND_ENDPOINT': 'test', 'FROM_EMAIL': 'test'},
        {'BRAZE_REST_API_KEY': None, 'BRAZE_WEBAPP_API_KEY': 'test',
         'REST_API_URL': 'test', 'MESSAGES_SEND_ENDPOINT': 'test', 'FROM_EMAIL': 'test'},
        {'BRAZE_REST_API_KEY': 'test', 'BRAZE_WEBAPP_API_KEY': 'test',
         'REST_API_URL': None, 'MESSAGES_SEND_ENDPOINT': 'test', 'FROM_EMAIL': 'test'},
        {'BRAZE_REST_API_KEY': 'test', 'BRAZE_WEBAPP_API_KEY': 'test',
         'REST_API_URL': 'test', 'MESSAGES_SEND_ENDPOINT': None, 'FROM_EMAIL': 'test'},
        {'BRAZE_REST_API_KEY': 'test', 'BRAZE_WEBAPP_API_KEY': 'test',
         'REST_API_URL': 'test', 'MESSAGES_SEND_ENDPOINT': 'test', 'FROM_EMAIL': None},
    )
    def test_get_braze_client_without_credentials(self, braze_config):
        """
        Verify the method raises a ConfigurationError if Braze is not configured properly.
        """
        braze_config['BRAZE_ENABLE'] = True

        with mock.patch('ecommerce_worker.braze.v1.client.log.error') as mock_log:
            self.assert_get_braze_client_raises(ConfigurationError, braze_config)

        mock_log.assert_called_once_with('Required parameters missing for site {}'.format(self.SITE_CODE))

    @responses.activate
    def test_send_braze_message_success(self):
        """
        Verify that an email message is sent via BrazeClient.
        """
        success_response = {
            'dispatch_id': '66cdc28f8f082bc3074c0c79f',
            'errors': [],
            'message': 'success',
            'status_code': 201
        }
        host = 'https://rest.iad-06.braze.com/messages/send'

        responses.add(
            responses.POST,
            host,
            json=success_response,
            status=201)

        client = get_braze_client(self.SITE_CODE)
        response = client.send_message(
            ['test1@example.com', 'test2@example.com'],
            'Test Subject',
            '<html>Test Html Message</html>'
        )
        self.assertEqual(response['message'], 'success')

    @responses.activate
    @ddt.data(
        (400, BrazeClientError),
        (429, BrazeRateLimitError),
        (500, BrazeInternalServerError),
    )
    @ddt.unpack
    def test_send_braze_message_failure(self, status_code, error):
        """
        Verify that a failed email message throws the relevant error.
        """
        failure_response = {
            'message': 'Not a Success',
            'status_code': status_code
        }
        host = 'https://rest.iad-06.braze.com/messages/send'

        responses.add(
            responses.POST,
            host,
            json=failure_response,
            status=status_code
        )

        client = get_braze_client(self.SITE_CODE)
        with self.assertRaises(error):
            response = client.send_message(
                ['test1@example.com', 'test2@example.com'],
                'Test Subject',
                '<html>Test Html Message</html>'
            )

    @ddt.data(
        (['test1@example.com', 'test2@example.com'], None, '<html>Test Html Message</html>'),
        (None, 'Test Subject', '<html>Test Html Message</html>'),
        (['test1@example.com', 'test2@example.com'], 'Test Subject', None),
    )
    @ddt.unpack
    def test_send_braze_message_failure_missing_parameters(self, email, subject, body):
        """
        Verify that an error is raised for missing email parameters.
        """
        client = get_braze_client(self.SITE_CODE)
        with self.assertRaises(BrazeClientError):
            response = client.send_message(email, subject, body)
