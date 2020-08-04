"""Tests of Sailthru worker code."""
import logging
import json
from decimal import Decimal
from unittest import TestCase
import ddt

import httpretty
from celery.exceptions import Retry
from mock import patch, Mock
from sailthru import SailthruClient
from sailthru.sailthru_error import SailthruClientError
from testfixtures import LogCapture
from requests.exceptions import RequestException
from six import text_type
from ecommerce_worker.sailthru.v1.exceptions import SailthruError
from ecommerce_worker.sailthru.v1.tasks import (
    update_course_enrollment, _update_unenrolled_list, _get_course_content, _get_course_content_from_ecommerce,
    send_course_refund_email, send_offer_assignment_email, send_offer_update_email, send_offer_usage_email,
    _update_assignment_email_status,

)
from ecommerce_worker.utils import get_configuration

TEST_EMAIL = "test@edx.org"


class MockSailthruResponse(object):
    """
    Mock object for SailthruResponse
    """

    def __init__(self, json_response, error=None, code=1):
        self.json = json_response
        self.error = error
        self.code = code

    def is_ok(self):
        """
        Return true of no error
        """
        return self.error is None

    def get_error(self):
        """
        Get error description
        """
        return MockSailthruError(self.error, self.code)


class MockSailthruError(object):
    """
    Mock object for Sailthru Error
    """

    def __init__(self, error, code=1):
        self.error = error
        self.code = code

    def get_message(self):
        """
        Get error description
        """
        return self.error

    def get_error_code(self):
        """
        Get error code
        """
        return self.code


