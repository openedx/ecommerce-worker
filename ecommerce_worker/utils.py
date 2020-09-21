"""Helper functions."""
from __future__ import absolute_import
import os
import sys

from edx_rest_api_client.client import EdxRestApiClient

from ecommerce_worker.configuration import CONFIGURATION_MODULE


def get_configuration(variable, site_code=None):
    """
    Get a value from configuration.

    Retrieves the value corresponding to the given variable from the configuration module
    currently in use by the app.  Specify a site_code value to check for a site-specific override.

    Arguments:
        variable (str): The name of a variable from the configuration module.

    Keyword Arguments:
        site_code (str): The SITE_OVERRIDES key to inspect for site-specific values

    Returns:
        The value corresponding to the variable, or None if the variable is not found.
    """
    name = os.environ.get(CONFIGURATION_MODULE)

    # __import__ performs a full import, but only returns the top-level
    # package, not the targeted module. sys.modules is a dictionary
    # mapping module names to loaded modules.
    __import__(name)
    module = sys.modules[name]

    # Locate the setting in the specified module, then attempt to apply a site-specific override
    setting_value = getattr(module, variable, None)
    site_overrides = getattr(module, 'SITE_OVERRIDES', None)
    if site_overrides and site_code is not None:
        site_specific_overrides = site_overrides.get(site_code)
        if site_specific_overrides:
            override_value = site_specific_overrides.get(variable)
            if override_value:
                setting_value = override_value

    if setting_value is None:
        raise RuntimeError('Worker is improperly configured: {} is unset in {}.'.format(variable, module))
    return setting_value


def get_ecommerce_client(url_postfix='', site_code=None):
    """
    Get client for fetching data from ecommerce API.
    Arguments:
        site_code (str): (Optional) The SITE_OVERRIDES key to inspect for site-specific values
        url_postfix (str): (Optional) The URL postfix value to append to the ECOMMERCE_API_ROOT value.

    Returns:
        EdxRestApiClient object
    """
    ecommerce_api_root = get_configuration('ECOMMERCE_API_ROOT', site_code=site_code)
    signing_key = get_configuration('JWT_SECRET_KEY', site_code=site_code)
    issuer = get_configuration('JWT_ISSUER', site_code=site_code)
    service_username = get_configuration('ECOMMERCE_SERVICE_USERNAME', site_code=site_code)
    return EdxRestApiClient(
        ecommerce_api_root + url_postfix, signing_key=signing_key, issuer=issuer, username=service_username)
