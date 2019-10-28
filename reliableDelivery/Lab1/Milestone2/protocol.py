import threading

from playground.network.common import StackingProtocolFactory, StackingProtocol, StackingTransport
from playground.network.packet import PacketType, FIELD_NOT_SET
import logging
import random
from packets import * # for unit testing
# from .packets import *
import math, binascii
from collections import deque
# from .sized_dict import SizedDict
from sized_dict import SizedDict # for unit testing

logger = logging.getLogger("playground.__connector__." + __name__)

# max value a UINT32 can store
MAX_UINT32 = int(math.pow(2,32) - 1)

# Max Transmission Unit (max length of the data field)
MTU = 1500

# Max SizedDict size
SD_SIZE = 1

# Timeout
timeout_time = 5

'''
Utility functions
'''

# Returns True if all fields are set, otherwise False
def is_set(*fields):
    for field in fields:
        if field == FIELD_NOT_SET:
            return False
    return True


def not_set(*fields):
    for field in fields:
        if is_set(field):
            return False
    return True


def increment_mod(x):
    return (x + 1) % (MAX_UINT32 + 1)


def decrement_mod(x):
    return (x - 1) % (MAX_UINT32 + 1)


def getHash(data):
    return binascii.crc32(data) & 0xffffffff

class PoopTransport(StackingTransport):

    def __init__(self, transport):
        super().__init__(transport)
        self.send_seq = None
        self.rcv_seq = None
        self.timeout = None

    def close(self):
        p = ShutdownPacket()
        max_seq = None
        for seq in iter(self.send_buf):
            if max_seq is None or seq >= max_seq:
                max_seq = seq
        p.last_valid_sequence = self.pt.max_seq
        logger.debug(
            '{} side sending packet:\n'
            'syn: {}\n'
            'ack: {}\n'
            'status: {}\n'
            'error: {}\n'
            'last_valid_sequence: {}'.format(self._mode, p.SYN, p.ACK, p.status, p.error, p.last_valid_sequence))
        self.lowerTransport().write(p.__serialize__())

    def setMode(self, mode):
        logger.debug('setting PoopTransport mode to {}'.format(mode))
        self._mode = mode

    def setSeq(self, send_seq, rcv_seq):
        self.send_seq = send_seq
        self.rcv_seq = rcv_seq

    def setDataBuf(self, dataq):
        self.dataq = dataq # collections.deque

    def setSendBuf(self, send_buf):
        self.send_buf = send_buf # SizedDict


    def write(self, data):
        logger.debug('{} side transport.write() data of len {}'.format(self._mode, len(data)))
        self.add_data(data)
        self.fill_send_buf()
        self.write_send_buf()

    def add_data(self, data):
        logger.debug('{} side transport in add_data()'.format(self._mode))
        data_len = len(data)
        i = 0
        j = MTU
        n = data_len // MTU
        n += 1 if data_len % MTU > 0 else 0
        logger.debug('{} side n = {}'.format(self._mode, n))
        for _ in range(n):
            p_data = data[i:min(j, data_len)]
            logger.debug('{} side transport, iteration {}, appending to dataq a data chunk of size {}'.format(self._mode, _, len(p_data)))
            self.dataq.append(p_data)
            i += MTU
            j += MTU
            logger.debug('{} side incrementing i and j to {} and {}'.format(self._mode, i, j))

    def fill_send_buf(self):
        logger.debug('{} side transport in fill_send_buf()'.format(self._mode))
        for _ in range(min(SD_SIZE-len(self.send_buf), len(self.dataq))):
            logger.debug('{} side transport, iteration {}, filling self.send_buf with a PoopDataPacket and seq {}'.format(self._mode, _, self.send_seq))
            p = DataPacket()
            p.seq = self.send_seq
            p.data = self.dataq.popleft()
            p.hash = DataPacket.DEFAULT_DATAHASH
            p.hash = getHash(p.__serialize__())
            self.send_buf[self.send_seq] = p
            self.send_seq = increment_mod(self.send_seq)

    def write_send_buf(self):
        logger.debug('{} side transport in write_buf()'.format(self._mode))
        for seq in iter(self.send_buf):
            logger.debug('{} side transport writing packet with seq {}'.format(self._mode, seq))
            logger.debug('{} side PoopTransport.write(). Info:\n'
                         'seq: {}\n'
                         'data: {}\n'
                         'hash: {}\n'.format(self._mode, self.send_buf[seq].seq, self.send_buf[seq].data, self.send_buf[seq].hash))
            self.lowerTransport().write(self.send_buf[seq].__serialize__())
        self.timeout = threading.Timer(timeout_time, self.write_send_buf)
        self.timeout.start()


