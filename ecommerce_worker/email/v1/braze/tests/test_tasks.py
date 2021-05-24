"""Tests of Braze task code."""

import logging
from unittest import TestCase

import ddt
import responses
from celery.exceptions import Retry
from mock import patch, Mock
from requests.exceptions import RequestException
from testfixtures import LogCapture

from ecommerce_worker.email.v1.braze.exceptions import (
    BrazeError,
    BrazeInternalServerError,
    BrazeRateLimitError
)
from ecommerce_worker.email.v1.tasks import (
    send_code_assignment_nudge_email,
    send_offer_assignment_email,
    send_offer_update_email,
    send_offer_usage_email,
)


@ddt.ddt
class SendEmailsViaBrazeTests(TestCase):
    """ Validates the email sending tasks with Braze api. """
    LOG_NAME = 'ecommerce_worker.email.v1.braze.tasks'
    LOG_TASK_NAME = 'ecommerce_worker.email.v1.braze.tasks'
    USER_EMAIL = 'user@unknown.com'
    EMAILS = 'user@unknown.com, user1@example.com'
    OFFER_ASSIGNMENT_ID = '555'
    SEND_ID = '66cdc28f8f082bc3074c0c79f'
    SUBJECT = 'New edX course assignment'
    EMAIL_BODY = 'Template message with johndoe@unknown.com GIL7RUEOU7VHBH7Q ' \
                 'https://tempurl.url/enroll 3 2012-04-23'
    SENDER_ALIAS = 'edx Support Team'
    REPLY_TO = 'reply@edx.org'
    SITE_CODE = 'test'
    BRAZE_CONFIG = {
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
        'BRAZE_RETRY_SECONDS': 3600,
        'BRAZE_RETRY_ATTEMPTS': 6,
    }

    ASSIGNMENT_TASK_KWARGS = {
        'user_email': USER_EMAIL,
        'offer_assignment_id': OFFER_ASSIGNMENT_ID,
        'subject': SUBJECT,
        'email_body': EMAIL_BODY,
        'sender_alias': SENDER_ALIAS,
        'reply_to': REPLY_TO,
        'site_code': SITE_CODE,
    }

    UPDATE_TASK_KWARGS = {
        'user_email': USER_EMAIL,
        'subject': SUBJECT,
        'email_body': EMAIL_BODY,
        'sender_alias': SENDER_ALIAS,
        'reply_to': REPLY_TO,
        'site_code': SITE_CODE,
    }

    USAGE_TASK_KWARGS = {
        'emails': EMAILS,
        'subject': SUBJECT,
        'email_body': EMAIL_BODY,
        'reply_to': REPLY_TO,
        'site_code': SITE_CODE,
    }

    NUDGE_TASK_KWARGS = {
        'email': USER_EMAIL,
        'subject': SUBJECT,
        'email_body': EMAIL_BODY,
        'sender_alias': SENDER_ALIAS,
        'reply_to': REPLY_TO,
        'site_code': SITE_CODE,
    }

    def execute_task(self):
        """ Execute the send_offer_assignment_email task. """
        with patch('ecommerce_worker.configuration.test.BRAZE', self.BRAZE_CONFIG):
            send_offer_assignment_email(**self.ASSIGNMENT_TASK_KWARGS)

    def mock_braze_user_endpoints(self):
        """ Mock POST requests to the user alias and track endpoints. """
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
            json={"users": [], "message": "success"},
            status=201
        )

    @patch('ecommerce_worker.email.v1.braze.tasks.get_braze_client', Mock(side_effect=BrazeError))
    @ddt.data(
        (send_offer_assignment_email, ASSIGNMENT_TASK_KWARGS, "Offer Assignment", 'assignment'),
        (send_offer_update_email, UPDATE_TASK_KWARGS, "Offer Assignment", 'update'),
        (send_offer_usage_email, USAGE_TASK_KWARGS, "Offer Usage", 'usage'),
        (send_code_assignment_nudge_email, NUDGE_TASK_KWARGS, "Code Assignment Nudge Email", 'nudge'),
    )
    @ddt.unpack
    def test_client_instantiation_error(self, task, task_kwargs, logger_prefix, log_message):
        """ Verify no message is sent if an error occurs while instantiating the Braze API client. """
        with patch('ecommerce_worker.configuration.test.BRAZE', self.BRAZE_CONFIG):
            with LogCapture(level=logging.INFO) as log:
                task(**task_kwargs)
        log.check(
            (
                self.LOG_NAME,
                'ERROR',
                '[{logger_prefix}] Error in offer {log_message} notification with message --- '
                '{message}'.format(
                    logger_prefix=logger_prefix,
                    log_message=log_message,
                    message=self.EMAIL_BODY
                )
            ),
        )

    @patch('ecommerce_worker.email.v1.braze.tasks.logger.exception')
    @ddt.data(
        (send_offer_assignment_email, ASSIGNMENT_TASK_KWARGS, "Offer Assignment", 'assignment'),
        (send_offer_update_email, UPDATE_TASK_KWARGS, "Offer Assignment", 'update'),
        (send_offer_usage_email, USAGE_TASK_KWARGS, "Offer Usage", 'usage'),
        (send_code_assignment_nudge_email, NUDGE_TASK_KWARGS, "Code Assignment Nudge Email", 'nudge'),
    )
    @ddt.unpack
    def test_api_client_error(self, task, task_kwargs, logger_prefix, log_message,  mock_log):
        """ Verify API client errors are logged. """
        with patch('ecommerce_worker.configuration.test.BRAZE', self.BRAZE_CONFIG):
            task(**task_kwargs)
        mock_log.assert_called_once_with(
            '[{logger_prefix}] Error in offer {log_message} notification with message --- '
            '{message}'.format(
                logger_prefix=logger_prefix,
                log_message=log_message,
                message=self.EMAIL_BODY
            )
        )

    @responses.activate
    @ddt.data(
        (send_offer_assignment_email, ASSIGNMENT_TASK_KWARGS),
        (send_offer_update_email, UPDATE_TASK_KWARGS),
        (send_offer_usage_email, USAGE_TASK_KWARGS),
        (send_code_assignment_nudge_email, NUDGE_TASK_KWARGS),
    )
    @ddt.unpack
    def test_api_429_error_with_retry(self, task, task_kwargs):
        """ Verify the task is rescheduled if an API error occurs, and the request can be retried. """
        self.mock_braze_user_endpoints()
        failure_response = {
            'message': 'Not a Success',
            'status_code': 429
        }
        host = 'https://rest.iad-06.braze.com/messages/send'
        responses.add(
            responses.POST,
            host,
            json=failure_response,
            status=429
        )
        with patch('ecommerce_worker.configuration.test.BRAZE', self.BRAZE_CONFIG):
            with self.assertRaises((BrazeRateLimitError, Retry)):
                task(**task_kwargs)

    @responses.activate
    @ddt.data(
        (send_offer_assignment_email, ASSIGNMENT_TASK_KWARGS),
        (send_offer_update_email, UPDATE_TASK_KWARGS),
        (send_offer_usage_email, USAGE_TASK_KWARGS),
        (send_code_assignment_nudge_email, NUDGE_TASK_KWARGS),
    )
    @ddt.unpack
    def test_api_500_error_with_retry(self, task, task_kwargs):
        """ Verify 500 error triggers a request retry. """
        self.mock_braze_user_endpoints()
        failure_response = {
            'message': 'Not a Success',
            'status_code': 500
        }
        host = 'https://rest.iad-06.braze.com/messages/send'
        responses.add(
            responses.POST,
            host,
            json=failure_response,
            status=500
        )
        with patch('ecommerce_worker.configuration.test.BRAZE', self.BRAZE_CONFIG):
            with self.assertRaises((BrazeInternalServerError, Retry)):
                task(**task_kwargs)

    @responses.activate
    @ddt.data(
        (send_offer_update_email, UPDATE_TASK_KWARGS),
        (send_offer_usage_email, USAGE_TASK_KWARGS),
        (send_code_assignment_nudge_email, NUDGE_TASK_KWARGS),
    )
    @ddt.unpack
    def test_api(self, task, task_kwargs):
        """
        Test the happy path.
        """
        self.mock_braze_user_endpoints()
        success_response = {
            "dispatch_id": "66cdc28f8f082bc3074c0c79f",
            "errors": [],
            "message": "success",
            "status_code": 201
        }
        host = 'https://rest.iad-06.braze.com/messages/send'
        responses.add(
            responses.POST,
            host,
            json=success_response,
            status=201)
        with patch('ecommerce_worker.configuration.test.BRAZE', self.BRAZE_CONFIG):
            task(**task_kwargs)
        self.assertTrue('success' in responses.calls[0].response.text)

    @responses.activate
    @patch('ecommerce_worker.email.v1.braze.tasks.update_assignment_email_status')
    def test_message_sent(self, mock_update_assignment):
        """ Verify a message is logged after a successful API call to send the message. """
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
            status=201)
        with LogCapture(level=logging.INFO) as log:
            self.execute_task()
        log.check_present(
            (
                self.LOG_TASK_NAME,
                'INFO',
                '[Offer Assignment] Offer assignment notification sent with message --- '
                '{message}'.format(message=self.EMAIL_BODY)
            ),
        )
        self.assertEqual(mock_update_assignment.call_count, 1)

    @responses.activate
    @patch('ecommerce_worker.email.v1.utils.get_ecommerce_client')
    def test_update_assignment_exception(self, mock_get_ecommerce_client):
        """ Verify a message is logged after an unsuccessful API call to update the status. """
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
            status=201)
        mock_get_ecommerce_client.status.side_effect = RequestException
        with LogCapture(level=logging.INFO) as log:
            self.execute_task()
        log.check_present(
            (
                self.LOG_TASK_NAME,
                'ERROR',
                '[Offer Assignment] An error occurred while updating email status data for offer {token_offer} and '
                'email {token_email} via the ecommerce API.'.format(
                    token_offer=self.OFFER_ASSIGNMENT_ID,
                    token_email=self.USER_EMAIL
                )
            )
        )
