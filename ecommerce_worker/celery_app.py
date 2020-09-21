from __future__ import absolute_import
import os
from celery import Celery

from ecommerce_worker.configuration import CONFIGURATION_MODULE


# Set the default configuration module, if one is not aleady defined.
os.environ.setdefault(CONFIGURATION_MODULE, 'ecommerce_worker.configuration.local')

app = Celery('ecommerce_worker')
# See http://celery.readthedocs.org/en/latest/userguide/application.html#config-from-envvar.
app.config_from_envvar(CONFIGURATION_MODULE)
