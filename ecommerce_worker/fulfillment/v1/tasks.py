"""Order fulfillment tasks."""
from __future__ import absolute_import
from ssl import SSLError

from celery import shared_task
from celery.exceptions import Ignore
from celery.utils.log import get_task_logger
from edx_rest_api_client import exceptions

from ecommerce_worker.utils import get_configuration, get_ecommerce_client

logger = get_task_logger(__name__)  # pylint: disable=invalid-name


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
    max_fulfillment_retries = get_configuration('MAX_FULFILLMENT_RETRIES', site_code=site_code)
    api = get_ecommerce_client(site_code=site_code)
    try:
        logger.info('Requesting fulfillment of order [%s].', order_number)
        api.orders(order_number).fulfill.put(email_opt_in=email_opt_in)
    except exceptions.HttpClientError as exc:
        status_code = exc.response.status_code  # pylint: disable=no-member
        if status_code == 406:
            # The order is not fulfillable. Therefore, it must be complete.
            logger.info('Order [%s] has already been fulfilled. Ignoring.', order_number)
            raise Ignore()
        # Unknown client error. Let's retry to resolve it.
        logger.warning(
            'Fulfillment of order [%s] failed because of HttpClientError. Retrying',
            order_number,
            exc_info=True
        )
        _retry_order(self, exc, max_fulfillment_retries, order_number)

    except (exceptions.HttpServerError, exceptions.Timeout, SSLError) as exc:
        # Fulfillment failed, retry
        _retry_order(self, exc, max_fulfillment_retries, order_number)
