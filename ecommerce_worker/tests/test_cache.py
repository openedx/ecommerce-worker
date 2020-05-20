"""Tests of cache."""
from __future__ import absolute_import
import logging
from unittest import TestCase

from ecommerce_worker.cache import Cache

log = logging.getLogger(__name__)


class CacheTests(TestCase):
    """
    Tests for the cache routine.
    """

    def test_content_cache(self):
        """
        Test content cache code
        """

        # Create a cache and add 5 items to it
        cache = Cache()
        cache.set('key1', 'value1', 100)
        cache.set('key2', 'value2', 100)
        # set duration to zero or negative so they expire
        cache.set('key3', 'value3', 0)
        cache.set('key4', 'value4', -100)
        cache.set('key5', 'value5', -100)

        # should be 5 to start
        self.assertEqual(len(cache), 5)

        # getting one of the expired should clean out all expired
        self.assertEqual(cache.get('key5'), None)
        # make sure 2 left
        self.assertEqual(len(cache), 2)
        self.assertEqual(cache.get('key2'), 'value2')
        self.assertEqual(cache.get('key1'), 'value1')
        self.assertEqual(cache.get('key3'), None)
