""" Tests for utility functions. """
import json
from json import JSONDecodeError
from unittest import TestCase, mock
from urllib.parse import urljoin

import ddt
import responses
from requests.exceptions import HTTPError

from ecommerce_worker.email.v1.utils import (
    did_email_bounce,
    remove_special_characters_from_string,
    update_assignment_email_status,
)
from ecommerce_worker.utils import get_configuration


@ddt.ddt
class EmailUtilsTests(TestCase):
    """
    Tests for email v1 utility functions.
    """

    OAUTH_ACCESS_TOKEN_URL = urljoin(
        get_configuration('BACKEND_SERVICE_EDX_OAUTH2_PROVIDER_URL') + '/', 'access_token/'
    )
    ACCESS_TOKEN = 'FAKE-access-token'

    def mock_ecommerce_assignment_email_api(self, body, status=200):
        """ Mock POST requests to the ecommerce assignment-email API endpoint. """
        responses.reset()
        responses.add(
            responses.POST, '{}/assignment-email/status/'.format(
                get_configuration('ECOMMERCE_API_ROOT').strip('/')
            ),
            status=status,
            body=json.dumps(body), content_type='application/json',
        )

    def mock_access_token_api(self, status=200):
        """
        Mock POST requests to retrieve an access token for this site's service user.
        """
        responses.add(
            responses.POST,
            self.OAUTH_ACCESS_TOKEN_URL,
            status=status,
            json={
                'access_token': self.ACCESS_TOKEN
            }
        )

    @responses.activate
    @ddt.data(
        (
            # Success case
            {
                'offer_assignment_id': '555',
                'send_id': '1234ABC',
                'status': 'updated',
                'error': ''
            },
            True,
        ),
        (
            # Exception case
            {
                'offer_assignment_id': '555',
                'send_id': '1234ABC',
                'status': 'failed',
                'error': ''
            },
            False,
        ),
    )
    @ddt.unpack
    def test_update_assignment_email_status(self, data, return_value):
        """
        Test routine that updates email send status in ecommerce.
        """
        self.mock_ecommerce_assignment_email_api(data)
        self.mock_access_token_api()
        self.assertEqual(
            update_assignment_email_status('555', '1234ABC', 'success'),
            return_value
        )

    @ddt.data(HTTPError, JSONDecodeError)
    @mock.patch('ecommerce_worker.email.v1.utils.get_access_token')
    @mock.patch('ecommerce_worker.email.v1.utils.requests.post')
    def test_update_assignment_email_exceptions(self, expected_exception, mock_access_token, mock_request_post):
        """
        Test that we gracefully catch a request exceptions.
        """
        mock_access_token.return_value.json.return_value = {'access_token': 'FAKE-access-token'}

        mock_response = mock.MagicMock()
        mock_response.raise_for_status.side_effect = expected_exception
        mock_request_post.return_value = mock_response

        assert not update_assignment_email_status('555', '1234ABC', 'success')

    @mock.patch('ecommerce_worker.email.v1.utils.get_braze_client')
    @mock.patch('ecommerce_worker.email.v1.utils.is_braze_enabled')
    @ddt.data(True, False)
    def test_did_email_bounce_routing(self, braze_enabled, braze_enabled_mock, braze_client_mock):
        """
        Test that we direct requests for email bouncing correctly.
        """
        braze_enabled_mock.return_value = braze_enabled
        braze_client_mock.return_value.did_email_bounce.return_value = True
        bounced = did_email_bounce('email', 'site_code')
        assert bounced == braze_enabled

    @ddt.data(
        ('', ''),
        ('EdX Support Team', 'EdX Support Team'),
        ('ABC Mills, Inc. on edX', 'ABC Mills Inc on edX'),
        ('A&B Enterprise, inc.', 'AB Enterprise inc'),
    )
    @ddt.unpack
    def test_remove_special_characters_from_string(self, input_string, expected):
        """
        Test that the utility returns string with all special characters removed.
        """
        actual_string = remove_special_characters_from_string(input_string)
        self.assertEqual(actual_string, expected)
