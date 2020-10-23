"""
This file contains a primitive cache
"""
from __future__ import absolute_import
import threading
import time

lock = threading.Lock()  # pylint: disable=invalid-name


class CacheObject:
    """Object saved in cache"""
    def __init__(self, value, duration):
        self.value = value
        self.expire = time.time() + duration


class Cache(dict):
    """
    Primitive key/value cache.  Entries are kept in a dict with an expiration.
    When a get of an expired entry is done, the cache is cleaned of all expired entries.
    Locking is used for thread safety
    """
    def get(self, key):
        """Get an object from the cache

        Arguments:
            key (str): Cache key

        Returns:
            Cached object
        """
        lock.acquire()
        try:
            if key not in self:
                return None

            current_time = time.time()
            if self[key].expire > current_time:
                return self[key].value

            # expired key, clean out all expired keys
            deletes = []
            for k, val in self.items():
                if val.expire <= current_time:
                    deletes.append(k)
            for k in deletes:
                del self[k]

            return None
        finally:
            lock.release()

    def set(self, key, value, duration):
        """Save an object in the cache

        Arguments:
            key (str): Cache key
            value (object): object to cache
            duration (int): time in seconds to keep object in cache

        """
        lock.acquire()
        try:
            self[key] = CacheObject(value, duration)
        finally:
            lock.release()
