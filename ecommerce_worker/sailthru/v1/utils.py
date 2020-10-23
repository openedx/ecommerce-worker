""" Utility functions. """

from __future__ import absolute_import
from celery.utils.log import get_task_logger
from sailthru.sailthru_client import SailthruClient

from ecommerce_worker.sailthru.v1.exceptions import ConfigurationError, SailthruNotEnabled
from ecommerce_worker.utils import get_configuration

log = get_task_logger(__name__)


def get_sailthru_configuration(site_code):
    """ Returns the Sailthru configuration for the specified site. """
    config = get_configuration('SAILTHRU', site_code=site_code)
    return config


def get_sailthru_client(site_code):
    """
    Returns a Sailthru client for the specified site.

    Args:
        site_code (str): Site for which the client should be configured.

    Returns:
        SailthruClient

    Raises:
        SailthruNotEnabled: If Sailthru is not enabled for the specified site.
        ConfigurationError: If either the Sailthru API key or secret are not set for the site.
    """
    # Get configuration
    config = get_sailthru_configuration(site_code)

    # Return if Sailthru integration disabled
    if not config.get('SAILTHRU_ENABLE'):
        msg = 'Sailthru is not enabled for site {}'.format(site_code)
        log.debug(msg)
        raise SailthruNotEnabled(msg)

    # Make sure key and secret configured
    key = config.get('SAILTHRU_KEY')
    secret = config.get('SAILTHRU_SECRET')

    if not (key and secret):
        msg = 'Both key and secret are required for site {}'.format(site_code)
        log.error(msg)
        raise ConfigurationError(msg)

    return SailthruClient(key, secret)


def can_retry_sailthru_request(error):
    """ Returns True if a Sailthru request and be re-submitted after an error has occurred.

    Responses with the following codes can be retried:
         9: Internal Error
        43: Too many [type] requests this minute to /[endpoint] API

    All other errors are considered failures, that should not be retried. A complete list of error codes is available at
    https://getstarted.sailthru.com/new-for-developers-overview/api/api-response-errors/.

    Args:
        error (SailthruResponseError)

    Returns:
        bool: Indicates if the original request can be retried.
    """
    code = error.get_error_code()
    return code in (9, 43)
