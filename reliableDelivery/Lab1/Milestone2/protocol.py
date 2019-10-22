from playground.network.common import StackingProtocolFactory, StackingProtocol, StackingTransport
from playground.network.packet import PacketType, FIELD_NOT_SET
import logging
import random
from .packets import *
import math,binascii

logger = logging.getLogger("playground.__connector__." + __name__)

# max value a UINT32 can store
MAX_UINT32 = int(math.pow(2,32) - 1)


def is_set(*fields):
    for field in fields:
        if field == FIELD_NOT_SET:
            return False
    return True


def increment_mod(data):
    return (data + 1) % (MAX_UINT32 + 1)


def getHash(data):
    return binascii.crc32(data) & 0xffffffff


class PoopTransport(StackingTransport):

    def __init__(self, transport):
        super().__init__(transport)
        self.send_seq = None
        self.rcv_seq = None

    def setMode(self, mode):
        logger.debug('setting PoopTransport mode to {}'.format(mode))
        self._mode = mode

    def setSeq(self, send_seq, rcv_seq):
        self.send_seq = send_seq
        self.rcv_seq = rcv_seq

    def write(self, data):
        datahash = getHash(data)
        logger.debug('{} side PoopTransport.write(). Info:\n'
                     'seq: {}\n'
                     'data: {}\n'
                     'datahash: {}\n'.format(self._mode, self.send_seq, data, datahash))
        p = PoopDataPacket(seq=self.send_seq, data=data, datahash=datahash)
        self.lowerTransport().write(p.__serialize__())
        logger.debug('{} side setting send_seq = {}'.format(self._mode, self.send_seq))
        self.send_seq = increment_mod(self.send_seq)


