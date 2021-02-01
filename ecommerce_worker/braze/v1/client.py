"""
    Braze Client functions.
"""

from __future__ import absolute_import

import requests

from celery.utils.log import get_task_logger

from ecommerce_worker.braze.v1.exceptions import (
    ConfigurationError,
    BrazeNotEnabled,
    BrazeClientError,
    BrazeRateLimitError,
    BrazeInternalServerError
)
from ecommerce_worker.utils import get_configuration

log = get_task_logger(__name__)


def get_braze_configuration(site_code):
    """
    Returns the Braze configuration for the specified site.

    Arguments:
        site_code (str): Site for fetching the configuration.
    """
    config = get_configuration('BRAZE', site_code=site_code)
    return config


def get_braze_client(site_code):
    """
    Returns a Braze client for the specified site.

    Arguments:
        site_code (str): Site for which the client should be configured.

    Returns:
        BrazeClient

    Raises:
        BrazeNotEnabled: If Braze is not enabled for the specified site.
        ConfigurationError: If either the Braze API key or Webapp key are not set for the site.
    """
    # Get configuration
    config = get_braze_configuration(site_code)

    # Return if Braze integration disabled
    if not config.get('BRAZE_ENABLE'):
        msg = 'Braze is not enabled for site {}'.format(site_code)
        log.debug(msg)
        raise BrazeNotEnabled(msg)

    rest_api_key = config.get('BRAZE_REST_API_KEY')
    webapp_api_key = config.get('BRAZE_WEBAPP_API_KEY')
    rest_api_url = config.get('REST_API_URL')
    messages_send_endpoint = config.get('MESSAGES_SEND_ENDPOINT')
    from_email = config.get('FROM_EMAIL')

    if (
            not rest_api_key or
            not webapp_api_key or
            not rest_api_url or
            not messages_send_endpoint or
            not from_email
    ):
        msg = 'Required parameters missing for site {}'.format(site_code)
        log.error(msg)
        raise ConfigurationError(msg)

    return BrazeClient(rest_api_key, webapp_api_key, rest_api_url + messages_send_endpoint, from_email)


class BrazeClient(object):
    """
    Client for Braze REST API
    """

    def __init__(self, rest_api_key, webapp_api_key, request_url, from_email):
        """
        Initialize the Braze Client with configuration values.

        Arguments:
            rest_api_key (str): API key to use for accessing Braze REST endpoints
            webapp_api_key (str): Key that identifies the Braze webapp application
            request_url (str): Braze endpoint url
            from_email (str): Braze email from address
        """
        self.rest_api_key = rest_api_key
        self.webapp_api_key = webapp_api_key
        self.from_email = from_email
        self.session = requests.Session()
        self.request_url = request_url

    def __create_request(self, body):
        """
        Creates a request and returns a response.

        Arguments:
            body (dict): The request body

        Returns:
            response (dict): The response object
        """
        response = {'errors': []}
        r = self._post_request(body)
        response.update(r.json())
        response['status_code'] = r.status_code

        message = response["message"]
        response['success'] = (
            message in ('success', 'queued') and not response['errors']
        )
        if message not in ('success', 'queued'):
            raise BrazeClientError(message, response['errors'])
        return response

    def _post_request(self, body):
        """
        Http posts the message body with associated headers.

        Arguments:
            body (dict): The request body

        Returns:
            r (requests.Response): The http response object
        """
        self.session.headers.update(
            {'Authorization': u'Bearer {}'.format(self.rest_api_key), 'Content-Type': 'application/json'}
        )
        r = self.session.post(self.request_url, json=body, timeout=2)
        if r.status_code == 429:
            reset_epoch_s = float(r.headers.get('X-RateLimit-Reset', 0))
            raise BrazeRateLimitError(reset_epoch_s)
        elif str(r.status_code).startswith('5'):
            raise BrazeInternalServerError
        return r

    def send_message(
        self,
        email_ids,
        subject,
        body,
        sender_alias='EdX Support Team'
    ):
        """
        Sends the message via Braze Rest API /messages/send

        Arguments:
            email_ids (list): e.g. ['test1@example.com', 'test2@example.com']
            subject (str): e.g. 'Test Subject'
            body (str): e.g. '<html>Test Html Message</html>'
            sender_alias (str): sender alias for email e.g. edX Support Team

        Request message format:
            Content-Type: application/json
            Authorization: Bearer {{api_key}}
            Body:
                {
                    "external_user_ids": [ "user1@example.com", "user2@example.org" ],
                    "messages": {
                        "email": {
                            "app_id": "99999999-9999-9999-9999-999999999999",
                            "subject": "Testing",
                            "from": "edX <edx-for-business-no-reply@info.edx.org>",
                            "body": "<html>Test</html>"
                        }
                    }
                }

        Returns:
            response (dict): e.g:
                {
                    "dispatch_id": "9179894df02dab49c1d1f85c6a01c41b",
                    "message": "success"
                }
        """
        if not email_ids or not subject or not body:
            raise BrazeClientError("Missing parameters for Braze email")
        email = {
            'app_id': self.webapp_api_key,
            'subject': subject,
            'from': sender_alias + self.from_email,
            'body': body
        }
        message = {
            'external_user_ids': email_ids,
            'messages': {
                'email': email
            }
        }

        return self.__create_request(message)
