"""Helper functions."""
import json
import os
import sys

import requests
from edx_rest_api_client.client import REQUEST_READ_TIMEOUT, REQUEST_CONNECT_TIMEOUT

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
    The access token is retrieved using the current site's OAuth credentials and the client credentials grant.
    The token is cached for the lifetime of the token, as specified by the OAuth provider's response. The token
    type is JWT.

    Returns:
        str: JWT access token
    """

    oauth_access_token_url = f"{get_configuration('BACKEND_SERVICE_EDX_OAUTH2_PROVIDER_URL')}/access_token/"
    response = requests.post(
        oauth_access_token_url,
        data={
            'grant_type': 'client_credentials',
            'client_id': get_configuration('BACKEND_SERVICE_EDX_OAUTH2_KEY'),
            'client_secret': get_configuration('BACKEND_SERVICE_EDX_OAUTH2_SECRET'),
            'token_type': 'jwt',
        },
        headers={
            'User-Agent': 'ecommerce-worker',
        },
        timeout=(REQUEST_CONNECT_TIMEOUT, REQUEST_READ_TIMEOUT)
    )

    try:
        data = response.json()
        access_token = data['access_token']

    except (KeyError, json.decoder.JSONDecodeError) as json_error:
        raise requests.RequestException(response=response) from json_error
    return access_token
