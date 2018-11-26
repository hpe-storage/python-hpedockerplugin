# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
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

"""Plugin base exception handling.

Includes decorator for re-raising Plugin-type exceptions.

SHOULD include dedicated exception logging.

"""

import sys

from oslo_config import cfg
from oslo_log import log as logging
import six
import webob.exc
from webob.util import status_generic_reasons
from webob.util import status_reasons

from hpedockerplugin.i18n import _, _LE


LOG = logging.getLogger(__name__)

exc_log_opts = [
    cfg.BoolOpt('fatal_exception_format_errors',
                default=False,
                help='Make exception message format errors fatal.'),
]

CONF = cfg.CONF
CONF.register_opts(exc_log_opts)


class ConvertedException(webob.exc.WSGIHTTPException):
    def __init__(self, code=500, title="", explanation=""):
        self.code = code
        # There is a strict rule about constructing status line for HTTP:
        # '...Status-Line, consisting of the protocol version followed by a
        # numeric status code and its associated textual phrase, with each
        # element separated by SP characters'
        # (http://www.faqs.org/rfcs/rfc2616.html)
        # 'code' and 'title' can not be empty because they correspond
        # to numeric status code and its associated text
        if title:
            self.title = title
        else:
            try:
                self.title = status_reasons[self.code]
            except KeyError:
                generic_code = self.code // 100
                self.title = status_generic_reasons[generic_code]
        self.explanation = explanation
        super(ConvertedException, self).__init__()


class Error(Exception):
    pass


class PluginException(Exception):
    """Base Plugin Exception

    To correctly use this class, inherit from it and define
    a 'message' property. That message will get printf'd
    with the keyword arguments provided to the constructor.

    """
    message = _("An unknown exception occurred.")
    code = 500
    headers = {}
    safe = False

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs
        self.kwargs['message'] = message

        if 'code' not in self.kwargs:
            try:
                self.kwargs['code'] = self.code
            except AttributeError:
                pass

        for k, v in self.kwargs.items():
            if isinstance(v, Exception):
                self.kwargs[k] = six.text_type(v)

        if self._should_format():
            try:
                message = self.message % kwargs

            except Exception:
                exc_info = sys.exc_info()
                # kwargs doesn't match a variable in the message
                # log the issue and the kwargs
                LOG.exception(_LE('Exception in string format operation'))
                for name, value in kwargs.items():
                    LOG.error(_LE("%(name)s: %(value)s"),
                              {'name': name, 'value': value})
                if CONF.fatal_exception_format_errors:
                    six.reraise(*exc_info)
                # at least get the core message out if something happened
                message = self.message
        elif isinstance(message, Exception):
            message = six.text_type(message)

        # NOTE(luisg): We put the actual message in 'msg' so that we can access
        # it, because if we try to access the message via 'message' it will be
        # overshadowed by the class' message attribute
        self.msg = message
        super(PluginException, self).__init__(message)

    def _should_format(self):
        return self.kwargs['message'] is None or '%(message)' in self.message

    def __unicode__(self):
        return six.text_type(self.msg)


class Duplicate(PluginException):
    pass


class Invalid(PluginException):
    message = _("Unacceptable parameters.")


class Invalid3PARDomain(PluginException):
    message = _("Invalid 3PAR Domain: %(err)s")


class ConnectionError(PluginException):
    message = _("Unable to connect to storage array/appliance: %(err)s")


class InvalidInput(PluginException):
    message = _("Invalid input received: %(reason)s")


class NotAuthorized(PluginException):
    message = _("Not authorized.")


class RevertSnapshotException(PluginException):
    message = _("Exception during revering the snapshot")


class VolumeBackendAPIException(PluginException):
    message = _("Bad or unexpected response from the storage volume "
                "backend API: %(data)s")


class VolumeIsBusy(PluginException):
    message = _("deleting volume %(volume_name)s that has snapshot")


# HPE Docker Volume Plugin
class HPEPluginStartPluginException(PluginException):
    message = _("HPE Docker Volume Plugin Start Plugin Service Failed: "
                "%(reason)s")


class HPEPluginNotInitializedException(PluginException):
    message = _("HPE Docker Volume plugin not ready: %(reason)s")


class HPEPluginCreateException(PluginException):
    message = _("HPE Docker Volume plugin Create volume failed: %(reason)s")


class HPEPluginRemoveException(PluginException):
    message = _("HPE Docker Volume plugin Remove volume failed: %(reason)s")


class HPEPluginMountException(PluginException):
    message = _("HPE Docker Volume Plugin Mount Failed: %(reason)s")


