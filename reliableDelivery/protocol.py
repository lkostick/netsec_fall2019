from playground.network.common import StackingProtocolFactory, StackingProtocol, StackingTransport
from playground.network.packet.fieldtypes import UINT8, STRING, BUFFER, UINT16, BOOL
from playground.network.packet.fieldtypes.attributes import Optional
from playground.network.packet import PacketType
import logging
import random

logger = logging.getLogger("playground.__connector__." + __name__)


class HandshakePacket(PacketType):
    DEFINITION_IDENTIFIER = "handshakepacket"
    DEFINITION_VERSION = "1.0"

    NOT_STARTED = 0
    SUCCESS = 1
    ERROR = 2

    FIELDS = [
        ("SYN", UINT8({Optional: True})),
        ("ACK", UINT8({Optional: True})),
        ("status", UINT8),
        ("error", STRING({Optional: True}))
    ]


class HandshakeTransport(StackingTransport):
    def write(self, data):
        # passthrough_packet = HandshakePacket()
        # passthrough_packet.data=data
        # self.lowerTransport().write(passthrough_packet.__serialize__())
        # print('HandshakeTransport.write()')
        logger.debug('HandshakeTransport.write()')
        self.lowerTransport().write(data)


class HandshakeProtocol(StackingProtocol):
    def __init__(self, mode):
        super().__init__()
        self._mode = mode
        self.deserializer = HandshakePacket.Deserializer()
        self.SYN = None
        self.ACK = None
        self.handshakeComplete = False

    def data_received(self, data):
        # logger.debug("{} passthrough received a buffer of size {}".format(self._mode, len(data)))
        # print('something received: ' + str(data))
        if self.handshakeComplete:
            # why does client-side data_received get called twice each time the server responds with the echo???????
            logger.debug('{} mode, data: {}'.format(self._mode, data))
            # self.counter += 1
            self.higherProtocol().data_received(data)
            return  # hacky way to end the method call
        # print('This should not print during the running of echotest.py')
        self.deserializer.update(data)
        for packet in self.deserializer.nextPackets():
            if isinstance(packet, HandshakePacket):
                print('Packet Received: \n' +
                      'Info: \n' +
                      'SYN: ' + str(packet.SYN) + '\n'
                                                  'ACK: ' + str(packet.ACK) + '\n'
                                                                              'status: ' + str(packet.status) + '\n'
                                                                                                                'error: ' + str(
                    packet.error) + '\n')
            if (self.handshakeComplete):  # The packet is not for this layer and should go upper level
                # in the current mess that is this file, this if block should never be reached -Justin
                pass
            else:
                if packet.status == HandshakePacket.SUCCESS:
                    if self._mode == "client":
                        if packet.SYN == self.SYN + 1:
                            self.handshakeComplete = True
                            responsePacket = HandshakePacket(ACK=1, status=HandshakePacket.SUCCESS)
                            packetBytes = responsePacket.__serialize__()
                            print('Sending:\n' +
                                  'Info: \n' +
                                  'SYN: ' + str(responsePacket.SYN) + '\n'
                                                                      'ack: ' + str(responsePacket.ACK) + '\n'
                                                                                                          'status: ' + str(
                                responsePacket.status) + '\n'
                                                         'error: ' + str(responsePacket.error) + '\n'
                                  )
                            self.transport.write(packetBytes)
                            print('Client-side calling self.higherProtocol().connection_made(higher_transport)')
                            higher_transport = HandshakeTransport(self.transport)
                            self.higherProtocol().connection_made(higher_transport)
                        else:
                            self.handshakeComplete = False
                            responsePacket = HandshakePacket(status=HandshakePacket.ERROR,
                                                             error=self._mode + ': SYN does not match!')
                            packetBytes = responsePacket.__serialize__()
                            print('Sending:\n' +
                                  'Info: \n' +
                                  'SYN: ' + str(responsePacket.SYN) + '\n'
                                                                      'ack: ' + str(responsePacket.ACK) + '\n'
                                                                                                          'status: ' + str(
                                responsePacket.status) + '\n'
                                                         'error: ' + str(responsePacket.error) + '\n'
                                  )
                            self.transport.write(packetBytes)
                    elif self._mode == 'server':
                        if packet.ACK == 1:
                            self.handshakeComplete = True
                            print('Server-side calling self.higherProtocol().connection_made(higher_transport)')
                            higher_transport = HandshakeTransport(self.transport)
                            self.higherProtocol().connection_made(higher_transport)
                        else:
                            self.handshakeComplete = False
                            responsePacket = HandshakePacket(status=HandshakePacket.ERROR,
                                                             error=self._mode + ': SYN does not match!')
                            packetBytes = responsePacket.__serialize__()
                            print('Sending:\n' +
                                  'Info: \n' +
                                  'SYN: ' + str(responsePacket.SYN) + '\n'
                                                                      'ack: ' + str(responsePacket.ACK) + '\n'
                                                                                                          'status: ' + str(
                                responsePacket.status) + '\n'
                                                         'error: ' + str(responsePacket.error) + '\n'
                                  )
                            self.transport.write(packetBytes)
                elif packet.status == HandshakePacket.NOT_STARTED:
                    returnPacket = HandshakePacket(SYN=packet.SYN + 1, ACK=0, status=HandshakePacket.SUCCESS)
                    packetBytes = returnPacket.__serialize__()
                    print('Sending:\n' +
                          'Info: \n' +
                          'SYN: ' + str(returnPacket.SYN) + '\n'
                                                            'ack: ' + str(returnPacket.ACK) + '\n'
                                                                                              'status: ' + str(
                        returnPacket.status) + '\n'
                                               'error: ' + str(returnPacket.error) + '\n'
                          )
                    self.transport.write(packetBytes)
                elif packet.status == HandshakePacket.ERROR:
                    self.handshakeComplete = False
                    print('{} got ERROR packet. {}'.format(self._mode, packet.error))

    def connection_made(self, transport):
        self.transport = transport
        # logger.debug("{} passthrough connection made. Calling connection made higher.".format(self._mode))
        # higher_transport = HandshakeTransport(transport)
        # self.higherProtocol().connection_made(higher_transport)

        if (self._mode == "client"):
            self.SYN = random.randint(0, 254)
            self.ACK = random.randint(1, 254)
            packet = HandshakePacket(SYN=self.SYN, status=HandshakePacket.NOT_STARTED)
            packetBytes = packet.__serialize__()
            print('Sending:\n' +
                  'Info: \n' +
                  'SYN: ' + str(packet.SYN) + '\n'
                                              'ack: ' + str(packet.ACK) + '\n'
                                                                          'status: ' + str(packet.status) + '\n'
                                                                                                            'error: ' + str(
                packet.error) + '\n'
                  )
            self.transport.write(packetBytes)

    def connection_lost(self, exc):
        # logger.debug("{} passthrough connection lost. Shutting down higher layer.".format(self._mode))
        self.higherProtocol().connection_lost(exc)


HandshakeClientFactory = StackingProtocolFactory.CreateFactoryType(
    lambda: HandshakeProtocol(mode="client")
)

HandshakeServerFactory = StackingProtocolFactory.CreateFactoryType(
    lambda: HandshakeProtocol(mode="server")
)