class PoopHandshakeClientProtocol(StackingProtocol):
    def __init__(self):
        super().__init__()
        self._mode = "CLIENT"
        self.deserializer = PoopPacketType.Deserializer()
        self.syn = None     # will be used to sequence outbound packets... by feeding original syn value to a transport which will store the value and do the arithmetic for the client
        self.ack = None     # will be used to check sequence of incoming packets
        self.handshakeComplete = False
        self.state = 0      # increments by 1 for each packet sent during the handshake
        self.transport_protocol = None

    def connection_made(self, transport):
        self.transport = transport
        self.syn = random.randint(0, MAX_UINT32)    # self.syn = X
        packet = PoopHandshakePacket(syn=self.syn, status=PoopHandshakePacket.NOT_STARTED)  # pkt.syn = X
        packetBytes = packet.__serialize__()
        logger.debug('{} side setting state to {}'.format(self._mode, self.state+1))
        self.state += 1
        logger.debug('{} side sending packet. Info:\n'
                     'syn: {}\n'
                     'ack: {}\n'
                     'status: {}\n'
                     'error: {}\n'.format(self._mode, packet.syn, packet.ack, packet.status, packet.error))
        self.transport.write(packetBytes)

    def handle_handshake_error(self):
        self.handshakeComplete = False
        self.state = 0

    def data_received(self, data):
        logger.debug("{} POOP received a buffer of size {}".format(self._mode, len(data)))
        logger.debug("{} POOP current state: {}".format(self._mode, self.state))
        self.deserializer.update(data)
        if self.handshakeComplete:
            logger.debug("{} mode, data: {}".format(self._mode, data))
            for pkt in self.deserializer.nextPackets():
                if isinstance(pkt, PoopDataPacket):
                    logger.debug("{} side packet recieved: Info:\n"
                                 "seq: {}\n"
                                 "data: {}\n"
                                 "datahash: {}\n".format(self._mode, pkt.seq, pkt.data, pkt.datahash))
                    if is_set(pkt.seq, pkt.data, pkt.datahash):
                        # do check if seq number matches
                        logger.debug('{} side checking {} == {}'.format(self._mode, pkt.seq, increment_mod(self.transport_protocol.rcv_seq)))
                        if pkt.seq == increment_mod(self.transport_protocol.rcv_seq):
                            datahash = getHash(pkt.data)
                            logger.debug('{} side checking {} == {}'.format(self._mode, pkt.datahash, datahash))
                            if pkt.datahash == datahash:
                                self.transport_protocol.rcv_seq = increment_mod(self.transport_protocol.rcv_seq)
                                logger.debug('{} side setting rcv_seq = {}'.format(self._mode, self.transport_protocol.rcv_seq))
                                self.higherProtocol().data_received(pkt.data)
                            else:
                                error = 'data corruption error: pkt.datahash != getHash(pkt.data)'
                                logger.debug(
                                    '{} side ERROR = {}'.format(self._mode, error))
                                # TODO
                        else:
                            error = 'pkt.seq != increment_mod(self.transport_protocol.rcv_seq)'
                            logger.debug(
                                '{} side ERROR = {}'.format(self._mode, error))
                            # TODO error
                    else:
                        error = 'Either pkt.seq, pkt.data or pkt.datahash are not set'
                        logger.debug(
                            '{} side ERROR = {}'.format(self._mode, error))
                        # TODO error
                else:
                    error = 'got something other than a PoopDataPacket: ignore'
                    logger.debug(
                        '{} side ERROR = {}'.format(self._mode, error))

        # do handshake
        else:
            for pkt in self.deserializer.nextPackets():
                if isinstance(pkt, PoopHandshakePacket):
                    if self.state==1 and pkt.status==PoopHandshakePacket.SUCCESS and is_set(pkt.syn, pkt.ack) and not is_set(pkt.error):
                        if pkt.ack==increment_mod(self.syn):
                            self.ack = pkt.syn # self.ack = Y
                            self.syn = pkt.ack # self.syn = X+1
                            p = PoopHandshakePacket(status=PoopHandshakePacket.SUCCESS)
                            p.syn = self.syn # p.syn = X+1
                            p.ack = increment_mod(self.ack) # p.ack = Y+1
                            logger.debug('{} side sending packet:\nsyn: {}\nack: {}\nstatus: {}\nerror: {}'.format(self._mode, p.syn, p.ack, p.status, p.error))
                            self.transport.write(p.__serialize__())
                            logger.debug('{} side setting state to {}'.format(self._mode, self.state+1))
                            self.state += 1
                            logger.debug('{} side setting handshakeComplete to True'.format(self._mode))
                            self.handshakeComplete = True
                            # should this go back in connection_made() ?
                            higher_transport = PoopTransport(self.transport)
                            higher_transport.setMode(self._mode)
                            # send_seq = Y+1
                            # rcv_seq = X+1
                            send_seq = increment_mod(self.ack)
                            rcv_seq = self.syn
                            logger.debug('{} side setting send_seq to {} and rcv_seq to {}'.format(self._mode,
                                                                                                             send_seq,
                                                                                                             rcv_seq))
                            higher_transport.setSeq(send_seq=send_seq, rcv_seq=rcv_seq)
                            self.transport_protocol = higher_transport
                            logger.debug('{} side calling self.higherProtocol().connection_made()'.format(self._mode))
                            # higher_transport.setSeq(pkt.syn) # c_t.seq = Y
                            self.higherProtocol().connection_made(self.transport_protocol)
                        else:
                            # What should be done if the error is noticed by the client side
                            self.handle_handshake_error()
                            # ack does not match syn+1
                            # I don't think this is part of milestone 2 yet
                            p = PoopHandshakePacket(status=PoopHandshakePacket.ERROR)
                            p.error = 'Client: Ack does not match Syn + 1'
                            logger.debug('{} side sending packet. Info:\n'
                                         'syn: {}\n'
                                         'ack: {}\n'
                                         'status: {}\n'
                                         'error: {}'.format(self._mode, p.syn, p.ack, p.status, p.error))
                            self.transport.write(p.__serialize__())
                    elif pkt.status == PoopHandshakePacket.ERROR:
                        logger.debug('Client: An error packet was received from the server: ' + str(pkt.error))
                        # What should be done if the server has identified the error and sent the client an error packet
                        self.handle_handshake_error()

                    else:
                        # What should be done if the error is noticed by the client side
                        # either state != 1 or status != SUCCESS or syn not set or ack not set
                        self.handle_handshake_error()
                        p = PoopHandshakePacket(status=PoopHandshakePacket.ERROR)
                        p.error = 'Client: Either state != 1 or status != SUCCESS or syn not set or ack not set'
                        logger.debug(
                            '{} side sending packet:\nsyn: {}\nack: {}\nstatus: {}\nerror: {}'.format(self._mode, p.syn,
                                                                                                      p.ack, p.status,
                                                                                                      p.error))
                        self.transport.write(p.__serialize__())
                else:
                    # not the PoopHandshakePacket: ignore
                    pass

    def connection_lost(self, exc):
        logger.debug("{} POOP connection lost. Shutting down higher layer.".format(self._mode))
        self.higherProtocol().connection_lost(exc)


