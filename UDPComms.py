
"""
This is a simple library to enable communication between different processes (potentially on different machines) over a network using UDP. It's goals a simplicity and easy of understanding and reliability

mikadam@stanford.edu
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import socket
import struct
from enum import Enum, auto

import msgpack

from sys import version_info

USING_PYTHON_2 = (version_info[0] < 3)
if USING_PYTHON_2:
    from time import time as monotonic
else:
    from time import monotonic

timeout = socket.timeout

MAX_SIZE = 65507

##TODO:
# Nicer configuration
# Test on ubuntu and debian
# Documentation (targets, and security disclaimer)

class Target(Enum):
    LOCALHOST = auto()
    BROADCAST = auto()
    MULTICAST = auto()

class Publisher:
    broadcast_ip = "10.0.0.255"
    muticast_ip = '224.1.1.1'
    def __init__(self, port, target = Target.BROADCAST):
        """ Create a Publisher Object

        Arguments:
            port         -- the port to publish the messages on
            target       -- where to publish the message
        """
        print("magic")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        if target == Target.BROADCAST:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.ip = self.broadcast_ip

        elif target == Target.LOCALHOST:
            self.ip = "127.0.0.1"

        elif target == Target.MULTICAST:
            # raise NotImplementedError
            self.ip = self.muticast_ip
            self.sock.setsockopt(socket.IPPROTO_IP,
                                 socket.IP_MULTICAST_TTL,
                                 struct.pack('b', 1))
        else:
            raise ValueError

        self.sock.settimeout(0.2)
        self.sock.connect((self.ip, port))

        self.port = port

    def send(self, obj):
        """ Publish a message. The obj can be any nesting of standard python types """
        msg = msgpack.dumps(obj, use_bin_type=False)
        assert len(msg) < MAX_SIZE, "Encoded message too big!"
        self.sock.send(msg)

    def __del__(self):
        self.sock.close()


class Subscriber:
    muticast_ip = '224.1.1.1'
    def __init__(self, port, timeout=0.2):
        """ Create a Subscriber Object

        Arguments:
            port         -- the port to listen to messages on
            timeout      -- how long to wait before a message is considered out of date
        """
        self.max_size = MAX_SIZE

        self.port = port
        self.timeout = timeout

        self.last_data = None
        self.last_time = float('-inf')

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        mreq = struct.pack("4sl", socket.inet_aton(self.muticast_ip), socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        self.sock.settimeout(timeout)
        self.sock.bind(("", port))

    def recv(self):
        """ Receive a single message from the socket buffer. It blocks for up to timeout seconds.
        If no message is received before timeout it raises a UDPComms.timeout exception"""

        try:
            self.last_data, address = self.sock.recvfrom(self.max_size)
        except BlockingIOError:
            raise socket.timeout("no messages in buffer and called with timeout = 0")

        self.last_time = monotonic()
        return msgpack.loads(self.last_data, raw=USING_PYTHON_2)

    def get(self):
        """ Returns the latest message it can without blocking. If the latest massage is 
            older then timeout seconds it raises a UDPComms.timeout exception"""
        try:
            self.sock.settimeout(0)
            while True:
                self.last_data, address = self.sock.recvfrom(self.max_size)
                self.last_time = monotonic()
        except socket.error:
            pass
        finally:
            self.sock.settimeout(self.timeout)

        current_time = monotonic()
        if (current_time - self.last_time) < self.timeout:
            return msgpack.loads(self.last_data, raw=USING_PYTHON_2)
        else:
            raise socket.timeout("timeout=" + str(self.timeout) + \
                                 ", last message time=" + str(self.last_time) + \
                                 ", current time=" + str(current_time))

    def get_list(self):
        """ Returns list of messages, in the order they were received"""
        msg_bufer = []
        try:
            self.sock.settimeout(0)
            while True:
                self.last_data, address = self.sock.recvfrom(self.max_size)
                self.last_time = monotonic()
                msg = msgpack.loads(self.last_data, raw=USING_PYTHON_2)
                msg_bufer.append(msg)
        except socket.error:
            pass
        finally:
            self.sock.settimeout(self.timeout)

        return msg_bufer

    def __del__(self):
        self.sock.close()


if __name__ == "__main__":
    msg = 'very important data'

    a = Publisher(1000)
    a.send( {"text": "magic", "number":5.5, "bool":False} )
