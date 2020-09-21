PACKAGE = ecommerce_worker
PYTHON_VERSION = py27

help:
	@echo '                                                                                             '
	@echo 'Makefile for the edX ecommerce worker project.                                               '
	@echo '                                                                                             '
	@echo 'Usage:                                                                                       '
	@echo '    make help                         display this message                                   '
	@echo '    make requirements                 install requirements for local development             '
	@echo '    make worker                       start the Celery worker process                        '
	@echo '    make test                         run unit tests and report on coverage                  '
	@echo '    make html_coverage                generate and view HTML coverage report                 '
	@echo '    make quality                      run pep8 and pylint                                    '
	@echo '    make validate                     run tests and quality checks                           '
	@echo '    make clean                        delete generated byte code and coverage reports        '
	@echo '                                                                                             '

requirements:
	pip install -r requirements/test.txt

requirements_tox:
	pip install -r requirements/tox.txt

worker:
	celery -A ecommerce_worker worker --app=$(PACKAGE).celery_app:app --loglevel=info --queue=fulfillment,email_marketing

test: requirements_tox
	tox -e ${PYTHON_VERSION}

quality: requirements_tox
	tox -e quality

validate: clean test quality

clean:
	find . -name '*.pyc' -delete
	coverage erase
	rm -rf cover htmlcov

export CUSTOM_COMPILE_COMMAND = make upgrade
upgrade: ## update the requirements/*.txt files with the latest packages satisfying requirements/*.in
	pip install -q -r requirements/pip_tools.txt
	pip-compile --rebuild --upgrade -o requirements/pip_tools.txt requirements/pip_tools.in
	pip-compile --upgrade -o requirements/tox.txt requirements/tox.in
	pip-compile --upgrade -o requirements/base.txt requirements/base.in
	pip-compile --upgrade -o requirements/test.txt requirements/test.in
	pip-compile --upgrade -o requirements/optional.txt requirements/optional.in
	pip-compile --upgrade -o requirements/production.txt requirements/production.in
	# Let tox control the Django version for tests
	sed '/^[dD]jango==/d;/^edx-rest-api-client==/d' requirements/test.txt > requirements/test.tmp
	mv requirements/test.tmp requirements/test.txt

.PHONY: help requirements worker test html_coverage quality validate clean upgrade
