"""Helper functions."""
import os
import sys
from urllib.parse import urljoin

import requests
from edx_rest_api_client.client import REQUEST_CONNECT_TIMEOUT, REQUEST_READ_TIMEOUT
from requests.exceptions import HTTPError, RequestException

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
        raise RuntimeError(f'Worker is improperly configured: {variable} is unset in {module}.')
    return setting_value


def get_access_token():
    """
    Returns an access token for this site's service user.

    Returns:
        str: JWT access token
    """
    oauth_access_token_url = urljoin(
        get_configuration('BACKEND_SERVICE_EDX_OAUTH2_PROVIDER_URL') + '/', 'access_token/'
    )
    try:
        post_data = {
            'grant_type': 'client_credentials',
            'client_id': get_configuration('BACKEND_SERVICE_EDX_OAUTH2_KEY'),
            'client_secret': get_configuration('BACKEND_SERVICE_EDX_OAUTH2_SECRET'),
            'token_type': 'jwt',
        }
        headers = {
            'User-Agent': 'ecommerce-worker',
        }
        response = requests.post(
            oauth_access_token_url,
            data=post_data,
            headers=headers,
            timeout=(REQUEST_CONNECT_TIMEOUT, REQUEST_READ_TIMEOUT)
        )
        response.raise_for_status()
        data = response.json()
        access_token = data['access_token']
    except (HTTPError, KeyError) as exc:
        raise RequestException(response=response) from exc

    return access_token
