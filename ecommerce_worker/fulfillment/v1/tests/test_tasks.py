"""Tests of fulfillment tasks."""
# pylint: disable=no-value-for-parameter
from unittest import TestCase

from celery.exceptions import Ignore
import ddt
from edx_rest_api_client import exceptions
import httpretty
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

    @httpretty.activate
    def test_fulfillment_success(self):
        """Verify that the task exits without an error when fulfillment succeeds."""
        httpretty.register_uri(httpretty.PUT, self.API_URL, status=200, body={})

        result = fulfill_order.delay(self.ORDER_NUMBER).get()
        self.assertIsNone(result)

        # Validate the value of the HTTP Authorization header.
        last_request = httpretty.last_request()
        token = last_request.headers.get('authorization').split()[1]
        payload = jwt.decode(token, get_configuration('JWT_SECRET_KEY'))
        self.assertEqual(payload['username'], get_configuration('ECOMMERCE_SERVICE_USERNAME'))

    @httpretty.activate
    def test_fulfillment_not_possible(self):
        """Verify that the task exits without an error when fulfillment is not possible."""
        httpretty.register_uri(httpretty.PUT, self.API_URL, status=406, body={})

        with self.assertRaises(Ignore):
            fulfill_order(self.ORDER_NUMBER)

    @httpretty.activate
    def test_fulfillment_unknown_client_error(self):
        """
        Verify that the task raises an exception when fulfillment fails because of an
        unknown client error.
        """
        httpretty.register_uri(httpretty.PUT, self.API_URL, status=404, body={})

        with self.assertRaises(exceptions.HttpClientError):
            fulfill_order(self.ORDER_NUMBER)

    @httpretty.activate
    def test_fulfillment_unknown_client_error_retry_success(self):
        """Verify that the task is capable of successfully retrying after client error."""
        httpretty.register_uri(httpretty.PUT, self.API_URL, responses=[
            httpretty.Response(status=404, body={}),
            httpretty.Response(status=200, body={}),
        ])

        result = fulfill_order.delay(self.ORDER_NUMBER).get()
        self.assertIsNone(result)

    @httpretty.activate
    def test_fulfillment_failure(self):
        """Verify that the task raises an exception when fulfillment fails."""
        httpretty.register_uri(httpretty.PUT, self.API_URL, status=500, body={})

        with self.assertRaises(exceptions.HttpServerError):
            fulfill_order.delay(self.ORDER_NUMBER).get()

    @httpretty.activate
    def test_fulfillment_timeout(self):
        """Verify that the task raises an exception when fulfillment times out."""
        httpretty.register_uri(httpretty.PUT, self.API_URL, status=404, body=self._timeout_body)

        with self.assertRaises(exceptions.Timeout):
            fulfill_order.delay(self.ORDER_NUMBER).get()

    @httpretty.activate
    def test_fulfillment_retry_success(self):
        """Verify that the task is capable of successfully retrying after fulfillment failure."""
        httpretty.register_uri(httpretty.PUT, self.API_URL, responses=[
            httpretty.Response(status=500, body={}),
            httpretty.Response(status=200, body={}),
        ])

        result = fulfill_order.delay(self.ORDER_NUMBER).get()
        self.assertIsNone(result)

    @ddt.data(
        [True, 'True'],
        [False, 'False']
    )
    @ddt.unpack
    @httpretty.activate
    def test_email_opt_in_parameter_sent(self, email_opt_in_bool, email_opt_in_str):
        """Verify that the task correctly adds the email_opt_in parameter to the request."""
        email_opt_in_api_url = self.API_URL + '?email_opt_in=' + email_opt_in_str
        httpretty.register_uri(httpretty.PUT, email_opt_in_api_url, status=200, body={})

        result = fulfill_order.delay(self.ORDER_NUMBER, email_opt_in=email_opt_in_bool).get()
        self.assertIsNone(result)

        last_request = httpretty.last_request()
        self.assertIn('?email_opt_in=' + email_opt_in_str, last_request.path)
        # QueryDicts store their values as lists in case multiple values are passed in.
        # last_request.querystring is returned as a dict instead of a QueryDict
        # so we have the grab the first element in the list to actually get the value.
        self.assertEqual(last_request.querystring['email_opt_in'][0], email_opt_in_str)

    def _timeout_body(self, request, uri, headers):  # pylint: disable=unused-argument
        """Helper used to force httpretty to raise Timeout exceptions."""
        raise exceptions.Timeout
