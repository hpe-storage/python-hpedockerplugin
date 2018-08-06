# Copyright 2015 Rackspace Inc.
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

"""Serialization/Deserialization for privsep.

The wire format is a stream of msgpack objects encoding primitive
python datatypes.  Msgpack 'raw' is assumed to be a valid utf8 string
(msgpack 2.0 'bin' type is used for bytes).  Python lists are
converted to tuples during serialization/deserialization.
"""

import logging
import socket
import threading

import msgpack
import six

from oslo_privsep._i18n import _


LOG = logging.getLogger(__name__)


try:
    import greenlet

    def _get_thread_ident():
        # This returns something sensible, even if the current thread
        # isn't a greenthread
        return id(greenlet.getcurrent())

except ImportError:
    def _get_thread_ident():
        return threading.current_thread().ident


class Serializer(object):
    def __init__(self, writesock):
        self.writesock = writesock

    def send(self, msg):
        buf = msgpack.packb(msg, use_bin_type=True, unicode_errors='replace')
        self.writesock.sendall(buf)

    def close(self):
        # Hilarious. `socket._socketobject.close()` doesn't actually
        # call `self._sock.close()`.  Oh well, we really wanted a half
        # close anyway.
        self.writesock.shutdown(socket.SHUT_WR)


class Deserializer(six.Iterator):
    def __init__(self, readsock):
        self.readsock = readsock
        self.unpacker = msgpack.Unpacker(use_list=False, encoding='utf-8')

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            try:
                return next(self.unpacker)
            except StopIteration:
                try:
                    buf = self.readsock.recv(4096)
                    if not buf:
                        raise
                    self.unpacker.feed(buf)
                except socket.timeout:
                    pass


class Future(object):
    """A very simple object to track the return of a function call"""

    def __init__(self, lock):
        self.condvar = threading.Condition(lock)
        self.error = None
        self.data = None

    def set_result(self, data):
        """Must already be holding lock used in constructor"""
        self.data = data
        self.condvar.notify()

    def set_exception(self, exc):
        """Must already be holding lock used in constructor"""
        self.error = exc
        self.condvar.notify()

    def result(self):
        """Must already be holding lock used in constructor"""
        self.condvar.wait()
        if self.error is not None:
            raise self.error
        return self.data


class ClientChannel(object):
    def __init__(self, sock):
        self.writer = Serializer(sock)
        self.lock = threading.Lock()
        self.reader_thread = threading.Thread(
            name='privsep_reader',
            target=self._reader_main,
            args=(Deserializer(sock),),
        )
        self.reader_thread.daemon = True
        self.outstanding_msgs = {}

        self.reader_thread.start()

    def _reader_main(self, reader):
        """This thread owns and demuxes the read channel"""
        for msg in reader:
            msgid, data = msg
            if msgid is None:
                self.out_of_band(data)
            else:
                with self.lock:
                    if msgid not in self.outstanding_msgs:
                        raise AssertionError("msgid should in "
                                             "outstanding_msgs.")
                    self.outstanding_msgs[msgid].set_result(data)

        # EOF.  Perhaps the privileged process exited?
        # Send an IOError to any oustanding waiting readers.  Assuming
        # the write direction is also closed, any new writes should
        # get an immediate similar error.
        LOG.debug('EOF on privsep read channel')

        exc = IOError(_('Premature eof waiting for privileged process'))
        with self.lock:
            for mbox in self.outstanding_msgs.values():
                mbox.set_exception(exc)

    def out_of_band(self, msg):
        """Received OOB message. Subclasses might want to override this."""
        pass

    def send_recv(self, msg):
        myid = _get_thread_ident()
        future = Future(self.lock)

        with self.lock:
            if myid in self.outstanding_msgs:
                raise AssertionError("myid shoudn't be in outstanding_msgs.")
            self.outstanding_msgs[myid] = future
            try:
                self.writer.send((myid, msg))

                reply = future.result()
            finally:
                del self.outstanding_msgs[myid]

        return reply

    def close(self):
        with self.lock:
            self.writer.close()

        self.reader_thread.join()


class ServerChannel(six.Iterator):
    """Server-side twin to ClientChannel"""

    def __init__(self, sock):
        self.rlock = threading.Lock()
        self.reader_iter = iter(Deserializer(sock))
        self.wlock = threading.Lock()
        self.writer = Serializer(sock)

    def __iter__(self):
        return self

    def __next__(self):
        with self.rlock:
            return next(self.reader_iter)

    def send(self, msg):
        with self.wlock:
            self.writer.send(msg)
