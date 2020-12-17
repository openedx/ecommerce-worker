from __future__ import absolute_import
import logging
from logging.config import dictConfig

from ecommerce_worker.configuration.base import *
from ecommerce_worker.configuration.logger import get_logger_config

logger = logging.getLogger(__name__)


# CELERY
BROKER_URL = 'redis://'
# END CELERY


# ORDER FULFILLMENT
ECOMMERCE_API_ROOT = 'http://localhost:18130/api/v2/'
# END ORDER FULFILLMENT

# AUTHENTICATION
JWT_SECRET_KEY = 'insecure-secret-key'
JWT_ISSUER = 'ecommerce_worker'
# END AUTHENTICATION

# LOGGING
logger_config = get_logger_config(debug=True, dev_env=True, local_loglevel='DEBUG')
dictConfig(logger_config)
# END LOGGING

# Apply any developer-defined overrides.
try:
    from ecommerce_worker.configuration.private import *  # pylint: disable=import-error
except ImportError:
    logger.warning('No developer-defined configuration overrides have been applied.')
    pass
