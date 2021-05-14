""" Utility functions. """

from requests.exceptions import RequestException

from ecommerce_worker.email.v1.braze.client import is_braze_enabled, get_braze_client
from ecommerce_worker.utils import get_ecommerce_client


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
    api = get_ecommerce_client(url_postfix='assignment-email/', site_code=site_code)
    post_data = {
        'offer_assignment_id': offer_assignment_id,
        'send_id': send_id,
        'status': status,
    }
    try:
        api_response = api.status().post(post_data)
    except RequestException:
        return False
    return bool(api_response.get('status') == 'updated')


def did_email_bounce(user_email, site_code=None) -> bool:
    """
    Checks if the given user's emails have bounced.

    Args:
        user_email (str): Recipient's email address.
        site_code (str): Identifier of the site sending the email.
    """
    if is_braze_enabled():
        client = get_braze_client(site_code)
        return client.did_email_bounce(user_email)

    return False
