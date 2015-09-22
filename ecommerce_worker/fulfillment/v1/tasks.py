"""Order fulfillment tasks."""
from celery import shared_task
from celery.exceptions import Ignore
from celery.utils.log import get_task_logger
from ecommerce_api_client import exceptions
from ecommerce_api_client.client import EcommerceApiClient

from ecommerce_worker.utils import get_configuration

logger = get_task_logger(__name__)  # pylint: disable=invalid-name


@shared_task(bind=True, ignore_result=True)
def fulfill_order(self, order_number):
    """Fulfills an order.

    Arguments:
        order_number (str): Order number indicating which order to fulfill.

    Returns:
        None
    """
    ecommerce_api_root = get_configuration('ECOMMERCE_API_ROOT')
    worker_access_token = get_configuration('WORKER_ACCESS_TOKEN')
    max_fulfillment_retries = get_configuration('MAX_FULFILLMENT_RETRIES')

    if not (ecommerce_api_root and worker_access_token and max_fulfillment_retries):
        raise RuntimeError('Worker is improperly configured for order fulfillment.')

    api = EcommerceApiClient(ecommerce_api_root, oauth_access_token=worker_access_token)

    try:
        logger.info('Requesting fulfillment of order [%s].', order_number)
        api.orders(order_number).fulfill.put()
    except exceptions.HttpClientError as exc:
        status_code = exc.response.status_code
        if status_code == 406:
            # The order is not fulfillable. Therefore, it must be complete.
            logger.info('Order [%s] has already been fulfilled. Ignoring.', order_number)
            raise Ignore()
        else:
            # Unknown client error. Re-raise the exception.
            logger.exception('Fulfillment of order [%s] failed.', order_number)
            raise exc
    except (exceptions.HttpServerError, exceptions.Timeout) as exc:
        # Fulfillment failed. Retry with exponential backoff until fulfillment
        # succeeds or the retry limit is reached. If the retry limit is exceeded,
        # the exception is re-raised.
        retries = self.request.retries
        if retries == max_fulfillment_retries:
            logger.exception('Fulfillment of order [%s] failed.', order_number)
        else:
            logger.exception('Fulfillment of order [%s] failed. Retrying.', order_number)

        countdown = 2 ** retries
        raise self.retry(exc=exc, countdown=countdown, max_retries=max_fulfillment_retries)
