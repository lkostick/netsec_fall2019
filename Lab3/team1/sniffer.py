from playground.network.protocols.vsockets import VNICDumpProtocol
from playground.network.protocols.packets.switching_packets import WirePacket
from playground.network.packet import PacketType
import random
import time
import uuid
import getpass, sys, os, asyncio
import random
import playground
from playground.common.logging import EnablePresetLogging, PRESET_VERBOSE, PRESET_DEBUG
from game_packets import *
from BankMessages import *

EnablePresetLogging(PRESET_VERBOSE)


class ClientProtocol(VNICDumpProtocol):
    def __init__(self, loop):
        self.loop = loop
        self.wirepacket_deserializer = WirePacket.Deserializer()
        self.packettype_deserializer = PacketType.Deserializer()

    def data_received(self, data):
        self.wirepacket_deserializer.update(data)
        for wirepacket in self.wirepacket_deserializer.nextPackets():
            info = f"Packet Received:\n \
            Info:::\n \
            Source: {wirepacket.source}:{wirepacket.sourcePort}\n \
            Destination: {wirepacket.destination}:{wirepacket.destinationPort}\n"
            #Data: {wirepacket.data}"
            #print(f'wirepacket: {wirepacket}')
            #print(wirepacket.data)
            self.packettype_deserializer.update(wirepacket.data)
            for packet in self.packettype_deserializer.nextPackets():
                if isinstance(packet, OpenSession):
                    phashhex = packet.PasswordHash.hex()
                    info += f"Username: {packet.Login}\nHash: {phashhex}"
                    print(info)
                    with open("sniffed_bank_packet.txt", "a+") as myfile:
                        myfile.write(info)

        #self.wirepacket_deserializer.update(data)
        #for wirepacket in self.wirepacket_deserializer.nextPackets():
        #    #filter_packet_condition = packet.source != packet.destination and 'flyingkey' not in str(packet.data) and 'flyingring' not in str(packet.data) and 'clock' not in str(packet.data)\
        #    #                          and (packet.source == '20194.0.1.1' or packet.destination == '20194.0.1.1')
        #    #if (wirepacket.source != wirepacket.destination) and (wirepacket.source == '20194.0.1.1'):
        #    print(f'Packet Received:\nSource:\t{wirepacket.source}:{wirepacket.sourcePort} \
        #    \nDestination:\t{wirepacket.destination}:{wirepacket.destinationPort}')
        #    #if (wirepacket.source == '20194.0.1.1'):
        #    #print("Source correct")
        #    info = f"Packet Received:\n \
        #    Info:::\n \
        #    Source: {wirepacket.source}:{wirepacket.sourcePort}\n \
        #    Destination: {wirepacket.destination}:{wirepacket.destinationPort}\n \
        #    Data: {wirepacket.data}"
        #    with open("sniffed_wire_packet2.txt", "a+") as myfile:
        #        myfile.write(info)
        #    #if isinstance(wirepacket, PacketType):
        #    #self.buffer += wirepacket.data
        #    self.packettype_deserializer.update(wirepacket.data)
        #    print(list(self.packettype_deserializer.nextPackets()))
        #    for packet in self.packettype_deserializer.nextPackets():
        #        print(f"Got here: {packet}")
                #    info = f'''Packet Received:
                #    Info:::
                #    Source: {wirepacket.source}:{wirepacket.sourcePort}
                #    Destination: {packet.destination}:{wirepacket.destinationPort}
                #    Data: {packet}
                #    '''
                #    with open("sniffed_wire_packet2.txt", "a+") as myfile:
                #        myfile.write(info)
                    #print(info)
                #info = 'Packet Received - Wire Packet: ' + str(packet) + \
                #       '\nPacket Info:\n' + \
                #    'Source: ' + str(packet.source) + \
                #    '\nSource Port: ' + str(packet.sourcePort) + \
                #    '\nDestination: ' + str(packet.destination) + \
                #    '\nDestination Port: ' + str(packet.destinationPort) + \
                #    '\nFrag Data: ' + str(packet.fragData) + \
                #    '\nData: ' + str(packet.data) + '\n'

            #if filter_packet_condition:
            #    info = 'Packet Received - Wire Packet: ' + str(packet) + \
            #           '\nPacket Info:\n' + \
            #        'Source: ' + str(packet.source) + \
            #        '\nSource Port: ' + str(packet.sourcePort) + \
            #        '\nDestination: ' + str(packet.destination) + \
            #        '\nDestination Port: ' + str(packet.destinationPort) + \
            #        '\nFrag Data: ' + str(packet.fragData) + \
            #        '\nData: ' + str(packet.data) + '\n'

                #with open("sniffed wire packet.txt", "a+") as myfile:

                        #packet2 = PacketType.Deserialize(packet.data)
                        #print(packet2)

                # self.packettype_deserializer.update(packet.data)
                # for packet2 in self.packettype_deserializer.nextPackets():
                #     info = 'Packet Received - Packet-Type Packet: ' + str(packet2) + '\n'

                #     with open("sniffed data packet.txt", "a+") as myfile:
                #         myfile.write(info)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(playground.connect.raw_vnic_connection(lambda: ClientProtocol(loop)))
    loop.run_forever()
    loop.run_forever()
    loop.close()