class PoopHandshakeServerProtocol(StackingProtocol):
    def __init__(self):
        super().__init__()
        self._mode = "SERVER"
        self.deserializer = PoopPacketType.Deserializer()
        self.syn = None     # will be used to sequence outbound packets... by feeding original syn value to a transport which will store the value and do the arithmetic for the client
        self.ack = None     # will be used to sequence of incoming packets
        self.handshakeComplete = False
        self.state = 0      # increments by 1 for each packet sent during the handshake
        self.transport_protocol = None

    def connection_made(self, transport):
        self.transport = transport

    def handle_handshake_error(self):
        self.handshakeComplete = False
        self.state = 0

    def data_received(self, data):
        logger.debug("{} POOP received a buffer of size {}".format(self._mode, len(data)))
        logger.debug("{} POOP current state: {}".format(self._mode, self.state))
        self.deserializer.update(data)
        if self.handshakeComplete:
            for pkt in self.deserializer.nextPackets():
                if isinstance(pkt, PoopDataPacket):
                    logger.debug("{} side packet recieved: Info:\n"
                                 "seq: {}\n"
                                 "data: {}\n"
                                 "datahash: {}\n".format(self._mode, pkt.seq, pkt.data, pkt.datahash))
                    if is_set(pkt.data, pkt.seq, pkt.datahash):
                        # do check if seq number matches
                        logger.debug('{} side checking {} == {}'.format(self._mode, pkt.seq, increment_mod(self.transport_protocol.rcv_seq)))
                        if pkt.seq == increment_mod(self.transport_protocol.rcv_seq):
                            datahash = getHash(pkt.data)
                            logger.debug('{} side checking {} == {}'.format(self._mode, pkt.datahash, datahash))
                            if pkt.datahash == datahash:
                                self.transport_protocol.rcv_seq = increment_mod(self.transport_protocol.rcv_seq)
                                logger.debug('{} side setting p.ack to rcv_seq = {}'.format(self._mode, self.transport_protocol.rcv_seq))
                                self.higherProtocol().data_received(pkt.data)
                            else:
                                error = 'data corruption error: pkt.datahash != getHash(pkt.data)'
                                logger.debug(
                                    '{} side ERROR = {}'.format(self._mode, error))
                                # TODO
                        else:
                            error = 'pkt.seq != increment_mod(self.transport_protocol.rcv_seq)'
                            logger.debug(
                                '{} side ERROR = {}'.format(self._mode, error))
                            # TODO error
                    else:
                        error = 'Either pkt.seq, pkt.data or pkt.datahash are not set'
                        logger.debug(
                            '{} side ERROR = {}'.format(self._mode, error))
                        # TODO error
                else:
                    error = 'got something other than a PoopDataPacket: ignore'
                    logger.debug(
                        '{} side ERROR = {}'.format(self._mode, error))

        # do handshake
        else:
            for pkt in self.deserializer.nextPackets():
                if isinstance(pkt, PoopHandshakePacket):
                    logger.debug('{} side packet received:\nsyn: {}\nack: {}\nstatus: {}\nerror: {}'.format(self._mode, pkt.syn, pkt.ack, pkt.status, pkt.error))
                    # should receive syn = X
                    if self.state==0 and pkt.status==PoopHandshakePacket.NOT_STARTED and is_set(pkt.syn) and not is_set(pkt.error):
                        self.ack = pkt.syn # self.ack = X
                        self.syn = random.randint(0, MAX_UINT32) # self.syn = Y
                        p = PoopHandshakePacket(status=PoopHandshakePacket.SUCCESS)
                        p.syn = self.syn # p.syn = Y
                        p.ack = increment_mod(self.ack) # p.ack = X+1
                        logger.debug('{} side setting state to {}'.format(self._mode, self.state+1))
                        self.state += 1
                        logger.debug('{} side sending packet:\nsyn: {}\nack: {}\nstatus: {}\nerror: {}'.format(self._mode, p.syn, p.ack, p.status, p.error))
                        self.transport.write(p.__serialize__())
                    # should receive syn = (X+1)mod2^32 and ack = (Y+1)mod2^32
                    elif self.state==1 and pkt.status==PoopHandshakePacket.SUCCESS and is_set(pkt.syn, pkt.ack) and not is_set(pkt.error):
                        # if handshake successful
                        if pkt.ack == increment_mod(self.syn) and pkt.syn == increment_mod(self.ack):
                            logger.debug('{} side setting handshakeComplete to True'.format(self._mode))
                            self.handshakeComplete = True
                            self.ack = pkt.syn
                            # should this go back in connection_made() ?

                            higher_transport = PoopTransport(self.transport)
                            higher_transport.setMode(self._mode)
                            # send_seq = X+1
                            # rcv_seq = Y
                            send_seq = increment_mod(self.ack)
                            rcv_seq = self.syn
                            logger.debug('{} side setting send_seq to {} and rcv_seq to {}'.format(self._mode,
                                                                                                             send_seq,
                                                                                                             rcv_seq))
                            higher_transport.setSeq(send_seq=send_seq, rcv_seq=rcv_seq)
                            self.transport_protocol = higher_transport
                            logger.debug('{} side calling self.higherProtocol().connection_made()'.format(self._mode))
                            # higher_transport.setSeq(pkt.syn) # c_t.seq = Y
                            self.higherProtocol().connection_made(self.transport_protocol)
                        else:
                            # What should be done if the error is noticed by the server side
                            # ack != self.syn + 1 or syn != self.ack + 1
                            self.handle_handshake_error()
                            p = PoopHandshakePacket(status=PoopHandshakePacket.ERROR)
                            p.error = 'Server: ack != self.syn + 1 or syn != self.ack + 1'
                            logger.debug(
                                '{} side sending packet:\nsyn: {}\nack: {}\nstatus: {}\nerror: {}'.format(self._mode,
                                                                                                          p.syn,
                                                                                                          p.ack,
                                                                                                          p.status,
                                                                                                          p.error))
                            self.transport.write(p.__serialize__())
                    elif pkt.status == PoopHandshakePacket.ERROR:
                        logger.debug('Server: An error packet was received from the client: ' + str(pkt.error))
                        self.handle_handshake_error()
                        # What should be done if the client has identified the error and sent the server an error packet

                    else:
                        # What should be done if the error is noticed by the server side
                        # invalid state and PoopHandshakePacket.status combination
                        self.handle_handshake_error()
                        p = PoopHandshakePacket(status=PoopHandshakePacket.ERROR)
                        p.error = 'Server: invalid state and PoopHandshakePacket.status combination'
                        logger.debug(
                            '{} side sending packet:\nsyn: {}\nack: {}\nstatus: {}\nerror: {}'.format(self._mode,
                                                                                                      p.syn,
                                                                                                      p.ack,
                                                                                                      p.status,
                                                                                                      p.error))
                        self.transport.write(p.__serialize__())
                else:
                    # What should be done if the error is noticed by the server side
                    # not the PoopHandshakePacket: ignore
                    pass

    def connection_lost(self, exc):
        logger.debug("{} POOP connection lost. Shutting down higher layer.".format(self._mode))
        self.higherProtocol().connection_lost(exc)

PoopHandshakeClientFactory = StackingProtocolFactory.CreateFactoryType(PoopHandshakeClientProtocol)

PoopHandshakeServerFactory = StackingProtocolFactory.CreateFactoryType(PoopHandshakeServerProtocol)