class PoopHandshakeClientProtocol(StackingProtocol):
    def __init__(self):
        super().__init__()
        self._mode = "CLIENT"
        self.deserializer = PoopPacketType.Deserializer()
        self.syn = None     # will be used to sequence outbound packets... by feeding original syn value to a transport which will store the value and do the arithmetic for the client
        self.ack = None     # will be used to check sequence of incoming packets
        self.handshakeComplete = False
        self.state = 0      # increments by 1 for each packet sent during the handshake
        self.pt = None # Poop Transport given to higher layer
        self.dataq = deque()
        self.send_buf = SizedDict(SD_SIZE)


    def connection_made(self, transport):
        self.transport = transport
        self.syn = random.randint(0, MAX_UINT32)    # self.syn = X
        packet = HandshakePacket(SYN=self.syn, status=HandshakePacket.NOT_STARTED)  # pkt.syn = X
        packetBytes = packet.__serialize__()
        logger.debug('{} side setting state to {}'.format(self._mode, self.state+1))
        self.state += 1
        logger.debug('{} side sending packet. Info:\n'
                     'syn: {}\n'
                     'ack: {}\n'
                     'status: {}\n'
                     'error: {}\n'
                     'last_valid_sequence: {}\n'.format(self._mode, packet.SYN, packet.ACK, packet.status, packet.error, packet.last_valid_sequence))
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
                if isinstance(pkt, DataPacket):
                    logger.debug("{} side packet recieved: Info:\n"
                                 "seq: {}\n"
                                 "ack: {}\n"
                                 "data: {}\n"
                                 "hash: {}\n".format(self._mode, pkt.seq, pkt.ACK, pkt.data, pkt.hash))
                    # recieved data packet
                    if not_set(pkt.ack) and is_set(pkt.seq, pkt.data, pkt.hash):
                        # do check if seq number matches
                        logger.debug('{} side checking {} == {}'.format(self._mode, pkt.seq, increment_mod(self.pt.rcv_seq)))
                        if pkt.seq == increment_mod(self.pt.rcv_seq):
                            # datahash = getHash(pkt.data)
                            pkt_hash = pkt.hash # received datahash
                            pkt.hash = DataPacket.DEFAULT_DATAHASH
                            gen_hash = getHash(pkt.__serialize__()) # generated datahash

                            # logger.debug('{} side checking {} == {}'.format(self._mode, pkt.datahash, datahash))
                            logger.debug('{} side checking {} == {}'.format(self._mode, pkt_hash, gen_hash))
                            # if pkt.datahash == datahash:
                            if pkt_hash == gen_hash:
                                logger.debug('{} side sending ack = {}'.format(self._mode, self.pt.rcv_seq))
                                ack_p = DataPacket(ACK=pkt.seq)
                                ack_p.hash = DataPacket.DEFAULT_DATAHASH
                                ack_p.hash = getHash(ack_p.__serialize__())
                                self.transport.write(ack_p.__serialize__())
                                logger.debug('{} side setting rcv_seq - 1 = {}'.format(self._mode, increment_mod(self.pt.rcv_seq)))
                                self.pt.rcv_seq = increment_mod(self.pt.rcv_seq)
                                self.higherProtocol().data_received(pkt.data)
                            else:
                                error = 'data corruption error: pkt.datahash != getHash(pkt.data)'
                                logger.debug(
                                    '{} side ERROR = {}. Resending last sent ack = {}'.format(self._mode, error, self.pt.rcv_seq))
                                # Resend last successful ack
                                ack_p = DataPacket(ACK=self.pt.rcv_seq)
                                ack_p.hash = DataPacket.DEFAULT_DATAHASH
                                ack_p.hash = getHash(ack_p.__serialize__())
                                self.transport.write(ack_p.__serialize__())
                        else:
                            # just drop the packet?
                            error = 'pkt.seq != self.pt.rcv_seq'
                            logger.debug(
                                '{} side ERROR = {}. Dropping packet.'.format(self._mode, error))
                            # TODO error
                    # received data ack
                    elif is_set(pkt.ACK) and not_set(pkt.data, pkt.seq, pkt.hash):
                        logger.debug('{} side received data ack'.format(self._mode))
                        pkt_hash = pkt.hash # received datahash
                        pkt.hash = DataPacket.DEFAULT_DATAHASH
                        gen_hash = getHash(pkt.__serialize__()) # generated datahash

                        # logger.debug('{} side checking {} == {}'.format(self._mode, pkt.datahash, datahash))
                        logger.debug('{} side checking {} == {}'.format(self._mode, pkt_hash, gen_hash))
                        # if pkt.datahash == datahash:
                        if pkt_hash == gen_hash:
                            logger.debug('{} side received ack = {}'.format(self._mode, pkt.ACK))
                            if self.pt.timeout is not None:
                                self.pt.timeout.cancel()
                                self.pt.timeout = None
                            # if pkt.ack in self.send_buf:
                            del self.send_buf[pkt.ACK] # don't need to resend acked data packets
                            self.pt.fill_send_buf() # refill send_buf
                            self.pt.write_send_buf() # resend send_buf
                    else:
                        error = 'Either pkt.seq, pkt.data or pkt.datahash are not set'
                        logger.debug(
                            '{} side ERROR = {}'.format(self._mode, error))
                        # TODO error

                elif isinstance(pkt, ShutdownPacket):
                    logger.debug('{} side received shutdown packet:\n'
                                 'syn: {}\n'
                                 'ack: {}\n'
                                 'status: {}\n'
                                 'error: {}\n'
                                 'last_valid_sequence: {}'.format(self._mode, pkt.SYN, pkt.ACK, pkt.status, pkt.error,
                                                                  pkt.last_valid_sequence))
                    if is_set(pkt.last_valid_sequence, pkt.ACK) and not_set(pkt.SYN, pkt.status, pkt.error):
                        self.connection_lost(None)
                    elif is_set(pkt.last_valid_sequence) and not_set(pkt.SYN, pkt.ACK, pkt.status, pkt.error):
                        if self.pt.rcv_seq >= pkt.last_valid_sequence:
                            p = ShutdownPacket()
                            p.ACK = pkt.last_valid_sequence
                            max_seq = None
                            for seq in iter(self.pt.send_buf):
                                if max_seq is None or seq >= max_seq:
                                    max_seq = seq
                            p.last_valid_sequence = max_seq
                            self.transport.write(p.__serialize__())

                        else:
                            # Error: some packets are still left to be received
                            p = ShutdownPacket()
                            p.status = ShutdownPacket.ERROR
                            p.error = 'Some packets are still left to be received'
                            self.transport.write(p.__serialize__())
                    elif pkt.status == ShutdownPacket.ERROR and is_set(pkt.error):
                        # Error reported from the other side while trying shutdown
                        # try again
                        p = ShutdownPacket()
                        max_seq = None
                        for seq in iter(self.pt.send_buf):
                            if max_seq is None or seq >= max_seq:
                                max_seq = seq
                        p.last_valid_sequence = self.pt.max_seq
                        logger.debug(
                            '{} side sending packet:\n'
                            'syn: {}\n'
                            'ack: {}\n'
                            'status: {}\n'
                            'error: {}\n'
                            'last_valid_sequence: {}'.format(self._mode, p.SYN, p.ACK, p.status, p.error,
                                                             p.last_valid_sequence))
                        self.transport.write(p.__serialize__())
                    else:
                        # fields not set correctly
                        p = ShutdownPacket()
                        p.status = ShutdownPacket.ERROR
                        p.error = 'fields not set correctly'
                        self.transport.write(p.__serialize__())


                else:
                    error = 'got something other than a PoopDataPacket: ignore'
                    logger.debug(
                        '{} side ERROR = {}'.format(self._mode, error))

        # do handshake
        else:
            for pkt in self.deserializer.nextPackets():
                if isinstance(pkt, HandshakePacket):
                    if self.state==1 and pkt.status==HandshakePacket.SUCCESS and \
                            is_set(pkt.SYN, pkt.ACK) and not_set(pkt.last_valid_sequence, pkt.error):
                        if pkt.ACK==increment_mod(self.syn):
                            self.ack = pkt.SYN # self.ack = Y
                            self.syn = pkt.ACK # self.syn = X+1
                            p = HandshakePacket(status=HandshakePacket.SUCCESS)
                            p.SYN = self.syn # p.syn = X+1
                            p.ACK = increment_mod(self.ack) # p.ack = Y+1
                            logger.debug('{} side sending packet:\n'
                                         'syn: {}\n'
                                         'ack: {}\n'
                                         'status: {}\n'
                                         'error: {}\n'
                                         'last_valid_sequence: {}'.format(self._mode, p.SYN, p.ACK, p.status, p.error, p.last_valid_sequence))
                            self.transport.write(p.__serialize__())
                            logger.debug('{} side setting state to {}'.format(self._mode, self.state+1))
                            self.state += 1
                            logger.debug('{} side setting handshakeComplete to True'.format(self._mode))
                            self.handshakeComplete = True
                            # should this go back in connection_made() ?
                            higher_transport = PoopTransport(self.transport)
                            higher_transport.setMode(self._mode)
                            # send_seq = X
                            # rcv_seq = Y
                            send_seq = decrement_mod(self.syn)
                            rcv_seq = self.ack
                            logger.debug('{} side setting send_seq to {} and rcv_seq to {}'.format(self._mode,
                                                                                                             send_seq,
                                                                                                             rcv_seq))
                            higher_transport.setSeq(send_seq=send_seq, rcv_seq=decrement_mod(rcv_seq))
                            higher_transport.setDataBuf(self.dataq)
                            higher_transport.setSendBuf(self.send_buf)
                            self.pt = higher_transport
                            logger.debug('{} side calling self.higherProtocol().connection_made()'.format(self._mode))
                            # higher_transport.setSeq(pkt.syn) # c_t.seq = Y
                            self.higherProtocol().connection_made(self.pt)
                        else:
                            # What should be done if the error is noticed by the client side
                            self.handle_handshake_error()
                            # ack does not match syn+1
                            # I don't think this is part of milestone 2 yet
                            p = HandshakePacket(status=HandshakePacket.ERROR)
                            p.error = 'Client: Ack does not match Syn + 1'
                            logger.debug('{} side sending packet. Info:\n'
                                         'syn: {}\n'
                                         'ack: {}\n'
                                         'status: {}\n'
                                         'error: {}\n'
                                         'last_valid_sequence: {}'.format(self._mode, p.SYN, p.ACK, p.status, p.error, p.last_valid_sequence))
                            self.transport.write(p.__serialize__())
                    elif pkt.status == HandshakePacket.ERROR:
                        logger.debug('Client: An error packet was received from the server: ' + str(pkt.error))
                        # What should be done if the server has identified the error and sent the client an error packet
                        self.handle_handshake_error()

                    else:
                        # What should be done if the error is noticed by the client side
                        # either state != 1 or status != SUCCESS or syn not set or ack not set
                        self.handle_handshake_error()
                        p = HandshakePacket(status=HandshakePacket.ERROR)
                        p.error = 'Client: Either state != 1 or status != SUCCESS or syn not set or ack not set'
                        logger.debug(
                            '{} side sending packet:\n'
                            'syn: {}\n'
                            'ack: {}\n'
                            'status: {}\n'
                            'error: {}\n'
                            'last_valid_sequence: {}'.format(self._mode, p.SYN, p.ACK, p.status, p.error, p.last_valid_sequence))
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
        self.pt = None # Poop Transport given to higher layer
        self.dataq = deque()
        self.send_buf = SizedDict(SD_SIZE)

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
                if isinstance(pkt, DataPacket):
                    logger.debug("{} side packet recieved: Info:\n"
                                 "seq: {}\n"
                                 "ack: {}\n"
                                 "data: {}\n"
                                 "hash: {}\n".format(self._mode, pkt.seq, pkt.ACK, pkt.data, pkt.hash))
                    # recieved data packet
                    if not_set(pkt.ack) and is_set(pkt.seq, pkt.data, pkt.hash):
                        # do check if seq number matches
                        logger.debug('{} side checking {} == {}'.format(self._mode, pkt.seq, increment_mod(self.pt.rcv_seq)))
                        if pkt.seq == increment_mod(self.pt.rcv_seq):
                            # datahash = getHash(pkt.data)
                            pkt_hash = pkt.hash # received datahash
                            pkt.hash = DataPacket.DEFAULT_DATAHASH
                            gen_hash = getHash(pkt.__serialize__()) # generated datahash

                            # logger.debug('{} side checking {} == {}'.format(self._mode, pkt.datahash, datahash))
                            logger.debug('{} side checking {} == {}'.format(self._mode, pkt_hash, gen_hash))
                            # if pkt.datahash == datahash:
                            if pkt_hash == gen_hash:
                                logger.debug('{} side sending ack = {}'.format(self._mode, self.pt.rcv_seq))
                                ack_p = DataPacket(ACK=pkt.seq)
                                ack_p.hash = DataPacket.DEFAULT_DATAHASH
                                ack_p.hash = getHash(ack_p.__serialize__())
                                self.transport.write(ack_p.__serialize__())
                                logger.debug('{} side setting rcv_seq - 1 = {}'.format(self._mode, increment_mod(self.pt.rcv_seq)))
                                self.pt.rcv_seq = increment_mod(self.pt.rcv_seq)
                                self.higherProtocol().data_received(pkt.data)
                            else:
                                error = 'data corruption error: pkt.datahash != getHash(pkt.data)'
                                logger.debug(
                                    '{} side ERROR = {}. Resending last sent ack = {}'.format(self._mode, error, self.pt.rcv_seq))
                                # Resend last successful ack
                                ack_p = DataPacket(ACK=self.pt.rcv_seq)
                                ack_p.hash = DataPacket.DEFAULT_DATAHASH
                                ack_p.hash = getHash(ack_p.__serialize__())
                                self.transport.write(ack_p.__serialize__())
                        else:
                            # just drop the packet?
                            error = 'pkt.seq != self.pt.rcv_seq'
                            logger.debug(
                                '{} side ERROR = {}. Dropping packet.'.format(self._mode, error))
                            # TODO error
                    # received data ack
                    elif is_set(pkt.ACK) and not_set(pkt.data, pkt.seq, pkt.hash):
                        logger.debug('{} side received data ack'.format(self._mode))
                        pkt_hash = pkt.hash # received datahash
                        pkt.hash = DataPacket.DEFAULT_DATAHASH
                        gen_hash = getHash(pkt.__serialize__()) # generated datahash

                        # logger.debug('{} side checking {} == {}'.format(self._mode, pkt.datahash, datahash))
                        logger.debug('{} side checking {} == {}'.format(self._mode, pkt_hash, gen_hash))
                        # if pkt.datahash == datahash:
                        if pkt_hash == gen_hash:
                            logger.debug('{} side received ack = {}'.format(self._mode, pkt.ACK))
                            if self.pt.timeout is not None:
                                self.pt.timeout.cancel()
                            # if pkt.ack in self.send_buf:
                            del self.send_buf[pkt.ACK] # don't need to resend acked data packets
                            self.pt.fill_send_buf() # refill send_buf
                            self.pt.write_send_buf() # resend send_buf
                    else:
                        error = 'Either pkt.seq, pkt.data or pkt.datahash are not set'
                        logger.debug(
                            '{} side ERROR = {}'.format(self._mode, error))
                        # TODO error

                elif isinstance(pkt, ShutdownPacket):
                    logger.debug('{} side received shutdown packet:\n'
                                 'syn: {}\n'
                                 'ack: {}\n'
                                 'status: {}\n'
                                 'error: {}\n'
                                 'last_valid_sequence: {}'.format(self._mode, pkt.SYN, pkt.ACK, pkt.status, pkt.error,
                                                                  pkt.last_valid_sequence))
                    if is_set(pkt.last_valid_sequence, pkt.ACK) and not_set(pkt.SYN, pkt.status, pkt.error):
                        self.connection_lost(None)
                    elif is_set(pkt.last_valid_sequence) and not_set(pkt.SYN, pkt.ACK, pkt.status, pkt.error):
                        if self.pt.rcv_seq >= pkt.last_valid_sequence:
                            p = ShutdownPacket()
                            p.ACK = pkt.last_valid_sequence
                            max_seq = None
                            for seq in iter(self.pt.send_buf):
                                if max_seq is None or seq >= max_seq:
                                    max_seq = seq
                            p.last_valid_sequence = max_seq
                            self.transport.write(p.__serialize__())

                        else:
                            # Error: some packets are still left to be received
                            p = ShutdownPacket()
                            p.status = ShutdownPacket.ERROR
                            p.error = 'Some packets are still left to be received'
                            self.transport.write(p.__serialize__())
                    elif pkt.status == ShutdownPacket.ERROR and is_set(pkt.error):
                        # Error reported from the other side while trying shutdown
                        # try again
                        p = ShutdownPacket()
                        max_seq = None
                        for seq in iter(self.pt.send_buf):
                            if max_seq is None or seq >= max_seq:
                                max_seq = seq
                        p.last_valid_sequence = self.pt.max_seq
                        logger.debug(
                            '{} side sending packet:\n'
                            'syn: {}\n'
                            'ack: {}\n'
                            'status: {}\n'
                            'error: {}\n'
                            'last_valid_sequence: {}'.format(self._mode, p.SYN, p.ACK, p.status, p.error,
                                                             p.last_valid_sequence))
                        self.transport.write(p.__serialize__())
                    else:
                        # fields not set correctly
                        p = ShutdownPacket()
                        p.status = ShutdownPacket.ERROR
                        p.error = 'fields not set correctly'
                        self.transport.write(p.__serialize__())
                else:
                    error = 'got something other than a PoopDataPacket: ignore'
                    logger.debug(
                        '{} side ERROR = {}'.format(self._mode, error))
        # do handshake
        else:
            for pkt in self.deserializer.nextPackets():
                if isinstance(pkt, HandshakePacket):
                    logger.debug('{} side packet received:\n'
                                 'syn: {}\n'
                                 'ack: {}\n'
                                 'status: {}\n'
                                 'error: {}\n'
                                 'last_valid_sequence: {}\n'.format(self._mode, pkt.SYN, pkt.ACK, pkt.status, pkt.error, pkt.last_valid_sequence))
                    # should receive syn = X
                    if self.state==0 and pkt.status==HandshakePacket.NOT_STARTED and \
                            is_set(pkt.SYN) and not_set(pkt.ACK, pkt.last_valid_sequence, pkt.error):
                        self.ack = pkt.SYN # self.ack = X
                        self.syn = random.randint(0, MAX_UINT32) # self.syn = Y
                        p = HandshakePacket(status=HandshakePacket.SUCCESS)
                        p.SYN = self.syn # p.syn = Y
                        p.ACK = increment_mod(self.ack) # p.ack = X+1
                        logger.debug('{} side setting state to {}'.format(self._mode, self.state+1))
                        self.state += 1
                        logger.debug('{} side sending packet:\n'
                                     'syn: {}\n'
                                     'ack: {}\n'
                                     'status: {}\n'
                                     'error: {}\n'
                                     'last_valid_sequence: {}\n'.format(self._mode, p.SYN, p.ACK, p.status, p.error, p.last_valid_sequence))
                        self.transport.write(p.__serialize__())

                    # should receive syn = (X+1)mod2^32 and ack = (Y+1)mod2^32
                    elif self.state==1 and pkt.status==HandshakePacket.SUCCESS and \
                            is_set(pkt.SYN, pkt.ACK) and not_set(pkt.last_valid_sequence, pkt.error):
                        logger.debug('{} side protocol here'.format(self._mode))
                        # if handshake successful
                        if pkt.ACK == increment_mod(self.syn) and pkt.SYN == increment_mod(self.ack):
                            logger.debug('{} side setting handshakeComplete to True'.format(self._mode))
                            self.handshakeComplete = True
                            self.ack = pkt.SYN # X + 1
                            self.syn = pkt.ACK # Y + 1
                            # should this go back in connection_made() ?

                            higher_transport = PoopTransport(self.transport)
                            higher_transport.setMode(self._mode)
                            # send_seq = Y
                            # rcv_seq = X
                            send_seq = decrement_mod(self.syn)
                            rcv_seq = decrement_mod(self.ack)
                            logger.debug('{} side setting send_seq to {} and rcv_seq to {}'.format(self._mode,
                                                                                                             send_seq,
                                                                                                             rcv_seq))
                            higher_transport.setSeq(send_seq=send_seq, rcv_seq=decrement_mod(rcv_seq))
                            higher_transport.setDataBuf(self.dataq)
                            higher_transport.setSendBuf(self.send_buf)
                            self.pt = higher_transport
                            logger.debug('{} side calling self.higherProtocol().connection_made()'.format(self._mode))
                            # higher_transport.setSeq(pkt.syn) # c_t.seq = Y
                            self.higherProtocol().connection_made(self.pt)
                        else:
                            # What should be done if the error is noticed by the server side
                            # ack != self.syn + 1 or syn != self.ack + 1
                            self.handle_handshake_error()
                            p = HandshakePacket(status=HandshakePacket.ERROR)
                            p.error = 'Server: ack != self.syn + 1 or syn != self.ack + 1'
                            logger.debug(
                                '{} side sending packet:\n'
                                'syn: {}\n'
                                'ack: {}\n'
                                'status: {}\n'
                                'error: {}\n'
                                'last_valid_sequence: {}\n'.format(self._mode, p.SYN, p.ACK, p.status, p.error,
                                                                   p.last_valid_sequence))
                            self.transport.write(p.__serialize__())
                    elif pkt.status == HandshakePacket.ERROR:
                        logger.debug('Server: An error packet was received from the client: ' + str(pkt.error))
                        self.handle_handshake_error()
                        # What should be done if the client has identified the error and sent the server an error packet

                    else:
                        # What should be done if the error is noticed by the server side
                        # invalid state and PoopHandshakePacket.status combination
                        self.handle_handshake_error()
                        p = HandshakePacket(status=HandshakePacket.ERROR)
                        p.error = 'Server: invalid state and PoopHandshakePacket.status combination'
                        logger.debug(
                            '{} side sending packet:\n'
                            'syn: {}\n'
                            'ack: {}\n'
                            'status: {}\n'
                            'error: {}\n'
                            'last_valid_sequence: {}\n'.format(self._mode, p.SYN, p.ACK, p.status, p.error,
                                                               p.last_valid_sequence))
                        self.transport.write(p.__serialize__())
                else:
                    # What should be done if the error is noticed by the server side
                    # not the PoopHandshakePacket: ignore
                    pass

    def connection_lost(self, exc):
        logger.debug("{} POOP connection lost. Shutting down higher layer.".format(self._mode))
        p = ShutdownPacket()
        max_seq = None
        for seq in iter(self.pt.send_buf):
            if max_seq is None or seq >= max_seq:
                max_seq = seq
        p.last_valid_sequence = self.pt.max_seq
        logger.debug(
            '{} side sending packet:\n'
            'syn: {}\n'
            'ack: {}\n'
            'status: {}\n'
            'error: {}\n'
            'last_valid_sequence: {}'.format(self._mode, p.SYN, p.ACK, p.status, p.error, p.last_valid_sequence))
        self.higherProtocol().connection_lost(exc)

PoopHandshakeClientFactory = StackingProtocolFactory.CreateFactoryType(PoopHandshakeClientProtocol)

PoopHandshakeServerFactory = StackingProtocolFactory.CreateFactoryType(PoopHandshakeServerProtocol)
