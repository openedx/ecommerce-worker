"""Tests of fulfillment tasks."""
# pylint: disable=no-value-for-parameter
from __future__ import absolute_import, unicode_literals
from unittest import TestCase

from celery.exceptions import Ignore
import ddt
from edx_rest_api_client import exceptions
import responses
import jwt
import mock

# Ensures that a Celery app is initialized when tests are run.
from ecommerce_worker import celery_app  # pylint: disable=unused-import
from ecommerce_worker.fulfillment.v1.tasks import fulfill_order
from ecommerce_worker.utils import get_configuration


@ddt.ddt
class OrderFulfillmentTaskTests(TestCase):
    """Tests of the order fulfillment task."""
    ORDER_NUMBER = 'FAKE-123456'
    API_URL = '{root}/orders/{number}/fulfill/'.format(
        root=get_configuration('ECOMMERCE_API_ROOT').strip('/'),
        number=ORDER_NUMBER
    )

    @ddt.data(
        'ECOMMERCE_API_ROOT',
        'MAX_FULFILLMENT_RETRIES',
        'JWT_SECRET_KEY',
        'JWT_ISSUER',
        'ECOMMERCE_SERVICE_USERNAME'
    )
    def test_requires_configuration(self, setting):
        """Verify that the task refuses to run without the configuration it requires."""
        with mock.patch('ecommerce_worker.configuration.test.' + setting, None):
            with self.assertRaises(RuntimeError):
                fulfill_order(self.ORDER_NUMBER)

    @responses.activate
    def test_fulfillment_success(self):
        """Verify that the task exits without an error when fulfillment succeeds."""
        responses.add(responses.PUT, self.API_URL, status=200, body="{}")

        result = fulfill_order.delay(self.ORDER_NUMBER).get()
        self.assertIsNone(result)

        # Validate the value of the HTTP Authorization header.
        last_request = responses.calls[-1].request
        token = last_request.headers.get('authorization').split()[1]
        payload = jwt.decode(token, get_configuration('JWT_SECRET_KEY'), algorithms=['HS256'])
        self.assertEqual(payload['username'], get_configuration('ECOMMERCE_SERVICE_USERNAME'))

    @responses.activate
    def test_fulfillment_not_possible(self):
        """Verify that the task exits without an error when fulfillment is not possible."""
        responses.add(responses.PUT, self.API_URL, status=406, body="{}")

        with self.assertRaises(Ignore):
            fulfill_order(self.ORDER_NUMBER)

    @responses.activate
    def test_fulfillment_unknown_client_error(self):
        """
        Verify that the task raises an exception when fulfillment fails because of an
        unknown client error.
        """
        responses.add(responses.PUT, self.API_URL, status=404, body="{}")

        with self.assertRaises(exceptions.HttpClientError):
            fulfill_order(self.ORDER_NUMBER)

    @responses.activate
    def test_fulfillment_unknown_client_error_retry_success(self):
        """Verify that the task is capable of successfully retrying after client error."""
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
        """Verify that the task raises an exception when fulfillment fails."""
        responses.add(responses.PUT, self.API_URL, status=500, body="{}")

        with self.assertRaises(exceptions.HttpServerError):
            fulfill_order.delay(self.ORDER_NUMBER).get()

    @responses.activate
    def test_fulfillment_timeout(self):
        """Verify that the task raises an exception when fulfillment times out."""
        responses.add(responses.PUT, self.API_URL, status=404, body=exceptions.Timeout())

        with self.assertRaises(exceptions.Timeout):
            fulfill_order.delay(self.ORDER_NUMBER).get()

    @responses.activate
    def test_fulfillment_retry_success(self):
        """Verify that the task is capable of successfully retrying after fulfillment failure."""
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
        """Verify that the task correctly adds the email_opt_in parameter to the request."""
        email_opt_in_api_url = self.API_URL + '?email_opt_in=' + email_opt_in_str
        responses.add(responses.PUT, email_opt_in_api_url, status=200, body="{}")

        result = fulfill_order.delay(self.ORDER_NUMBER, email_opt_in=email_opt_in_bool).get()
        self.assertIsNone(result)

        last_request = responses.calls[-1].request
        self.assertIn('?email_opt_in=' + email_opt_in_str, last_request.path_url)
