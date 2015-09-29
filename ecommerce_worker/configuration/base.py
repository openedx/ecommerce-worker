# CELERY
# Default broker URL. See http://celery.readthedocs.org/en/latest/configuration.html#broker-url.
BROKER_URL = None

# Backend used to store task results.
# See http://celery.readthedocs.org/en/latest/configuration.html#celery-result-backend.
CELERY_RESULT_BACKEND = None

# A sequence of modules to import when the worker starts.
# See http://celery.readthedocs.org/en/latest/configuration.html#celery-imports.
CELERY_IMPORTS = (
    'ecommerce_worker.fulfillment.v1.tasks',
)

# Prevent Celery from removing handlers on the root logger. Allows setting custom logging handlers.
# See http://celery.readthedocs.org/en/latest/configuration.html#celeryd-hijack-root-logger.
CELERYD_HIJACK_ROOT_LOGGER = False
# END CELERY


# ORDER FULFILLMENT
# Absolute URL used to construct API calls against the ecommerce service.
ECOMMERCE_API_ROOT = None

# Maximum number of retries before giving up on the fulfillment of an order.
# For reference, 11 retries with exponential backoff yields a maximum waiting
# time of 2047 seconds (about 30 minutes). Defaulting this to None could yield
# unwanted behavior: infinite retries.
MAX_FULFILLMENT_RETRIES = 11
# END ORDER FULFILLMENT

# AUTHENTICATION
JWT_SECRET_KEY = None
JWT_ISSUER = None

ECOMMERCE_SERVICE_USERNAME = 'ecommerce_worker'
# END AUTHENTICATION
