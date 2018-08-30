# (c) Copyright [2016] Hewlett Packard Enterprise Development LP
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import os
import time

from io import BytesIO

from zope.interface import implementer

from twisted.internet.endpoints import UNIXClientEndpoint
from twisted.web.iweb import IAgentEndpointFactory
from twisted.web.client import Agent, readBody, FileBodyProducer

from twisted.internet import reactor
from twisted.web.http_headers import Headers
import json
from json import dumps

from twisted.trial import unittest
import subprocess
from sh import cat
from sh import kill

from config.setupcfg import getdefaultconfig, setup_logging
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

CONFIG_FILE = '/etc/hpedockerplugin/hpe.conf'
CONFIG = ['--config-file', CONFIG_FILE]

TEST_DIR = os.path.abspath('../')
TWISTD_PID = TEST_DIR + '/twistd.pid'

hpe_sock_path = b"/run/docker/plugins/hpe/hpe.sock"


@implementer(IAgentEndpointFactory)
class HPEEndpointFactory(object):
    """
    Connect to hpe3's Unix socket.
    """
    def __init__(self):
        self.reactor = reactor

    def endpointForURI(self, uri):
        return UNIXClientEndpoint(self.reactor, hpe_sock_path)


class HPEPLUGINTESTS(unittest.TestCase):
    def _wait_for_pid_file(self, filename, wait_time):
        count = 0
        while not os.path.exists(filename):
            if count == wait_time:
                break
            time.sleep(1)
            count += 1

        if os.path.isfile(filename):
            self.twistd_pid = cat(filename)
            print('self.twistd_pid: %d ' % (self.twistd_pid))
        else:
            raise ValueError("%s isn't a file!" % filename)

    def checkResponse(self, response, exp_result):
        # TODO: convert to log messages
        """
        print 'Response version:', response.version
        print 'Response code:', response.code
        print 'Response phrase:', response.phrase
        print 'Response headers:'
        print pformat(list(response.headers.getAllRawHeaders()))
        """
        """
        LOG.debug("Response Body %s", str(response.version))
        LOG.debug("Response Body %s", str(response.code))
        LOG.debug("Response Body %s", str(response.phrase))
        LOG.debug("Response Body %s",
                  str(list(response.headers.getAllRawHeaders())))
        LOG.debug("Expected Results %s", str(exp_result))
        """

        d = readBody(response)
        d.addCallback(self.assertResponse, exp_result)
        return d

    def getResponse(self, response):
        # TODO: convert to log messages
        """
        print 'Response version:', response.version
        print 'Response code:', response.code
        print 'Response phrase:', response.phrase
        print 'Response headers:'
        print pformat(list(response.headers.getAllRawHeaders()))
        """
        """
        LOG.debug("Response Body %s", str(response.version))
        LOG.debug("Response Body %s", str(response.code))
        LOG.debug("Response Body %s", str(response.phrase))
        LOG.debug("Response Body %s",
                  str(list(response.headers.getAllRawHeaders())))
        LOG.debug("Expected Results %s", str(exp_result))
        """

        d = readBody(response)
        return d

    def assertResponse(self, body, exp_result):
        LOG.debug("Response Body %s", str(body))
        LOG.debug("Expected Results %s", str(exp_result))
        self.assertEqual(body, exp_result)

    def cbFailed(self, failure):
        LOG.error("Test Failed %s", str(failure))
        self.fail(msg='Test Failed')

    """
    Connect to hpe3's Unix socket.
    """
    def setUp(self):
        # Setup Test Logging
        # Set Logging level
        # Setup the default, hpe3parconfig, and hpelefthandconfig
        # configuration objects.
        hpedefaultconfig = getdefaultconfig(CONFIG)

        logging_level = hpedefaultconfig.logging
        setup_logging('test_hpe_plugin', logging_level)

        # Start HPE Docker Plugin
        bashcommand = "/bin/twistd hpe_plugin_service"
        try:
            subprocess.check_output(['sh', '-c', bashcommand], cwd=TEST_DIR)
        except Exception:
            LOG.error("Test Setup Failed: Could not change dir")
            self.fail(msg='Test Failed')

        self._wait_for_pid_file(TWISTD_PID, 5)

    def tearDown(self):
        # Stop HPE Docker Plugin
        kill(str(self.twistd_pid))

        is_running = os.path.exists("/proc/%s" % str(self.twistd_pid))
        while is_running:
            is_running = os.path.exists("/proc/%s" % str(self.twistd_pid))
            time.sleep(0.25)

    def test_hpe_activate(self):
        path = b"/Plugin.Activate"
        agent = Agent.usingEndpointFactory(reactor, HPEEndpointFactory())
        d = agent.request(b'POST', b"UNIX://localhost" + path)
        d.addCallback(self.checkResponse, json.dumps({u"Implements":
                                                     [u"VolumeDriver"]}))
        d.addErrback(self.cbFailed)
        return d

    def test_hpe_create_volume(self):
        name = 'test-create-volume'
        path = b"/VolumeDriver.Create"
        body = {u"Name": name,
                u"Opts": None}

        headers = Headers({b"content-type": [b"application/json"]})
        body_producer = FileBodyProducer(BytesIO(dumps(body)))
        agent = Agent.usingEndpointFactory(reactor, HPEEndpointFactory())
        d = agent.request(b'POST', b"UNIX://localhost" + path, headers,
                          body_producer)
        d.addCallback(self.checkResponse, json.dumps({u"Err": ''}))
        d.addErrback(self.cbFailed)
        return d

    def test_hpe_create_volume_size_option(self):
        name = 'test-create-volume'
        path = b"/VolumeDriver.Create"
        body = {u"Name": name,
                u"Opts": {u"size": u"50"}}

        headers = Headers({b"content-type": [b"application/json"]})
        body_producer = FileBodyProducer(BytesIO(dumps(body)))
        agent = Agent.usingEndpointFactory(reactor, HPEEndpointFactory())
        d = agent.request(b'POST', b"UNIX://localhost" + path, headers,
                          body_producer)
        d.addCallback(self.checkResponse, json.dumps({u"Err": ''}))
        d.addCallback(self._remove_volume_callback, name)
        d.addErrback(self.cbFailed)
        return d

    def test_hpe_create_volume_provisioning_option(self):
        name = 'test-create-volume'
        path = b"/VolumeDriver.Create"
        body = {u"Name": name,
                u"Opts": {u"provisioning": u"full"}}

        headers = Headers({b"content-type": [b"application/json"]})
        body_producer = FileBodyProducer(BytesIO(dumps(body)))
        agent = Agent.usingEndpointFactory(reactor, HPEEndpointFactory())
        d = agent.request(b'POST', b"UNIX://localhost" + path, headers,
                          body_producer)
        d.addCallback(self.checkResponse, json.dumps({u"Err": ''}))
        d.addCallback(self._remove_volume_callback, name)
        d.addErrback(self.cbFailed)
        return d

    def test_hpe_create_volume_invalid_provisioning_option(self):
        name = 'test-create-volume-fake'
        path = b"/VolumeDriver.Create"
        body = {u"Name": name,
                u"Opts": {u"provisioning": u"fake"}}

        headers = Headers({b"content-type": [b"application/json"]})
        body_producer = FileBodyProducer(BytesIO(dumps(body)))
        agent = Agent.usingEndpointFactory(reactor, HPEEndpointFactory())
        d = agent.request(b'POST', b"UNIX://localhost" + path, headers,
                          body_producer)
        d.addCallback(self.checkResponse, json.dumps({
            u"Err": "Invalid input received: Must specify a valid " +
            "provisioning type ['thin', 'full', " +
            "'dedup'], value 'fake' is invalid."}))
        d.addCallback(self._remove_volume_callback, name)
        d.addErrback(self.cbFailed)
        return d

    def test_hpe_create_volume_invalid_option(self):
        name = 'test-create-volume-fake'
        path = b"/VolumeDriver.Create"
        body = {u"Name": name,
                u"Opts": {u"fake": u"fake"}}

        headers = Headers({b"content-type": [b"application/json"]})
        body_producer = FileBodyProducer(BytesIO(dumps(body)))
        agent = Agent.usingEndpointFactory(reactor, HPEEndpointFactory())
        d = agent.request(b'POST', b"UNIX://localhost" + path, headers,
                          body_producer)
        d.addCallback(self.checkResponse, json.dumps({
            u"Err": "create volume failed, error is: fake is not a valid "
            "option. Valid options are: ['size', 'provisioning', "
            "'flash-cache']"}))
        d.addCallback(self._remove_volume_callback, name)
        d.addErrback(self.cbFailed)
        return d

    def _remove_volume_callback(self, body, name):
        # NOTE: body arg is the result from last deferred call.
        # Python complains about parameter mis-match if you don't include it
        return self._remove_volume(name)

    def _remove_volume(self, name):
        path = b"/VolumeDriver.Remove"
        body = {u"Name": name}

        headers = Headers({b"content-type": [b"application/json"]})
        body_producer = FileBodyProducer(BytesIO(dumps(body)))
        agent = Agent.usingEndpointFactory(reactor, HPEEndpointFactory())
        d = agent.request(b'POST', b"UNIX://localhost" + path, headers,
                          body_producer)
        d.addCallback(self.checkResponse, json.dumps({u"Err": ''}))
        d.addErrback(self.cbFailed)
        return d

    def test_hpe_remove_volume(self):
        name = 'test-create-volume'
        return self._remove_volume(name)

    def _get_volume_mount_path(self, body, name):
        # NOTE: body arg is the result from last deferred call.
        # Python complains about parameter mis-match if you don't include it
        # In this test, we need it to compare expected results with Path
        # request

        # Compare path returned by mount (body) with Get Path request
        path = b"/VolumeDriver.Path"
        newbody = {u"Name": name}
        headers = Headers({b"content-type": [b"application/json"]})
        body_producer = FileBodyProducer(BytesIO(dumps(newbody)))
        agent = Agent.usingEndpointFactory(reactor, HPEEndpointFactory())
        d = agent.request(b'POST', b"UNIX://localhost" + path, headers,
                          body_producer)
        d.addCallback(self.checkResponse, body)
        d.addErrback(self.cbFailed)
        return d

    def _mount_the_volume(self, body, name):
        # NOTE: body arg is the result from last deferred call.
        # Python complains about parameter mis-match if you don't include it

        # Mount the previously created volume
        path = b"/VolumeDriver.Mount"
        newbody = {u"Name": name}
        headers = Headers({b"content-type": [b"application/json"]})
        body_producer = FileBodyProducer(BytesIO(dumps(newbody)))
        agent = Agent.usingEndpointFactory(reactor, HPEEndpointFactory())
        d = agent.request(b'POST', b"UNIX://localhost" + path, headers,
                          body_producer)

        d.addCallback(self.getResponse)

        # If we get a valid response from Path request then we assume
        # the mount passed.
        # TODO: Add additonal logic to verify the mountpath
        d.addCallback(self._get_volume_mount_path, name)
        return d

    def _unmount_the_volume(self, body, name):
        # NOTE: body arg is the result from last deferred call.
        # Python complains about parameter mis-match if you don't include it
        path = b"/VolumeDriver.Unmount"
        newbody = {u"Name": name}
        headers = Headers({b"content-type": [b"application/json"]})
        body_producer = FileBodyProducer(BytesIO(dumps(newbody)))

        agent = Agent.usingEndpointFactory(reactor, HPEEndpointFactory())
        d = agent.request(b'POST', b"UNIX://localhost" + path, headers,
                          body_producer)
        d.addCallback(self.checkResponse, json.dumps({u"Err": ''}))
        d.addErrback(self.cbFailed)
        return d

    def broken_test_hpe_mount_umount_volume(self):
        name = 'test-mount-volume'
        path = b"/VolumeDriver.Create"
        body = {u"Name": name}

        # Create a volume to be mounted
        headers = Headers({b"content-type": [b"application/json"]})
        body_producer = FileBodyProducer(BytesIO(dumps(body)))
        agent = Agent.usingEndpointFactory(reactor, HPEEndpointFactory())
        d = agent.request(b'POST', b"UNIX://localhost" + path, headers,
                          body_producer)
        d.addCallback(self.checkResponse, json.dumps({u"Err": ''}))
        d.addErrback(self.cbFailed)

        # Mount the previously created volume
        d.addCallback(self._mount_the_volume, name)

        # UMount the previously created volume
        d.addCallback(self._unmount_the_volume, name)

        # Remove the previously created volume
        d.addCallback(self._remove_volume_callback, name)
        return d

    def test_hpe_get_volume(self):
        name = 'test-get-volume'
        path = b"/VolumeDriver.Create"
        body = {u"Name": name}

        # Create a volume to be mounted
        headers = Headers({b"content-type": [b"application/json"]})
        body_producer = FileBodyProducer(BytesIO(dumps(body)))
        agent = Agent.usingEndpointFactory(reactor, HPEEndpointFactory())
        d = agent.request(b'POST', b"UNIX://localhost" + path, headers,
                          body_producer)
        d.addCallback(self.checkResponse, json.dumps({u"Err": ''}))
        d.addErrback(self.cbFailed)

        # Get the previously created volume
        expected = {u"Volume": {u"Status": {},
                                u"Mountpoint": '',
                                u"Name": name},
                    u"Err": ''}
        d.addCallback(self._get_volume, name, expected)

        # Remove the previously created volume
        d.addCallback(self._remove_volume_callback, name)
        return d

    def test_hpe_get_non_existent_volume(self):
        name = 'test-get-volume'

        # Get the previously created volume
        expected = {u"Err": ''}
        d = self._get_volume({}, name, expected)

        return d

    def _get_volume(self, body, name, expected):
        path = b"/VolumeDriver.Get"
        body = {u"Name": name}

        # Get a volume
        headers = Headers({b"content-type": [b"application/json"]})
        body_producer = FileBodyProducer(BytesIO(dumps(body)))
        agent = Agent.usingEndpointFactory(reactor, HPEEndpointFactory())
        d = agent.request(b'POST', b"UNIX://localhost" + path, headers,
                          body_producer)
        d.addCallback(self.checkResponse, json.dumps(expected))
        d.addErrback(self.cbFailed)

        return d

    def broken_test_hpe_list_volume(self):
        name = 'test-list-volume'
        path = b"/VolumeDriver.Create"
        body = {u"Name": name}

        # Create a volume to be mounted
        headers = Headers({b"content-type": [b"application/json"]})
        body_producer = FileBodyProducer(BytesIO(dumps(body)))
        agent = Agent.usingEndpointFactory(reactor, HPEEndpointFactory())
        d = agent.request(b'POST', b"UNIX://localhost" + path, headers,
                          body_producer)
        d.addCallback(self.checkResponse, json.dumps({u"Err": ''}))
        d.addErrback(self.cbFailed)

        # List volumes
        expected = {u"Err": '',
                    u"Volumes": [{u"Mountpoint": '',
                                  u"Name": name}]}
        d.addCallback(self._list_volumes, name, expected)

        # Remove the previously created volume
        d.addCallback(self._remove_volume_callback, name)

        return d

    def broken_test_hpe_list_volume_no_volumes(self):
        path = b"/VolumeDriver.List"

        # Create a volume to be mounted
        headers = Headers({b"content-type": [b"application/json"]})
        body_producer = FileBodyProducer(BytesIO(dumps({})))
        agent = Agent.usingEndpointFactory(reactor, HPEEndpointFactory())
        d = agent.request(b'POST', b"UNIX://localhost" + path, headers,
                          body_producer)
        d.addCallback(self.checkResponse, json.dumps({u"Err": '',
                                                      u"Volumes": []}))
        d.addErrback(self.cbFailed)

        return d

    def _list_volumes(self, body, name, expected):
        path = b"/VolumeDriver.List"
        body = {u"Name": name}

        # Get a volume
        headers = Headers({b"content-type": [b"application/json"]})
        body_producer = FileBodyProducer(BytesIO(dumps(body)))
        agent = Agent.usingEndpointFactory(reactor, HPEEndpointFactory())
        d = agent.request(b'POST', b"UNIX://localhost" + path, headers,
                          body_producer)
        d.addCallback(self.checkResponse, json.dumps(expected))
        d.addErrback(self.cbFailed)

        return d
