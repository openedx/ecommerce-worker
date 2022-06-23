"""
This file contains celery tasks for email marketing signal handler.
"""
import logging

from celery import shared_task

from ecommerce_worker.email.v1.braze.client import is_braze_enabled
from ecommerce_worker.email.v1.braze.tasks import (
    send_code_assignment_nudge_email_via_braze,
    send_offer_assignment_email_via_braze,
    send_offer_update_email_via_braze,
    send_offer_usage_email_via_braze,
)

# Disable unused imports because these are public API functions and previous implementations used some of these
# arguments, but current ones don't use all of them. And maybe future implementations will use them again. But
# regardless, they are intentionally there as part of the public API, to be used or not by implementations.
# pylint: disable=unused-argument

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True)
def send_offer_assignment_email(self, user_email, offer_assignment_id, subject, email_body, sender_alias,  # pylint: disable=dangerous-default-value
                                reply_to='', attachments=[], site_code=None, base_enterprise_url='') -> None:
    """
    Sends the offer assignment email.

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
        base_enterprise_url (str): Url for the enterprise learner portal.
    """
    if not is_braze_enabled(site_code):
        logger.error('Braze not enabled for site code {}'.format(site_code))
        return

    send_offer_assignment_email_via_braze(
        self, user_email, offer_assignment_id, subject, email_body,
        sender_alias, reply_to, attachments, site_code
    )


@shared_task(bind=True, ignore_result=True)
def send_offer_update_email(self, user_email, subject, email_body, sender_alias, reply_to='', attachments=[],  # pylint: disable=dangerous-default-value
                            site_code=None, base_enterprise_url='') -> None:
    """
    Sends the offer emails after assignment, either for revoking or reminding.

    Args:
        self: Ignore.
        user_email (str): Recipient's email address.
        subject (str): Email subject.
        email_body (str): The body of the email.
        site_code (str): Identifier of the site sending the email.
        sender_alias (str): Enterprise Customer sender alias used as From Name.
        reply_to (str): Enterprise Customer reply to address for email reply.
        attachments (list): File attachment list with dicts having 'file_name' and 'url' keys.
        base_enterprise_url (str): Enterprise learner portal url.
    """
    if not is_braze_enabled(site_code):
        logger.error('Braze not enabled for site code {}'.format(site_code))
        return

    send_offer_update_email_via_braze(
        self, user_email, subject, email_body, sender_alias, reply_to, attachments, site_code
    )


@shared_task(bind=True, ignore_result=True)
def send_offer_usage_email(
        self, lms_user_ids_by_email, subject, email_body_variables, site_code=None, campaign_id=None
) -> None:
    """
    Sends the offer usage email.

    Args:
        self: Ignore.
        lms_user_ids_by_email (dict): Map of user email to LMS user ids.
        subject (str): Email subject.
        email_body_variables (dict): key-value pairs that are injected into Braze email template for personalization.
        site_code (str): Identifier of the site sending the email.
        campaign_id (str): Identifier of Braze API-triggered campaign to send message through; defaults
            to config.ENTERPRISE_CODE_USAGE_CAMPAIGN_ID
    """
    if not is_braze_enabled(site_code):
        logger.error('Braze not enabled for site code {}'.format(site_code))
        return

    send_offer_usage_email_via_braze(
        self, lms_user_ids_by_email, subject, email_body_variables, site_code, campaign_id,
    )


@shared_task(bind=True, ignore_result=True)
def send_code_assignment_nudge_email(self, email, subject, email_body, sender_alias, reply_to='', attachments=[],  # pylint: disable=dangerous-default-value
                                     site_code=None, base_enterprise_url='') -> None:
    """
    Sends the code assignment nudge email.

    Args:
        self: Ignore.
        email (str): Recipient's email address.
        subject (str): Email subject.
        email_body (str): The body of the email.
        sender_alias (str): Enterprise Customer sender alias used as From Name.
        reply_to (str): Enterprise Customer reply to address for email reply.
        attachments (list): File attachment list with dicts having 'file_name' and 'url' keys.
        site_code (str): Identifier of the site sending the email.
        base_enterprise_url (str): Enterprise learner portal url.
    """
    if not is_braze_enabled(site_code):
        logger.error('Braze not enabled for site code {}'.format(site_code))
        return

    send_code_assignment_nudge_email_via_braze(
        self, email, subject, email_body, sender_alias, reply_to, attachments, site_code
    )
