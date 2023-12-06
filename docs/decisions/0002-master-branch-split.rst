2. Master branch split from 2u/main
------------------------------------------------------------

Status
------

Accepted

Context
-------

Both 2U and the Open edX community use ecommerce-worker's master branch for releases. Occasionally, changes
specific to 2U's business case are merged into code, which also influences the structure
of the code that the community runs, even if the changes are not relevant or beneficial
to the community at large.

Additionally, 2U has internal compliance checks that can slow the release cycle of
major changes to ecommerce-worker (for example, the upgrade to Django 4.2). This puts the Open edX community at risk of releasing
with deprecated packages.

Decision
--------

A new protected branch will be created named "2u/main", which 2U will continue to use
as its own main branch, while leaving the "master" branch for use by the community.

Consequences
------------

This allows the community to move forward with contributions on "master" without risk of
breaking functionality for 2U or 2U committing changes to "master" that are irrelevant or
otherwise inappropriate for the community's use case.

Because protected branches in ecommerce-worker require a user with Write access to the repository,
the "master" branch will now require someone from the community to review and manage
code contributions to that branch.

Additionally, changes pushed to the "2u/main" branch will not be published to PyPI. Tags will still be
made for the "2u/main" branch, but to prevent version collisions with "master", they will be namespaced
with "2u/", much like openedx releases are with "open-release/".

Rejected Alternatives
---------------------

Publishing 2u/main ecommerce-worker to PyPI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Packaging up the "2u/main" branch and publishing it to PyPI would preserve the
current deployment strategy that 2U currently has internally; however, given that
going forward the "2u/main"  branch is intended for internal use only, and PyPI is a
place for public consumption, it no longer appropriate to follow this pattern, especially
when there are other means of installing python requirements (namely, git urls and git tags).

Repo fork
~~~~~~~~~

Why not fork the repo entirely? 2U and the community use a shared set of tools for
working in development environments. While working from separate branches and repo
forks are functionally equivalent, working in separate branches allows for
minimal updates to shared tooling to support this change. One can simply checkout a
branch name, without needing the tooling to be updated to know about non-openedx
git remotes.

This is not a one way door, and if we decide later the a proper repo fork is a better
solution, then we are open to making adjustments.
