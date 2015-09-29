"""Helper functions."""
import os
import sys

from ecommerce_worker.celery_app import CONFIGURATION


def get_configuration(variable):
    """Get a value from configuration.

    Retrieves the value corresponding to the given variable from the
    configuration module currently in use by the app.

    Arguments:
        variable (str): The name of a variable from the configuration module.

    Returns:
        The value corresponding to the variable, or None if the variable is not found.
    """
    name = os.environ.get(CONFIGURATION)

    # __import__ performs a full import, but only returns the top-level
    # package, not the targeted module. sys.modules is a dictionary
    # mapping module names to loaded modules.
    __import__(name)
    module = sys.modules[name]

    value = getattr(module, variable, None)
    if value is None:
        raise RuntimeError('Worker is improperly configured: {} is unset in {}.'.format(variable, module))
    return value
