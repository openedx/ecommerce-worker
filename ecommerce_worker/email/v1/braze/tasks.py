"""
This file contains celery task functionality for braze.
"""

from celery.utils.log import get_task_logger

from ecommerce_worker.email.v1.braze.client import get_braze_client, get_braze_configuration
from ecommerce_worker.email.v1.braze.exceptions import BrazeError, BrazeRateLimitError, BrazeInternalServerError
from ecommerce_worker.email.v1.utils import update_assignment_email_status

logger = get_task_logger(__name__)


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
        response = braze_client.send_message(
            email_ids=user_emails,
            subject=subject,
            body=email_body,
            sender_alias=sender_alias,
            reply_to=reply_to,
            attachments=attachments
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
    except (BrazeRateLimitError, BrazeInternalServerError):
        raise self.retry(countdown=config.get('BRAZE_RETRY_SECONDS'),
                         max_retries=config.get('BRAZE_RETRY_ATTEMPTS'))
    except BrazeError:
        logger.exception(
            ('[Offer Assignment] Error in offer assignment notification with message --- '
             '{message}'.format(message=email_body)
             )
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
        braze_client.send_message(
            email_ids=user_emails,
            subject=subject,
            body=email_body,
            sender_alias=sender_alias,
            reply_to=reply_to,
            attachments=attachments
        )
    except (BrazeRateLimitError, BrazeInternalServerError):
        raise self.retry(countdown=config.get('BRAZE_RETRY_SECONDS'),
                         max_retries=config.get('BRAZE_RETRY_ATTEMPTS'))
    except BrazeError:
        logger.exception(
            '[Offer Assignment] Error in offer update notification with message --- '
            '{message}'.format(message=email_body)
        )


def send_offer_usage_email_via_braze(self, emails, subject, email_body, reply_to, attachments, site_code):
    """
    Sends the offer usage email via braze.

    Args:
        self: Ignore.
        emails (str): comma separated emails.
        subject (str): Email subject.
        email_body (str): The body of the email.
        reply_to (str): Enterprise Customer reply to address for email reply.
        attachments (list): File attachment list with dicts having 'file_name' and 'url' keys.
        site_code (str): Identifier of the site sending the email.
    """
    config = get_braze_configuration(site_code)
    try:
        user_emails = list(emails.strip().split(","))
        braze_client = get_braze_client(site_code)
        braze_client.send_message(
            email_ids=user_emails,
            subject=subject,
            body=email_body,
            reply_to=reply_to,
            attachments=attachments
        )
    except (BrazeRateLimitError, BrazeInternalServerError):
        raise self.retry(countdown=config.get('BRAZE_RETRY_SECONDS'),
                         max_retries=config.get('BRAZE_RETRY_ATTEMPTS'))
    except BrazeError:
        logger.exception(
            '[Offer Usage] Error in offer usage notification with message --- '
            '{message}'.format(message=email_body)
        )


def send_code_assignment_nudge_email_via_braze(self, email, subject, email_body, sender_alias, reply_to,
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
        braze_client.send_message(
            email_ids=user_emails,
            subject=subject,
            body=email_body,
            sender_alias=sender_alias,
            reply_to=reply_to,
            attachments=attachments,
        )
    except (BrazeRateLimitError, BrazeInternalServerError):
        raise self.retry(countdown=config.get('BRAZE_RETRY_SECONDS'),
                         max_retries=config.get('BRAZE_RETRY_ATTEMPTS'))
    except BrazeError:
        logger.exception(
            '[Code Assignment Nudge Email] Error in offer nudge notification with message --- '
            '{message}'.format(message=email_body)
        )
