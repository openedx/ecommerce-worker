"""
This file contains celery tasks for email marketing signal handler.
"""

from __future__ import absolute_import
from decimal import Decimal

from celery import shared_task
from celery.utils.log import get_task_logger
from sailthru.sailthru_error import SailthruClientError

from requests.exceptions import RequestException
from six import text_type

from ecommerce_worker.cache import Cache
from ecommerce_worker.braze.v1.client import get_braze_client, get_braze_configuration
from ecommerce_worker.braze.v1.exceptions import BrazeError, BrazeRateLimitError, BrazeInternalServerError
from ecommerce_worker.sailthru.v1.exceptions import SailthruError
from ecommerce_worker.sailthru.v1.notification import Notification
from ecommerce_worker.sailthru.v1.utils import (
    can_retry_sailthru_request,
    get_sailthru_client,
    get_sailthru_configuration
)
from ecommerce_worker.utils import get_ecommerce_client

logger = get_task_logger(__name__)  # pylint: disable=invalid-name
cache = Cache()  # pylint: disable=invalid-name


# pylint: disable=unused-argument

def schedule_retry(self, config):
    """Schedule a retry"""
    raise self.retry(countdown=config.get('SAILTHRU_RETRY_SECONDS'),
                     max_retries=config.get('SAILTHRU_RETRY_ATTEMPTS'))


def _build_purchase_item(course_id, course_url, cost_in_cents, mode, course_data, sku):
    """Build and return Sailthru purchase item object"""

    # build item description
    item = {
        'id': "{}-{}".format(course_id, mode),
        'url': course_url,
        'price': cost_in_cents,
        'qty': 1,
    }

    # get title from course info if we don't already have it from Sailthru
    if 'title' in course_data:
        item['title'] = course_data['title']
    else:
        # can't find, just invent title
        item['title'] = 'Course {} mode: {}'.format(course_id, mode)

    if 'tags' in course_data:
        item['tags'] = course_data['tags']

    # add vars to item
    item['vars'] = dict(course_data.get('vars', {}), mode=mode, course_run_id=course_id)

    item['vars']['purchase_sku'] = sku

    return item


def _record_purchase(sailthru_client, email, item, purchase_incomplete, message_id, options):
    """Record a purchase in Sailthru

    Arguments:
        sailthru_client (object): SailthruClient
        email (str): user's email address
        item (dict): Sailthru required information about the course
        purchase_incomplete (boolean): True if adding item to shopping cart
        message_id (str): Cookie used to identify marketing campaign
        options (dict): Sailthru purchase API options (e.g. template name)

    Returns:
        False if retryable error, else True
    """
    try:
        sailthru_response = sailthru_client.purchase(email, [item],
                                                     incomplete=purchase_incomplete, message_id=message_id,
                                                     options=options)

        if not sailthru_response.is_ok():
            error = sailthru_response.get_error()
            logger.error("Error attempting to record purchase in Sailthru: %s", error.get_message())
            return not can_retry_sailthru_request(error)

    except SailthruClientError as exc:
        logger.exception("Exception attempting to record purchase for %s in Sailthru - %s", email, text_type(exc))
        return False

    return True


def _get_course_content(course_id, course_url, sailthru_client, site_code, config):
    """Get course information using the Sailthru content api or from cache.

    If there is an error, just return with an empty response.

    Arguments:
        course_id (str): course key of the course
        course_url (str): LMS url for course info page.
        sailthru_client (object): SailthruClient
        site_code (str): site code
        config (dict): config options

    Returns:
        course information from Sailthru
    """
    # check cache first
    cache_key = "{}:{}".format(site_code, course_url)
    response = cache.get(cache_key)
    if not response:
        try:
            sailthru_response = sailthru_client.api_get("content", {"id": course_url})
            if not sailthru_response.is_ok():
                response = {}
            else:
                response = sailthru_response.json
                cache.set(cache_key, response, config.get('SAILTHRU_CACHE_TTL_SECONDS'))

        except SailthruClientError:
            response = {}

        if not response:
            logger.error('Could not get course data from Sailthru on enroll/purchase event. '
                         'Calling Ecommerce Course API to get course info for enrollment confirmation email')
            response = _get_course_content_from_ecommerce(course_id, site_code=site_code)
            if response:
                cache.set(cache_key, response, config.get('SAILTHRU_CACHE_TTL_SECONDS'))

    return response