class SailthruTests(TestCase):
    """
    Tests for the Sailthru tasks class.
    """

    def setUp(self):
        super(SailthruTests, self).setUp()
        self.course_id = 'edX/toy/2012_Fall'
        self.course_url = 'http://lms.testserver.fake/courses/edX/toy/2012_Fall/info'
        self.course_id2 = 'edX/toy/2016_Fall'
        self.course_url2 = 'http://lms.testserver.fake/courses/edX/toy/2016_Fall/info'

    def mock_ecommerce_api(self, body, course_id, status=200):
        """ Mock GET requests to the ecommerce course API endpoint. """
        httpretty.reset()
        httpretty.register_uri(
            httpretty.GET, '{}/courses/{}/'.format(
                get_configuration('ECOMMERCE_API_ROOT').strip('/'), text_type(course_id)
            ),
            status=status,
            body=json.dumps(body), content_type='application/json',
        )

    def ecom_course_data(self, course_id):
        """ Returns dummy course data. """
        return {
            "id": course_id,
            "url": "https://test-ecommerce.edx.org/api/v2/courses/{}/".format(course_id),
            "name": "test course",
            "verification_deadline": "2016-12-01T23:59:00Z",
            "type": "verified",
            "products_url": "https://test-ecommerce.edx.org/api/v2/courses/{}/products/".format(course_id),
            "last_edited": "2016-12-28T15:20:58Z"
        }

    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.purchase')
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.api_get')
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.api_post')
    def test_update_course_upgrade(self, mock_sailthru_api_post,
                                   mock_sailthru_api_get, mock_sailthru_purchase):
        """test add upgrade to cart"""

        # create mocked Sailthru API responses
        mock_sailthru_api_post.return_value = MockSailthruResponse({'ok': True})
        mock_sailthru_api_get.return_value = MockSailthruResponse({'vars': {'upgrade_deadline_verified': '2020-03-12'}})
        mock_sailthru_purchase.return_value = MockSailthruResponse({'ok': True})

        update_course_enrollment.delay(TEST_EMAIL,
                                       self.course_url,
                                       True,
                                       'verified',
                                       course_id=self.course_id,
                                       currency='USD',
                                       message_id='cookie_bid',
                                       unit_cost=49)
        mock_sailthru_purchase.assert_called_with(
            TEST_EMAIL,
            [{
                'vars': {
                    'purchase_sku': None,
                    'course_run_id': self.course_id,
                    'mode': 'verified',
                    'upgrade_deadline_verified': '2020-03-12'
                },
                'title': 'Course ' + self.course_id + ' mode: verified',
                'url': self.course_url,
                'price': 4900, 'qty': 1,
                'id': self.course_id + '-verified'
            }],
            options={
                'reminder_template': 'abandoned_template',
                'reminder_time': '+60 minutes'
            },
            incomplete=True, message_id='cookie_bid')

    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.purchase')
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.api_get')
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.api_post')
    def test_update_course_purchase(self, mock_sailthru_api_post,
                                    mock_sailthru_api_get, mock_sailthru_purchase):
        """test add purchase to cart"""

        # create mocked Sailthru API responses
        mock_sailthru_api_post.return_value = MockSailthruResponse({'ok': True})
        mock_sailthru_api_get.return_value = MockSailthruResponse({
            'tags': 'tag1,tag2',
            'title': 'Course title'
        })
        mock_sailthru_purchase.return_value = MockSailthruResponse({'ok': True})

        update_course_enrollment.delay(
            TEST_EMAIL,
            self.course_url2,
            True,
            'credit',
            course_id=self.course_id2,
            currency='USD',
            message_id='cookie_bid',
            unit_cost=49
        )
        mock_sailthru_purchase.assert_called_with(
            TEST_EMAIL,
            [{
                'vars': {
                    'purchase_sku': None,
                    'course_run_id': self.course_id2,
                    'mode': 'credit'
                },
                'title': 'Course title',
                'url': self.course_url2,
                'tags': 'tag1,tag2',
                'price': 4900, 'qty': 1,
                'id': self.course_id2 + '-credit'
            }],
            options={
                'reminder_template': 'abandoned_template',
                'reminder_time': '+60 minutes'
            },
            incomplete=True,
            message_id='cookie_bid'
        )

    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.purchase')
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.api_get')
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.api_post')
    def test_update_course_purchase_complete(self, mock_sailthru_api_post,
                                             mock_sailthru_api_get, mock_sailthru_purchase):
        """test purchase complete"""

        # create mocked Sailthru API responses
        mock_sailthru_api_post.return_value = MockSailthruResponse({'ok': True})
        mock_sailthru_api_get.return_value = MockSailthruResponse({'vars': {'upgrade_deadline_verified': '2020-03-12'}})
        mock_sailthru_purchase.return_value = MockSailthruResponse({'ok': True})

        update_course_enrollment.delay(
            TEST_EMAIL,
            self.course_url,
            False,
            'credit',
            course_id=self.course_id,
            currency='USD',
            message_id='cookie_bid',
            unit_cost=99
        )
        mock_sailthru_purchase.assert_called_with(
            TEST_EMAIL,
            [{
                'vars': {
                    'purchase_sku': None,
                    'course_run_id': self.course_id,
                    'mode': 'credit',
                    'upgrade_deadline_verified': '2020-03-12'
                },
                'title': 'Course ' + self.course_id + ' mode: credit',
                'url': self.course_url,
                'price': 9900, 'qty': 1,
                'id': self.course_id + '-credit'
            }],
            options={'send_template': 'purchase_template'},
            incomplete=False,
            message_id='cookie_bid'
        )

    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.purchase')
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.api_get')
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.api_post')
    def test_update_course_upgrade_complete(self, mock_sailthru_api_post,
                                            mock_sailthru_api_get, mock_sailthru_purchase):
        """test upgrade complete"""

        # create mocked Sailthru API responses
        mock_sailthru_api_post.return_value = MockSailthruResponse({'ok': True})
        mock_sailthru_api_get.return_value = MockSailthruResponse({'vars': {'upgrade_deadline_verified': '2020-03-12'}})
        mock_sailthru_purchase.return_value = MockSailthruResponse({'ok': True})

        update_course_enrollment.delay(
            TEST_EMAIL,
            self.course_url,
            False,
            'verified',
            course_id=self.course_id,
            currency='USD',
            message_id='cookie_bid',
            unit_cost=99
        )
        mock_sailthru_purchase.assert_called_with(
            TEST_EMAIL,
            [{
                'vars': {
                    'purchase_sku': None,
                    'course_run_id': self.course_id,
                    'mode': 'verified',
                    'upgrade_deadline_verified': '2020-03-12'
                },
                'title': 'Course ' + self.course_id + ' mode: verified',
                'url': self.course_url,
                'price': 9900, 'qty': 1,
                'id': self.course_id + '-verified'
            }],
            options={'send_template': 'upgrade_template'},
            incomplete=False,
            message_id='cookie_bid'
        )

    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.purchase')
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.api_get')
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.api_post')
    def test_update_course_upgrade_complete_site(self, mock_sailthru_api_post,
                                                 mock_sailthru_api_get, mock_sailthru_purchase):
        """test upgrade complete with site code"""

        # create mocked Sailthru API responses
        mock_sailthru_api_post.return_value = MockSailthruResponse({'ok': True})
        mock_sailthru_api_get.return_value = MockSailthruResponse({'vars': {'upgrade_deadline_verified': '2020-03-12'}})
        mock_sailthru_purchase.return_value = MockSailthruResponse({'ok': True})

        # test upgrade complete with site code
        with patch('ecommerce_worker.configuration.test.SITE_OVERRIDES', get_configuration('TEST_SITE_OVERRIDES')):
            update_course_enrollment.delay(
                TEST_EMAIL,
                self.course_url,
                False,
                'verified',
                course_id=self.course_id,
                currency='USD',
                message_id='cookie_bid',
                unit_cost=Decimal(99.01),
                site_code='test_site'
            )
        mock_sailthru_purchase.assert_called_with(
            TEST_EMAIL,
            [{
                'vars': {
                    'purchase_sku': None,
                    'course_run_id': self.course_id,
                    'mode': 'verified',
                    'upgrade_deadline_verified': '2020-03-12'
                },
                'title': 'Course ' + self.course_id + ' mode: verified',
                'url': self.course_url,
                'price': 9901, 'qty': 1,
                'id': self.course_id + '-verified'
            }],
            options={'send_template': 'site_upgrade_template'},
            incomplete=False,
            message_id='cookie_bid'
        )

    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.purchase')
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.api_get')
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.api_post')
    def test_update_course_enroll(self, mock_sailthru_api_post, mock_sailthru_api_get, mock_sailthru_purchase):
        """test audit enroll"""

        # create mocked Sailthru API responses
        mock_sailthru_api_post.return_value = MockSailthruResponse({'ok': True})
        mock_sailthru_api_get.return_value = MockSailthruResponse({'vars': {'upgrade_deadline_verified': '2020-03-12'}})
        mock_sailthru_purchase.return_value = MockSailthruResponse({'ok': True})

        update_course_enrollment.delay(
            TEST_EMAIL,
            self.course_url,
            False,
            'audit',
            course_id=self.course_id,
            currency='USD',
            message_id='cookie_bid',
            unit_cost=Decimal(0)
        )
        mock_sailthru_purchase.assert_called_with(
            TEST_EMAIL,
            [{
                'vars': {
                    'purchase_sku': None,
                    'course_run_id': self.course_id,
                    'mode': 'audit',
                    'upgrade_deadline_verified': '2020-03-12'
                },
                'title': 'Course ' + self.course_id + ' mode: audit',
                'url': self.course_url,
                'price': 0,
                'qty': 1,
                'id': self.course_id + '-audit'
            }],
            options={'send_template': 'enroll_template'},
            incomplete=False,
            message_id='cookie_bid'
        )

    @patch('ecommerce_worker.sailthru.v1.tasks.logger.error')
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.purchase')
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.api_get')
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.api_post')
    def test_purchase_api_error(self, mock_sailthru_api_post,
                                mock_sailthru_api_get, mock_sailthru_purchase, mock_log_error):
        """test purchase API error"""

        # create mocked Sailthru API responses
        mock_sailthru_api_post.return_value = MockSailthruResponse({'ok': True})
        mock_sailthru_api_get.return_value = MockSailthruResponse({'vars': {'upgrade_deadline_verified': '2020-03-12'}})

        mock_sailthru_purchase.return_value = MockSailthruResponse({}, error='error')
        update_course_enrollment.delay(
            TEST_EMAIL,
            self.course_url,
            False,
            'verified',
            course_id=self.course_id,
            currency='USD',
            message_id='cookie_bid',
            unit_cost=Decimal(99)
        )
        self.assertTrue(mock_log_error.called)

    @patch('ecommerce_worker.sailthru.v1.tasks.logger.error')
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.purchase')
    def test_purchase_api_exception(self,
                                    mock_sailthru_purchase, mock_log_error):
        """test purchase API exception"""
        mock_sailthru_purchase.side_effect = SailthruClientError
        update_course_enrollment.delay(
            TEST_EMAIL,
            self.course_url,
            False,
            'verified',
            course_id=self.course_id,
            currency='USD',
            message_id='cookie_bid',
            unit_cost=Decimal(99)
        )
        self.assertTrue(mock_log_error.called)

    @patch('ecommerce_worker.sailthru.v1.tasks.logger.error')
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient.api_get')
    def test_user_get_error(self,
                            mock_sailthru_api_get, mock_log_error):
        # test error reading unenrolled list
        mock_sailthru_api_get.return_value = MockSailthruResponse({}, error='error', code=43)
        update_course_enrollment.delay(
            TEST_EMAIL,
            self.course_url,
            False,
            'honor',
            course_id=self.course_id,
            currency='USD',
            message_id='cookie_bid',
            unit_cost=Decimal(99)
        )
        self.assertTrue(mock_log_error.called)

    @httpretty.activate
    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient')
    def test_get_course_content(self, mock_sailthru_client):
        """
        test routine which fetches data from Sailthru content api
        """
        config = {'SAILTHRU_CACHE_TTL_SECONDS': 100}
        mock_sailthru_client.api_get.return_value = MockSailthruResponse({"title": "The title"})
        response_json = _get_course_content(self.course_id, 'course:123', mock_sailthru_client, None, config)
        self.assertEquals(response_json, {"title": "The title"})
        mock_sailthru_client.api_get.assert_called_with('content', {'id': 'course:123'})

        # test second call uses cache
        mock_sailthru_client.reset_mock()
        response_json = _get_course_content(self.course_id, 'course:123', mock_sailthru_client, None, config)
        self.assertEquals(response_json, {"title": "The title"})
        mock_sailthru_client.api_get.assert_not_called()

        # test error from Sailthru
        mock_sailthru_client.api_get.return_value = MockSailthruResponse({}, error='Got an error')
        data = self.ecom_course_data(self.course_id)
        expected_response = {
            'title': 'test course',
            'verification_deadline': '2016-12-01T23:59:00Z'
        }
        self.mock_ecommerce_api(data, self.course_id)
        self.assertEquals(
            _get_course_content(self.course_id, 'course:124', mock_sailthru_client, None, config), expected_response
        )

        # test Sailthru exception
        data = self.ecom_course_data(self.course_id)
        expected_response = {
            'title': 'test course',
            'verification_deadline': '2016-12-01T23:59:00Z'
        }
        mock_sailthru_client.api_get.side_effect = SailthruClientError
        self.mock_ecommerce_api(data, self.course_id)
        self.assertEquals(
            _get_course_content(self.course_id, 'course:125', mock_sailthru_client, None, config), expected_response
        )

        # test Sailthru and Ecommerce exception
        mock_sailthru_client.api_get.side_effect = SailthruClientError
        self.mock_ecommerce_api({}, self.course_id2, status=500)
        self.assertEquals(
            _get_course_content(self.course_id2, 'course:126', mock_sailthru_client, None, config), {}
        )

    @httpretty.activate
    def test_get_course_content_from_ecommerce(self):
        """
        Test routine that fetches data from ecommerce.
        """
        data = self.ecom_course_data(self.course_id)
        expected_response = {
            'title': 'test course',
            'verification_deadline': '2016-12-01T23:59:00Z'
        }
        self.mock_ecommerce_api(data, self.course_id)

        response_json = _get_course_content_from_ecommerce(self.course_id, None)
        self.assertEquals(response_json, expected_response)

        # test error getting data
        self.mock_ecommerce_api({}, self.course_id2, status=500)
        response_json = _get_course_content_from_ecommerce(self.course_id2, None)
        self.assertEquals(response_json, {})

    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient')
    def test_update_unenrolled_list_new(self, mock_sailthru_client):
        """
        test routine which updates the unenrolled list in Sailthru
        """

        # test a new unenroll
        mock_sailthru_client.api_get.return_value = MockSailthruResponse({'vars': {'unenrolled': ['course_u1']}})
        self.assertTrue(_update_unenrolled_list(mock_sailthru_client, TEST_EMAIL,
                                                self.course_url, True))
        mock_sailthru_client.api_get.assert_called_with("user", {"id": TEST_EMAIL, "fields": {"vars": 1}})
        mock_sailthru_client.api_post.assert_called_with(
            'user',
            {
                'vars': {'unenrolled': ['course_u1', self.course_url]},
                'id': TEST_EMAIL, 'key': 'email'
            })

    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient')
    def test_update_unenrolled_list_old(self, mock_sailthru_client):
        # test an existing unenroll
        mock_sailthru_client.reset_mock()
        mock_sailthru_client.api_get.return_value = MockSailthruResponse({'vars': {'unenrolled': [self.course_url]}})
        self.assertTrue(_update_unenrolled_list(mock_sailthru_client, TEST_EMAIL,
                                                self.course_url, True))
        mock_sailthru_client.api_get.assert_called_with("user", {"id": TEST_EMAIL, "fields": {"vars": 1}})
        mock_sailthru_client.api_post.assert_not_called()

    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient')
    def test_update_unenrolled_list_reenroll(self, mock_sailthru_client):
        # test an enroll of a previously unenrolled course
        mock_sailthru_client.reset_mock()
        mock_sailthru_client.api_get.return_value = MockSailthruResponse({'vars': {'unenrolled': [self.course_url]}})
        self.assertTrue(_update_unenrolled_list(mock_sailthru_client, TEST_EMAIL,
                                                self.course_url, False))
        mock_sailthru_client.api_post.assert_called_with(
            'user',
            {
                'vars': {'unenrolled': []},
                'id': TEST_EMAIL, 'key': 'email'
            })

    @patch('ecommerce_worker.sailthru.v1.utils.SailthruClient')
    def test_update_unenrolled_list_errors(self, mock_sailthru_client):
        # test get error from Sailthru
        mock_sailthru_client.reset_mock()
        # simulate retryable error
        mock_sailthru_client.api_get.return_value = MockSailthruResponse({}, error='Got an error', code=43)
        self.assertFalse(_update_unenrolled_list(mock_sailthru_client, TEST_EMAIL,
                                                 self.course_url, False))

        # test get error from Sailthru
        mock_sailthru_client.reset_mock()
        # simulate unretryable error
        mock_sailthru_client.api_get.return_value = MockSailthruResponse({}, error='Got an error', code=1)
        self.assertTrue(_update_unenrolled_list(mock_sailthru_client, TEST_EMAIL,
                                                self.course_url, False))

        # test post error from Sailthru
        mock_sailthru_client.reset_mock()
        mock_sailthru_client.api_post.return_value = MockSailthruResponse({}, error='Got an error', code=9)
        mock_sailthru_client.api_get.return_value = MockSailthruResponse({'vars': {'unenrolled': [self.course_url]}})
        self.assertFalse(_update_unenrolled_list(mock_sailthru_client, TEST_EMAIL,
                                                 self.course_url, False))

        # test exception
        mock_sailthru_client.api_get.side_effect = SailthruClientError
        self.assertFalse(_update_unenrolled_list(mock_sailthru_client, TEST_EMAIL,
                                                 self.course_url, False))


