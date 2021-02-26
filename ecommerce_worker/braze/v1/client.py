"""
    Braze Client functions.
"""

from __future__ import absolute_import

import requests

from urllib.parse import urlencode, urljoin

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
    email_bounce_endpoint = config.get('EMAIL_BOUNCE_ENDPOINT')
    new_alias_endpoint = config.get('NEW_ALIAS_ENDPOINT')
    users_track_endpoint = config.get('USERS_TRACK_ENDPOINT')
    from_email = config.get('FROM_EMAIL')
    email_template_id = config.get('EMAIL_TEMPLATE_ID')

    if (
            not rest_api_key or
            not webapp_api_key
    ):
        msg = 'Required keys missing for site {}'.format(site_code)
        log.error(msg)
        raise ConfigurationError(msg)

    return BrazeClient(
        rest_api_key=rest_api_key,
        webapp_api_key=webapp_api_key,
        rest_api_url=rest_api_url,
        messages_send_endpoint=messages_send_endpoint,
        email_bounce_endpoint=email_bounce_endpoint,
        new_alias_endpoint=new_alias_endpoint,
        users_track_endpoint=users_track_endpoint,
        from_email=from_email,
        email_template_id=email_template_id
    )


class BrazeClient(object):
    """
    Client for Braze REST API
    """

    def __init__(
            self,
            rest_api_key,
            webapp_api_key,
            rest_api_url,
            messages_send_endpoint,
            email_bounce_endpoint,
            new_alias_endpoint,
            users_track_endpoint,
            from_email,
            email_template_id
    ):
        """
        Initialize the Braze Client with configuration values.

        Arguments:
            rest_api_key (str): API key to use for accessing Braze REST endpoints
            webapp_api_key (str): Key that identifies the Braze webapp application
            rest_api_url    (str): REST API url,
            messages_send_endpoint  (str): Messages send endpoint,
            email_bounce_endpoint   (str): Email bounce endpoint,
            new_alias_endpoint  (str): New alias endpoint,
            users_track_endpoint    (str): Users track endpoint,
            from_email (str): Braze email from address
            email_template_id (str): Braze email template identifier
        """
        self.rest_api_key = rest_api_key
        self.webapp_api_key = webapp_api_key
        self.rest_api_url = rest_api_url
        self.messages_send_endpoint = messages_send_endpoint
        self.email_bounce_endpoint = email_bounce_endpoint
        self.new_alias_endpoint = new_alias_endpoint
        self.users_track_endpoint = users_track_endpoint
        self.from_email = from_email
        self.email_template_id = email_template_id
        self.session = requests.Session()

    def __create_post_request(self, body, endpoint):
        """
        Creates a request and returns a response.

        Arguments:
            body (dict): The request body
            endpoint (str): The endpoint for the API e.g. /messages/send or /email/hard_bounces

        Returns:
            response (dict): The response object
        """
        response = {'errors': []}
        r = self._post_request(body, endpoint)
        response.update(r.json())
        response['status_code'] = r.status_code

        message = response["message"]
        response['success'] = (
            message in ('success', 'queued') and not response['errors']
        )
        if message not in ('success', 'queued'):
            raise BrazeClientError(message, response['errors'])
        return response

    def _post_request(self, body, endpoint):
        """
        Http posts the message body with associated headers.

        Arguments:
            body (dict): The request body
            endpoint (str): The endpoint for the API e.g. /messages/send or /email/hard_bounces

        Returns:
            r (requests.Response): The http response object
        """
        self.session.headers.update(
            {'Authorization': u'Bearer {}'.format(self.rest_api_key), 'Content-Type': 'application/json'}
        )
        r = self.session.post(urljoin(self.rest_api_url, endpoint), json=body, timeout=2)
        if r.status_code == 429:
            reset_epoch_s = float(r.headers.get('X-RateLimit-Reset', 0))
            raise BrazeRateLimitError(reset_epoch_s)
        elif str(r.status_code).startswith('5'):
            raise BrazeInternalServerError
        return r

    def __create_get_request(self, parameters, endpoint):
        """
        Creates a request and returns a response.

        Arguments:
            parameters (dict): The request parameters
            endpoint (str): The endpoint for the API e.g. /messages/send or /email/hard_bounces

        Returns:
            response (dict): The response object
        """
        response = {'errors': []}
        r = self._get_request(parameters, endpoint)
        response.update(r.json())
        response['status_code'] = r.status_code
        message = response["message"]
        response['success'] = (
            message in ('success', 'queued') and not response['errors']
        )
        if message not in ('success', 'queued'):
            raise BrazeClientError(message, response['errors'])
        return response

    def _get_request(self, parameters, endpoint):
        """
        Http GET the parameters with associated headers.

        Arguments:
            parameters (dict): The request parameters
            endpoint (str): The endpoint for the API e.g. /messages/send or /email/hard_bounces

        Returns:
            r (requests.Response): The http response object
        """
        self.session.headers.update(
            {'Authorization': u'Bearer {}'.format(self.rest_api_key), 'Content-Type': 'application/json'}
        )
        url_with_parameters = urljoin(self.rest_api_url, endpoint) + '?' + urlencode(parameters)
        r = self.session.get(url_with_parameters)
        if r.status_code == 429:
            reset_epoch_s = float(r.headers.get('X-RateLimit-Reset', 0))
            raise BrazeRateLimitError(reset_epoch_s)
        elif str(r.status_code).startswith('5'):
            raise BrazeInternalServerError
        return r

    def create_braze_alias(self, recipient_emails):
        """
        Creates a Braze anonymous user and assigns it the recipient email address.

        Alias naming format:
        {
            "attributes": [
                {
                    "user_alias" : {
                        "alias_name" : "Enterprise",
                        "alias_label" : "someuser@someorg.org"
                    },
                    "email" : "someuser@someorg.org"
                }
            ]
        }

        Arguments:
            recipient_emails (list): e.g. ['test1@example.com', 'test2@example.com']

        """
        if not recipient_emails:
            raise BrazeClientError("Missing parameters for Alias creation")
        user_aliases = []
        attributes = []
        for recipient_email in recipient_emails:
            user_alias = {
                'alias_name': 'Enterprise',
                'alias_label': recipient_email
            }
            user_aliases.append(user_alias)
            attribute = {
                'user_alias': {
                    'alias_name': 'Enterprise',
                    'alias_label': recipient_email
                },
                'email': recipient_email
            }
            attributes.append(attribute)

        alias_message = {
            'user_aliases': user_aliases,
        }
        self.__create_post_request(alias_message, self.new_alias_endpoint)

        attribute_message = {
            'attributes': attributes
        }
        self.__create_post_request(attribute_message, self.users_track_endpoint)

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
        self.create_braze_alias(email_ids)
        user_aliases = []
        for email_id in email_ids:
            user_alias = {
                'alias_name': 'Enterprise',
                'alias_label': email_id
            }
            user_aliases.append(user_alias)
        email = {
            'app_id': self.webapp_api_key,
            'subject': subject,
            'from': sender_alias + self.from_email,
            'body': body,
            'email_template_id': self.email_template_id
        }
        message = {
            'user_aliases': user_aliases,
            'messages': {
                'email': email
            }
        }

        return self.__create_post_request(message, self.messages_send_endpoint)

    def did_email_bounce(
        self,
        email_id
    ):
        """
        Sends the message via Braze Rest API /email/hard_bounces

        Arguments:
            email_id (str): e.g. 'test1@example.com'

        Returns:
             True (boolean): True if email bounced,
        """
        if not email_id:
            raise BrazeClientError("Missing parameters for Braze email")
        parameters = {
            'email': email_id
        }

        response = self.__create_get_request(parameters, self.email_bounce_endpoint)
        if response['emails']:
            return True

        return False
