"""
Braze-related exception classes.
"""


class BrazeError(Exception):
    """
    Base class for Braze-related errors.
    """


class ConfigurationError(BrazeError):
    """
    Raised when Braze is not properly configured.
    """


class BrazeNotEnabled(BrazeError):
    """
    Raised when Braze is not enabled.
    """


class BrazeClientError(BrazeError):
    """
    Represents any Braze Client Error.
    https://www.braze.com/docs/developer_guide/rest_api/user_data/#user-track-responses
    """


class BrazeRateLimitError(BrazeClientError):
    def __init__(self, reset_epoch_s):
        """
        A rate limit error was encountered.

        Arguments:
            reset_epoch_s (float): Unix timestamp for when the API may be called again.
        """
        self.reset_epoch_s = reset_epoch_s
        super(BrazeRateLimitError, self).__init__()


class BrazeInternalServerError(BrazeClientError):
    """
    Used for Braze API responses where response code is of type 5XX suggesting
    Braze side server errors.
    """