class SendCourseRefundEmailTests(TestCase):
    """ Validates the send_course_refund_email task. """
    LOG_NAME = 'ecommerce_worker.sailthru.v1.tasks'
    REFUND_ID = 1
    SITE_CODE = 'test'

    def execute_task(self):
        """ Execute the send_course_refund_email task. """
        send_course_refund_email(
            'test@example.com', self.REFUND_ID, '$150.00', 'Test Course', 'EDX-123', 'http://example.com', None
        )

    def mock_api_response(self, status, body):
        """ Mock the Sailthru send API. """
        httpretty.register_uri(
            httpretty.POST,
            'https://api.sailthru.com/send',
            status=status,
            body=json.dumps(body),
            content_type='application/json'
        )

    def test_client_instantiation_error(self):
        """ Verify no message is sent if an error occurs while instantiating the Sailthru API client. """
        with patch('ecommerce_worker.sailthru.v1.utils.get_sailthru_client', raises=SailthruError):
            self.execute_task()

    @patch('ecommerce_worker.sailthru.v1.tasks.logger.exception')
    def test_api_client_error(self, mock_log):
        """ Verify API client errors are logged. """
        with patch.object(SailthruClient, 'send', side_effect=SailthruClientError):
            self.execute_task()

        mock_log.assert_called_once_with(
            'A client error occurred while attempting to send a course refund notification for refund [%d].',
            self.REFUND_ID
        )

    @httpretty.activate
    def test_api_error_with_retry(self):
        """ Verify the task is rescheduled if an API error occurs, and the request can be retried. """
        error_code = 43
        error_msg = 'This is a fake error.'
        body = {
            'error': error_code,
            'errormsg': error_msg
        }
        self.mock_api_response(429, body)

        with LogCapture(level=logging.INFO) as log:
            with self.assertRaises(Retry):
                self.execute_task()

        log.check(
            (self.LOG_NAME, 'ERROR',
             'An error occurred while attempting to send a course refund notification for refund [%d]: %d - %s' % (
                 self.REFUND_ID, error_code, error_msg)),
            (self.LOG_NAME, 'INFO',
             'An attempt will be made again to send a course refund notification for refund [%d].' % self.REFUND_ID),
        )

    @httpretty.activate
    def test_api_error_without_retry(self):
        """ Verify error details are logged if an API error occurs, and the request can NOT be retried. """
        error_code = 1
        error_msg = 'This is a fake error.'
        body = {
            'error': error_code,
            'errormsg': error_msg
        }
        self.mock_api_response(500, body)

        with LogCapture(level=logging.INFO) as log:
            self.execute_task()

        log.check(
            (self.LOG_NAME, 'ERROR',
             'An error occurred while attempting to send a course refund notification for refund [%d]: %d - %s' % (
                 self.REFUND_ID, error_code, error_msg)),
            (self.LOG_NAME, 'WARNING',
             'No further attempts will be made to send a course refund notification for refund [%d].' % self.REFUND_ID),
        )

    @httpretty.activate
    def test_message_sent(self):
        """ Verify a message is logged after a successful API call to send the message. """
        self.mock_api_response(200, {'send_id': '1234ABC'})

        with LogCapture(level=logging.INFO) as log:
            self.execute_task()
        log.check(
            (self.LOG_NAME, 'INFO', 'Course refund notification sent for refund %d.' % self.REFUND_ID),
        )


