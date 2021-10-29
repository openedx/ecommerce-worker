## Anyone merging to this repository is expected to [release and monitor their changes](https://openedx.atlassian.net/wiki/spaces/RS/pages/1835106870/How+to+contribute+to+our+repositories); if you are not able to do this DO NOT MERGE, please coordinate with someone who can to ensure that the changes are released.

**Merge checklist:**
- [ ] Any new requirements are in the right place (do **not** manually modify the `requirements/*.txt` files)
    - `base.in` if needed in production
    - `test.in` for test requirements
    - `make upgrade && make requirements` have been run to regenerate requirements
- [ ] [Version](https://github.com/edx/ecommerce-worker/blob/master/setup.py) bumped

**Post merge:**
- [ ] Tag pushed and a new [version](https://github.com/edx/ecommerce-worker/releases) released
    - *Note*: Assets will be added automatically. You just need to provide a tag (should match your version number) and title and description.
- [ ] After versioned build finishes in [GitHub CI](https://github.com/edx/ecommerce-worker/actions?query=workflow%3A%22Python+CI%22), verify version has been pushed to [PyPI](https://pypi.org/project/edx-ecommerce-worker/)
    - Each step in the release build has a condition flag that checks if the rest of the steps are done and if so will deploy to PyPi.
    (so basically once your build finishes, after maybe a minute you should see the new version in PyPi automatically (on refresh))
- [ ] PR created in [ecommerce](https://github.com/edx/ecommerce) to upgrade dependencies (including ecommerce-worker)
    - This **must** be done after the version is visible in PyPi as `make upgrade` in ecommerce will look for the latest version in PyPi.
    - Note: the ecommerce-worker constraint in ecommerce **must** also be bumped to the latest version in PyPi.
- [ ] Deploy `ecommerce`
- [ ] Deploy `ecomworker` on GoCD.
    - While some functions in ecommerce-worker are run via ecommerce, others are handled by a standalone AMI and must be
      released via GoCD.
