"""
Tests for Braze client.
"""

from unittest import TestCase
from urllib.parse import urlencode

import ddt
import mock
import responses
from mock import patch, Mock

from ecommerce_worker.email.v1.braze.client import get_braze_client
from ecommerce_worker.email.v1.braze.exceptions import (
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
    BRAZE_OVERRIDES = {
        SITE_CODE: {
            'BRAZE': {
                'BRAZE_ENABLE': True,
                'BRAZE_REST_API_KEY': 'rest_api_key',
                'BRAZE_WEBAPP_API_KEY': 'webapp_api_key',
                'REST_API_URL': 'https://rest.iad-06.braze.com',
                'MESSAGES_SEND_ENDPOINT': '/messages/send',
                'EMAIL_BOUNCE_ENDPOINT': '/email/hard_bounces',
                'NEW_ALIAS_ENDPOINT': '/users/alias/new',
                'USERS_TRACK_ENDPOINT': '/users/track',
                'EXPORT_ID_ENDPOINT': '/users/export/ids',
                'CAMPAIGN_SEND_ENDPOINT': '/campaigns/trigger/send',
                'ENTERPRISE_CAMPAIGN_ID': '',
                'FROM_EMAIL': '<edx-for-business-no-reply@info.edx.org>',
            }
        }
    }

    def mock_braze_user_endpoints(self, users=[]):
        """ Mock POST requests to the user alias, track and export endpoints. """
        host = 'https://rest.iad-06.braze.com/users/track'
        responses.add(
            responses.POST,
            host,
            json={'message': 'success'},
            status=201
        )
        host = 'https://rest.iad-06.braze.com/users/alias/new'
        responses.add(
            responses.POST,
            host,
            json={'message': 'success'},
            status=201
        )
        host = 'https://rest.iad-06.braze.com/users/export/ids'
        responses.add(
            responses.POST,
            host,
            json={"users": users, "message": "success"},
            status=201
        )

    def assert_get_braze_client_raises(self, exc_class, config):
        """
        Asserts an error is raised by a call to get_braze_client.
        """
        with patch('ecommerce_worker.email.v1.braze.client.get_braze_configuration', Mock(return_value=config)):
            with self.assertRaises(exc_class):
                get_braze_client(self.SITE_CODE)

    def test_get_braze_client_with_braze_disabled(self):
        """
        Verify the method raises a BrazeNotEnabled if Braze is not enabled for the site.
        """

        with mock.patch('ecommerce_worker.email.v1.braze.client.log.debug') as mock_log:
            self.assert_get_braze_client_raises(BrazeNotEnabled, {'BRAZE_ENABLE': False})

        mock_log.assert_called_once_with('Braze is not enabled for site {}'.format(self.SITE_CODE))

    @ddt.data(
        {},
        {'BRAZE_REST_API_KEY': None, 'BRAZE_WEBAPP_API_KEY': None},
        {'BRAZE_REST_API_KEY': 'test', 'BRAZE_WEBAPP_API_KEY': None},
    )
    def test_get_braze_client_without_credentials(self, braze_config):
        """
        Verify the method raises a ConfigurationError if Braze is not configured properly.
        """
        braze_config['BRAZE_ENABLE'] = True

        with mock.patch('ecommerce_worker.email.v1.braze.client.log.error') as mock_log:
            self.assert_get_braze_client_raises(ConfigurationError, braze_config)

        mock_log.assert_called_once_with('Required keys missing for site {}'.format(self.SITE_CODE))

    def test_create_braze_alias(self):
        """
        Asserts an error is raised by a call to create_braze_alias.
        """
        braze = self.BRAZE_OVERRIDES[self.SITE_CODE]['BRAZE']
        with patch('ecommerce_worker.email.v1.braze.client.get_braze_configuration', Mock(return_value=braze)):
            client = get_braze_client(self.SITE_CODE)
            with self.assertRaises(BrazeClientError):
                client.create_braze_alias(recipient_emails=[])

    @responses.activate
    def test_send_braze_message_success(self):
        """
        Verify that an email message is sent via /messages/send.
        """
        self.mock_braze_user_endpoints()
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
            status=201
        )
        braze = self.BRAZE_OVERRIDES[self.SITE_CODE]['BRAZE']
        with patch('ecommerce_worker.email.v1.braze.client.get_braze_configuration', Mock(return_value=braze)):
            client = get_braze_client(self.SITE_CODE)
            response = client.send_message(
                email_ids=['test1@example.com', 'test2@example.com'],
                subject='Test Subject',
                body='<html>Test Html Message</html>',
                attachments=[{'file_name': 'filename1', 'url': 'url1'}]
            )
            self.assertEqual(response['success'], True)

    @responses.activate
    def test_send_braze_message_success_with_external_ids(self):
        """
        Verify that an email message is sent via /messages/send in presence of existing edX users.
        """
        self.mock_braze_user_endpoints(users=[{"external_id": "99999"}])
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
            status=201
        )
        braze = self.BRAZE_OVERRIDES[self.SITE_CODE]['BRAZE']
        with patch('ecommerce_worker.email.v1.braze.client.get_braze_configuration', Mock(return_value=braze)):
            client = get_braze_client(self.SITE_CODE)
            response = client.send_message(
                ['test1@example.com', 'test2@example.com'],
                'Test Subject',
                '<html>Test Html Message</html>'
            )
            self.assertEqual(response['success'], True)

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
        self.mock_braze_user_endpoints()
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
        braze = self.BRAZE_OVERRIDES[self.SITE_CODE]['BRAZE']
        with patch('ecommerce_worker.email.v1.braze.client.get_braze_configuration', Mock(return_value=braze)):
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
        braze = self.BRAZE_OVERRIDES[self.SITE_CODE]['BRAZE']
        with patch('ecommerce_worker.email.v1.braze.client.get_braze_configuration', Mock(return_value=braze)):
            client = get_braze_client(self.SITE_CODE)
            with self.assertRaises(BrazeClientError):
                response = client.send_message(email, subject, body)

    @responses.activate
    def test_send_braze_campaign_message_success(self):
        """
        Verify that an email message is sent via /campaigns/trigger/send.
        """
        self.mock_braze_user_endpoints()
        success_response = {
            'dispatch_id': '66cdc28f8f082bc3074c0c79f',
            'errors': [],
            'message': 'success',
            'status_code': 201
        }
        host = 'https://rest.iad-06.braze.com/campaigns/trigger/send'
        responses.add(
            responses.POST,
            host,
            json=success_response,
            status=201
        )
        braze = self.BRAZE_OVERRIDES[self.SITE_CODE]['BRAZE']
        with patch('ecommerce_worker.email.v1.braze.client.get_braze_configuration', Mock(return_value=braze)):
            client = get_braze_client(self.SITE_CODE)
            response = client.send_campaign_message(
                ['test1@example.com', 'test2@example.com'],
                'Test Subject',
                '<html>Test Html Message</html>'
            )
            self.assertEqual(len(response.keys()), 2)

    @responses.activate
    @ddt.data(
        (400, BrazeClientError),
        (429, BrazeRateLimitError),
        (500, BrazeInternalServerError),
    )
    @ddt.unpack
    def test_send_braze_campaign_message_failure(self, status_code, error):
        """
        Verify that a failed email message throws the relevant error.
        """
        self.mock_braze_user_endpoints()
        failure_response = {
            'message': 'Not a Success',
            'status_code': status_code
        }
        host = 'https://rest.iad-06.braze.com/campaigns/trigger/send'

        responses.add(
            responses.POST,
            host,
            json=failure_response,
            status=status_code
        )
        braze = self.BRAZE_OVERRIDES[self.SITE_CODE]['BRAZE']
        with patch('ecommerce_worker.email.v1.braze.client.get_braze_configuration', Mock(return_value=braze)):
            client = get_braze_client(self.SITE_CODE)
            with self.assertRaises(error):
                response = client.send_campaign_message(
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
    def test_send_braze_campaign_message_failure_missing_parameters(self, email, subject, body):
        """
        Verify that an error is raised for missing email parameters.
        """
        braze = self.BRAZE_OVERRIDES[self.SITE_CODE]['BRAZE']
        with patch('ecommerce_worker.email.v1.braze.client.get_braze_configuration', Mock(return_value=braze)):
            client = get_braze_client(self.SITE_CODE)
            with self.assertRaises(BrazeClientError):
                response = client.send_campaign_message(email, subject, body)

    @ddt.data(
        (
            {
                'emails': [
                   {
                       'email': 'foo@braze.com',
                       'hard_bounced_at': '2016-08-25 15:24:32 +0000'
                   }
                ],
                'message': 'success',
            },
            True
        ),
        (
            {
                'emails': [],
                'message': 'success',
            },
            False
        ),
    )
    @ddt.unpack
    @responses.activate
    def test_bounced_email(self, response, did_bounce):
        """
        Verify that an email id bounced on Braze.
        """
        bounced_email = 'foo@braze.com'
        host = 'https://rest.iad-06.braze.com/email/hard_bounces?{email}'.format(
            email=urlencode({'email': bounced_email})
        )

        responses.add(
            responses.GET,
            host,
            json=response,
            status=200
        )
        braze = self.BRAZE_OVERRIDES[self.SITE_CODE]['BRAZE']
        with patch('ecommerce_worker.email.v1.braze.client.get_braze_configuration', Mock(return_value=braze)):
            client = get_braze_client(self.SITE_CODE)
            bounce = client.did_email_bounce(bounced_email)
            self.assertEqual(bounce, did_bounce)

    @responses.activate
    @ddt.data(
        (400, BrazeClientError),
        (429, BrazeRateLimitError),
        (500, BrazeInternalServerError),
    )
    @ddt.unpack
    def test_bounce_message_failure(self, status_code, error):
        """
        Verify that a failed email message throws the relevant error.
        """
        failure_response = {
            'message': 'Not a Success'
        }
        bounced_email = 'foo@braze.com'
        host = 'https://rest.iad-06.braze.com/email/hard_bounces?{email}'.format(
            email=urlencode({'email': bounced_email})
        )

        responses.add(
            responses.GET,
            host,
            json=failure_response,
            status=status_code
        )
        braze = self.BRAZE_OVERRIDES[self.SITE_CODE]['BRAZE']
        with patch('ecommerce_worker.email.v1.braze.client.get_braze_configuration', Mock(return_value=braze)):
            client = get_braze_client(self.SITE_CODE)
            with self.assertRaises(error):
                client.did_email_bounce(bounced_email)

    def test_did_email_bounce_failure_missing_parameters(self):
        """
        Verify that an error is raised for missing parameters.
        """
        braze = self.BRAZE_OVERRIDES[self.SITE_CODE]['BRAZE']
        with patch('ecommerce_worker.email.v1.braze.client.get_braze_configuration', Mock(return_value=braze)):
            client = get_braze_client(self.SITE_CODE)
            with self.assertRaises(BrazeClientError):
                client.did_email_bounce(email_id=None)

    def test_get_braze_external_id(self):
        """
        Asserts an error is raised by a call to get_braze_external_id.
        """
        braze = self.BRAZE_OVERRIDES[self.SITE_CODE]['BRAZE']
        with patch('ecommerce_worker.email.v1.braze.client.get_braze_configuration', Mock(return_value=braze)):
            client = get_braze_client(self.SITE_CODE)
            with self.assertRaises(BrazeClientError):
                client.get_braze_external_id(email_id=None)

    @responses.activate
    def test_get_braze_external_id_success(self):
        """
        Tests a successful call to the /users/export/ids endpoint
        """
        host = 'https://rest.iad-06.braze.com/users/export/ids'
        responses.add(
            responses.POST,
            host,
            json={"users": [{"external_id": "5261613"}], "message": "success"},
            status=201
        )
        braze = self.BRAZE_OVERRIDES[self.SITE_CODE]['BRAZE']
        with patch('ecommerce_worker.email.v1.braze.client.get_braze_configuration', Mock(return_value=braze)):
            client = get_braze_client(self.SITE_CODE)
            external_id = client.get_braze_external_id(email_id='test@example.com')
            self.assertEqual(external_id, '5261613')
