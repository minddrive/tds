# Copyright 2016 Ifwe Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Mock Graphite server for feature tests."""

import os
import SocketServer
from multiprocessing import Process, Manager

class GraphiteHandler(SocketServer.BaseRequestHandler):
    """
    Handler for requests.
    """

    def handle(self):
        data = self.request[0].strip()
        socket = self.request[1]
        self.server.add_notification(data)
        # print "{} wrote:".format(self.client_address[0])
        # print data
        socket.sendto(data.upper(), self.client_address)


class GraphiteServer(SocketServer.UDPServer, object):
    """
    Custom test Graphite server.
    """

    def __init__(self, addr, *args, **kwargs):
        SocketServer.UDPServer.__init__(self, addr, GraphiteHandler, *args,
                                        **kwargs)

        self._manager = Manager()
        self.notifications = self._manager.list()
        self.prefix = 'tagged.deploy'

    def serve_forever(self, notifications):
        """Add notifications to self and serve forever."""
        self.notifications = notifications
        SocketServer.UDPServer.serve_forever(self)

    def start(self):
        """Start serving."""
        self.server_process = Process(
            target=self.serve_forever,
            args=(self.notifications,)
        )
        self.server_process.start()

    def add_notification(self, notification):
        """Add a notification to the list."""
        self.notifications.append(notification)

    def halt(self):
        """Halt the server."""
        self.socket.close()
        self.server_process.terminate()
        self.server_process.join()

    def get_notifications(self):
        """Return all notifications."""
        return self.notifications

if __name__ == "__main__":
    HOST, PORT = "localhost", 9999
    server = SocketServer.UDPServer((HOST, PORT), MyUDPHandler)
    server.serve_forever()
