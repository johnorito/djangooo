"""
Functions for creating and restoring url-safe signed JSON objects.

The format used looks like this:

>>> signing.dumps("hello")
'ImhlbGxvIg:1QaUZC:YIye-ze3TTx7gtSv422nZA4sgmk'

There are two components here, separated by a ':'. The first component is a
URLsafe base64 encoded JSON of the object passed to dumps(). The second
component is a base64 encoded hmac/SHA1 hash of "$first_component:$secret"

signing.loads(s) checks the signature and returns the deserialized object.
If the signature fails, a BadSignature exception is raised.

>>> signing.loads("ImhlbGxvIg:1QaUZC:YIye-ze3TTx7gtSv422nZA4sgmk")
'hello'
>>> signing.loads("ImhlbGxvIg:1QaUZC:YIye-ze3TTx7gtSv422nZA4sgmk-modified")
...
BadSignature: Signature failed: ImhlbGxvIg:1QaUZC:YIye-ze3TTx7gtSv422nZA4sgmk-modified

You can optionally compress the JSON prior to base64 encoding it to save
space, using the compress=True argument. This checks if compression actually
helps and only applies compression if the result is a shorter string:

>>> signing.dumps(list(range(1, 20)), compress=True)
'.eJwFwcERACAIwLCF-rCiILN47r-GyZVJsNgkxaFxoDgxcOHGxMKD_T7vhAml:1QaUaL:BA0thEZrp4FQVXIXuOvYJtLJSrQ'

The fact that the string is compressed is signalled by the prefixed '.' at the
start of the base64 JSON.

There are 65 url-safe characters: the 64 used by url-safe base64 and the ':'.
These functions make use of all of them.
"""

import base64
import datetime
import json
import re
import time
import zlib

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.secret_keys import get_old_keys, get_secret_key
from django.utils import baseconv
from django.utils.crypto import (
    constant_time_any, constant_time_compare, salted_hmac,
)
from django.utils.encoding import force_bytes
from django.utils.module_loading import import_string

_SEP_UNSAFE = re.compile(r'^[A-z0-9-_=]*$')


class BadSignature(Exception):
    """Signature does not match."""
    pass


class SignatureExpired(BadSignature):
    """Signature timestamp is older than required max_age."""
    pass


def b64_encode(s):
    return base64.urlsafe_b64encode(s).strip(b'=')


def b64_decode(s):
    pad = b'=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def base64_hmac(salt, value, key):
    return b64_encode(salted_hmac(salt, value, key).digest()).decode()


def _cookie_signer_key(key):
    return b'django.http.cookies' + force_bytes(key)


def get_cookie_signer(salt='django.core.signing.get_cookie_signer'):
    Signer = import_string(settings.SIGNING_BACKEND)
    return Signer(
        _cookie_signer_key(get_secret_key()),
        salt=salt,
        old_keys=[_cookie_signer_key(k) for k in get_old_keys()],
    )


class JSONSerializer:
    """
    Simple wrapper around json to be used in signing.dumps and
    signing.loads.
    """
    def dumps(self, obj):
        return json.dumps(obj, separators=(',', ':')).encode('latin-1')

    def loads(self, data):
        return json.loads(data.decode('latin-1'))


def dumps(
    obj,
    key=None,
    old_keys=None,
    salt='django.core.signing',
    serializer=JSONSerializer,
    compress=False,
):
    """
    Return URL-safe, hmac/SHA1 signed base64 compressed JSON string. If key is
    None, use the default secret key instead.

    If compress is True (not the default), check if compressing using zlib can
    save some space. Prepend a '.' to signify compression. This is included
    in the signature, to protect against zip bombs.

    Salt can be used to namespace the hash, so that a signed string is
    only valid for a given namespace. Leaving this at the default
    value or re-using a salt value across different parts of your
    application without good cause is a security risk.

    The serializer is expected to return a bytestring.
    """
    data = serializer().dumps(obj)

    # Flag for if it's been compressed or not
    is_compressed = False

    if compress:
        # Avoid zlib dependency unless compress is being used
        compressed = zlib.compress(data)
        if len(compressed) < (len(data) - 1):
            data = compressed
            is_compressed = True
    base64d = b64_encode(data).decode()
    if is_compressed:
        base64d = '.' + base64d
    return TimestampSigner(key, old_keys=old_keys, salt=salt).sign(base64d)


def loads(s, key=None, salt='django.core.signing', serializer=JSONSerializer, max_age=None):
    """
    Reverse of dumps(), raise BadSignature if signature fails.

    The serializer is expected to accept a bytestring.
    """
    # TimestampSigner.unsign() returns str but base64 and zlib compression
    # operate on bytes.
    base64d = TimestampSigner(key, salt=salt).unsign(s, max_age=max_age).encode()
    decompress = base64d[:1] == b'.'
    if decompress:
        # It's compressed; uncompress it first
        base64d = base64d[1:]
    data = b64_decode(base64d)
    if decompress:
        data = zlib.decompress(data)
    return serializer().loads(data)


class Signer:

    def __init__(self, key=None, sep=':', old_keys=None, salt=None):
        if key is None:
            if old_keys is not None:
                raise ImproperlyConfigured('You must specify key when you specify old_keys.')

            self.key = get_secret_key()
            self.old_keys = [self.key] + get_old_keys()
        else:
            self.key = key
            self.old_keys = [key] + (
                [] if old_keys is None else list(old_keys)
            )

        self.sep = sep
        if _SEP_UNSAFE.match(self.sep):
            raise ValueError(
                'Unsafe Signer separator: %r (cannot be empty or consist of '
                'only A-z0-9-_=)' % sep,
            )
        self.salt = salt or '%s.%s' % (self.__class__.__module__, self.__class__.__name__)

    def _signature(self, value, key):
        return base64_hmac(self.salt + 'signer', value, key)

    def signature(self, value):
        return self._signature(value, self.key)

    def sign(self, value):
        return '%s%s%s' % (value, self.sep, self._signature(value, self.key))

    def unsign(self, signed_value):
        if self.sep not in signed_value:
            raise BadSignature('No "%s" found in value' % self.sep)
        value, sig = signed_value.rsplit(self.sep, 1)

        attempts = [
            constant_time_compare(sig, self._signature(value, key))
            for key in self.old_keys
        ]

        if constant_time_any(attempts):
            return value

        raise BadSignature('Signature "%s" does not match' % sig)


class TimestampSigner(Signer):

    def timestamp(self):
        return baseconv.base62.encode(int(time.time()))

    def sign(self, value):
        value = '%s%s%s' % (value, self.sep, self.timestamp())
        return super().sign(value)

    def unsign(self, value, max_age=None):
        """
        Retrieve original value and check it wasn't signed more
        than max_age seconds ago.
        """
        result = super().unsign(value)
        value, timestamp = result.rsplit(self.sep, 1)
        timestamp = baseconv.base62.decode(timestamp)
        if max_age is not None:
            if isinstance(max_age, datetime.timedelta):
                max_age = max_age.total_seconds()
            # Check timestamp is not older than max_age
            age = time.time() - timestamp
            if age > max_age:
                raise SignatureExpired(
                    'Signature age %s > %s seconds' % (age, max_age))
        return value
