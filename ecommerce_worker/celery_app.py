import os
from celery import Celery


# Environment variable indicating which configuration module to use.
CONFIGURATION = 'WORKER_CONFIGURATION_MODULE'

# Set the default configuration module, if one is not aleady defined.
os.environ.setdefault(CONFIGURATION, 'ecommerce_worker.configuration.local')

app = Celery('ecommerce_worker')
# See http://celery.readthedocs.org/en/latest/userguide/application.html#config-from-envvar.
app.config_from_envvar(CONFIGURATION)
