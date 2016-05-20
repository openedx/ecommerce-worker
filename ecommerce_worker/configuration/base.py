# CELERY
# Default broker URL. See http://celery.readthedocs.org/en/latest/configuration.html#broker-url.
BROKER_URL = None

# Disable connection pooling. Connections may be severed by load balancers.
# This forces the application to connect explicitly to the broker each time
# rather than assume a long-lived connection.
BROKER_POOL_LIMIT = 0
BROKER_CONNECTION_TIMEOUT = 1

# Use heartbeats to prevent broker connection loss. When the broker
# is behind a load balancer, the load balancer may timeout Celery's
# connection to the broker, causing messages to be lost.
BROKER_HEARTBEAT = 10.0
BROKER_HEARTBEAT_CHECKRATE = 2

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

# Site Overrides provide support for site/partner-specific configuration settings where applicable
# For example, the ECOMMERCE_API_ROOT value is different from one ecommerce site to the next
SITE_OVERRIDES = None
