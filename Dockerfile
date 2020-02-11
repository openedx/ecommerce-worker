FROM ubuntu:xenial as openedx

RUN apt update && \
  apt install -y git-core language-pack-en python python-pip python-dev && \
  pip install --upgrade pip setuptools && \
  rm -rf /var/lib/apt/lists/*

RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

WORKDIR /edx/app/ecommerce_worker
COPY requirements /edx/app/ecommerce_worker/requirements
RUN pip install -r requirements/production.txt

ENV WORKER_CONFIGURATION_MODULE ecommerce_worker.configuration.production
CMD celery worker --app=ecommerce_worker.celery_app:app --loglevel=info  --maxtasksperchild 100 --queue=fulfillment,email_marketing

RUN useradd -m --shell /bin/false app
USER app

COPY . /edx/app/ecommerce_worker


FROM openedx as edx.org
RUN pip install newrelic
CMD newrelic-admin run-program celery worker --app=ecommerce_worker.celery_app:app --loglevel=info  --maxtasksperchild 100 --queue=fulfillment,email_marketing