def _get_course_content_from_ecommerce(course_id, site_code=None):
    """
    Get course information using the Ecommerce course api.

    In case of error returns empty response.
    Arguments:
        course_id (str): course key of the course
        site_code (str): site code

    Returns:
        course information from Ecommerce
    """
    api = get_ecommerce_client(site_code=site_code)
    try:
        api_response = api.courses(course_id).get()
    except Exception:  # pylint: disable=broad-except
        logger.exception(
            'An error occurred while retrieving data for course run [%s] from the Catalog API.',
            course_id,
            exc_info=True
        )
        return {}

    return {
        'title': api_response.get('name'),
        'verification_deadline': api_response.get('verification_deadline')
    }


def _update_unenrolled_list(sailthru_client, email, course_url, unenroll):
    """Maintain a list of courses the user has unenrolled from in the Sailthru user record

    Arguments:
        sailthru_client (object): SailthruClient
        email (str): user's email address
        course_url (str): LMS url for course info page.
        unenroll (boolean): True if unenrolling, False if enrolling

    Returns:
        False if retryable error, else True
    """
    try:
        # get the user 'vars' values from sailthru
        sailthru_response = sailthru_client.api_get("user", {"id": email, "fields": {"vars": 1}})
        if not sailthru_response.is_ok():
            error = sailthru_response.get_error()
            logger.error("Error attempting to read user record from Sailthru: %s", error.get_message())
            return not can_retry_sailthru_request(error)

        response_json = sailthru_response.json

        unenroll_list = []
        if response_json and "vars" in response_json and response_json["vars"] \
           and "unenrolled" in response_json["vars"]:
            unenroll_list = response_json["vars"]["unenrolled"]

        changed = False
        # if unenrolling, add course to unenroll list
        if unenroll:
            if course_url not in unenroll_list:
                unenroll_list.append(course_url)
                changed = True

        # if enrolling, remove course from unenroll list
        elif course_url in unenroll_list:
            unenroll_list.remove(course_url)
            changed = True

        if changed:
            # write user record back
            sailthru_response = sailthru_client.api_post(
                'user', {'id': email, 'key': 'email', 'vars': {'unenrolled': unenroll_list}})

            if not sailthru_response.is_ok():
                error = sailthru_response.get_error()
                logger.error("Error attempting to update user record in Sailthru: %s", error.get_message())
                return not can_retry_sailthru_request(error)

        return True

    except SailthruClientError as exc:
        logger.exception("Exception attempting to update user record for %s in Sailthru - %s", email, text_type(exc))
        return False


@shared_task(bind=True, ignore_result=True)
def update_course_enrollment(self, email, course_url, purchase_incomplete, mode, unit_cost=None, course_id=None,
                             currency=None, message_id=None, site_code=None, sku=None):
    """Adds/updates Sailthru when a user adds to cart/purchases/upgrades a course

     Args:
        email(str): The user's email address
        course_url(str): Course home page url
        purchase_incomplete(boolean): True if adding to cart
        mode(string): enroll mode (audit, verification, ...)
        unit_cost(decimal): cost if purchase event
        course_id(CourseKey): course id
        currency(str): currency if purchase event - currently ignored since Sailthru only supports USD
        message_id(str): value from Sailthru marketing campaign cookie
        site_code(str): site code

    Returns:
        None
    """
    # Celery converts decimals to strings, so convert back
    unit_cost = Decimal(unit_cost)

    # Get configuration
    config = get_sailthru_configuration(site_code)

    try:
        sailthru_client = get_sailthru_client(site_code)
    except SailthruError:
        # NOTE: We rely on the function to log the error for us
        return

    # Use event type to figure out processing required
    new_enroll = False
    send_template = None

    if not purchase_incomplete:
        if mode == 'verified':
            # upgrade complete
            send_template = config.get('SAILTHRU_UPGRADE_TEMPLATE')
        elif mode in ('audit', 'honor'):
            # free enroll
            new_enroll = True
            send_template = config.get('SAILTHRU_ENROLL_TEMPLATE')
        else:
            # paid course purchase complete
            new_enroll = True
            send_template = config.get('SAILTHRU_PURCHASE_TEMPLATE')

    # calc price in pennies for Sailthru
    #  https://getstarted.sailthru.com/new-for-developers-overview/advanced-features/purchase/
    cost_in_cents = int(unit_cost * 100)

    # update the "unenrolled" course array in the user record on Sailthru if new enroll or unenroll
    if new_enroll:
        if not _update_unenrolled_list(sailthru_client, email, course_url, False):
            schedule_retry(self, config)

    # Get course data from Sailthru content library or cache
    course_data = _get_course_content(course_id, course_url, sailthru_client, site_code, config)

    # build item description
    item = _build_purchase_item(course_id, course_url, cost_in_cents, mode, course_data, sku)

    # build purchase api options list
    options = {}
    if purchase_incomplete and config.get('SAILTHRU_ABANDONED_CART_TEMPLATE'):
        options['reminder_template'] = config.get('SAILTHRU_ABANDONED_CART_TEMPLATE')
        # Sailthru reminder time format is '+n time unit'
        options['reminder_time'] = "+{} minutes".format(config.get('SAILTHRU_ABANDONED_CART_DELAY'))

    # add appropriate send template
    if send_template:
        options['send_template'] = send_template

    if not _record_purchase(sailthru_client, email, item, purchase_incomplete, message_id, options):
        schedule_retry(self, config)


