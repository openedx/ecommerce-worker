"""
Notification class for sending the notification emails.
"""
from __future__ import absolute_import
from celery.utils.log import get_task_logger

from sailthru.sailthru_error import SailthruClientError
from ecommerce_worker.sailthru.v1.exceptions import SailthruError
from ecommerce_worker.sailthru.v1.utils import can_retry_sailthru_request, get_sailthru_client

log = get_task_logger(__name__)


class Notification:
    """
    This class exports the 'send' function for sending the emails.
    """

    def __init__(self, config, emails, email_vars, logger_prefix, site_code, template):
        self.config = config
        self.emails = emails
        self.email_vars = email_vars
        self.logger_prefix = logger_prefix
        self.site_code = site_code
        self.template = template

    def _is_eligible_for_retry(self, response):
        """
        Return a bool whether this task is eligible for retry or not.
        Also log the appropriate message according to occurred error.
        """
        is_eligible_for_retry = False
        error = response.get_error()
        log.error(
            '[{logger_prefix}] An error occurred while attempting to send a notification. Message: {message},'
            ' Error code: {token_error_code}, Error Message: {token_error_message}.'.format(
                logger_prefix=self.logger_prefix,
                message=self.email_vars.get('email_body'),
                token_error_code=error.get_error_code(),
                token_error_message=error.get_message()
            )
        )
        if can_retry_sailthru_request(error):
            log.info(
                '[{logger_prefix}] An attempt will be made to resend the notification.'
                ' Message: {message}'.format(
                    logger_prefix=self.logger_prefix,
                    message=self.email_vars.get('email_body')
                )
            )
            is_eligible_for_retry = True
        else:
            log.warning(
                '[{logger_prefix}] No further attempts will be made to send the notification.'
                ' Failed Message: {message}'.format(
                    logger_prefix=self.logger_prefix,
                    message=self.email_vars.get('email_body')
                )
            )
        return is_eligible_for_retry

    @staticmethod
    def _get_send_callback(is_multi_send):
        """
        Return the associated function 'send' in case of single send and 'multi_send' in case of multi_send
        """
        return 'multi_send' if is_multi_send else 'send'

    def _get_client(self):
        """
        Return the sailthru client or None if exception raised.
        """
        sailthru_client = None
        try:
            sailthru_client = get_sailthru_client(self.site_code)
        except SailthruError:
            log.exception(
                '[{logger_prefix}] A client error occurred while attempting to send a notification.'
                ' Message: {message}'.format(
                    logger_prefix=self.logger_prefix,
                    message=self.email_vars.get('email_body')
                )
            )
        return sailthru_client

    def _get_params(self, is_multi_send):
        """
        Return the dict of parameters according to the given 'is_multi_send' parameter.

        It can be a simple 'send' function in which we will send an email
        to a single email address or it can be a 'multi_send' function.
        """
        params = {
            'template': self.config['templates'][self.template],
            '_vars': self.email_vars
        }
        email_param = 'emails' if is_multi_send else 'email'
        params[email_param] = self.emails
        return params

    def send(self, is_multi_send=False):
        """
        Send the notification email to single email address or comma
        separated emails on bases of is_multi_send parameter

        Returns:
            response: Sailthru endpoint response.
            is_eligible_for_retry(Bool): whether this response is eligible for retry or not.
        """
        is_eligible_for_retry = False
        sailthru_client = self._get_client()
        if sailthru_client is None:
            return None, is_eligible_for_retry

        try:
            response = getattr(
                sailthru_client,
                self._get_send_callback(is_multi_send)
            )(**self._get_params(is_multi_send))
        except SailthruClientError:
            log.exception(
                '[{logger_prefix}] A client error occurred while attempting to send a notification.'
                ' Message: {message}'.format(
                    logger_prefix=self.logger_prefix,
                    message=self.email_vars.get('email_body')
                )
            )
            return None, is_eligible_for_retry

        if response.is_ok():
            log.info(
                '[{logger_prefix}] A notification has been sent successfully. Message: {message}'.format(
                    logger_prefix=self.logger_prefix,
                    message=self.email_vars.get('email_body')
                )
            )
        else:
            is_eligible_for_retry = self._is_eligible_for_retry(response)
        return response, is_eligible_for_retry
