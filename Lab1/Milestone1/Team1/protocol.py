from playground.network.common import StackingProtocolFactory, StackingProtocol, StackingTransport
from playground.network.packet.fieldtypes import UINT8, STRING, BUFFER, UINT16, BOOL
from playground.network.packet.fieldtypes.attributes import Optional
from playground.network.packet import PacketType
import logging
import Crypto.Hash.MD5 as MD5
import Crypto.PublicKey.RSA as RSA
import os
import random
import string

logger = logging.getLogger("playground.__connector__." + __name__)


class PassthroughPacket(PacketType):
    DEFINITION_IDENTIFIER = "passthroughpacket"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("syn", BOOL({Optional: True})),
        ("ack", BOOL({Optional: True})),
        ("certificate", BUFFER({Optional: True})),
        ("public_key", BUFFER({Optional: True})),
        ("challenge", STRING({Optional: True})),
        ("signature", BUFFER({Optional: True})),
        ("seq_num", UINT16({Optional: True})),
    ]


class PassthroughTransport(StackingTransport):
    def write(self, data):
        passthrough_packet = PassthroughPacket()
        passthrough_packet.data = data
        self.lowerTransport().write(passthrough_packet.__serialize__())


class PassthroughProtocol(StackingProtocol):
    def __init__(self, mode):
        super().__init__()
        self._mode = mode
        # Using RSA for our signature scheme. The public key is derived from the secret key
        self.secret_key_generator = RSA.generate(1024, os.urandom)
        self.public_key_generator = self.secret_key_generator.publickey()
        self.secret_key = self.secret_key_generator.exportKey('PEM')
        self.public_key = self.public_key_generator.exportKey('PEM')
        self.deserializer = PassthroughPacket.Deserializer()
        self.seq_num = random.randint(0, 127)
        self.handshake_complete = False

    def data_received(self, data):
        # print('passthrough: something received: ' + str(data))
        logger.debug("{} passthrough received a buffer of size {}".format(self._mode, len(data)))

        self.deserializer.update(data)
        for packet in self.deserializer.nextPackets():
            if not self.handshake_complete:
                print('Packet Received: \n' +
                      'Info: \n' +
                      'syn: ' + str(packet.syn) + '\n'
                                                  'ack: ' + str(packet.ack) + '\n'
                                                                              'certificate: ' + str(
                    packet.certificate) + '\n'
                                          'public key: ' + str(packet.public_key) + '\n'
                                                                                    'challenge: ' + str(
                    packet.challenge) + '\n'
                                        'signature: ' + str(packet.signature) + '\n'
                                                                                'seq_num: ' + str(
                    packet.seq_num) + '\n')
                if (packet.syn and packet.ack):
                    generator = RSA.importKey(packet.public_key)
                    signature = int(packet.signature.decode())
                    signature = (signature,)
                    passChallenge = generator.verify(MD5.new(self.challenge.encode()).digest(), signature)
                    print(passChallenge)
                    if (passChallenge):
                        responsePacket = PassthroughPacket(ack=True, seq_num=self.seq_num + 1)
                        print('Sending: ack\n' +
                              'Info: \n' +
                              'syn: ' + str(responsePacket.syn) + '\n'
                                                                  'ack: ' + str(responsePacket.ack) + '\n'
                                                                                                      'certificate: ' + str(
                            responsePacket.certificate) + '\n'
                                                          'public key: ' + str(responsePacket.public_key) + '\n'
                                                                                                            'challenge: ' + str(
                            responsePacket.challenge) + '\n'
                                                        'signature: ' + str(responsePacket.signature) + '\n'
                                                                                                        'seq_num: ' + str(
                            responsePacket.seq_num) + '\n'
                              )
                        packetBytes = responsePacket.__serialize__()
                        self.transport.write(packetBytes)
                    else:  # retries handshake - shouldn't be done by the server :|
                        raise Exception('Something went wrong with the handshake')
                        # letters = string.ascii_lowercase
                        # self.challenge = ''.join(random.choice(letters) for i in range(128))
                        # responsePacket = PassthroughPacket(syn = True, challenge = self.challenge)
                        # print('Sending: retry-handshake\n' +
                        #       'Info: \n' +
                        #       'syn: ' + str(responsePacket.syn) + '\n'
                        #       'ack: ' + str(responsePacket.ack) + '\n'
                        #       'certificate: ' + str(responsePacket.certificate) + '\n'
                        #       'public key: ' + str(responsePacket.public_key) + '\n'
                        #       'challenge: ' + str(responsePacket.challenge) + '\n'
                        #       'signature: ' + str(responsePacket.signature) + '\n'
                        #       'seq_num: ' + str(responsePacket.seq_num) + '\n'
                        #       )
                        # packetBytes = responsePacket.__serialize__()
                        # self.transport.write(packetBytes)
                elif (packet.syn):
                    digest = MD5.new(packet.challenge.encode()).digest()
                    signature = self.secret_key_generator.sign(digest, "")[0]
                    signature = str(signature).encode()
                    responsePacket = PassthroughPacket(syn=True, ack=True, signature=signature,
                                                       public_key=self.public_key)
                    print('Sending: syn-ack\n' +
                          'Info: \n' +
                          'syn: ' + str(responsePacket.syn) + '\n'
                                                              'ack: ' + str(responsePacket.ack) + '\n'
                                                                                                  'certificate: ' + str(
                        responsePacket.certificate) + '\n'
                                                      'public key: ' + str(responsePacket.public_key) + '\n'
                                                                                                        'challenge: ' + str(
                        responsePacket.challenge) + '\n'
                                                    'signature: ' + str(responsePacket.signature) + '\n'
                                                                                                    'seq_num: ' + str(
                        responsePacket.seq_num) + '\n'
                          )
                    packetBytes = responsePacket.__serialize__()
                    self.transport.write(packetBytes)
                elif (packet.ack and not self.handshake_complete):
                    print("Handshake Completed")
                    self.handshake_complete = True
            else: # a packet for the higher protocol
                self.higherProtocol().data_received(packet)

    def connection_made(self, transport):
        self.transport = transport
        logger.debug("{} passthrough connection made. Calling connection made higher.".format(self._mode))
        higher_transport = PassthroughTransport(transport)
        self.higherProtocol().connection_made(higher_transport)

        if self._mode == "client":
            letters = string.ascii_lowercase
            self.challenge = ''.join(
                random.choice(letters) for i in range(128))  # Create random 128 length strings for challenge
            responsePacket = PassthroughPacket(syn=True, challenge=self.challenge)
            print('Sending: syn\n' +
                  'Info: \n' +
                  'syn: ' + str(responsePacket.syn) + '\n'
                                                      'ack: ' + str(responsePacket.ack) + '\n'
                                                                                          'certificate: ' + str(
                responsePacket.certificate) + '\n'
                                              'public key: ' + str(responsePacket.public_key) + '\n'
                                                                                                'challenge: ' + str(
                responsePacket.challenge) + '\n'
                                            'signature: ' + str(responsePacket.signature) + '\n'
                                                                                            'seq_num: ' + str(
                responsePacket.seq_num) + '\n'
                  )
            packetBytes = responsePacket.__serialize__()
            self.transport.write(packetBytes)

    def connection_lost(self, exc):
        logger.debug("{} passthrough connection lost. Shutting down higher layer.".format(self._mode))
        self.higherProtocol().connection_lost(exc)


PassthroughClientFactory = StackingProtocolFactory.CreateFactoryType(
    lambda: PassthroughProtocol(mode="client")
)

PassthroughServerFactory = StackingProtocolFactory.CreateFactoryType(
    lambda: PassthroughProtocol(mode="server")
)