@shared_task(bind=True, ignore_result=True)
def send_course_refund_email(self, email, refund_id, amount, course_name, order_number, order_url, site_code=None):
    """ Sends the course refund email.

    Args:
        self: Ignore.
        email (str): Recipient's email address.
        refund_id (int): ID of the refund that initiated this task.
        amount (str): Formatted amount of the refund.
        course_name (str): Name of the course for which payment was refunded.
        order_number (str): Order number of the order that was refunded.
        order_url (str): Receipt URL of the refunded order.
        site_code (str): Identifier of the site sending the email.
    """
    config = get_sailthru_configuration(site_code)

    try:
        sailthru_client = get_sailthru_client(site_code)
    except SailthruError:
        # NOTE: We rely on the function to log the error for us
        return

    email_vars = {
        'amount': amount,
        'course_name': course_name,
        'order_number': order_number,
        'order_url': order_url,
    }

    try:
        response = sailthru_client.send(
            template=config['templates']['course_refund'],
            email=email,
            _vars=email_vars
        )
    except SailthruClientError:
        logger.exception(
            'A client error occurred while attempting to send a course refund notification for refund [%d].',
            refund_id
        )
        return

    if response.is_ok():
        logger.info('Course refund notification sent for refund %d.', refund_id)
    else:
        error = response.get_error()
        logger.error(
            'An error occurred while attempting to send a course refund notification for refund [%d]: %d - %s',
            refund_id, error.get_error_code(), error.get_message()
        )

        if can_retry_sailthru_request(error):
            logger.info(
                'An attempt will be made again to send a course refund notification for refund [%d].',
                refund_id
            )
            schedule_retry(self, config)
        else:
            logger.warning(
                'No further attempts will be made to send a course refund notification for refund [%d].',
                refund_id
            )


def _send_offer_assignment_email_via_braze(self, user_email, offer_assignment_id, subject, email_body, sender_alias,
                                site_code=None, base_enterprise_url=''):
    """
    Sends the offer assignment email via Braze.

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
    config = get_braze_configuration(site_code)
    try:
        braze_client = get_braze_client(site_code)
        response = braze_client.send_message(
            email_ids=list(user_email),
            subject=subject,
            body=email_body,
            sender_alias=sender_alias
        )
        if response and response['success']:
            dispatch_id = response['dispatch_id']
            if _update_assignment_email_status(offer_assignment_id, dispatch_id, 'success'):
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


def _send_offer_assignment_email_via_sailthru(self, user_email, offer_assignment_id, subject, email_body, sender_alias,
                                site_code=None, base_enterprise_url=''):
    """
    Sends the offer assignment email via Sailthru.

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
    config = get_sailthru_configuration(site_code)
    notification = Notification(
        config=config,
        emails=user_email,
        email_vars={
            'subject': subject,
            'email_body': email_body,
            'base_enterprise_url': base_enterprise_url,
            'sender_alias': sender_alias,
        },
        logger_prefix='Offer Assignment',
        site_code=site_code,
        template='enterprise_portal_email'
    )
    response, is_eligible_for_retry = notification.send()
    if is_eligible_for_retry:
        schedule_retry(self, config)

    if response and response.is_ok():
        send_id = response.get_body().get('send_id')  # pylint: disable=no-member
        if _update_assignment_email_status(offer_assignment_id, send_id, 'success'):
            logger.info('[Offer Assignment] Offer assignment notification sent with message --- '
                        '{message}; base enterprise url --- {base_enterprise_url}'.format(
                            message=email_body,
                            base_enterprise_url=base_enterprise_url))
        else:
            logger.exception(
                '[Offer Assignment] An error occurred while updating email status data for '
                'offer {token_offer} and email {token_email} via the ecommerce API.'.format(
                    token_offer=offer_assignment_id,
                    token_email=user_email,
                )
            )