class HPEPluginUMountException(PluginException):
    message = _("HPE Docker Volume Plugin Unmount Failed: %(reason)s")


class HPEPluginMapHourException(PluginException):
    message = _("HPE Docker Volume Plugin Failed to map expiration hours:"
                "%(reason)s")


class HPEPluginMapSizeException(PluginException):
    message = _("HPE Docker Volume Plugin Failed to map size: %(reason)s")


class HPEPluginMapProvisioningException(PluginException):
    message = _("HPE Docker Volume Plugin Failed to map provisioning:"
                "%(reason)s")


class HPEPluginMakeDirException(PluginException):
    message = _("HPE Docker Volume Plugin Makedir Failed: %(reason)s")


class HPEPluginRemoveDirException(PluginException):
    message = _("HPE Docker Volume Plugin Removedir Failed: %(reason)s")


class HPEPluginFileSystemException(PluginException):
    message = _("HPE Docker Volume Plugin File System error: %(reason)s")


class HPEPluginMakeEtcdRootException(PluginException):
    message = _("HPE Docker Volume Plugin Make Etcd Root error: %(reason)s")


class HPEPluginEtcdException(PluginException):
    message = _("Encountered Etcd exception: %(reason)s")


class HPEPluginSaveFailed(HPEPluginEtcdException):
    message = _("ETCD data save failed: %(obj)s")


class HPEPluginLockFailed(HPEPluginEtcdException):
    message = _("ETCD lock failed: %(obj)s")


class HPEPluginReadBackendFailed(HPEPluginEtcdException):
    message = _("ETCD read for backend failed for vol: %(volname)s")


class HPEPluginActiveDriverEntryNotFound(HPEPluginEtcdException):
    message = _("ETCD active driver info not found: %(key)s")


class HPEPluginUnlockFailed(HPEPluginEtcdException):
    message = _("ETCD unlock failed: %(obj)s")


class HPEDriverException(PluginException):
    pass


class HPEDriverInvalidInput(HPEDriverException):
    message = _("Invalid input received: %(reason)s")


class HPEDriverInvalidSizeForCompressedVolume(HPEDriverException):
    message = _("Invalid input received: %(reason)s")


class HPEDriverInvalidDedupVersion(HPEDriverException):
    message = _("Invalid input received: %(reason)s")


class HPEDriverManageVolumeAttached(HPEDriverException):
    message = _("Failed to manage volume/snapshot because its attached:"
                "%(reason)s")


class HPEDriverCreateVolumeWithQosFailed(HPEDriverException):
    message = ""


class HPEDriverGetQosFromVvSetFailed(HPEDriverException):
    message = ""


class HPEDriverSetFlashCacheOnVvsFailed(HPEDriverException):
    message = _("%(reason)s")


class HPEDriverVolumeAlreadyExists(HPEDriverException):
    message = ""


class HPEDriverAddVvToVvSetFailed(HPEDriverException):
    message = ""


class HPEDriverCreateScheduleFailed(HPEDriverException):
    message = _("Creation of snapshot schedule failed: %(reason)s")


class HPEDriverRemoveScheduleFailed(HPEDriverException):
    message = _("Removal of snapshot schedule failed: %(reason)s")


class HPEDriverForceRemoveVLUNFailed(HPEDriverException):
    message = "Forced removal of VLUN failed: %(reason)"


class HPEDriverNoVLUNsCreated(HPEDriverException):
    message = "No new VLUN(s) were created!"


class HPEDriverRemoteCopyGroupNotFound(HPEDriverException):
    message = "Remote copy group '%(name)s' not found"


class HPEArrayNotReachable(PluginException):
    message = "Array is not reachable: '%(url)s'"
    # message = "Array is not reachable: '%(array_ip)'"


class HPERemoteCopyGroupBackendAPIException(PluginException):
    message = _("Bad or unexpected response from the RCG "
                "backend API: %(data)s")


class HPERemoteCopyGroupAlreadyExists(PluginException):
    message = "Remote copy group %(rcg_name)s already exists"


class HPERemoteCopyGroupNotPrimary(PluginException):
    message = "Remote copy group '%(rcg_name)s' not in Primary role"


class HPEDriverUnknownException(HPEDriverException):
    message = "An unknown exception occurred: %(ex)s"


class InvalidRcgRoleForDeleteVolume(PluginException):
    message = _("Error: %(reason)s")


class DeleteReplicatedVolumeFailed(PluginException):
    message = _("Delete Replication Volume Failed: %(reason)s")


class RcgStateInTransitionException(PluginException):
    message = _("Remote copy group state is in transition: %(reason)s")
