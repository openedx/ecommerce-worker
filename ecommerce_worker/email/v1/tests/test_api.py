""" Tests for api entry point. """

from inspect import getmembers
from unittest import TestCase

from ecommerce_worker.email.v1 import api


class EmailApiTests(TestCase):
    """Tests for email v1 api entry point."""

    def test_public_api(self):
        """
        Test that we don't accidentally expose anything we don't expect to
        """
        assert [k for k, v in getmembers(api) if not k.startswith('_')] == [
            'did_email_bounce',
            'send_code_assignment_nudge_email',
            'send_offer_assignment_email',
            'send_offer_update_email',
            'send_offer_usage_email',
        ]
