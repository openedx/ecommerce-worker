"""Order fulfillment tasks."""
from celery import shared_task
from celery.exceptions import Ignore
from celery.utils.log import get_task_logger
from edx_rest_api_client import exceptions

from ecommerce_worker.utils import get_configuration, get_ecommerce_api_client

logger = get_task_logger(__name__)  # pylint: disable=invalid-name


@shared_task(bind=True, ignore_result=True)
def process_notification(self, processor_name, notification_data, site_code=None):
    """
    Process a payment processor notification.

    Arguments:
        processor_name (str): The name of the payment processor which should process the notification.
        notification_data (str): The notification data sent by the payment processor.
        site_code (str): Partner short_code for the relevant site.

    Returns:
        None
    """
    max_notification_retries = get_configuration('MAX_NOTIFICATION_RETRIES', site_code=site_code)
    api = get_ecommerce_api_client(site_code)
    try:
        logger.info('Requesting processing of notification from payment processor [%s].', processor_name)
        notification_data['payment_processor'] = processor_name
        api.payment.processors.notification.process.put(notification_data)
    except exceptions.HttpClientError as exc:
        status_code = exc.response.status_code  # pylint: disable=no-member
        if status_code == 406:
            # The notification has already been processed.
            logger.info(
                'Notification from payment processor [%s] has already been processed. Ignoring.',
                processor_name
            )
            raise Ignore()
        else:
            # Unknown client error. Re-raise the exception.
            logger.exception('Processing of notification from payment processor [%s] failed.', processor_name)
            raise exc
    except (exceptions.HttpServerError, exceptions.Timeout) as exc:
        # Notification processing failed. Retry with exponential backoff until processing
        # succeeds or the retry limit is reached. If the retry limit is exceeded,
        # the exception is re-raised.
        retries = self.request.retries
        if retries == max_notification_retries:
            logger.exception('Processing of notification [%s] failed. Giving up.', order_number)
        else:
            logger.warning('Processing of notification [%s] failed. Retrying.', order_number)

        countdown = 2 ** retries
        raise self.retry(exc=exc, countdown=countdown, max_retries=max_fulfillment_retries)
