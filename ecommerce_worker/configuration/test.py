from __future__ import absolute_import
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
JWT_SECRET_KEY = 'test-key'
JWT_ISSUER = 'ecommerce_worker'

ECOMMERCE_SERVICE_USERNAME = 'service'
# END AUTHENTICATION


# SITE-SPECIFIC CONFIGURATION OVERRIDES
SITE_OVERRIDES = {}

# Sailthru support unit test settings
SAILTHRU.update({
    'SAILTHRU_ENABLE': True,
    'SAILTHRU_UPGRADE_TEMPLATE': 'upgrade_template',
    'SAILTHRU_PURCHASE_TEMPLATE': 'purchase_template',
    'SAILTHRU_ENROLL_TEMPLATE': 'enroll_template',
    'SAILTHRU_ABANDONED_CART_TEMPLATE': 'abandoned_template',
    'SAILTHRU_KEY': 'key',
    'SAILTHRU_SECRET': 'secret',
})

# Braze unit test settings
BRAZE.update({
    'BRAZE_ENABLE': False,
    'BRAZE_REST_API_KEY': 'rest_api_key',
    'BRAZE_WEBAPP_API_KEY': 'webapp_api_key',
    'EMAIL_TEMPLATE_ID': 'email_template_id',
})

# Sailthru support unit test settings with override
TEST_SITE_OVERRIDES = {
    'test_site': { 'SAILTHRU': dict(SAILTHRU,
                                    SAILTHRU_UPGRADE_TEMPLATE='site_upgrade_template')}
}
