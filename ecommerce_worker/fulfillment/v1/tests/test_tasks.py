"""Tests of fulfillment tasks."""
# pylint: disable=no-value-for-parameter
from unittest import TestCase, mock
from urllib.parse import urljoin

import ddt
import responses
from celery.exceptions import Ignore
from edx_rest_api_client import exceptions
from requests.exceptions import HTTPError

# Ensures that a Celery app is initialized when tests are run.
from ecommerce_worker import celery_app  # pylint: disable=unused-import
from ecommerce_worker.fulfillment.v1.tasks import fulfill_order
from ecommerce_worker.utils import get_configuration


@ddt.ddt
class OrderFulfillmentTaskTests(TestCase):
    """
    Tests of the order fulfillment task.
    """
    ORDER_NUMBER = 'FAKE-123456'
    API_URL = urljoin(get_configuration('ECOMMERCE_API_ROOT') + '/', f'orders/{ORDER_NUMBER}/fulfill/')
    OAUTH_ACCESS_TOKEN_URL = urljoin(
        get_configuration('BACKEND_SERVICE_EDX_OAUTH2_PROVIDER_URL') + '/', 'access_token/'
    )
    ACCESS_TOKEN = 'FAKE-access-token'

    def setUp(self):
        super().setUp()
        self.mock_access_token_api()

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

    @ddt.data(
        'ECOMMERCE_API_ROOT',
        'MAX_FULFILLMENT_RETRIES',
        'BACKEND_SERVICE_EDX_OAUTH2_PROVIDER_URL',
        'BACKEND_SERVICE_EDX_OAUTH2_KEY',
        'BACKEND_SERVICE_EDX_OAUTH2_SECRET'
    )
    def test_requires_configuration(self, setting):
        """
        Verify that the task refuses to run without the configuration it requires.
        """
        with mock.patch('ecommerce_worker.configuration.test.' + setting, None):
            with self.assertRaises(RuntimeError):
                fulfill_order(self.ORDER_NUMBER)

    @responses.activate
    def test_fulfillment_success(self):
        """
        Verify that the task exits without an error when fulfillment succeeds.
        """
        responses.add(responses.PUT, self.API_URL, status=200, body="{}")

        result = fulfill_order.delay(self.ORDER_NUMBER).get()
        self.assertIsNone(result)

        # Validate the value of the HTTP Authorization header.
        last_request = responses.calls[-1].request
        token = last_request.headers.get('Authorization').split()[1]
        self.assertEqual(token, self.ACCESS_TOKEN)

    @responses.activate
    def test_fulfillment_not_possible(self):
        """
        Verify that the task exits without an error when fulfillment is not possible.
        """
        responses.add(responses.PUT, self.API_URL, status=406, body="{}")

        with self.assertRaises(Ignore):
            fulfill_order(self.ORDER_NUMBER)

    @responses.activate
    def test_fulfillment_connection_error(self):
        """
        Verify that the task raises an exception when fulfillment fails because of connection error.
        """
        responses.add(responses.PUT, self.API_URL, status=404, body="{}")

        with self.assertRaises(HTTPError):
            fulfill_order(self.ORDER_NUMBER)

    @responses.activate
    def test_fulfillment_connection_error_retry_success(self):
        """
        Verify that the task is capable of successfully retrying after connection error.
        """
        responses.add(
            responses.Response(responses.PUT, self.API_URL, status=404, body="{}"),
        )
        responses.add(
            responses.Response(responses.PUT, self.API_URL, status=200, body="{}"),
        )

        result = fulfill_order.delay(self.ORDER_NUMBER).get()
        self.assertIsNone(result)

    @responses.activate
    def test_fulfillment_failure(self):
        """
        Verify that the task raises an exception when fulfillment fails.
        """
        responses.add(responses.PUT, self.API_URL, status=500, body="{}")

        with self.assertRaises(HTTPError):
            fulfill_order.delay(self.ORDER_NUMBER).get()

    @responses.activate
    def test_fulfillment_timeout(self):
        """
        Verify that the task raises an exception when fulfillment times out.
        """
        responses.add(responses.PUT, self.API_URL, status=404, body=exceptions.Timeout())

        with self.assertRaises(exceptions.Timeout):
            fulfill_order.delay(self.ORDER_NUMBER).get()

    @responses.activate
    def test_fulfillment_retry_success(self):
        """
        Verify that the task is capable of successfully retrying after fulfillment failure.
        """
        responses.add(
            responses.Response(responses.PUT, self.API_URL, status=500, body="{}"),
        )
        responses.add(
            responses.Response(responses.PUT, self.API_URL, status=200, body="{}"),
        )

        result = fulfill_order.delay(self.ORDER_NUMBER).get()
        self.assertIsNone(result)

    @ddt.data(
        [True, 'True'],
        [False, 'False']
    )
    @ddt.unpack
    @responses.activate
    def test_email_opt_in_parameter_sent(self, email_opt_in_bool, email_opt_in_str):
        """
        Verify that the task correctly adds the email_opt_in parameter to the request.
        """
        email_opt_in_api_url = self.API_URL + '?email_opt_in=' + email_opt_in_str
        responses.add(responses.PUT, email_opt_in_api_url, status=200, body="{}")

        result = fulfill_order.delay(self.ORDER_NUMBER, email_opt_in=email_opt_in_bool).get()
        self.assertIsNone(result)

        last_request = responses.calls[-1].request
        self.assertIn('?email_opt_in=' + email_opt_in_str, last_request.path_url)
