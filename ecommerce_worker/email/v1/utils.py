""" Utility functions. """
import string
from json import JSONDecodeError
from urllib.parse import urljoin

import requests
from requests.exceptions import HTTPError

from ecommerce_worker.email.v1.braze.client import is_braze_enabled, get_braze_client
from ecommerce_worker.utils import get_access_token, get_configuration


def update_assignment_email_status(offer_assignment_id, send_id, status, site_code=None):
    """
    Update the offer_assignment and offer_assignment_email model using the Ecommerce assignment-email api.
    Arguments:
        offer_assignment_id (str): Key of the entry in the offer_assignment model.
        send_id (str): Unique message id from Sailthru
        status (str): status to be sent to the api
        site_code (str): site code
    Returns:
        True or False based on model update status from Ecommerce api
    """

    api_url = urljoin(get_configuration('ECOMMERCE_API_ROOT', site_code=site_code) + '/', 'assignment-email/status/')
    try:
        headers = {'Authorization': f'JWT {get_access_token()}'}
        post_data = {
            'offer_assignment_id': offer_assignment_id,
            'send_id': send_id,
            'status': status,
        }
        response = requests.post(
            api_url,
            data=post_data,
            headers=headers
        )
        response.raise_for_status()
        data = response.json()
    except (HTTPError, JSONDecodeError):
        return False

    return bool(data.get('status') == 'updated')


def did_email_bounce(user_email, site_code=None) -> bool:
    """
    Checks if the given user's emails have bounced.

    Args:
        user_email (str): Recipient's email address.
        site_code (str): Identifier of the site sending the email.
    """
    if is_braze_enabled():  # pylint: disable=no-value-for-parameter
        client = get_braze_client(site_code)
        return client.did_email_bounce(user_email)

    return False


def remove_special_characters_from_string(input_string):
    """
    Removes all special characters from the string passed as argument.
    string.punctuation contains the following characters:  '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'

    Args:
        input_string (str): Input string from which special characters need to be removed.
    """
    if input_string:
        return input_string.translate(str.maketrans('', '', string.punctuation))
    return ''
