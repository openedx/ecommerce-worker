"""Tests of Braze task code."""

import logging
from unittest import TestCase
from unittest.mock import patch, MagicMock, Mock

import braze.exceptions as edx_braze_exceptions
import ddt
import responses
from celery.exceptions import Retry
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


LOG_NAME = 'ecommerce_worker.email.v1.braze.tasks'
LOG_TASK_NAME = 'ecommerce_worker.email.v1.braze.tasks'
USER_EMAIL = 'user@unknown.com'
EMAILS = 'user@unknown.com, user1@example.com'
LMS_USER_IDS_BY_EMAIL = {
    'user@unknown.com': None,
    'user1@example.com': 456,
}
OFFER_ASSIGNMENT_ID = '555'
SEND_ID = '66cdc28f8f082bc3074c0c79f'
SUBJECT = 'New edX course assignment'
EMAIL_BODY = 'Template message with johndoe@unknown.com GIL7RUEOU7VHBH7Q ' \
             'https://tempurl.url/enroll 3 2012-04-23'
USAGE_EMAIL_BODY_VARIABLES = {
    'FOO': 123,
    'BAR': 555,
}
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
    'ENTERPRISE_CODE_ASSIGNMENT_CAMPAIGN_ID': 'the-code-assignment-campaign-id',
    'ENTERPRISE_CODE_UPDATE_CAMPAIGN_ID': 'the-code-update-campaign-id',
    'ENTERPRISE_CODE_USAGE_CAMPAIGN_ID': 'the-code-usage-campaign-id',
    'ENTERPRISE_CODE_NUDGE_CAMPAIGN_ID': '',  # cover case where a `campaign_id` kwarg is falsey.
    'FROM_EMAIL': '<edx-for-business-no-reply@info.edx.org>',
    'BRAZE_RETRY_SECONDS': 3600,
    'BRAZE_RETRY_ATTEMPTS': 6,
}


