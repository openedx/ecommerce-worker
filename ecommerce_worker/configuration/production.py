from __future__ import absolute_import
from logging.config import dictConfig

import yaml

from ecommerce_worker.configuration import get_overrides_filename
from ecommerce_worker.configuration.base import *
from ecommerce_worker.configuration.logger import get_logger_config


# LOGGING
logger_config = get_logger_config()
dictConfig(logger_config)
# END LOGGING


filename = get_overrides_filename('ECOMMERCE_WORKER_CFG')
with open(filename) as f:
    config_from_yaml = yaml.load(f)

# Override base configuration with values from disk.
vars().update(config_from_yaml)
