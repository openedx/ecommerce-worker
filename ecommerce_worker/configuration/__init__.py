import os


# Environment variable indicating which configuration module to use
# when running the worker.
CONFIGURATION_MODULE = 'WORKER_CONFIGURATION_MODULE'


def get_overrides_filename(variable):
    """
    Get the name of the file containing configuration overrides
    from the provided environment variable.
    """
    filename = os.environ.get(variable)

    if filename is None:
        msg = f'Please set the {variable} environment variable.'
        raise EnvironmentError(msg)

    return filename
