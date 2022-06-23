"""
This file contains celery task functionality for braze.
"""
from operator import itemgetter

import braze.exceptions as edx_braze_exceptions
from celery.utils.log import get_task_logger

from ecommerce_worker.email.v1.braze.client import (
    get_braze_client,
    get_braze_configuration,
    EdxBrazeClient,
)
from ecommerce_worker.email.v1.braze.exceptions import BrazeError, BrazeRateLimitError, BrazeInternalServerError
from ecommerce_worker.email.v1.utils import update_assignment_email_status

logger = get_task_logger(__name__)

# Use a smaller countdown for the offer usage task,
# since the mgmt command that executes it blocks until the task is done/failed.
OFFER_USAGE_RETRY_DELAY_SECONDS = 10


def send_offer_assignment_email_via_braze(self, user_email, offer_assignment_id, subject, email_body, sender_alias,
                                          reply_to, attachments, site_code):
    """
    Sends the offer assignment email via Braze.

    Args:
        self: Ignore.
        user_email (str): Recipient's email address.
        offer_assignment_id (str): Key of the entry in the offer_assignment model.
        subject (str): Email subject.
        email_body (str): The body of the email.
        sender_alias (str): Enterprise Customer sender alias used as From Name.
        reply_to (str): Enterprise Customer reply to address for email reply.
        attachments (list): File attachment list with dicts having 'file_name' and 'url' keys.
        site_code (str): Identifier of the site sending the email.
    """
    config = get_braze_configuration(site_code)
    try:
        user_emails = [user_email]
        braze_client = get_braze_client(site_code)
        response = _send_braze_message(
            braze_client,
            email_ids=user_emails,
            subject=subject,
            body=email_body,
            sender_alias=sender_alias,
            reply_to=reply_to,
            attachments=attachments,
            campaign_id=config.get('ENTERPRISE_CODE_ASSIGNMENT_CAMPAIGN_ID'),
            message_variation_id=config.get('ENTERPRISE_CODE_ASSIGNMENT_MESSAGE_VARIATION_ID'),
        )
        if response and response['success']:
            dispatch_id = response['dispatch_id']
            if update_assignment_email_status(offer_assignment_id, dispatch_id, 'success'):
                logger.info('[Offer Assignment] Offer assignment notification sent with message --- '
                            '{message}'.format(message=email_body))
            else:
                logger.exception(
                    '[Offer Assignment] An error occurred while updating email status data for '
                    'offer {token_offer} and email {token_email} via the ecommerce API.'.format(
                        token_offer=offer_assignment_id,
                        token_email=user_email,
                    )
                )
    except (BrazeRateLimitError, BrazeInternalServerError) as exc:
        raise self.retry(countdown=config.get('BRAZE_RETRY_SECONDS'),
                         max_retries=config.get('BRAZE_RETRY_ATTEMPTS')) from exc
    except BrazeError:
        logger.exception(
            '[Offer Assignment] Error in offer assignment notification with message --- '
            '{message}'.format(message=email_body)
        )


def send_offer_update_email_via_braze(self, user_email, subject, email_body, sender_alias, reply_to, attachments,
                                      site_code):
    """
    Sends the offer emails after assignment via braze, either for revoking or reminding.

    Args:
        self: Ignore.
        user_email (str): Recipient's email address.
        subject (str): Email subject.
        email_body (str): The body of the email.
        site_code (str): Identifier of the site sending the email.
        sender_alias (str): Enterprise Customer sender alias used as From Name.
        reply_to (str): Enterprise Customer reply to address for email reply.
        attachments (list): File attachment list with dicts having 'file_name' and 'url' keys.
    """
    config = get_braze_configuration(site_code)
    try:
        user_emails = [user_email]
        braze_client = get_braze_client(site_code)
        _send_braze_message(
            braze_client,
            email_ids=user_emails,
            subject=subject,
            body=email_body,
            sender_alias=sender_alias,
            reply_to=reply_to,
            attachments=attachments,
            campaign_id=config.get('ENTERPRISE_CODE_UPDATE_CAMPAIGN_ID'),
            message_variation_id=config.get('ENTERPRISE_CODE_UPDATE_MESSAGE_VARIATION_ID'),
        )
    except (BrazeRateLimitError, BrazeInternalServerError) as exc:
        raise self.retry(countdown=config.get('BRAZE_RETRY_SECONDS'),
                         max_retries=config.get('BRAZE_RETRY_ATTEMPTS')) from exc
    except BrazeError:
        logger.exception(
            '[Offer Assignment] Error in offer update notification with message --- '
            '{message}'.format(message=email_body)
        )


