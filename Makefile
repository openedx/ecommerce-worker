PACKAGE = ecommerce_worker
PYTHON_VERSION_VAR=$(if $(PYTHON_VERSION),$(PYTHON_VERSION),3.12)
PYTHON_ENV_VAR=$(if $(PYTHON_ENV),$(PYTHON_ENV),py312)

help: ## display this help message
	@echo "Please use \`make <target>' where <target> is one of"
	@grep '^[a-zA-Z]' $(MAKEFILE_LIST) | sort | awk -F ':.*?## ' 'NF==2 {printf "\033[36m  %-25s\033[0m %s\n", $$1, $$2}'

requirements:  ## install requirements for local development
	pip3 install -r requirements/test.txt

requirements_tox:  ## install tox requirements
	pip3 install -r requirements/tox.txt

worker: ## start the Celery worker process
	celery -A ecommerce_worker worker --app=$(PACKAGE).celery_app:app --loglevel=info --queue=fulfillment,email_marketing

test: requirements_tox  ## run unit tests and report on coverage
	python${PYTHON_VERSION_VAR} -m tox -e ${PYTHON_ENV_VAR}

quality: requirements_tox  ## run pep8 and pylint
	tox -e quality

validate: clean test quality  ## run tests and quality checks

clean:  ## delete generated byte code and coverage reports
	find . -name '*.pyc' -delete
	coverage erase
	rm -rf cover htmlcov

COMMON_CONSTRAINTS_TXT=requirements/common_constraints.txt
.PHONY: $(COMMON_CONSTRAINTS_TXT)
$(COMMON_CONSTRAINTS_TXT):
	wget -O "$(@)" https://raw.githubusercontent.com/edx/edx-lint/master/edx_lint/files/common_constraints.txt || touch "$(@)"

export CUSTOM_COMPILE_COMMAND = make upgrade
upgrade:  $(COMMON_CONSTRAINTS_TXT)
	## update the requirements/*.txt files with the latest packages satisfying requirements/*.in
	pip install -q -r requirements/pip_tools.txt
	pip-compile --allow-unsafe --rebuild --upgrade -o requirements/pip.txt requirements/pip.in
	pip-compile --rebuild --upgrade -o requirements/pip_tools.txt requirements/pip_tools.in
	pip install -q -r requirements/pip.txt
	pip install -q -r requirements/pip_tools.txt
	pip-compile --upgrade -o requirements/tox.txt requirements/tox.in
	pip-compile --upgrade -o requirements/base.txt requirements/base.in
	pip-compile --upgrade -o requirements/test.txt requirements/test.in
	pip-compile --upgrade -o requirements/optional.txt requirements/optional.in
	pip-compile --upgrade -o requirements/production.txt requirements/production.in
	# Let tox control the Django version for tests
	sed '/^[dD]jango==/d' requirements/test.txt > requirements/test.tmp
	mv requirements/test.tmp requirements/test.txt

.PHONY: help requirements worker test html_coverage quality validate clean upgrade
