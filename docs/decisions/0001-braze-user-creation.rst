Braze User Creation For Potential Learners
------------------------------------------

Status
======

Draft

Context
=======

EdX Enterprise theme has been using Sailthru for emails to learners and potential learners. Since the potential learners do not yet have an account on the edX platform, their account on Sailthru is created when an email is initiated to their email address. This account creation is automatically performed by Sailthru.

With transition to Braze as the multi-channel communication and analytics platform, the account creation for the potential learners would be initiated from the edX platform. This is necessitated by the user onboarding flow in Braze.

The Braze configuration for edX has a mapping for the `lms_user_id` field in LMS to Braze's `external_user_id field`. In case of unavailability of the `external_user_id`, Braze also has a user alias object that can be used to identify a user. Each user alias consists of two parts: a label, which defines the key of the alias, and a name, which defines the value. An alias name for any single label must be unique across the user base. More details at https://www.braze.com/docs/user_guide/data_and_analytics/user_data_collection/user_profile_lifecycle/

Decisions
=========

#. For potential enterprise learners, if an alias is to be created, the label would hold the value 'Enterprise' and the key would be their email address.
e.g.
  "user_alias" : {
      "alias_name" : "Enterprise",
      "alias_label" : "someuser@someorg.org"
  }

#. Since the potential learners do not have an `lms_user_id`, the `external_user_id` can be temporarily mapped to their email address with an Enterprise prefix.
e.g. 'external_user_id': 'Enterprise-someemail@someemail.com'

#. A batch job would periodically remove the duplicate accounts in Braze for the potential learners once they graduate to learner status in edX.

Consequences
============

#. Potential users can be sent emails via the Braze system. Sailthru can be discontinued.
#. Duplicate accounts in Braze would need to be removed once potential learners graduate to learner status.
#. PII data management would need to be performed for potential learners who do not become learners.
