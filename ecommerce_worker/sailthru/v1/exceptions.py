""" Sailthru-related exception classes. """


class SailthruError(Exception):
    """ Base class for Sailthru-related errors. """
    pass


class ConfigurationError(SailthruError):
    """ Raised when Sailthru is not properly configured. """
    pass


class SailthruNotEnabled(SailthruError):
    """ Raised when Sailthru is not enabled. """
    pass