class BaseSendEmailTests(TestCase):
    """
    Base class for testing the sending notification through sailthru client.
    """

    def mock_api_response(self, status, body):
        """ Mock the Sailthru send API. """
        httpretty.register_uri(
            httpretty.POST,
            'https://api.sailthru.com/send',
            status=status,
            body=json.dumps(body),
            content_type='application/json'
        )


@ddt.ddt
class SendOfferAssignmentEmailTests(BaseSendEmailTests):
    """ Validates the send_offer_assignment_email task. """
    LOG_NAME = 'ecommerce_worker.sailthru.v1.tasks'
    USER_EMAIL = 'user@unknown.com'
    OFFER_ASSIGNMENT_ID = '555'
    SEND_ID = '1234ABC'
    SUBJECT = 'New edX course assignment'
    EMAIL_BODY = 'Template message with johndoe@unknown.com GIL7RUEOU7VHBH7Q ' \
                 'http://tempurl.url/enroll 3 2012-04-23'

    ASSIGNMENT_TASK_KWARGS = {
        'user_email': USER_EMAIL,
        'offer_assignment_id': OFFER_ASSIGNMENT_ID,
        'subject': SUBJECT,
        'email_body': EMAIL_BODY,
    }

    UPDATE_TASK_KWARGS = {
        'user_email': USER_EMAIL,
        'subject': SUBJECT,
        'email_body': EMAIL_BODY,
    }

    def execute_task(self):
        """ Execute the send_offer_assignment_email task. """
        send_offer_assignment_email(**self.ASSIGNMENT_TASK_KWARGS)

    def mock_ecommerce_assignmentemail_api(self, body, status=200):
        """ Mock POST requests to the ecommerce assignmentemail API endpoint. """
        httpretty.reset()
        httpretty.register_uri(
            httpretty.POST, '{}/assignment-email/status/'.format(
                get_configuration('ECOMMERCE_API_ROOT').strip('/')
            ),
            status=status,
            body=json.dumps(body), content_type='application/json',
        )

    @patch('ecommerce_worker.sailthru.v1.tasks.get_sailthru_client', Mock(side_effect=SailthruError))
    @ddt.data(
        (send_offer_assignment_email, ASSIGNMENT_TASK_KWARGS),
        (send_offer_update_email, UPDATE_TASK_KWARGS),
    )
    @ddt.unpack
    def test_client_instantiation_error(self, task, task_kwargs):
        """ Verify no message is sent if an error occurs while instantiating the Sailthru API client. """
        with LogCapture(level=logging.INFO) as log:
            task(**task_kwargs)
        log.check(
            (self.LOG_NAME, 'ERROR', '[Offer Assignment] A client error occurred while attempting to send'
             ' a offer assignment notification. Message: {message}'.format(message=self.EMAIL_BODY)),
        )

    @patch('ecommerce_worker.sailthru.v1.tasks.logger.exception')
    @ddt.data(
        (send_offer_assignment_email, ASSIGNMENT_TASK_KWARGS),
        (send_offer_update_email, UPDATE_TASK_KWARGS),
    )
    @ddt.unpack
    def test_api_client_error(self, task, task_kwargs, mock_log):
        """ Verify API client errors are logged. """
        with patch.object(SailthruClient, 'send', side_effect=SailthruClientError):
            task(**task_kwargs)
        mock_log.assert_called_once_with(
            '[Offer Assignment] A client error occurred while attempting to send a offer assignment notification.'
            ' Message: {message}'.format(message=self.EMAIL_BODY)
        )

    @httpretty.activate
    @ddt.data(
        (send_offer_assignment_email, ASSIGNMENT_TASK_KWARGS),
        (send_offer_update_email, UPDATE_TASK_KWARGS),
    )
    @ddt.unpack
    def test_api_error_with_retry(self, task, task_kwargs):
        """ Verify the task is rescheduled if an API error occurs, and the request can be retried. """
        error_code = 43
        error_msg = 'This is a fake error.'
        body = {
            'error': error_code,
            'errormsg': error_msg
        }
        self.mock_api_response(429, body)
        with LogCapture(level=logging.INFO) as log:
            with self.assertRaises(Retry):
                task(**task_kwargs)
        log.check(
            (self.LOG_NAME, 'ERROR',
             '[Offer Assignment] A {token_error_code} - {token_error_message} error occurred'
             ' while attempting to send a offer assignment notification.'
             ' Message: {message}'.format(
                 message=self.EMAIL_BODY,
                 token_error_code=error_code,
                 token_error_message=error_msg
             )),
            (self.LOG_NAME, 'INFO',
             '[Offer Assignment] An attempt will be made to resend the offer assignment notification.'
             ' Message: {message}'.format(message=self.EMAIL_BODY)),
        )

    @httpretty.activate
    @ddt.data(
        (send_offer_assignment_email, ASSIGNMENT_TASK_KWARGS),
        (send_offer_update_email, UPDATE_TASK_KWARGS),
    )
    @ddt.unpack
    def test_api_error_without_retry(self, task, task_kwargs):
        """ Verify error details are logged if an API error occurs, and the request can NOT be retried. """
        error_code = 1
        error_msg = 'This is a fake error.'
        body = {
            'error': error_code,
            'errormsg': error_msg
        }
        self.mock_api_response(500, body)
        with LogCapture(level=logging.INFO) as log:
            task(**task_kwargs)
        log.check(
            (self.LOG_NAME, 'ERROR',
             '[Offer Assignment] A {token_error_code} - {token_error_message} error occurred'
             ' while attempting to send a offer assignment notification.'
             ' Message: {message}'.format(
                 message=self.EMAIL_BODY,
                 token_error_code=error_code,
                 token_error_message=error_msg
             )),
            (self.LOG_NAME, 'WARNING',
             '[Offer Assignment] No further attempts will be made to send the offer assignment notification.'
             ' Failed Message: {message}'.format(message=self.EMAIL_BODY)),
        )

    @httpretty.activate
    @patch('ecommerce_worker.sailthru.v1.tasks._update_assignment_email_status')
    def test_message_sent(self, mock_update_assignment):
        """ Verify a message is logged after a successful API call to send the message. """
        self.mock_api_response(200, {'send_id': '1234ABC'})
        with LogCapture(level=logging.INFO) as log:
            self.execute_task()
        log.check(
            (self.LOG_NAME, 'INFO',
             '[Offer Assignment] Offer assignment notification sent with message --- {message}'.format(
                 message=self.EMAIL_BODY)),
        )
        self.assertEqual(mock_update_assignment.call_count, 1)

    @httpretty.activate
    @patch('ecommerce_worker.utils.get_ecommerce_client')
    def test_update_assignment_exception(self, mock_get_ecommerce_client):
        """ Verify a message is logged after an unsuccessful API call to update the status. """
        self.mock_api_response(200, {'send_id': '1234ABC'})
        mock_get_ecommerce_client.side_effect = RequestException
        with LogCapture(level=logging.INFO) as log:
            self.execute_task()
        log.check(
            (self.LOG_NAME, 'ERROR', '[Offer Assignment] An error occurred while updating offer assignment email status'
             ' for offer id {token_offer} and message id {token_send_id} via the Ecommerce API.'.format(
                 token_offer=self.OFFER_ASSIGNMENT_ID,
                 token_send_id=self.SEND_ID)),
            (self.LOG_NAME, 'ERROR', '[Offer Assignment] An error occurred while updating email status data for '
             'offer {token_offer} and email {token_email} via the ecommerce API.'.format(
                 token_offer=self.OFFER_ASSIGNMENT_ID,
                 token_email=self.USER_EMAIL,))
        )

    @httpretty.activate
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
        self.mock_ecommerce_assignmentemail_api(data)
        self.assertEqual(_update_assignment_email_status(
            '555',
            '1234ABC',
            'success'), return_value)


