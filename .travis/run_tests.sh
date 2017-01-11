#!/bin/bash -xe
. /edx/app/ecomworker/venvs/ecomworker/bin/activate

cd /edx/app/ecomworker/ecomworker

make requirements

# Run validation
make validate
