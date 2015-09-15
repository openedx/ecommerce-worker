from logging.config import dictConfig
import os

import yaml

from ecommerce_worker.configuration.base import *
from ecommerce_worker.configuration.logger import get_logger_config


def get_overrides_filename(variable):
    """
    Get the name of the file containing configuration overrides
    from the provided environment variable.
    """
    filename = os.environ.get(variable)

    if filename is None:
        msg = 'Please set the {} environment variable.'.format(variable)
        raise EnvironmentError(msg)

    return filename


# LOGGING
logger_config = get_logger_config()
dictConfig(logger_config)
# END LOGGING


filename = get_overrides_filename('ECOMMERCE_WORKER_CFG')
with open(filename) as f:
    config_from_yaml = yaml.load(f)

# Override base configuration with values from disk.
vars().update(config_from_yaml)
