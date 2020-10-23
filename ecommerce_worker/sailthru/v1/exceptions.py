""" Sailthru-related exception classes. """


class SailthruError(Exception):
    """ Base class for Sailthru-related errors. """


class ConfigurationError(SailthruError):
    """ Raised when Sailthru is not properly configured. """


class SailthruNotEnabled(SailthruError):
    """ Raised when Sailthru is not enabled. """
