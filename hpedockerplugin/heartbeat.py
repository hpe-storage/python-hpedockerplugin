import os
from retrying import retry
import time
import threading

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import importutils

hpe3parclient = importutils.try_import("hpe3parclient")
if hpe3parclient:
    from hpe3parclient import client
    from hpe3parclient import exceptions as hpeexceptions

import exception as exc

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class ForeverThread(threading.Thread):
    def __init__(self, client):
        super(ForeverThread, self).__init__()
        self._client = client
        self._stop = False

    def run(self):
        while not self._stop:
            try:
                self._client.execute()
            except Exception as ex:
                # Log exception and continue with the loop
                # This loop is exited only when caller stops it
                LOG.error(ex)
                pass

    def stop(self):
        self._stop = True
        self._client.stop()


def retry_on_exception(ex):
    return isinstance(ex, exc.HPEArrayNotReachable)


class HeartbeatChecker(object):
    wait_exponential_multiplier = 1000
    wait_exponential_max = 10000
    stop_max_delay = 30000

    def __init__(self, config, hbc_client):
        self._config = config
        self._hbc_client = hbc_client
        self._stop = False
        if CONF.wait_exponential_multiplier:
            HeartbeatChecker.wait_exponential_multiplier = \
                CONF.wait_exponential_multiplier
        if CONF.wait_exponential_max:
            HeartbeatChecker.wait_exponential_max = CONF.wait_exponential_max
        if CONF.stop_max_delay:
            HeartbeatChecker.stop_max_delay = CONF.stop_max_delay

    def stop(self):
        self._stop = True

    def execute(self):
        try:
            self._ping_array()
            # Array is alive. Ping it after 2 seconds
            time.sleep(2)
        except exc.HPEArrayNotReachable as ex:
            LOG.error(ex.message)
            # The array is down and the client needs to be notified
            # Swap configuration file to point to the other array
            self._config = self._hbc_client.notify_array_not_reachable(
                self._config)

    @retry(retry_on_exception=retry_on_exception,
           wait_exponential_multiplier=wait_exponential_multiplier,
           wait_exponential_max=wait_exponential_max,
           stop_max_delay=stop_max_delay)
    def _ping_array(self):
        # Instantiation of HPE3ParClient results into following exceptions:
        # 1. HTTPBadRequest
        # 2. SSLCertFailed
        # 3. UnsupportedVersion
        # 2 and 3 should be taken care of initially when the plugin loads and
        # tries to create Client instance. It's the first one that is expected
        # when an array goes down. Retry will keep retrying even after getting
        # HTTPBadRequest till the other parameters in retry decorator above
        # are satisfied
        if self._stop:
            return
        # try:
        #     cli = client.HPE3ParClient(
        #         self._config.hpe3par_api_url, timeout=30,
        #         suppress_ssl_warnings=False)
        #     try:
        #         cli.login('3paradm', '3pardata')
        #         rcg = cli.getRemoteCopyGroup('Demo-RCG01')
        #         if rcg['role'] == 2:
        #             LOG.debug("My-RCG03 role changed to secondary. Going to sleep...")
        #             time.sleep(30)
        #             LOG.debug("Raising exception Array not reachable")
        #             raise exc.HPEArrayNotReachable(url=self._config.hpe3par_api_url)
        #     except hpeexceptions.HTTPNotFound as ex:
        #         LOG.error(ex)
        #         raise exc.HPEArrayNotReachable(url=self._config.hpe3par_api_url)
        #     finally:
        #         cli.logout()
        # except (hpeexceptions.HTTPBadRequest,
        #         hpeexceptions.SSLCertFailed,
        #         hpeexceptions.UnsupportedVersion) as ex:
        #     LOG.error(ex)
        #     raise exc.HPEArrayNotReachable(url=self._config.hpe3par_api_url)

        # TODO: This is the final ping implementation
        array_ip = self._get_ip_from_url(self._config.hpe3par_api_url)
        cmd = "ping -c 1 -w2 " + array_ip + " > /dev/null 2>&1"

        response = os.system(cmd)
        if response != 0:
            raise exc.HPEArrayNotReachable(array_ip=array_ip)

    # TODO: This must go to volume_manager where heartbeat is instantiated
    def _get_ip_from_url(self, url):
        # url is of the form 'https://192.168.67.4:8080/api/v1'
        return url.split(':')[1][2:]
