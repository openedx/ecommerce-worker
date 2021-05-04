""" Tests for utility functions. """

from unittest import TestCase

import ddt
import json
import responses
from mock import patch

from ecommerce_worker.email.v1.utils import did_email_bounce, update_assignment_email_status
from ecommerce_worker.utils import get_configuration


@ddt.ddt
class EmailUtilsTests(TestCase):
    """Tests for email v1 utility functions."""

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
        self.assertEqual(
            update_assignment_email_status('555', '1234ABC', 'success'),
            return_value
        )

    def test_update_assignment_email_exception(self):
        """
        Test that we gracefully catch a request exception.
        """
        # Do not mock api response - responses module will reject http request
        assert not update_assignment_email_status('555', '1234ABC', 'success')

    @patch('ecommerce_worker.email.v1.utils.get_braze_client')
    @patch('ecommerce_worker.email.v1.utils.is_braze_enabled')
    @ddt.data(True, False)
    def test_did_email_bounce_routing(self, braze_enabled, braze_enabled_mock, braze_client_mock):
        """
        Test that we direct requests for email bouncing correctly.
        """
        braze_enabled_mock.return_value = braze_enabled
        braze_client_mock.return_value.did_email_bounce.return_value = True
        bounced = did_email_bounce('email', 'site_code')
        assert bounced == braze_enabled