@ddt.ddt
class SendEmailsViaBrazeTests(TestCase):
    """ Validates the email sending tasks with Braze api. """
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
        with patch('ecommerce_worker.configuration.test.BRAZE', BRAZE_CONFIG):
            send_offer_assignment_email(**self.ASSIGNMENT_TASK_KWARGS)

    def mock_braze_user_endpoints(self):
        """ Mock POST requests to the user alias and track endpoints. """
        responses.add(
            responses.POST,
            'https://rest.iad-06.braze.com/users/track',
            json={'message': 'success'},
            status=201
        )
        responses.add(
            responses.POST,
            'https://rest.iad-06.braze.com/users/alias/new',
            json={'message': 'success'},
            status=201
        )
        responses.add(
            responses.POST,
            'https://rest.iad-06.braze.com/users/export/ids',
            json={"users": [], "message": "success"},
            status=201
        )

    @patch('ecommerce_worker.email.v1.braze.tasks.get_braze_client', Mock(side_effect=BrazeError))
    @ddt.data(
        (send_offer_assignment_email, ASSIGNMENT_TASK_KWARGS, "Offer Assignment", 'assignment'),
        (send_offer_update_email, UPDATE_TASK_KWARGS, "Offer Assignment", 'update'),
        (send_code_assignment_nudge_email, NUDGE_TASK_KWARGS, "Code Assignment Nudge Email", 'nudge'),
    )
    @ddt.unpack
    def test_client_instantiation_error(self, task, task_kwargs, logger_prefix, log_message):
        """ Verify no message is sent if an error occurs while instantiating the Braze API client. """
        with patch('ecommerce_worker.configuration.test.BRAZE', BRAZE_CONFIG):
            with LogCapture(level=logging.INFO) as log:
                task(**task_kwargs)
        log.check(
            (
                LOG_NAME,
                'ERROR',
                '[{logger_prefix}] Error in offer {log_message} notification with message --- '
                '{message}'.format(
                    logger_prefix=logger_prefix,
                    log_message=log_message,
                    message=EMAIL_BODY
                )
            ),
        )

    @patch('ecommerce_worker.email.v1.braze.tasks.logger.exception')
    @ddt.data(
        (send_offer_assignment_email, ASSIGNMENT_TASK_KWARGS, "Offer Assignment", 'assignment'),
        (send_offer_update_email, UPDATE_TASK_KWARGS, "Offer Assignment", 'update'),
        (send_code_assignment_nudge_email, NUDGE_TASK_KWARGS, "Code Assignment Nudge Email", 'nudge'),
    )
    @ddt.unpack
    def test_api_client_error(self, task, task_kwargs, logger_prefix, log_message, mock_log):
        """ Verify API client errors are logged. """
        with patch('ecommerce_worker.configuration.test.BRAZE', BRAZE_CONFIG):
            task(**task_kwargs)
        mock_log.assert_called_once_with(
            '[{logger_prefix}] Error in offer {log_message} notification with message --- '
            '{message}'.format(
                logger_prefix=logger_prefix,
                log_message=log_message,
                message=EMAIL_BODY
            )
        )

    @responses.activate
    @ddt.data(
        (send_offer_assignment_email, ASSIGNMENT_TASK_KWARGS),
        (send_offer_update_email, UPDATE_TASK_KWARGS),
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
        with patch('ecommerce_worker.configuration.test.BRAZE', BRAZE_CONFIG):
            with self.assertRaises((BrazeRateLimitError, Retry)):
                task(**task_kwargs)

    @responses.activate
    @ddt.data(
        (send_offer_assignment_email, ASSIGNMENT_TASK_KWARGS),
        (send_offer_update_email, UPDATE_TASK_KWARGS),
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
        with patch('ecommerce_worker.configuration.test.BRAZE', BRAZE_CONFIG):
            with self.assertRaises((BrazeInternalServerError, Retry)):
                task(**task_kwargs)

    @responses.activate
    @ddt.data(
        (send_offer_update_email, UPDATE_TASK_KWARGS),
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
        with patch('ecommerce_worker.configuration.test.BRAZE', BRAZE_CONFIG):
            task(**task_kwargs)
        self.assertIn('success', responses.calls[0].response.text)

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
                LOG_TASK_NAME,
                'INFO',
                '[Offer Assignment] Offer assignment notification sent with message --- '
                '{message}'.format(message=EMAIL_BODY)
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
                LOG_TASK_NAME,
                'ERROR',
                '[Offer Assignment] An error occurred while updating email status data for offer {token_offer} and '
                'email {token_email} via the ecommerce API.'.format(
                    token_offer=OFFER_ASSIGNMENT_ID,
                    token_email=USER_EMAIL
                )
            )
        )

    def test_braze_not_enabled(self):
        """
        Test that tasks do nothing when Braze is not enabled.
        """
        # pylint: disable=unnecessary-comprehension
        disabled_config = {key: value for key, value in BRAZE_CONFIG.items()}
        disabled_config['BRAZE_ENABLE'] = False
        for task, braze_task_name, kwargs in (
            (send_code_assignment_nudge_email, 'send_code_assignment_nudge_email_via_braze', self.NUDGE_TASK_KWARGS),
            (send_offer_assignment_email, 'send_offer_assignment_email_via_braze', self.ASSIGNMENT_TASK_KWARGS),
            (send_offer_update_email, 'send_offer_update_email_via_braze', self.UPDATE_TASK_KWARGS),
        ):
            task_path = 'ecommerce_worker.email.v1.tasks.{}'.format(braze_task_name)
            with patch(task_path) as mock_braze_task:
                task(**kwargs)
                self.assertFalse(mock_braze_task.called)


@ddt.ddt
class OfferUsageEmailTests(TestCase):
    """
    Separate test class for the offer usage email task, since it utilizes
    edx-braze-client.
    """
    USAGE_TASK_KWARGS = {
        'lms_user_ids_by_email': LMS_USER_IDS_BY_EMAIL,
        'subject': SUBJECT,
        'email_body_variables': USAGE_EMAIL_BODY_VARIABLES,
        'site_code': SITE_CODE,
    }

    def test_braze_not_enabled(self):
        """
        Test that this task does nothing when Braze is not enabled.
        """
        # pylint: disable=unnecessary-comprehension
        disabled_config = {key: value for key, value in BRAZE_CONFIG.items()}
        disabled_config['BRAZE_ENABLE'] = False
        task_path = 'ecommerce_worker.email.v1.tasks.send_offer_usage_email_via_braze'
        with patch(task_path) as mock_braze_task:
            send_offer_usage_email(**self.USAGE_TASK_KWARGS)
            self.assertFalse(mock_braze_task.called)

    @patch('ecommerce_worker.email.v1.braze.tasks.EdxBrazeClient', return_value=MagicMock())
    @ddt.data(
        edx_braze_exceptions.BrazeRateLimitError,
        edx_braze_exceptions.BrazeInternalServerError,
    )
    def test_api_error_with_retry(self, exception, mock_client):
        """ Verify the task is rescheduled if an expected API error occurs, and the request can be retried. """
        mock_client.return_value.send_campaign_message.side_effect = exception('msg')
        with patch('ecommerce_worker.configuration.test.BRAZE', BRAZE_CONFIG):
            with self.assertRaises((exception, Retry)):
                send_offer_usage_email(**self.USAGE_TASK_KWARGS)

    @patch('ecommerce_worker.email.v1.braze.tasks.EdxBrazeClient', return_value=MagicMock())
    def test_api_generic_braze_error(self, mock_client):
        """ Verify the task raises a BrazeError for other types of exceptions. """
        mock_client.return_value.send_campaign_message.side_effect = edx_braze_exceptions.BrazeError('msg')
        with patch('ecommerce_worker.configuration.test.BRAZE', BRAZE_CONFIG):
            with self.assertRaises(edx_braze_exceptions.BrazeError):
                send_offer_usage_email(**self.USAGE_TASK_KWARGS)

    @patch('ecommerce_worker.email.v1.braze.tasks.EdxBrazeClient', return_value=MagicMock(), autospec=True)
    @ddt.data(
        None,
        'custom-campaign-id',
    )
    def test_successful_usage_email(self, campaign_id, mock_client):
        """ Verify the task successfully calls send_campaign_message() and create_recipient(). """
        mock_client.reset_mock()

        def mock_create_recipient(user_email, lms_user_id):
            return {'user_email': user_email, 'lms_user_id': lms_user_id}

        client = mock_client.return_value
        client.create_recipient.side_effect = mock_create_recipient

        with patch('ecommerce_worker.configuration.test.BRAZE', BRAZE_CONFIG):
            send_offer_usage_email(campaign_id=campaign_id, **self.USAGE_TASK_KWARGS)

        client.create_recipient.assert_called_once_with(
            'user1@example.com', 456,
        )

        expected_trigger_properties = {
            'subject': 'New edX course assignment',
            **USAGE_EMAIL_BODY_VARIABLES,
        }
        expected_campaign_id = campaign_id or BRAZE_CONFIG['ENTERPRISE_CODE_USAGE_CAMPAIGN_ID']
        client.send_campaign_message.assert_called_once_with(
            campaign_id=expected_campaign_id,
            recipients=[
                {'user_email': 'user1@example.com', 'lms_user_id': 456}
            ],
            emails=['user@unknown.com'],
            trigger_properties=expected_trigger_properties,
        )
