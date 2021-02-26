# CELERY
# Default broker URL. See http://celery.readthedocs.org/en/latest/configuration.html#broker-url.
BROKER_URL = 'redis://:celery@127.0.0.1:6379'

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
    'ecommerce_worker.sailthru.v1.tasks',
)

DEFAULT_PRIORITY_QUEUE = 'ecommerce.default'
CELERY_DEFAULT_EXCHANGE = 'ecommerce'
CELERY_DEFAULT_ROUTING_KEY = 'ecommerce'
CELERY_DEFAULT_QUEUE = DEFAULT_PRIORITY_QUEUE
# Prevent Celery from removing handlers on the root logger. Allows setting custom logging handlers.
# See http://celery.readthedocs.org/en/latest/configuration.html#celeryd-hijack-root-logger.
CELERYD_HIJACK_ROOT_LOGGER = False

# Specify allowed serializers that are consistent with Celery 3 defaults
CELERY_TASK_SERIALIZER = 'pickle'
CELERY_RESULT_SERIALIZER = 'pickle'
CELERY_EVENT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json', 'pickle', 'yaml']
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

# .. toggle_name: BRAZE['BRAZE_ENABLE']
# .. toggle_implementation: PythonConstant
# .. toggle_default: False
# .. toggle_description: Toggle for allowing emails to be sent via Braze instead of sailthru
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2021-02-09
# .. toggle_target_removal_date: None
# .. toggle_warnings: None
# .. toggle_tickets: ENT-4071
BRAZE = {
    'BRAZE_ENABLE': False,
    'BRAZE_REST_API_KEY': None,
    'BRAZE_WEBAPP_API_KEY': None,
    'EMAIL_TEMPLATE_ID': '',
    'REST_API_URL': 'https://rest.iad-06.braze.com',
    'MESSAGES_SEND_ENDPOINT': '/messages/send',
    'EMAIL_BOUNCE_ENDPOINT': '/email/hard_bounces',
    'NEW_ALIAS_ENDPOINT': '/users/alias/new',
    'USERS_TRACK_ENDPOINT': '/users/track',
    'FROM_EMAIL': '<edx-for-business-no-reply@info.edx.org>',
    # Retry settings for Braze celery tasks
    'BRAZE_RETRY_SECONDS': 3600,
    'BRAZE_RETRY_ATTEMPTS': 6,
    }

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
        'enterprise_portal_email': 'Enterprise Portal Email',
    }
}
