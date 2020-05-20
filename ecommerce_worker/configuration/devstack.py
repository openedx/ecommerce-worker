import logging
from logging.config import dictConfig

import yaml

from . import get_overrides_filename
from ecommerce_worker.configuration.base import *
from ecommerce_worker.configuration.logger import get_logger_config

logger = logging.getLogger(__name__)


# LOGGING
logger_config = get_logger_config(debug=True, dev_env=True, local_loglevel='DEBUG')
dictConfig(logger_config)
# END LOGGING

filename = get_overrides_filename('ECOMMERCE_WORKER_CFG')
with open(filename) as f:
    config_from_yaml = yaml.load(f)

# Override base configuration with values from disk.
vars().update(config_from_yaml)

# Apply any developer-defined overrides.
try:
    from ecommerce_worker.configuration.private import *  # pylint: disable=import-error
except ImportError:
    logger.warning('No developer-defined configuration overrides have been applied.')
    pass
