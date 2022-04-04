"""Order fulfillment tasks."""
from urllib.parse import urljoin

import requests
from celery import shared_task
from celery.exceptions import Ignore
from celery.utils.log import get_task_logger
from requests.exceptions import HTTPError

from ecommerce_worker.utils import get_configuration, get_access_token

logger = get_task_logger(__name__)


def _retry_order(self, exception, max_fulfillment_retries, order_number):
    """
    Retry with exponential backoff until fulfillment
    succeeds or the retry limit is reached. If the retry limit is exceeded,
    the exception is re-raised.
    """
    retries = self.request.retries
    if retries == max_fulfillment_retries:
        logger.exception('Fulfillment of order [%s] failed. Giving up.', order_number)
    else:
        logger.warning('Fulfillment of order [%s] failed. Retrying.', order_number)

    countdown = 2 ** retries
    raise self.retry(exc=exception, countdown=countdown, max_retries=max_fulfillment_retries)


@shared_task(bind=True, ignore_result=True)
def fulfill_order(self, order_number, site_code=None, email_opt_in=False):
    """Fulfills an order.

    Arguments:
        order_number (str): Order number indicating which order to fulfill.

    Returns:
        None
    """

    api_url = urljoin(
        get_configuration('ECOMMERCE_API_ROOT', site_code=site_code),
        f'orders/{order_number}/fulfill/'
    )
    max_fulfillment_retries = get_configuration('MAX_FULFILLMENT_RETRIES', site_code=site_code)

    try:
        logger.info('Requesting fulfillment of order [%s].', order_number)
        access_token = get_access_token()

        headers = {'Authorization': f'JWT {access_token}'}
        response = requests.put(
            api_url,
            params={
                'email_opt_in': email_opt_in
            },
            headers=headers
        )
        response.raise_for_status()

    except HTTPError as exc:
        status_code = exc.response.status_code
        if status_code == 406:
            # The order is not fulfillable. Therefore, it must be complete.
            logger.info('Order [%s] has already been fulfilled. Ignoring.', order_number)
            raise Ignore() from exc

        # Unknown client error. Let's retry to resolve it.
        logger.warning(
            'Fulfillment of order [%s] failed because of HttpClientError. Retrying',
            order_number,
            exc_info=True
        )
        _retry_order(self, exc, max_fulfillment_retries, order_number)
