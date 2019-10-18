from playground.network.common import StackingProtocolFactory, StackingProtocol, StackingTransport
import logging
import random
import playground
from playground.network.packet import FIELD_NOT_SET
from packets import *
import math

logger = logging.getLogger("playground.__connector__." + __name__)


class HandshakeTransport(StackingTransport):
    def write(self, data):
        logger.debug('HandshakeTransport.write()')
        # logger.debug('I am writing')
        self.lowerTransport().write(data)


class HandshakeProtocol(StackingProtocol):
    def __init__(self, mode):
        super().__init__()
        self._mode = mode
        self.deserializer = PoopPacketType.Deserializer()
        self.SYN = None
        self.ACK = None
        self.handshakeComplete = False
        # self.X = None
        # self.Y = None

    def data_received(self, data):
        logger.debug("{} POOP received a buffer of size {}".format(self._mode, len(data)))
        # print('something received: ' + str(data))
        if self.handshakeComplete:
            logger.debug(
                '{} mode handshake complete. Calling self.higherProtocol().data_received(data)'.format(self._mode))
            # self.counter += 1
            self.higherProtocol().data_received(data)
            return  # hacky way to end the method call
        # print('This should not print during the running of echotest.py')
        self.deserializer.update(data)
        for packet in self.deserializer.nextPackets():

            logger.debug('Packet Received: \n' +
                         'Info: \n' +
                         'SYN: ' + str(packet.SYN) + '\n' +
                         'ACK: ' + str(packet.ACK) + '\n' +
                         'status: ' + str(packet.status) + '\n' +
                         'error: ' + str(packet.error) + '\n')

            if packet.status == HandshakePacket.SUCCESS:
                if self._mode == "client":
                    if (packet.SYN != FIELD_NOT_SET and 0 <= packet.SYN < int(math.pow(2, 32))) and \
                            (packet.ACK != FIELD_NOT_SET and packet.ACK == (self.SYN + 1)) % int(math.pow(2, 32)) and \
                            packet.error == FIELD_NOT_SET:
                        self.handshakeComplete = True
                        self.SYN = (self.SYN + 1) % int(math.pow(2, 32))
                        responsePacket = HandshakePacket(SYN=self.SYN, ACK=(packet.SYN + 1) % int(math.pow(2, 32)),
                                                         status=HandshakePacket.SUCCESS)
                        packetBytes = responsePacket.__serialize__()

                        logger.debug('Sending:\n' +
                                     'Info: \n' +
                                     'SYN: ' + str(responsePacket.SYN) + '\n' +
                                     'ack: ' + str(responsePacket.ACK) + '\n' +
                                     'status: ' + str(responsePacket.status) + '\n' +
                                     'error: ' + str(responsePacket.error) + '\n')

                        self.transport.write(packetBytes)
                        logger.debug('Client-side POOP calling self.higherProtocol().connection_made(higher_transport)')
                        higher_transport = HandshakeTransport(self.transport)
                        self.higherProtocol().connection_made(higher_transport)
                    else:
                        self.handshakeComplete = False
                        responsePacket = HandshakePacket(status=HandshakePacket.ERROR,
                                                         error=self._mode + ': SYN does not match or ACK is not set correctly!')
                        packetBytes = responsePacket.__serialize__()

                        logger.debug('Sending:\n' +
                                     'Info: \n' +
                                     'SYN: ' + str(responsePacket.SYN) + '\n' +
                                     'ack: ' + str(responsePacket.ACK) + '\n' +
                                     'status: ' + str(responsePacket.status) + '\n' +
                                     'error: ' + str(responsePacket.error) + '\n')

                        self.transport.write(packetBytes)
                elif self._mode == 'server':
                    if (packet.ACK != FIELD_NOT_SET and packet.ACK == (self.SYN + 1) % int(math.pow(2, 32))) and \
                            (packet.SYN != FIELD_NOT_SET and 0 <= packet.SYN < int(math.pow(2, 32))) and \
                            packet.error == FIELD_NOT_SET:
                        self.handshakeComplete = True
                        self.SYN = (self.SYN + 1) % int(math.pow(2, 32))
                        logger.debug('Server-side POOP calling self.higherProtocol().connection_made(higher_transport)')
                        higher_transport = HandshakeTransport(self.transport)
                        self.higherProtocol().connection_made(higher_transport)
                    else:
                        self.handshakeComplete = False
                        responsePacket = HandshakePacket(status=HandshakePacket.ERROR,
                                                         error=self._mode + ': SYN does not match!')
                        packetBytes = responsePacket.__serialize__()

                        logger.debug('Sending:\n' +
                                     'Info: \n' +
                                     'SYN: ' + str(responsePacket.SYN) + '\n' +
                                     'ack: ' + str(responsePacket.ACK) + '\n' +
                                     'status: ' + str(responsePacket.status) + '\n' +
                                     'error: ' + str(responsePacket.error) + '\n')

                        self.transport.write(packetBytes)
            elif packet.status == HandshakePacket.NOT_STARTED:
                if (packet.ACK == FIELD_NOT_SET or packet.ACK == 0) and packet.error == FIELD_NOT_SET and 0 <= packet.SYN < int(math.pow(2, 32)):
                    ack = (packet.SYN + 1) % int(math.pow(2, 32))
                    returnPacket = HandshakePacket(SYN=self.SYN, ACK=ack, status=HandshakePacket.SUCCESS)
                    packetBytes = returnPacket.__serialize__()

                    logger.debug('Sending:\n' +
                                 'Info: \n' +
                                 'SYN: ' + str(returnPacket.SYN) + '\n' +
                                 'ack: ' + str(returnPacket.ACK) + '\n' +
                                 'status: ' + str(returnPacket.status) + '\n'
                                                                         'error: ' + str(returnPacket.error) + '\n')

                    self.transport.write(packetBytes)
                else:
                    self.handshakeComplete = False
                    responsePacket = HandshakePacket(status=HandshakePacket.ERROR,
                                                     error=self._mode + ': Incorrect ACK or Incorrect Error!')
                    packetBytes = responsePacket.__serialize__()

                    logger.debug('Sending:\n' +
                                 'Info: \n' +
                                 'SYN: ' + str(responsePacket.SYN) + '\n' +
                                 'ack: ' + str(responsePacket.ACK) + '\n' +
                                 'status: ' + str(responsePacket.status) + '\n' +
                                 'error: ' + str(responsePacket.error) + '\n')

                    self.transport.write(packetBytes)
            elif packet.status == HandshakePacket.ERROR:
                self.handshakeComplete = False
                logger.debug('{}-side POOP got ERROR packet. {}'.format(self._mode, packet.error))

    def connection_made(self, transport):
        self.transport = transport
        self.SYN = random.randint(0, int(math.pow(2, 32)) - 1)  # To understand: self.SYN for client is X and for server is Y

        if self._mode == "client":
            packet = HandshakePacket(SYN=self.SYN, status=HandshakePacket.NOT_STARTED)
            packetBytes = packet.__serialize__()

            logger.debug('Sending:\n' +
                         'Info: \n' +
                         'SYN: ' + str(packet.SYN) + '\n' +
                         'ack: ' + str(packet.ACK) + '\n' +
                         'status: ' + str(packet.status) + '\n' +
                         'error: ' + str(packet.error) + '\n')

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