class SendOfferUsageEmailTests(BaseSendEmailTests):
    """ Validates the send_offer_assignment_email task. """
    LOG_NAME = 'ecommerce_worker.sailthru.v1.notification'
    EMAILS = 'user@unknown.com, user1@example.com'
    SUBJECT = 'New edX course assignment'
    EMAIL_BODY = 'Template message with johndoe@unknown.com GIL7RUEOU7VHBH7Q ' \
                 'http://tempurl.url/enroll 3 2012-04-23'
    USAGE_TASK_KWARGS = {
        'emails': EMAILS,
        'subject': SUBJECT,
        'email_body': EMAIL_BODY,
    }

    @patch('ecommerce_worker.sailthru.v1.notification.get_sailthru_client', Mock(side_effect=SailthruError))
    def test_client_instantiation_error(self):
        """ Verify no message is sent if an error occurs while instantiating the Sailthru API client. """
        with LogCapture(level=logging.INFO) as log:
            send_offer_usage_email(**self.USAGE_TASK_KWARGS)
        log.check(
            (
                self.LOG_NAME,
                'ERROR',
                '[Offer Usage] A client error occurred while attempting to send a notification. '
                'Message: {message}'.format(
                    message=self.EMAIL_BODY
                )
            ),
        )

    @patch('ecommerce_worker.sailthru.v1.notification.log.exception')
    def test_api_client_error(self, mock_log):
        """ Verify API client errors are logged. """
        with patch.object(SailthruClient, 'multi_send', side_effect=SailthruClientError):
            send_offer_usage_email(**self.USAGE_TASK_KWARGS)
        mock_log.assert_called_once_with(
            '[Offer Usage] A client error occurred while attempting to send a notification.'
            ' Message: {message}'.format(message=self.EMAIL_BODY)
        )

    @httpretty.activate
    def test_api_error_with_retry(self):
        """ Verify the task is rescheduled if an API error occurs, and the request can be retried. """
        error_code = 43
        error_msg = 'This is a fake error.'
        body = {
            'error': error_code,
            'errormsg': error_msg
        }
        self.mock_api_response(429, body)
        with LogCapture(level=logging.INFO) as log:
            with self.assertRaises(Retry):
                send_offer_usage_email(**self.USAGE_TASK_KWARGS)
        log.check(
            (
                self.LOG_NAME,
                'ERROR',
                '[Offer Usage] An error occurred while attempting to send a notification. Message: {message},'
                ' Error code: {token_error_code}, Error Message: {token_error_message}.'.format(
                    message=self.EMAIL_BODY,
                    token_error_code=error_code,
                    token_error_message=error_msg
                )
            ),
            (
                self.LOG_NAME,
                'INFO',
                '[Offer Usage] An attempt will be made to resend the notification. Message: {message}'.format(
                    message=self.EMAIL_BODY
                )
            ),
        )

    @httpretty.activate
    def test_api_error_without_retry(self):
        """ Verify error details are logged if an API error occurs, and the request can NOT be retried. """
        error_code = 1
        error_msg = 'This is a fake error.'
        body = {
            'error': error_code,
            'errormsg': error_msg
        }
        self.mock_api_response(429, body)
        with LogCapture(level=logging.INFO) as log:
            send_offer_usage_email(**self.USAGE_TASK_KWARGS)
        log.check(
            (
                self.LOG_NAME,
                'ERROR',
                '[Offer Usage] An error occurred while attempting to send a notification. Message: {message},'
                ' Error code: {token_error_code}, Error Message: {token_error_message}.'.format(
                    message=self.EMAIL_BODY,
                    token_error_code=error_code,
                    token_error_message=error_msg
                )
            ),
            (
                self.LOG_NAME,
                'WARNING',
                '[Offer Usage] No further attempts will be made to send the notification.'
                ' Failed Message: {message}'.format(
                    message=self.EMAIL_BODY
                )
            ),
        )

    @httpretty.activate
    def test_api(self):
        """
        Test the happy path.
        """
        body = {
            'dummy-key': 'dummy-value'
        }
        self.mock_api_response(200, body)
        with LogCapture(level=logging.INFO) as log:
            send_offer_usage_email(**self.USAGE_TASK_KWARGS)
        log.check(
            (
                self.LOG_NAME,
                'INFO',
                '[Offer Usage] A notification has been sent successfully. Message: {message}'.format(
                    message=self.EMAIL_BODY
                )
            )
        )
