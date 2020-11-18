edX Ecommerce Worker  |Travis|_ |Codecov|_
==========================================
.. |Travis| image:: https://travis-ci.com/edx/ecommerce-worker.svg?branch=master
.. _Travis: https://travis-ci.com/edx/ecommerce-worker

.. |Codecov| image:: http://codecov.io/github/edx/ecommerce-worker/coverage.svg?branch=master
.. _Codecov: http://codecov.io/github/edx/ecommerce-worker?branch=master

The Celery tasks contained herein are used to implement asynchronous order fulfillment and other features requiring the asynchronous execution of many small, common operations.

Prerequisites
-------------
* Python 3.x
* Celery 4.x
* RabbitMQ 3.5.x

Getting Started
---------------

Most commands necessary to develop and run this app can be found in the included Makefile. These instructions assume a working integration between the `edX ecommerce service <https://github.com/edx/ecommerce>`_ and the LMS, with asynchronous fulfillment configured on the ecommerce service.

To get started, create a new virtual environment and install the included requirements.

    $ make requirements

This project uses `Celery <http://celery.readthedocs.org/en/latest/>`_ to asynchronously execute tasks, such as those required during order fulfillment. Celery requires a solution to send and receive messages which typically comes in the form of a separate service called a message broker. This project uses `RabbitMQ <http://www.rabbitmq.com/>`_ as a message broker. On OS X, use Homebrew to install it.

    $ brew install rabbitmq

By default, most operating systems don't allow enough open files for a message broker. RabbitMQ's docs indicate that allowing at least 4096 file descriptors should be sufficient for most development workloads. Check the limit on the number of file descriptors in your current process.

    $ ulimit -n

If it needs to be adjusted, run:

    $ ulimit -n 4096

Next, start the RabbitMQ server.

    $ rabbitmq-server

In a separate process, start the Celery worker.

    $ make worker

In a third process, start the ecommerce service. In order for tasks to be visible to the ecommerce worker, the value of Celery's ``BROKER_URL`` setting must shared by the ecommerce service and the ecommerce worker.

Finally, in a fourth process, start the LMS. At this point, if you attempt to enroll in a course supported by the ecommerce service, enrollment will be handled asynchronously by the ecommerce worker.

If you're forced to shut down the Celery workers prematurely, tasks may remain in the queue. To clear them, you can reset RabbitMQ.

    $ rabbitmqctl stop_app
    $ rabbitmqctl reset
    $ rabbitmqctl start_app

License
-------

The code in this repository is licensed under the AGPL unless otherwise noted. Please see ``LICENSE.txt`` for details.

How To Contribute
-----------------

Contributions are welcome. Please read `How To Contribute <https://github.com/edx/edx-platform/blob/master/CONTRIBUTING.rst>`_ for details. Even though it was written with ``edx-platform`` in mind, these guidelines should be followed for Open edX code in general.

Reporting Security Issues
-------------------------

Please do not report security issues in public. Please email security@edx.org.

Mailing List and IRC Channel
----------------------------

You can discuss this code in the `edx-code Google Group <https://groups.google.com/forum/#!forum/edx-code>`_ or in the ``#edx-code`` IRC channel on Freenode.
