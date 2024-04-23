import os
from celery import Celery

from ecommerce_worker.configuration import CONFIGURATION_MODULE


# TEMP: This code will be removed by ARCH-BOM on 4/22/24
# ddtrace allows celery task logs to be traced by the dd agent
# TODO: remove this code.
try:
    from ddtrace import patch
    patch(celery=True)
except ImportError:
    pass

# Set the default configuration module, if one is not aleady defined.
os.environ.setdefault(CONFIGURATION_MODULE, 'ecommerce_worker.configuration.local')

app = Celery('ecommerce_worker')
# See http://celery.readthedocs.org/en/latest/userguide/application.html#config-from-envvar.
app.config_from_envvar(CONFIGURATION_MODULE)
