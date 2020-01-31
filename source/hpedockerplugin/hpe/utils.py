# Copyright (c) 2012 OpenStack Foundation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Volume-related Utilities and helpers."""

from Crypto.Random import random

# Default symbols to use for passwords. Avoids visually confusing characters.
# ~6 bits per symbol
DEFAULT_PASSWORD_SYMBOLS = ('23456789',  # Removed: 0,1
                            'ABCDEFGHJKLMNPQRSTUVWXYZ',   # Removed: I, O
                            'abcdefghijkmnopqrstuvwxyz')  # Removed: l


def generate_password(length=16, symbolgroups=DEFAULT_PASSWORD_SYMBOLS):
    """Generate a random password from the supplied symbol groups.
    At least one symbol from each group will be included. Unpredictable
    results if length is less than the number of symbol groups.
    Believed to be reasonably secure (with a reasonable password length!)
    """
    # NOTE(jerdfelt): Some password policies require at least one character
    # from each group of symbols, so start off with one random character
    # from each symbol group
    password = [random.choice(s) for s in symbolgroups]
    # If length < len(symbolgroups), the leading characters will only
    # be from the first length groups. Try our best to not be predictable
    # by shuffling and then truncating.
    random.shuffle(password)
    password = password[:length]
    length -= len(password)

    # then fill with random characters from all symbol groups
    symbols = ''.join(symbolgroups)
    password.extend([random.choice(symbols) for _i in range(length)])

    # finally shuffle to ensure first x characters aren't from a
    # predictable group
    random.shuffle(password)

    return ''.join(password)
