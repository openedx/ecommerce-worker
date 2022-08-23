from logging.config import dictConfig

from ecommerce_worker.configuration.base import *
from ecommerce_worker.configuration.logger import get_logger_config


# CELERY
CELERY_ALWAYS_EAGER = True
# END CELERY


# ORDER FULFILLMENT
ECOMMERCE_API_ROOT = 'http://localhost:18130/api/v2/'
WORKER_ACCESS_TOKEN = 'fake-access-token'
# END ORDER FULFILLMENT


# LOGGING
logger_config = get_logger_config(debug=True, dev_env=True, local_loglevel='DEBUG')
dictConfig(logger_config)
# END LOGGING


# AUTHENTICATION
ECOMMERCE_SERVICE_USERNAME = 'service'
# END AUTHENTICATION


# SITE-SPECIFIC CONFIGURATION OVERRIDES
SITE_OVERRIDES = {}
