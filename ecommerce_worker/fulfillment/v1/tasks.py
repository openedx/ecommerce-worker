"""Order fulfillment tasks."""
from celery import shared_task
from celery.exceptions import Ignore
from celery.utils.log import get_task_logger
from edx_rest_api_client import exceptions
from edx_rest_api_client.client import EdxRestApiClient

from ecommerce_worker.utils import get_configuration

logger = get_task_logger(__name__)  # pylint: disable=invalid-name


@shared_task(bind=True, ignore_result=True)
def fulfill_order(self, order_number, site_code=None):
    """Fulfills an order.

    Arguments:
        order_number (str): Order number indicating which order to fulfill.

    Returns:
        None
    """
    ecommerce_api_root = get_configuration('ECOMMERCE_API_ROOT', site_code=site_code)
    max_fulfillment_retries = get_configuration('MAX_FULFILLMENT_RETRIES', site_code=site_code)
    signing_key = get_configuration('JWT_SECRET_KEY', site_code=site_code)
    issuer = get_configuration('JWT_ISSUER', site_code=site_code)
    service_username = get_configuration('ECOMMERCE_SERVICE_USERNAME', site_code=site_code)

    api = EdxRestApiClient(ecommerce_api_root, signing_key=signing_key, issuer=issuer, username=service_username)
    try:
        logger.info('Requesting fulfillment of order [%s].', order_number)
        api.orders(order_number).fulfill.put()
    except exceptions.HttpClientError as exc:
        status_code = exc.response.status_code  # pylint: disable=no-member
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
            logger.exception('Fulfillment of order [%s] failed. Giving up.', order_number)
        else:
            logger.warning('Fulfillment of order [%s] failed. Retrying.', order_number)

        countdown = 2 ** retries
        raise self.retry(exc=exc, countdown=countdown, max_retries=max_fulfillment_retries)
