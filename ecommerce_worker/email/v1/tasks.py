"""
This file contains celery tasks for email marketing signal handler.
"""

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


@shared_task(bind=True, ignore_result=True)
def send_offer_assignment_email(self, user_email, offer_assignment_id, subject, email_body, sender_alias,
                                site_code=None, base_enterprise_url='') -> None:
    """
    Sends the offer assignment email.

    Args:
        self: Ignore.
        user_email (str): Recipient's email address.
        offer_assignment_id (str): Key of the entry in the offer_assignment model.
        subject (str): Email subject.
        email_body (str): The body of the email.
        site_code (str): Identifier of the site sending the email.
        base_enterprise_url (str): Url for the enterprise learner portal.
        sender_alias (str): Enterprise Customer sender alias used as From Name.
    """
    if is_braze_enabled(site_code):
        send_offer_assignment_email_via_braze(
            self, user_email, offer_assignment_id, subject, email_body, sender_alias, site_code)


@shared_task(bind=True, ignore_result=True)
def send_offer_update_email(self, user_email, subject, email_body, sender_alias, site_code=None,
                            base_enterprise_url='') -> None:
    """
    Sends the offer emails after assignment, either for revoking or reminding.

    Args:
        self: Ignore.
        user_email (str): Recipient's email address.
        subject (str): Email subject.
        email_body (str): The body of the email.
        site_code (str): Identifier of the site sending the email.
        sender_alias (str): Enterprise Customer sender alias used as From Name.
        base_enterprise_url (str): Enterprise learner portal url.
    """
    if is_braze_enabled(site_code):
        send_offer_update_email_via_braze(self, user_email, subject, email_body, sender_alias, site_code)


@shared_task(bind=True, ignore_result=True)
def send_offer_usage_email(self, emails, subject, email_body, site_code=None,
                           base_enterprise_url='') -> None:
    """
    Sends the offer usage email.

    Args:
        self: Ignore.
        emails (str): comma separated emails.
        subject (str): Email subject.
        email_body (str): The body of the email.
        site_code (str): Identifier of the site sending the email.
        base_enterprise_url (str): Url of the enterprise's learner portal
    """
    if is_braze_enabled(site_code):
        send_offer_usage_email_via_braze(self, emails, subject, email_body, site_code)


@shared_task(bind=True, ignore_result=True)
def send_code_assignment_nudge_email(self, email, subject, email_body, sender_alias, site_code=None,
                                     base_enterprise_url='') -> None:
    """
    Sends the code assignment nudge email.

    Args:
        self: Ignore.
        email (str): Recipient's email address.
        subject (str): Email subject.
        email_body (str): The body of the email.
        sender_alias (str): Enterprise Customer sender alias used as From Name.
        site_code (str): Identifier of the site sending the email.
        base_enterprise_url (str): Enterprise learner portal url.
    """
    if is_braze_enabled(site_code):
        send_code_assignment_nudge_email_via_braze(self, email, subject, email_body, sender_alias, site_code)
