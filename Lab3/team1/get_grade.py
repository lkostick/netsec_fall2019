import asyncio
import sys
import time

from playground.common.logging import EnablePresetLogging, PRESET_VERBOSE
from playground.network.packet.fieldtypes import BOOL, STRING
from playground.network.common import PlaygroundAddress
from playground.network.packet import PacketType
import playground
from autograder_ex6_packets import *
from get_grade_packets import *

EnablePresetLogging(PRESET_VERBOSE)


class ClientProtocol(asyncio.Protocol):
    def __init__(self, loop):
        self.loop = loop
        self.gotResult = False
        self.deserializer = PacketType.Deserializer()
        self.start_requesting = False

    def connection_made(self, transport):
        self.transport = transport
        print('Connection Made')

        get_result = AutogradeResultRequest(test_id="8ccbf497a5f0178aab33fac665434d143c0ee45850beec55246f6a87d86b425e")        
        get_result_byte = get_result.__serialize__()
        print('Packet that is going out: ' + str(get_result_byte))
        self.transport.write(get_result_byte)

    def data_received(self, data):
        if not self.gotResult:
            self.gotResult = True
            print('something received: ' + str(data))
            self.deserializer.update(data)
            for packet in self.deserializer.nextPackets():
                print('Packet Received: ' + str(packet))
                print('Packet Info:\n' + 
                    'test_id: ' + str(packet.test_id) + 
                    '\npassed: ' + str(packet.passed))

    def connection_lost(self, exc):
        print('Connection Lost!')
        self.loop.stop()

IP = "20194.0.0.19000"
PORT = 19008
# IP = "0.0.0.0"
# PORT = "1234"

loop = asyncio.get_event_loop()
coro = playground.create_connection(lambda: ClientProtocol(loop),
                              IP, PORT)
loop.run_until_complete(coro)
loop.run_forever()
loop.close()
