#!/bin/bash -xe
. /edx/app/ecomworker/venvs/ecomworker/bin/activate
cd /edx/app/ecomworker/ecomworker
coverage xml