@shared_task(bind=True, ignore_result=True)
def send_offer_assignment_email(self, user_email, offer_assignment_id, subject, email_body, sender_alias,
                                site_code=None, base_enterprise_url=''):
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
    config = get_braze_configuration(site_code)
    braze_enable = config.get('BRAZE_ENABLE')
    if braze_enable:
        _send_offer_assignment_email_via_braze(
            self, user_email, offer_assignment_id, subject, email_body, sender_alias, site_code, base_enterprise_url)
    else:
        _send_offer_assignment_email_via_sailthru(
            self, user_email, offer_assignment_id, subject, email_body, sender_alias, site_code, base_enterprise_url)


def _update_assignment_email_status(offer_assignment_id, send_id, status, site_code=None):
    """
    Update the offer_assignment and offer_assignment_email model using the Ecommerce assignmentemail api.
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
        logger.exception(
            '[Offer Assignment] An error occurred while updating offer assignment email status for '
            'offer id {token_offer} and message id {token_send_id} via the Ecommerce API.'.format(
                token_offer=offer_assignment_id,
                token_send_id=send_id
            )
        )
        return False
    return bool(api_response.get('status') == 'updated')


def _send_offer_update_email_via_braze(self, user_email, subject, email_body, sender_alias, site_code=None):
    """
    Sends the offer emails after assignment via braze, either for revoking or reminding.

    Args:
        self: Ignore.
        user_email (str): Recipient's email address.
        subject (str): Email subject.
        email_body (str): The body of the email.
        site_code (str): Identifier of the site sending the email.
        sender_alias (str): Enterprise Customer sender alias used as From Name.
    """
    config = get_braze_configuration(site_code)
    try:
        braze_client = get_braze_client(site_code)
        braze_client.send_message(
            email_ids=list(user_email),
            subject=subject,
            body=email_body,
            sender_alias=sender_alias
        )
    except (BrazeRateLimitError, BrazeInternalServerError):
        raise self.retry(countdown=config.get('BRAZE_RETRY_SECONDS'),
                         max_retries=config.get('BRAZE_RETRY_ATTEMPTS'))
    except BrazeError:
        logger.exception(
            '[Offer Assignment] Error in offer update notification with message --- '
            '{message}'.format(message=email_body)
        )


def _send_offer_update_email_via_sailthru(self, user_email, subject, email_body, sender_alias, site_code=None):
    """
    Sends the offer emails after assignment via sailthru, either for revoking or reminding.

    Args:
        self: Ignore.
        user_email (str): Recipient's email address.
        subject (str): Email subject.
        email_body (str): The body of the email.
        site_code (str): Identifier of the site sending the email.
        sender_alias (str): Enterprise Customer sender alias used as From Name.
    """
    config = get_sailthru_configuration(site_code)
    notification = Notification(
        config=config,
        emails=user_email,
        email_vars={
            'subject': subject,
            'email_body': email_body,
            'sender_alias': sender_alias,
        },
        logger_prefix='Offer Assignment',
        site_code=site_code,
        template='enterprise_portal_email'
    )
    _, is_eligible_for_retry = notification.send()
    if is_eligible_for_retry:
        schedule_retry(self, config)


@shared_task(bind=True, ignore_result=True)
def send_offer_update_email(self, user_email, subject, email_body, sender_alias, site_code=None):
    """
    Sends the offer emails after assignment, either for revoking or reminding.

    Args:
        self: Ignore.
        user_email (str): Recipient's email address.
        subject (str): Email subject.
        email_body (str): The body of the email.
        site_code (str): Identifier of the site sending the email.
        sender_alias (str): Enterprise Customer sender alias used as From Name.
    """
    config = get_braze_configuration(site_code)
    braze_enable = config.get('BRAZE_ENABLE')
    if braze_enable:
        _send_offer_update_email_via_braze(self, user_email, subject, email_body, sender_alias, site_code)
    else:
        _send_offer_update_email_via_sailthru(self, user_email, subject, email_body, sender_alias, site_code)


def _send_offer_usage_email_via_braze(self, emails, subject, email_body, site_code=None):
    """
    Sends the offer usage email via braze.

    Args:
        self: Ignore.
        emails (str): comma separated emails.
        subject (str): Email subject.
        email_body (str): The body of the email.
        site_code (str): Identifier of the site sending the email.
    """
    config = get_braze_configuration(site_code)
    try:
        braze_client = get_braze_client(site_code)
        braze_client.send_message(
            email_ids=list(emails),
            subject=subject,
            body=email_body
        )
    except (BrazeRateLimitError, BrazeInternalServerError):
        raise self.retry(countdown=config.get('BRAZE_RETRY_SECONDS'),
                         max_retries=config.get('BRAZE_RETRY_ATTEMPTS'))
    except BrazeError:
        logger.exception(
            '[Offer Usage] Error in offer usage notification with message --- '
            '{message}'.format(message=email_body)
        )


def _send_offer_usage_email_via_sailthru(self, emails, subject, email_body, site_code=None):
    """
    Sends the offer usage email via sailthru.

    Args:
        self: Ignore.
        emails (str): comma separated emails.
        subject (str): Email subject.
        email_body (str): The body of the email.
        site_code (str): Identifier of the site sending the email.
    """
    config = get_sailthru_configuration(site_code)
    notification = Notification(
        config=config,
        emails=emails,
        email_vars={
            'subject': subject,
            'email_body': email_body
        },
        logger_prefix='Offer Usage',
        site_code=site_code,
        template='assignment_email'
    )
    _, is_eligible_for_retry = notification.send(is_multi_send=True)
    if is_eligible_for_retry:
        schedule_retry(self, config)


@shared_task(bind=True, ignore_result=True)
def send_offer_usage_email(self, emails, subject, email_body, site_code=None):
    """
    Sends the offer usage email.

    Args:
        self: Ignore.
        emails (str): comma separated emails.
        subject (str): Email subject.
        email_body (str): The body of the email.
        site_code (str): Identifier of the site sending the email.
    """
    config = get_braze_configuration(site_code)
    braze_enable = config.get('BRAZE_ENABLE')
    if braze_enable:
        _send_offer_usage_email_via_braze(self, emails, subject, email_body, site_code)
    else:
        _send_offer_usage_email_via_sailthru(self, emails, subject, email_body, site_code)


def _send_code_assignment_nudge_email_via_braze(self, email, subject, email_body, site_code=None):
    """
    Sends the code assignment nudge email via braze.

    Args:
        self: Ignore.
        email (str): Recipient's email address.
        subject (str): Email subject.
        email_body (str): The body of the email.
        site_code (str): Identifier of the site sending the email.
    """
    config = get_braze_configuration(site_code)
    try:
        braze_client = get_braze_client(site_code)
        braze_client.send_message(
            email_ids=list(email),
            subject=subject,
            body=email_body,
        )
    except (BrazeRateLimitError, BrazeInternalServerError):
        raise self.retry(countdown=config.get('BRAZE_RETRY_SECONDS'),
                         max_retries=config.get('BRAZE_RETRY_ATTEMPTS'))
    except BrazeError:
        logger.exception(
            '[Code Assignment Nudge Email] Error in offer nudge notification with message --- '
            '{message}'.format(message=email_body)
        )


def _send_code_assignment_nudge_email_via_sailthru(self, email, subject, email_body, site_code=None):
    """
    Sends the code assignment nudge email via sailthru.

    Args:
        self: Ignore.
        email (str): Recipient's email address.
        subject (str): Email subject.
        email_body (str): The body of the email.
        site_code (str): Identifier of the site sending the email.
    """
    config = get_sailthru_configuration(site_code)
    notification = Notification(
        config=config,
        emails=email,
        email_vars={
            'subject': subject,
            'email_body': email_body,
            'sender_alias': 'edX Support Team',
        },
        logger_prefix='Code Assignment Nudge Email',
        site_code=site_code,
        template='enterprise_portal_email'
    )
    _, is_eligible_for_retry = notification.send()
    if is_eligible_for_retry:
        schedule_retry(self, config)


@shared_task(bind=True, ignore_result=True)
def send_code_assignment_nudge_email(self, email, subject, email_body, site_code=None):
    """
    Sends the code assignment nudge email.

    Args:
        self: Ignore.
        email (str): Recipient's email address.
        subject (str): Email subject.
        email_body (str): The body of the email.
        site_code (str): Identifier of the site sending the email.
    """
    config = get_braze_configuration(site_code)
    braze_enable = config.get('BRAZE_ENABLE')
    if braze_enable:
        _send_code_assignment_nudge_email_via_braze(self, email, subject, email_body, site_code)
    else:
        _send_code_assignment_nudge_email_via_sailthru(self, email, subject, email_body, site_code)
