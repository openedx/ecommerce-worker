"""
This file contains celery tasks for email marketing signal handler.
"""

from celery import shared_task
from celery.utils.log import get_task_logger
from sailthru.sailthru_client import SailthruClient
from sailthru.sailthru_error import SailthruClientError

from ecommerce_worker.cache import Cache
from ecommerce_worker.utils import get_configuration

logger = get_task_logger(__name__)  # pylint: disable=invalid-name
cache = Cache()  # pylint: disable=invalid-name


# pylint: disable=not-callable
@shared_task(bind=True, ignore_result=True)
def update_course_enrollment(self, email, course_url, purchase_incomplete, mode,
                             unit_cost=None, course_id=None,
                             currency=None, message_id=None, site_code=None):  # pylint: disable=unused-argument
    """Adds/updates Sailthru when a user adds to cart/purchases/upgrades a course

     Args:
        email(str): The user's email address
        course_url(str): Course home page url
        incomplete(boolean): True if adding to cart
        mode(string): enroll mode (audit, verification, ...)
        unit_cost(decimal): cost if purchase event
        course_id(CourseKey): course id
        currency(str): currency if purchase event - currently ignored since Sailthru only supports USD
        message_id(str): value from Sailthru marketing campaign cookie
        site_code(str): site code

    Returns:
        None
    """
    # Get configuration
    config = get_configuration('SAILTHRU', site_code=site_code)

    # Return if Sailthru integration disabled
    if not config.get('SAILTHRU_ENABLE'):
        return

    # Make sure key and secret configured
    sailthru_key = config.get('SAILTHRU_KEY')
    sailthru_secret = config.get('SAILTHRU_SECRET')
    if not (sailthru_key and sailthru_secret):
        logger.error("Sailthru key and or secret not specified for site %s", site_code)
        return

    sailthru_client = SailthruClient(sailthru_key, sailthru_secret)

    # Use event type to figure out processing required
    new_enroll = False
    send_template = None

    if not purchase_incomplete:
        if mode == 'verified':
            # upgrade complete
            send_template = config.get('SAILTHRU_UPGRADE_TEMPLATE')
        elif mode == 'audit' or mode == 'honor':
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
    if not cost_in_cents:
        cost_in_cents = config.get('SAILTHRU_MINIMUM_COST')
        # if still zero, ignore purchase since Sailthru can't deal with $0 transactions
        if not cost_in_cents:
            return

    # update the "unenrolled" course array in the user record on Sailthru if new enroll or unenroll
    if new_enroll:
        if not _update_unenrolled_list(sailthru_client, email, course_url, False):
            _schedule_retry(self, config)

    # Get course data from Sailthru content library or cache
    course_data = _get_course_content(course_url, sailthru_client, site_code, config)

    # build item description
    item = _build_purchase_item(course_id, course_url, cost_in_cents, mode, course_data)

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
        _schedule_retry(self, config)


def _schedule_retry(self, config):
    """Schedule a retry"""
    raise self.retry(countdown=config.get('SAILTHRU_RETRY_SECONDS'),
                     max_retries=config.get('SAILTHRU_RETRY_ATTEMPTS'))


def _build_purchase_item(course_id, course_url, cost_in_cents, mode, course_data):
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
            return not _retryable_sailthru_error(error)

    except SailthruClientError as exc:
        logger.exception("Exception attempting to record purchase for %s in Sailthru - %s", email, unicode(exc))
        return False

    return True


def _get_course_content(course_url, sailthru_client, site_code, config):
    """Get course information using the Sailthru content api or from cache.

    If there is an error, just return with an empty response.

    Arguments:
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
                return {}

            response = sailthru_response.json
            cache.set(cache_key, response, config.get('SAILTHRU_CACHE_TTL_SECONDS'))

        except SailthruClientError:
            response = {}

    return response


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
            return not _retryable_sailthru_error(error)

        response_json = sailthru_response.json

        unenroll_list = []
        if response_json and "vars" in response_json and "unenrolled" in response_json["vars"]:
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
                return not _retryable_sailthru_error(error)

        return True

    except SailthruClientError as exc:
        logger.exception("Exception attempting to update user record for %s in Sailthru - %s", email, unicode(exc))
        return False


def _retryable_sailthru_error(error):
    """ Return True if error should be retried.

    9: Retryable internal error
    43: Rate limiting response
    others: Not retryable

    See: https://getstarted.sailthru.com/new-for-developers-overview/api/api-response-errors/
    """
    code = error.get_error_code()
    return code == 9 or code == 43
