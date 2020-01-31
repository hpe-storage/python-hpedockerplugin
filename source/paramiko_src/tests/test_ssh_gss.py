# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
# Copyright (C) 2013-2014 science + computing ag
# Author: Sebastian Deiss <sebastian.deiss@t-online.de>
#
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Unit Tests for the GSS-API / SSPI SSHv2 Authentication (gssapi-with-mic)
"""

import socket
import threading
import unittest

import paramiko

from tests.util import test_path
from tests.test_client import FINGERPRINTS

class NullServer (paramiko.ServerInterface):

    def get_allowed_auths(self, username):
        return 'gssapi-with-mic,publickey'

    def check_auth_gssapi_with_mic(self, username,
                                   gss_authenticated=paramiko.AUTH_FAILED,
                                   cc_file=None):
        if gss_authenticated == paramiko.AUTH_SUCCESSFUL:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def enable_auth_gssapi(self):
        return True

    def check_auth_publickey(self, username, key):
        try:
            expected = FINGERPRINTS[key.get_name()]
        except KeyError:
            return paramiko.AUTH_FAILED
        else:
            if key.get_fingerprint() == expected:
                return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED

    def check_channel_exec_request(self, channel, command):
        if command != 'yes':
            return False
        return True


class GSSAuthTest(unittest.TestCase):
    @staticmethod
    def init(username, hostname):
        global krb5_principal, targ_name
        krb5_principal = username
        targ_name = hostname

    def setUp(self):
        self.username = krb5_principal
        self.hostname = socket.getfqdn(targ_name)
        self.sockl = socket.socket()
        self.sockl.bind((targ_name, 0))
        self.sockl.listen(1)
        self.addr, self.port = self.sockl.getsockname()
        self.event = threading.Event()
        thread = threading.Thread(target=self._run)
        thread.start()

    def tearDown(self):
        for attr in "tc ts socks sockl".split():
            if hasattr(self, attr):
                getattr(self, attr).close()

    def _run(self):
        self.socks, addr = self.sockl.accept()
        self.ts = paramiko.Transport(self.socks)
        host_key = paramiko.RSAKey.from_private_key_file('tests/test_rsa.key')
        self.ts.add_server_key(host_key)
        server = NullServer()
        self.ts.start_server(self.event, server)

    def _test_connection(self, **kwargs):
        """
        (Most) kwargs get passed directly into SSHClient.connect().

        The exception is ... no exception yet
        """
        host_key = paramiko.RSAKey.from_private_key_file('tests/test_rsa.key')
        public_host_key = paramiko.RSAKey(data=host_key.asbytes())

        self.tc = paramiko.SSHClient()
        self.tc.set_missing_host_key_policy(paramiko.WarningPolicy())
        self.tc.get_host_keys().add('[%s]:%d' % (self.addr, self.port),
                                    'ssh-rsa', public_host_key)
        self.tc.connect(hostname=self.addr, port=self.port, username=self.username, gss_host=self.hostname,
                        gss_auth=True, **kwargs)

        self.event.wait(1.0)
        self.assert_(self.event.is_set())
        self.assert_(self.ts.is_active())
        self.assertEquals(self.username, self.ts.get_username())
        self.assertEquals(True, self.ts.is_authenticated())

        stdin, stdout, stderr = self.tc.exec_command('yes')
        schan = self.ts.accept(1.0)

        schan.send('Hello there.\n')
        schan.send_stderr('This is on stderr.\n')
        schan.close()

        self.assertEquals('Hello there.\n', stdout.readline())
        self.assertEquals('', stdout.readline())
        self.assertEquals('This is on stderr.\n', stderr.readline())
        self.assertEquals('', stderr.readline())

        stdin.close()
        stdout.close()
        stderr.close()

    def test_1_gss_auth(self):
        """
        Verify that Paramiko can handle SSHv2 GSS-API / SSPI authentication
        (gssapi-with-mic) in client and server mode.
        """
        self._test_connection(allow_agent=False,
                              look_for_keys=False)

    def test_2_auth_trickledown(self):
        """
        Failed gssapi-with-mic auth doesn't prevent subsequent key auth from succeeding
        """
        self.hostname = "this_host_does_not_exists_and_causes_a_GSSAPI-exception"
        self._test_connection(key_filename=[test_path('test_rsa.key')],
                              allow_agent=False,
                              look_for_keys=False)