def send_offer_usage_email_via_braze(
    self, lms_user_ids_by_email, subject, email_body_variables, site_code, campaign_id=None
):
    """
    Sends the offer usage email via braze.

    Args:
        self: Ignore.
        lms_user_ids_by_email (dict): Map of recipient email addresses to LMS user ids.
        subject (str): Email subject.
        email_body_variables (dict): key-value pairs that are injected into Braze email template for personalization.
        site_code (str): Identifier of the site sending the email.
        campaign_id (str): Identifier of Braze API-triggered campaign to send message through; defaults
            to config.ENTERPRISE_CODE_USAGE_CAMPAIGN_ID
    """
    config = get_braze_configuration(site_code)
    try:
        braze_client = EdxBrazeClient(site_code)

        message_kwargs = {
            'campaign_id': campaign_id or config.get('ENTERPRISE_CODE_USAGE_CAMPAIGN_ID'),
            'recipients': [],
            'emails': [],
            'trigger_properties': {
                'subject': subject,
                **email_body_variables,
            },
        }

        for user_email, lms_user_id in sorted(lms_user_ids_by_email.items(), key=itemgetter(0)):
            if lms_user_id:
                recipient = braze_client.create_recipient(user_email, lms_user_id)
                message_kwargs['recipients'].append(recipient)
            else:
                message_kwargs['emails'].append(user_email)

        braze_client.send_campaign_message(**message_kwargs)
    except (edx_braze_exceptions.BrazeRateLimitError, edx_braze_exceptions.BrazeInternalServerError) as exc:
        raise self.retry(
            countdown=OFFER_USAGE_RETRY_DELAY_SECONDS,
            max_retries=config.get('BRAZE_RETRY_ATTEMPTS')
        ) from exc
    except edx_braze_exceptions.BrazeError:
        logger.exception(
            '[Offer Usage] Error in offer usage notification with message --- '
            '{message}'.format(message=email_body_variables)
        )
        raise


def send_code_assignment_nudge_email_via_braze(self, email, subject, email_body, sender_alias, reply_to,  # pylint: disable=invalid-name
                                               attachments, site_code):
    """
    Sends the code assignment nudge email via braze.

    Args:
        self: Ignore.
        email (str): Recipient's email address.
        subject (str): Email subject.
        email_body (str): The body of the email.
        sender_alias (str): Enterprise Customer sender alias used as From Name.
        reply_to (str): Enterprise Customer reply to address for email reply.
        attachments (list): File attachment list with dicts having 'file_name' and 'url' keys.
        site_code (str): Identifier of the site sending the email.
    """
    config = get_braze_configuration(site_code)
    try:
        user_emails = [email]
        braze_client = get_braze_client(site_code)
        _send_braze_message(
            braze_client,
            email_ids=user_emails,
            subject=subject,
            body=email_body,
            sender_alias=sender_alias,
            reply_to=reply_to,
            attachments=attachments,
            campaign_id=config.get('ENTERPRISE_CODE_NUDGE_CAMPAIGN_ID'),
            message_variation_id=config.get('ENTERPRISE_CODE_NUDGE_MESSAGE_VARIATION_ID'),
        )
    except (BrazeRateLimitError, BrazeInternalServerError) as exc:
        raise self.retry(countdown=config.get('BRAZE_RETRY_SECONDS'),
                         max_retries=config.get('BRAZE_RETRY_ATTEMPTS')) from exc
    except BrazeError:
        logger.exception(
            '[Code Assignment Nudge Email] Error in offer nudge notification with message --- '
            '{message}'.format(message=email_body)
        )


def _send_braze_message(braze_client, **kwargs):
    """
    Helper to send braze messages.  Pops any falsey `campaign_id`
    argument before sending.
    """
    if 'campaign_id' in kwargs and not kwargs['campaign_id']:
        kwargs.pop('campaign_id')
    return braze_client.send_message(**kwargs)
