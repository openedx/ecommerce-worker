"""Logging configuration"""
from logging.handlers import SysLogHandler
import os
import platform
import sys


def get_logger_config(log_dir='/var/tmp',
                      logging_env='no_env',
                      edx_filename='edx.log',
                      dev_env=False,
                      debug=False,
                      local_loglevel='INFO',
                      service_variant='ecomworker'):

    """
    Returns a dictionary containing logging configuration.

    If dev_env is True, logging will not be done via local rsyslogd.
    Instead, application logs will be dropped into log_dir. 'edx_filename'
    is ignored unless dev_env is True.
    """
    # Revert to INFO if an invalid string is passed in
    if local_loglevel not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        local_loglevel = 'INFO'

    hostname = platform.node().split('.')[0]
    syslog_format = (
        '[service_variant={service_variant}]'
        '[%(name)s][env:{logging_env}] %(levelname)s '
        '[{hostname}  %(process)d] [%(filename)s:%(lineno)d] '
        '- %(message)s'
    ).format(
        service_variant=service_variant,
        logging_env=logging_env, hostname=hostname
    )

    if debug:
        handlers = ['console']
    else:
        handlers = ['local']

    logger_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s %(levelname)s %(process)d '
                          '[%(name)s] %(filename)s:%(lineno)d - %(message)s',
            },
            'syslog_format': {'format': syslog_format},
            'raw': {'format': '%(message)s'},
        },
        'handlers': {
            'console': {
                'level': 'DEBUG' if debug else 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
                'stream': sys.stdout,
            },
        },
        'loggers': {
            'requests': {
                'handlers': handlers,
                'level': 'WARNING',
                'propagate': True
            },
            '': {
                'handlers': handlers,
                'level': 'DEBUG',
                'propagate': False
            },
        }
    }

    if dev_env:
        edx_file_loc = os.path.join(log_dir, edx_filename)
        logger_config['handlers'].update({
            'local': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': local_loglevel,
                'formatter': 'standard',
                'filename': edx_file_loc,
                'maxBytes': 1024 * 1024 * 2,
                'backupCount': 5,
            },
        })
    else:
        logger_config['handlers'].update({
            'local': {
                'level': local_loglevel,
                'class': 'logging.handlers.SysLogHandler',
                # Use a different address for Mac OS X
                'address': '/var/run/syslog' if sys.platform == 'darwin' else '/dev/log',
                'formatter': 'syslog_format',
                'facility': SysLogHandler.LOG_LOCAL0,
            },
        })

    return logger_config
