import threading

from playground.network.common import StackingProtocolFactory, StackingProtocol, StackingTransport
from playground.network.packet import PacketType, FIELD_NOT_SET
import logging
import random
from packets import * # TODO: Change for unit testing
# from .packets import *
import math, binascii
from collections import deque
# from .sized_dict import SizedDict
from sized_dict import SizedDict # for unit testing

logger = logging.getLogger("playground.__connector__." + __name__)

# max value a UINT32 can store
MAX_UINT32 = int(math.pow(2,32) - 1)

# Max Transmission Unit (max length of the data field)
MTU = 15000

# Max SizedDict size
SD_SIZE = 1

# Timeout
DATA_TRANSFER_TIMEOUT = 0.5
HANDSHAKE_TIMEOUT = 0.5
SHUTDOWN_TIMEOUT = 0.5

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

    def __init__(self, transport, protocol):
        super().__init__(transport)
        self.send_seq = None
        self.rcv_seq = None
        self.data_transfer_timer = None
        self.shutdown_timer = None
        self.shutdown_counter = 1
        self.max_seq = None
        self.closing = False
        self.protocol = protocol

    def close(self):
        logger.debug('{} side transport.close()'.format(self._mode))
        logger.debug('{} side setting self.closing to True'.format(self._mode))
        self.closing = True

        if len(self.send_buf) == 0: # if all data to be sent has been sent and already acked
            p = ShutdownPacket()
            p.FIN = self.max_seq
            p.hash = ShutdownPacket.DEFAULT_SHUTDOWN_HASH
            p.hash = getHash(p.__serialize__())
            packet_bytes = p.__serialize__()
            self.start_shutdown_timer(self.handle_shutdown_timeout, packet_bytes)
            logger.debug('{} side sending FIN packet. Info:\n'
                         'FIN: {}\n'
                         'hash: {}\n'.format(self._mode, p.FIN, p.hash))
            self.lowerTransport().write(packet_bytes)

    def handle_shutdown_timeout(self, *args, **kwargs):
        self.shutdown_counter += 1
        if self.shutdown_counter <= 3:
            self.start_shutdown_timer(kwargs["func"], kwargs["packet_bytes"])
            self.lowerTransport().write(kwargs["packet_bytes"])
        else:
            self.protocol.doShutdown()

    def stop_shutdown_timer(self):
        if self.shutdown_timer is not None:
            logger.debug('{} side stopping shutdown timer'.format(self._mode))
            self.shutdown_timer.cancel()
            self.shutdown_timer = None

    def start_shutdown_timer(self, func, packet_bytes):
        self.stop_shutdown_timer()
        logger.debug('{} side starting shutdown timer for {} seconds'.format(self._mode, SHUTDOWN_TIMEOUT))
        self.shutdown_timer = threading.Timer(SHUTDOWN_TIMEOUT, func, [], {"func": func, "packet_bytes": packet_bytes})
        self.shutdown_timer.start()

    def setMode(self, mode):
        logger.debug('setting PoopTransport mode to {}'.format(mode))
        self._mode = mode

    def setSeq(self, send_seq, rcv_seq):
        self.send_seq = send_seq
        self.rcv_seq = rcv_seq
        self.max_seq = send_seq - 1

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
        logger.debug('{} side number of packets representing one data = {}'.format(self._mode, n))
        for _ in range(n):
            p_data = data[i:min(j, data_len)]
            logger.debug('{} side transport, iteration {}, appending to dataq a data chunk of size {}'.format(self._mode, _, len(p_data)))
            self.dataq.append(p_data)
            i += MTU
            j += MTU
            logger.debug('{} side incrementing i and j to {} and {}'.format(self._mode, i, j))
        self.max_seq = (self.max_seq + n) % MAX_UINT32

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

    def stop_data_transfer_timer(self):
        if self.data_transfer_timer is not None:
            logger.debug('{} side stopping data transfer timer'.format(self._mode))
            self.data_transfer_timer.cancel()
            self.data_transfer_timer = None

    def write_send_buf(self):
        logger.debug('{}'.format(self.data_transfer_timer))
        if self.data_transfer_timer is not None:
            logger.debug('{}'.format(self.data_transfer_timer.is_alive()))

        if self.data_transfer_timer is not None and not self.data_transfer_timer.is_alive():
            logger.debug('{} side data transfer timeout'.format(self._mode))
            self.stop_data_transfer_timer()
        if len(self.send_buf) > 0 and self.data_transfer_timer is None: # if there's anything to send at all
            logger.debug('{} side transport in write_buf()'.format(self._mode))
            logger.debug('{} side send buf size: {}'.format(self._mode, len(self.send_buf)))
            for seq in iter(self.send_buf):
                logger.debug('{} side transport writing packet with seq {}'.format(self._mode, seq))
                logger.debug('{} side PoopTransport.write(). Info:\n'
                             'seq: {}\n'
                             'ACK: {}\n'
                             'data: {}\n'
                             'hash: {}\n'.format(self._mode, self.send_buf[seq].seq, self.send_buf[seq].ACK, self.send_buf[seq].data, self.send_buf[seq].hash))
                self.lowerTransport().write(self.send_buf[seq].__serialize__())
            logger.debug('{} side starting data-transfer timer for {} seconds'.format(self._mode, DATA_TRANSFER_TIMEOUT))
            self.data_transfer_timer = threading.Timer(DATA_TRANSFER_TIMEOUT, self.write_send_buf)
            self.data_transfer_timer.start()


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
        self.rcv_fin = None
        self.handshake_timer = None
        self.handshake_counter = 1

    def connection_made(self, transport):
        self.transport = transport
        self.syn = random.randint(0, MAX_UINT32)    # self.syn = X
        packet = HandshakePacket(SYN=self.syn, status=HandshakePacket.NOT_STARTED)  # pkt.syn = X
        packet.hash = HandshakePacket.DEFAULT_HANDSHAKE_HASH
        packet.hash = getHash(packet.__serialize__())
        packetBytes = packet.__serialize__()
        logger.debug('{} side setting state to {}'.format(self._mode, self.state+1))
        self.state += 1
        logger.debug('{} side sending handshake packet. Info:\n'
                     'syn: {}\n'
                     'ack: {}\n'
                     'status: {}\n'
                     'hash: {}\n'.format(self._mode, packet.SYN, packet.ACK, packet.status, packet.hash))
        self.start_handshake_timer(self.handle_handshake_timeout, packetBytes)
        self.transport.write(packetBytes)

    def handle_handshake_timeout(self, *args, **kwargs):
        self.handshake_counter += 1
        if self.handshake_counter <= 3:
            self.start_handshake_timer(kwargs["func"], kwargs["packet_bytes"])
            self.transport.write(kwargs["packet_bytes"])
        else:
            self.stop_handshake_timer()
            self.handle_handshake_error()

    def stop_handshake_timer(self):
        if self.handshake_timer is not None:
            logger.debug('{} side stopping handshake timer'.format(self._mode))
            self.handshake_timer.cancel()
            self.handshake_timer = None

    def start_handshake_timer(self, func, packet_bytes):
        self.stop_handshake_timer()
        logger.debug('{} side starting handshake timer for {} seconds'.format(self._mode, HANDSHAKE_TIMEOUT))
        self.handshake_timer = threading.Timer(HANDSHAKE_TIMEOUT, func, [], {"func": func, "packet_bytes": packet_bytes})
        self.handshake_timer.start()

    def handle_handshake_error(self):
        # self.stop_handshake_timer()
        self.handshakeComplete = False
        # self.state = 0
        self.handshake_counter = 1

    def data_received(self, data):
        logger.debug("{} POOP received a buffer of size {}".format(self._mode, len(data)))
        logger.debug("{} POOP current state: {}".format(self._mode, self.state))
        self.deserializer.update(data)
        if self.handshakeComplete:
            logger.debug("{} mode, data: {}".format(self._mode, data))
            for pkt in self.deserializer.nextPackets():
                if isinstance(pkt, DataPacket):
                    logger.debug("{} side data packet recieved: Info:\n"
                                 "seq: {}\n"
                                 "ack: {}\n"
                                 "data: {}\n"
                                 "hash: {}\n".format(self._mode, pkt.seq, pkt.ACK, pkt.data, pkt.hash))
                    # recieved data packet
                    if not_set(pkt.ACK) and is_set(pkt.seq, pkt.data, pkt.hash):
                        # drop data packets if self initiated shutdown
                        if self.pt.closing: #maybe move this somewhere else
                            # TODO change to be able to ack data packets in case
                            return
                        # do check if seq number matches
                        logger.debug('{} side checking seq {} == {}'.format(self._mode, pkt.seq, self.pt.rcv_seq))

                        if pkt.seq == self.pt.rcv_seq:
                            # datahash = getHash(pkt.data)
                            pkt_hash = pkt.hash # received datahash
                            pkt.hash = DataPacket.DEFAULT_DATAHASH
                            gen_hash = getHash(pkt.__serialize__()) # generated datahash

                            # logger.debug('{} side checking {} == {}'.format(self._mode, pkt.datahash, datahash))
                            logger.debug('{} side checking hashes {} == {}'.format(self._mode, pkt_hash, gen_hash))
                            # if not corrupted
                            if pkt_hash == gen_hash:
                                # self.pt.rcv_seq = increment_mod(self.pt.rcv_seq)
                                logger.debug('{} side sending ack = {}'.format(self._mode, self.pt.rcv_seq))
                                ack_p = DataPacket(ACK=pkt.seq)
                                ack_p.hash = DataPacket.DEFAULT_DATAHASH
                                ack_p.hash = getHash(ack_p.__serialize__())
                                logger.debug("{} side sending data packet ack: Info:\n"
                                             "seq: {}\n"
                                             "ack: {}\n"
                                             "data: {}\n"
                                             "hash: {}\n".format(self._mode, ack_p.seq, ack_p.ACK, ack_p.data, ack_p.hash))
                                self.transport.write(ack_p.__serialize__())
                                logger.debug('{} side setting rcv_seq = {}'.format(self._mode, increment_mod(self.pt.rcv_seq)))
                                self.pt.rcv_seq = increment_mod(self.pt.rcv_seq)
                                if not self.pt.closing:
                                    self.higherProtocol().data_received(pkt.data)
                                # if self.rcv_fin and self.rcv_fin <= self.pt.rcv_seq:
                                #     self.sendFinAck()
                            else:
                                error = 'data corruption error: pkt.datahash != getHash(pkt.data)'
                                logger.debug(
                                    '{} side ERROR = {}. Resending last sent ack = {}'.format(self._mode, error, self.pt.rcv_seq))
                                # Resend last successful ack
                                ack_p = DataPacket(ack=self.pt.rcv_seq)
                                ack_p.hash = DataPacket.DEFAULT_DATAHASH
                                ack_p.hash = getHash(ack_p.__serialize__())
                                self.transport.write(ack_p.__serialize__())
                        else:
                            # just drop the packet
                            error = 'pkt.seq != self.pt.rcv_seq'
                            logger.debug(
                                '{} side ERROR = {}. Dropping packet.'.format(self._mode, error))

                    # received data ack
                    elif is_set(pkt.ACK, pkt.hash) and not_set(pkt.data, pkt.seq):
                        logger.debug('{} side received data ack/shutdown ack'.format(self._mode))
                        pkt_hash = pkt.hash # received datahash
                        pkt.hash = DataPacket.DEFAULT_DATAHASH
                        gen_hash = getHash(pkt.__serialize__()) # generated datahash

                        # logger.debug('{} side checking {} == {}'.format(self._mode, pkt.datahash, datahash))
                        logger.debug('{} side checking hashes {} == {}'.format(self._mode, pkt_hash, gen_hash))
                        # if pkt.datahash == datahash:
                        # if not corrupted
                        if pkt_hash == gen_hash:
                            logger.debug('{} side received ack = {}'.format(self._mode, pkt.ACK))
                            # cancel timeout if exists
                            if self.pt.data_transfer_timer is not None:
                                self.pt.stop_data_transfer_timer()
                            logger.debug('{} checking if it should do shutdown. checking closing={} and {}>={} and the shutdown_timre_is_None={}'
                                         .format(self._mode, self.pt.closing, pkt.ACK, self.pt.max_seq, self.pt.shutdown_timer is None))
                            if self.pt.closing and pkt.ACK >= self.pt.max_seq: # other side received all data and we received all the acks
                                if self.pt.shutdown_timer is not None:
                                    # A shutdown was already initiated and so this is a shutdown ack
                                    self.pt.stop_shutdown_timer()
                                    self.doShutdown()
                                else:
                                    # We wanted to initiate shutdown but there were some packets left in the buffer so we can initiate now
                                    p = ShutdownPacket()
                                    p.FIN = self.pt.max_seq + 1 # how the other side knows until what data packet it has to ack
                                    p.hash = ShutdownPacket.DEFAULT_SHUTDOWN_HASH
                                    p.hash = getHash(p.__serialize__())
                                    packet_bytes = p.__serialize__()
                                    self.pt.start_shutdown_timer(self.doShutdown, packet_bytes)
                                    logger.debug('{} side transport writing FIN = {}'.format(self._mode, self.pt.max_seq))
                                    logger.debug("{} side sending shutdown packet: Info:\n"
                                                 "FIN: {}\n"
                                                 "hash: {}\n".format(self._mode, p.FIN, p.hash))
                                    self.transport.write(packet_bytes)
                                return

                            # if pkt.ack in self.send_buf:
                            del self.send_buf[pkt.ACK] # don't need to resend acked data packets
                            self.pt.fill_send_buf() # refill send_buf
                            self.pt.write_send_buf() # resend send_buf
                    else:
                        # ignore
                        error = 'Either pkt.seq, pkt.data or pkt.datahash are not set'
                        logger.debug(
                            '{} side ERROR = {}'.format(self._mode, error))

                elif isinstance(pkt, ShutdownPacket):
                    logger.debug('{} side received shutdown packet:\n'
                                 'fin: {}\n'
                                 'hash: {}\n'.format(self._mode, pkt.FIN, pkt.hash))
                    if self.pt.closing:
                        # if shutdown initated by self, can close on receiving FIN || FIN/ACK
                        logger.debug('{} side received shutdown packet while closing.'.format(self._mode))
                        logger.debug('{} side sending FACK. ack = {}'.format(self._mode, pkt.FIN))
                        ack_p = DataPacket(ACK=pkt.FIN)
                        ack_p.hash = DataPacket.DEFAULT_DATAHASH
                        ack_p.hash = getHash(ack_p.__serialize__())
                        self.transport.write(ack_p.__serialize__())
                        logger.debug('{} side shutting down.'.format(self._mode))
                        self.doShutdown()
                        return
                    pkt_hash = pkt.hash # received datahash
                    pkt.hash = DataPacket.DEFAULT_DATAHASH
                    gen_hash = getHash(pkt.__serialize__()) # generated datahash
                    logger.debug('{} side checking hashes {} == {}'.format(self._mode, pkt_hash, gen_hash))
                    # if pkt.datahash == datahash:
                    if pkt_hash == gen_hash:
                        logger.debug('{} side got FIN = {}. Checking against rcv_seq = {}'.format(self._mode, pkt.FIN, self.pt.rcv_seq))
                        # logger.debug('{} checking FIN+1 = rcv_seq')
                        if pkt.FIN <= self.pt.rcv_seq:
                            # matches, got all necessary data
                            logger.debug('{} side sending FACK. ack = {}'.format(self._mode, pkt.FIN))
                            ack_p = DataPacket(ACK=pkt.FIN)
                            logger.debug('{} side shutting down.'.format(self._mode))
                            self.doShutdown()
                        else: # probably will never be reached
                            # did not receive everything
                            self.rcv_fin = pkt.fin
                            logger.debug('{} side sending ack = {}'.format(self._mode, self.pt.rcv_seq))
                            ack_p = DataPacket(ACK=self.pt.rcv_seq)
                        ack_p.hash = DataPacket.DEFAULT_DATAHASH
                        ack_p.hash = getHash(ack_p.__serialize__())
                        # resend last ack
                        self.transport.write(ack_p.__serialize__())


                else:
                    error = 'got something other than a PoopDataPacket/PoopShutdownPacket: ignore'
                    logger.debug(
                        '{} side ERROR = {}'.format(self._mode, error))

        # do handshake
        else:
            for pkt in self.deserializer.nextPackets():
                if isinstance(pkt, HandshakePacket):
                    logger.debug('{} side handshake packet received:\n'
                                 'syn: {}\n'
                                 'ack: {}\n'
                                 'status: {}\n'
                                 'hash: {}\n'.format(self._mode, pkt.SYN, pkt.ACK, pkt.status, pkt.hash))
                    pkt_hash = pkt.hash
                    pkt.hash = HandshakePacket.DEFAULT_HANDSHAKE_HASH
                    gen_hash = getHash(pkt.__serialize__())
                    if self.state==1 and pkt.status==HandshakePacket.SUCCESS and \
                            is_set(pkt.SYN, pkt.ACK) and pkt_hash == gen_hash:
                        if pkt.ACK==increment_mod(self.syn): # ACK = X + 1
                            self.stop_handshake_timer()
                            self.handshake_counter = 1
                            self.ack = pkt.SYN # self.ack = Y, this is the rcv_seq
                            # self.syn = pkt.ACK # self.syn = X+1
                            p = HandshakePacket(status=HandshakePacket.SUCCESS)
                            p.SYN = increment_mod(self.syn) # p.syn = X+1
                            p.ACK = increment_mod(self.ack) # p.ack = Y+1
                            p.hash = HandshakePacket.DEFAULT_HANDSHAKE_HASH
                            p.hash = getHash(p.__serialize__())
                            logger.debug('{} side sending handshake packet:\n'
                                         'syn: {}\n'
                                         'ack: {}\n'
                                         'status: {}\n'
                                         'hash: {}\n'.format(self._mode, p.SYN, p.ACK, p.status, p.hash))
                            self.transport.write(p.__serialize__())
                            logger.debug('{} side setting state to {}'.format(self._mode, self.state+1))
                            self.state += 1
                            logger.debug('{} side setting handshakeComplete to True'.format(self._mode))
                            self.handshakeComplete = True
                            higher_transport = PoopTransport(self.transport, self)
                            higher_transport.setMode(self._mode)
                            logger.debug('{} side setting send_seq to {} and rcv_seq to {}'.format(self._mode, self.syn,
                                                                                                   self.ack))
                            higher_transport.setSeq(send_seq=self.syn, rcv_seq=self.ack)
                            higher_transport.setDataBuf(self.dataq)
                            higher_transport.setSendBuf(self.send_buf)
                            self.pt = higher_transport
                            logger.debug('{} side calling self.higherProtocol().connection_made()'.format(self._mode))
                            self.higherProtocol().connection_made(self.pt)
                        else:
                            # What should be done if the error is noticed by the client side
                            # let it do the timeout
                            self.handle_handshake_error()
                            error = "ack does not match syn+1"
                            logger.debug('{} side error: {}'.format(self._mode, error))
                            # ack does not match syn+1
                            # p = HandshakePacket(status=HandshakePacket.ERROR, hash=0)
                            # logger.debug('{} side sending packet. Info:\n'
                            #              'syn: {}\n'
                            #              'ack: {}\n'
                            #              'status: {}\n'
                            #              'hash: {}\n'.format(self._mode, p.SYN, p.ACK, p.status, p.hash))
                            # self.transport.write(p.__serialize__())
                    elif pkt.status == HandshakePacket.ERROR:
                        logger.debug('{} side a handshake error packet was received'.format(self._mode))
                        # What should be done if the server has identified the error and sent the client an error packet
                        self.handle_handshake_error()
                        # no need for timeout
                        self.stop_handshake_timer()

                    else:
                        # What should be done if the error is noticed by the client side
                        # let it do the timeout
                        self.handle_handshake_error()
                        error = "either state != 1 or status != SUCCESS or syn not set or ack not set"
                        logger.debug('{} side error: {}'.format(self._mode, error))
                        # p = HandshakePacket(status=HandshakePacket.ERROR, hash=0)
                        # logger.debug(
                        #     '{} side sending handshake packet:\n'
                        #     'syn: {}\n'
                        #     'ack: {}\n'
                        #     'status: {}\n'
                        #     'hash: {}\n'.format(self._mode, p.SYN, p.ACK, p.status, p.hash))
                        # self.transport.write(p.__serialize__())
                else:
                    # not the PoopHandshakePacket: ignore
                    # let it do the timeout
                    error = "not the PoopHandshakePacket: ignore"
                    logger.debug('{} side error: {}'.format(self._mode, error))

    def connection_lost(self, exc):
        logger.debug("{} POOP connection lost. Shutting down higher layer.".format(self._mode))
        self.higherProtocol().connection_lost(exc)
        
    def doShutdown(self):
        self.pt.stop_shutdown_timer()
        # do shutdown
        logger.debug('{} side calling higherProtocol.connection_lost().'.format(self._mode))
        self.higherProtocol().connection_lost('Connection closed by the server.')
        logger.debug('{} side calling self.transport.close()'.format(self._mode))
        self.transport.close()


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
        self.rcv_fin = None
        self.handshake_timer = None
        self.handshake_counter = 1

    def connection_made(self, transport):
        self.transport = transport

    def handle_handshake_timeout(self, *args, **kwargs):
        self.handshake_counter += 1
        if self.handshake_counter <= 3:
            self.start_handshake_timer(kwargs["func"], kwargs["packet_bytes"])
            self.transport.write(kwargs["packet_bytes"])
        else:
            self.stop_handshake_timer()
            self.handle_handshake_error()

    def stop_handshake_timer(self):
        if self.handshake_timer is not None:
            logger.debug('{} side stopping handshake timer'.format(self._mode))
            self.handshake_timer.cancel()
            self.handshake_timer = None

    def start_handshake_timer(self, func, packet_bytes):
        self.stop_handshake_timer()
        logger.debug('{} side starting handshake timer for {} seconds'.format(self._mode, HANDSHAKE_TIMEOUT))
        self.handshake_timer = threading.Timer(HANDSHAKE_TIMEOUT, func, [], {"func": func, "packet_bytes": packet_bytes})
        self.handshake_timer.start()

    def handle_handshake_error(self):
        # self.stop_handshake_timer()
        self.handshakeComplete = False
        # self.state = 0
        self.handshake_counter = 1

    def data_received(self, data):
        logger.debug("{} POOP received a buffer of size {}".format(self._mode, len(data)))
        logger.debug("{} POOP current state: {}".format(self._mode, self.state))
        self.deserializer.update(data)
        if self.handshakeComplete:
            logger.debug("{} mode, data: {}".format(self._mode, data))
            for pkt in self.deserializer.nextPackets():
                if isinstance(pkt, DataPacket):
                    logger.debug("{} side data packet recieved: Info:\n"
                                 "seq: {}\n"
                                 "ack: {}\n"
                                 "data: {}\n"
                                 "hash: {}\n".format(self._mode, pkt.seq, pkt.ACK, pkt.data, pkt.hash))
                    # recieved data packet
                    if not_set(pkt.ACK) and is_set(pkt.seq, pkt.data, pkt.hash):
                        # drop data packets if self initiated shutdown
                        if self.pt.closing:
                            # change to be able to ack data packets in case
                            return
                        # do check if seq number matches
                        logger.debug('{} side checking seq {} == {}'.format(self._mode, pkt.seq, self.pt.rcv_seq))

                        if pkt.seq == self.pt.rcv_seq:
                            # datahash = getHash(pkt.data)
                            pkt_hash = pkt.hash # received datahash
                            pkt.hash = DataPacket.DEFAULT_DATAHASH
                            gen_hash = getHash(pkt.__serialize__()) # generated datahash

                            # logger.debug('{} side checking {} == {}'.format(self._mode, pkt.datahash, datahash))
                            logger.debug('{} side checking hashes {} == {}'.format(self._mode, pkt_hash, gen_hash))
                            # if not corrupted
                            if pkt_hash == gen_hash:
                                # self.pt.rcv_seq = increment_mod(self.pt.rcv_seq)
                                logger.debug('{} side sending ack = {}'.format(self._mode, self.pt.rcv_seq))
                                ack_p = DataPacket(ACK=pkt.seq)
                                ack_p.hash = DataPacket.DEFAULT_DATAHASH
                                ack_p.hash = getHash(ack_p.__serialize__())
                                logger.debug("{} side sending data packet ack: Info:\n"
                                             "seq: {}\n"
                                             "ack: {}\n"
                                             "data: {}\n"
                                             "hash: {}\n".format(self._mode, ack_p.seq, ack_p.ACK, ack_p.data, ack_p.hash))
                                self.transport.write(ack_p.__serialize__())
                                logger.debug('{} side setting rcv_seq = {}'.format(self._mode, increment_mod(self.pt.rcv_seq)))
                                self.pt.rcv_seq = increment_mod(self.pt.rcv_seq)
                                if not self.pt.closing:
                                    self.higherProtocol().data_received(pkt.data)
                                # if self.rcv_fin and self.rcv_fin <= self.pt.rcv_seq:
                                #     self.sendFinAck()
                            else:
                                error = 'data corruption error: pkt.datahash != getHash(pkt.data)'
                                logger.debug(
                                    '{} side ERROR = {}. Resending last sent ack = {}'.format(self._mode, error, self.pt.rcv_seq))
                                # Resend last successful ack
                                ack_p = DataPacket(ack=self.pt.rcv_seq)
                                ack_p.hash = DataPacket.DEFAULT_DATAHASH
                                ack_p.hash = getHash(ack_p.__serialize__())
                                self.transport.write(ack_p.__serialize__())
                        else:
                            # just drop the packet
                            error = 'pkt.seq != self.pt.rcv_seq'
                            logger.debug(
                                '{} side ERROR = {}. Dropping packet.'.format(self._mode, error))
                    # received data ack
                    elif is_set(pkt.ACK) and not_set(pkt.data, pkt.seq):
                        logger.debug('{} side received data ack/ shutdown ack'.format(self._mode))
                        pkt_hash = pkt.hash # received datahash
                        pkt.hash = DataPacket.DEFAULT_DATAHASH
                        gen_hash = getHash(pkt.__serialize__()) # generated datahash

                        # logger.debug('{} side checking {} == {}'.format(self._mode, pkt.datahash, datahash))
                        logger.debug('{} side checking hashes {} == {}'.format(self._mode, pkt_hash, gen_hash))
                        # if pkt.datahash == datahash:
                        # if not corrupted
                        if pkt_hash == gen_hash:
                            logger.debug('{} side received ack = {}'.format(self._mode, pkt.ACK))
                            # cancel timeout if exists
                            if self.pt.data_transfer_timer is not None:
                                self.pt.stop_data_transfer_timer()
                            logger.debug('{} checking if it should do shutdown. checking closing={} and {}>={} and the shutdown_timre_is_None={}'
                                         .format(self._mode, self.pt.closing, pkt.ACK, self.pt.max_seq, self.pt.shutdown_timer is None))
                            if self.pt.closing and pkt.ACK >= self.pt.max_seq: # other side received all data
                                if self.pt.shutdown_timer is not None:
                                    # A shutdown was already initiated and so this is a shutdown ack
                                    self.pt.stop_shutdown_timer()
                                    self.doShutdown()
                                else:
                                    # We wanted to initiate shutdown but there were some packets left in the buffer so we can initiate now
                                    p = ShutdownPacket()
                                    p.FIN = self.pt.max_seq + 1 # how the other side knows until what data packet it has to ack
                                    p.hash = ShutdownPacket.DEFAULT_SHUTDOWN_HASH
                                    p.hash = getHash(p.__serialize__())
                                    packet_bytes = p.__serialize__()
                                    self.pt.start_shutdown_timer(self.doShutdown, packet_bytes)
                                    logger.debug('{} side transport writing FIN = {}'.format(self._mode, self.pt.max_seq))
                                    logger.debug("{} side sending shutdown packet: Info:\n"
                                                 "FIN: {}\n"
                                                 "hash: {}\n".format(self._mode, p.FIN, p.hash))
                                    self.transport.write(packet_bytes)
                                return
                            # if pkt.ack in self.send_buf:
                            del self.send_buf[pkt.ACK] # don't need to resend acked data packets
                            self.pt.fill_send_buf() # refill send_buf
                            self.pt.write_send_buf() # resend send_buf
                            # logger.debug('{} side incrementing rcv_seq to {}'.format(self._mode, increment_mod(self.pt.rcv_seq)))
                            # self.pt.rcv_seq = increment_mod(self.pt.rcv_seq)
                    else:
                        # ignore
                        error = 'Either pkt.seq, pkt.data or pkt.datahash are not set'
                        logger.debug(
                            '{} side ERROR = {}'.format(self._mode, error))

                elif isinstance(pkt, ShutdownPacket):
                    logger.debug('{} side received shutdown packet:\n'
                                 'fin: {}\n'
                                 'hash: {}\n'.format(self._mode, pkt.FIN, pkt.hash))
                    if self.pt.closing:
                        # if shutdown initated by self, can close on receiving FIN || FIN/ACK
                        logger.debug('{} side received shutdown packet while closing.'.format(self._mode))
                        logger.debug('{} side sending FACK. ack = {}'.format(self._mode, pkt.FIN))
                        ack_p = DataPacket(ACK=pkt.FIN)
                        ack_p.hash = DataPacket.DEFAULT_DATAHASH
                        ack_p.hash = getHash(ack_p.__serialize__())
                        self.transport.write(ack_p.__serialize__())
                        logger.debug('{} side shutting down.'.format(self._mode))
                        self.doShutdown()
                        return
                    pkt_hash = pkt.hash # received datahash
                    pkt.hash = DataPacket.DEFAULT_DATAHASH
                    gen_hash = getHash(pkt.__serialize__()) # generated datahash
                    logger.debug('{} side checking hashes {} == {}'.format(self._mode, pkt_hash, gen_hash))
                    # if pkt.datahash == datahash:
                    if pkt_hash == gen_hash:
                        logger.debug('{} side got FIN = {}. Checking against rcv_seq = {}'.format(self._mode, pkt.FIN, self.pt.rcv_seq))
                        # logger.debug('{} checking FIN+1 = rcv_seq')
                        if pkt.FIN <= self.pt.rcv_seq:
                            # matches, got all necessary data
                            logger.debug('{} side sending FACK. ack = {}'.format(self._mode, pkt.FIN))
                            ack_p = DataPacket(ACK=pkt.FIN)
                            logger.debug('{} side shutting down.'.format(self._mode))
                            self.doShutdown()
                        else: # probably will never be reached
                            # did not receive everything
                            self.rcv_fin = pkt.fin
                            logger.debug('{} side sending ack = {}'.format(self._mode, self.pt.rcv_seq))
                            ack_p = DataPacket(ACK=self.pt.rcv_seq)
                        ack_p.hash = DataPacket.DEFAULT_DATAHASH
                        ack_p.hash = getHash(ack_p.__serialize__())
                        self.transport.write(ack_p.__serialize__())

                else:
                    error = 'got something other than a PoopDataPacket/PoopShutdownPacket: ignore'
                    logger.debug(
                        '{} side ERROR = {}'.format(self._mode, error))
        # do handshake
        else:
            for pkt in self.deserializer.nextPackets():
                if isinstance(pkt, HandshakePacket):
                    logger.debug('{} side handshake packet received:\n'
                                 'syn: {}\n'
                                 'ack: {}\n'
                                 'status: {}\n'
                                 'hash: {}\n'.format(self._mode, pkt.SYN, pkt.ACK, pkt.status, pkt.hash))
                    pkt_hash = pkt.hash
                    pkt.hash = HandshakePacket.DEFAULT_HANDSHAKE_HASH
                    gen_hash = getHash(pkt.__serialize__())
                    # should receive syn = X
                    if self.state==0 and pkt.status==HandshakePacket.NOT_STARTED and \
                            is_set(pkt.SYN) and not_set(pkt.ACK) and pkt_hash == gen_hash:
                        self.ack = pkt.SYN # self.ack = X
                        self.syn = random.randint(0, MAX_UINT32) # self.syn = Y
                        p = HandshakePacket(status=HandshakePacket.SUCCESS)
                        p.SYN = self.syn # p.syn = Y
                        p.ACK = increment_mod(self.ack) # p.ack = X+1
                        p.hash = HandshakePacket.DEFAULT_HANDSHAKE_HASH
                        p.hash = getHash(p.__serialize__())
                        logger.debug('{} side setting state to {}'.format(self._mode, self.state+1))
                        self.state += 1
                        logger.debug('{} side sending handshake packet:\n'
                                     'syn: {}\n'
                                     'ack: {}\n'
                                     'status: {}\n'
                                     'hash: {}\n'.format(self._mode, p.SYN, p.ACK, p.status, p.hash))
                        packet_bytes = p.__serialize__()
                        self.start_handshake_timer(self.handle_handshake_timeout, packet_bytes)
                        self.transport.write(packet_bytes)

                    # should receive syn = (X+1)mod2^32 and ack = (Y+1)mod2^32
                    elif self.state==1 and pkt.status==HandshakePacket.SUCCESS and \
                            is_set(pkt.SYN, pkt.ACK) and pkt_hash == gen_hash:
                        logger.debug('{} side protocol handshake ack'.format(self._mode))
                        # if handshake successful
                        if pkt.ACK == increment_mod(self.syn) and pkt.SYN == increment_mod(self.ack):
                            self.stop_handshake_timer()
                            self.handshake_counter = 1
                            logger.debug('{} side setting handshakeComplete to True'.format(self._mode))
                            self.handshakeComplete = True

                            higher_transport = PoopTransport(self.transport, self)
                            higher_transport.setMode(self._mode)
                            logger.debug('{} side setting send_seq to {} and rcv_seq to {}'.format(self._mode, self.syn,
                                                                                                   self.ack))
                            higher_transport.setSeq(send_seq=self.syn, rcv_seq=self.ack)
                            higher_transport.setDataBuf(self.dataq)
                            higher_transport.setSendBuf(self.send_buf)
                            self.pt = higher_transport
                            logger.debug('{} side calling self.higherProtocol().connection_made()'.format(self._mode))
                            self.higherProtocol().connection_made(self.pt)
                        else:
                            # What should be done if the error is noticed by the server side
                            # ack != self.syn + 1 or syn != self.ack + 1
                            # let it timeout
                            self.handle_handshake_error()
                            error = "ack != self.syn + 1 or syn != self.ack + 1"
                            logger.debug('{} side error: {}'.format(self._mode, error))

                            # p = HandshakePacket(status=HandshakePacket.ERROR, hash=0)
                            # logger.debug(
                            #     '{} side sending packet:\n'
                            #     'syn: {}\n'
                            #     'ack: {}\n'
                            #     'status: {}\n'
                            #     'hash: {}\n'.format(self._mode, p.SYN, p.ACK, p.status, p.hash))
                            # self.transport.write(p.__serialize__())
                    elif pkt.status == HandshakePacket.ERROR:
                        logger.debug('{} side An handshake error packet was received'.format(self._mode))
                        self.handle_handshake_error()
                        # no need for timeout
                        self.stop_handshake_timer()
                        # What should be done if the client has identified the error and sent the server an error packet

                    else:
                        # What should be done if the error is noticed by the server side
                        # invalid state and PoopHandshakePacket.status combination
                        # let it timeout
                        self.handle_handshake_error()
                        error = "invalid state and PoopHandshakePacket.status combination"
                        logger.debug('{} side error: {}'.format(self._mode, error))
                        # p = HandshakePacket(status=HandshakePacket.ERROR, hash=0)
                        # logger.debug(
                        #     '{} side sending handshake packet:\n'
                        #     'syn: {}\n'
                        #     'ack: {}\n'
                        #     'status: {}\n'
                        #     'hash: {}\n'.format(self._mode, p.SYN, p.ACK, p.status, p.hash))
                        # self.transport.write(p.__serialize__())
                else:
                    # What should be done if the error is noticed by the server side
                    # not the PoopHandshakePacket: ignore
                    error = "not the PoopHandshakePacket: ignore"
                    logger.debug('{} side error: {}'.format(self._mode, error))
                    pass

    def connection_lost(self, exc):
        logger.debug("{} POOP connection lost. Shutting down higher layer.".format(self._mode))
        self.higherProtocol().connection_lost(exc)
        
    def doShutdown(self):
        self.pt.stop_shutdown_timer()
        # do shutdown
        logger.debug('{} side calling higherProtocol.connection_lost().'.format(self._mode))
        self.higherProtocol().connection_lost('Connection closed by the server.')
        logger.debug('{} side calling self.transport.close()'.format(self._mode))
        self.transport.close()

    # def connection_lost(self, exc):
    #     logger.debug("{} POOP connection lost. Shutting down higher layer.".format(self._mode))
    #     p = ShutdownPacket()
    #     max_seq = None
    #     for seq in iter(self.pt.send_buf):
    #         if max_seq is None or seq >= max_seq:
    #             max_seq = seq
    #     p.last_valid_sequence = self.pt.max_seq
    #     logger.debug(
    #         '{} side sending packet:\n'
    #         'syn: {}\n'
    #         'ack: {}\n'
    #         'status: {}\n'
    #         'error: {}\n'
    #         'last_valid_sequence: {}'.format(self._mode, p.SYN, p.ACK, p.status, p.error, p.last_valid_sequence))
    #     self.higherProtocol().connection_lost(exc)

PoopHandshakeClientFactory = StackingProtocolFactory.CreateFactoryType(PoopHandshakeClientProtocol)

PoopHandshakeServerFactory = StackingProtocolFactory.CreateFactoryType(PoopHandshakeServerProtocol)

