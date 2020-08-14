# CELERY
# Default broker URL. See http://celery.readthedocs.org/en/latest/configuration.html#broker-url.
broker_url = 'amqp://celery:celery@127.0.0.1:5672'

# Disable connection pooling. Connections may be severed by load balancers.
# This forces the application to connect explicitly to the broker each time
# rather than assume a long-lived connection.
broker_pool_limit = 0
broker_connection_timeout = 1

# Use heartbeats to prevent broker connection loss. When the broker
# is behind a load balancer, the load balancer may timeout Celery's
# connection to the broker, causing messages to be lost.
broker_heartbeat = 10.0
broker_heartbeat_checkrate = 2

# Backend used to store task results.
# See http://celery.readthedocs.org/en/latest/configuration.html#celery-result-backend.
result_backend = None

# A sequence of modules to import when the worker starts.
# See http://celery.readthedocs.org/en/latest/configuration.html#celery-imports.
imports = (
    'ecommerce_worker.fulfillment.v1.tasks',
    'ecommerce_worker.sailthru.v1.tasks',
)

DEFAULT_PRIORITY_QUEUE = 'ecommerce.default'
task_default_exchange = 'ecommerce'
task_default_routing_key = 'ecommerce'
task_default_queue = DEFAULT_PRIORITY_QUEUE
# Prevent Celery from removing handlers on the root logger. Allows setting custom logging handlers.
# See http://celery.readthedocs.org/en/latest/configuration.html#celeryd-hijack-root-logger.
worker_hijack_root_logger = False
# END CELERY


# ORDER FULFILLMENT
# Absolute URL used to construct API calls against the ecommerce service.
ECOMMERCE_API_ROOT = 'http://127.0.0.1:8002/api/v2/'

# Maximum number of retries before giving up on the fulfillment of an order.
# For reference, 11 retries with exponential backoff yields a maximum waiting
# time of 2047 seconds (about 30 minutes). Defaulting this to None could yield
# unwanted behavior: infinite retries.
MAX_FULFILLMENT_RETRIES = 11
# END ORDER FULFILLMENT

# AUTHENTICATION
JWT_SECRET_KEY = 'insecure-secret-key'
JWT_ISSUER = 'ecommerce_worker'

ECOMMERCE_SERVICE_USERNAME = 'ecommerce_worker'
# END AUTHENTICATION

# Site Overrides provide support for site/partner-specific configuration settings where applicable
# For example, the ECOMMERCE_API_ROOT value is different from one ecommerce site to the next
SITE_OVERRIDES = None

# Settings for Sailthru email marketing integration
SAILTHRU = {
    # Set to false to ignore Sailthru events
    'SAILTHRU_ENABLE': False,

    # Template used when user upgrades to verified
    'SAILTHRU_UPGRADE_TEMPLATE': None,

    # Template used with user purchases a course
    'SAILTHRU_PURCHASE_TEMPLATE': None,

    # Template used with user enrolls in a free course
    'SAILTHRU_ENROLL_TEMPLATE': None,

    # Abandoned cart template
    'SAILTHRU_ABANDONED_CART_TEMPLATE': None,

    # minutes to delay before abandoned cart message
    'SAILTHRU_ABANDONED_CART_DELAY': 60,

    # Sailthru key and secret required for integration
    'SAILTHRU_KEY': 'sailthru key here',
    'SAILTHRU_SECRET': 'sailthru secret here',

    # Retry settings for Sailthru celery tasks
    'SAILTHRU_RETRY_SECONDS': 3600,
    'SAILTHRU_RETRY_ATTEMPTS': 6,

    # ttl for cached course content from Sailthru (in seconds)
    'SAILTHRU_CACHE_TTL_SECONDS': 3600,

    # dummy price for audit/honor (i.e., if cost = 0)
    # Note: setting this value to 0 skips Sailthru calls for free transactions
    'SAILTHRU_MINIMUM_COST': 100,

    # Transactional email template name map
    'templates': {
        'course_refund': 'Course Refund',
        'assignment_email': 'Offer Assignment Email',
    }
}
