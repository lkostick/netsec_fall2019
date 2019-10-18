from playground.network.common import StackingProtocolFactory, StackingProtocol, StackingTransport
from playground.network.packet.fieldtypes import UINT8, UINT32, STRING, BUFFER
from playground.network.packet.fieldtypes.attributes import Optional
from playground.network.packet import PacketType, FIELD_NOT_SET
import logging
import random

logger = logging.getLogger("playground.__connector__." + __name__)

class PoopPacketType(PacketType):
    DEFINITION_IDENTIFIER = "poop"
    DEFINITION_VERSION = "1.0"

class PoopHandshakePacket(PoopPacketType):
    DEFINITION_IDENTIFIER = "poop.handshakepacket"
    DEFINITION_VERSION = "1.0"

    NOT_STARTED = 0
    SUCCESS = 1
    ERROR = 2

    FIELDS = [
        ("syn", UINT32({Optional: True})),
        ("ack", UINT32({Optional: True})),
        ("status", UINT8),
        ("error", STRING({Optional: True}))
    ]

class PoopDataPacket(PoopPacketType):
    DEFINITION_IDENTIFIER = "poop.datapacket"
    DEFINITION_VERSION = "1.0"

    FIELDS = [
        ("seq", UINT32),
        ("data", BUFFER)
    ]

def is_set(self, *fields):
    isset = True
    for field in fields:
        if field == FIELD_NOT_SET:
            isset = False
            break
    return isset

def increment_mod(uint32):
    return (uint32 + 1) % (MAX_UINT32 + 1)

# max value a UINT32 can store
MAX_UINT32 = 4294967295


class PoopTransport(StackingTransport):
    def setMode(self, mode):
        logger.debug('setting PoopTransport mode to {}'.format(mode))
        self._mode = mode

    # ALWAYS CALL setMode() BEFORE setSeq() !!!!!
    def setSeq(self, seq):
        logger.debug('setting {} side PoopTransport init seq to {}'.format(self._mode, seq))
        self.seq = seq;

    def write(self, data):
        self.seq = increment_mod(self.seq)
        logger.debug('{} side PoopTransport.write() with seq: {}'.format(self._mode, self.seq))
        p = PoopDataPacket()
        p.seq = self.seq
        p.data = data
        self.lowerTransport().write(p.__serialize__())

class PoopHandshakeClientProtocol(StackingProtocol):
    def __init__(self):
        super().__init__()
        self._mode = "CLIENT"
        self.deserializer = PoopPacketType.Deserializer()
        # self.syn = X
        self.syn = None # will be used to sequence outbound packets... by feeding original syn value to a transport which will store the value and do the arithmetic for the client
        # self.ack = Y
        self.ack = None # will be used to check sequence of incoming packets
        self.handshakeComplete = False
        self.state = 0 # increments by 1 for each packet sent during the handshake

    def connection_made(self, transport):
        self.transport = transport
        self.syn = random.randint(0, MAX_UINT32)
        packet = PoopHandshakePacket(syn=self.syn, status=PoopHandshakePacket.NOT_STARTED)
        packetBytes = packet.__serialize__()
        logger.debug('{} side setting state to {}'.format(self._mode, self.state+1))
        self.state += 1
        logger.debug('{} side sending packet:\nsyn: {}\nack: {}\nstatus: {}\nerror: {}'.format(self._mode, packet.syn, packet.ack, packet.status, packet.error))
        self.transport.write(packetBytes)

    def data_received(self, data):
        logger.debug("{} POOP received a buffer of size {}".format(self._mode, len(data)))
        logger.debug("{} POOP current state: {}".format(self._mode, self.state))
        self.deserializer.update(data)
        if self.handshakeComplete:
            logger.debug("{} mode, data: {}".format(self._mode, data))
            for pkt in self.deserializer.nextPackets():
                if isinstance(pkt, PoopDataPacket):
                    logger.debug('{} side packet received:\nseq: {}'.format(self._mode, pkt.seq))
                    # check if packets in order
                    logger.debug('{} side checking {} == {}'.format(self._mode, pkt.seq, increment_mod(self.ack)))
                    if pkt.seq == increment_mod(self.ack):
                        logger.debug('{} side setting ack to {}'.format(self._mode, increment_mod(self.ack)))
                        self.ack = increment_mod(self.ack)
                        self.higherProtocol().data_received(pkt.data)
                    else:
                        # TODO error
                        # got a seq number that doesnt match self.ack + 1
                        pass
                else:
                    # TODO error
                    # got something other than a PoopDataPacket
                    pass
        # do handshake
        else:
            for pkt in self.deserializer.nextPackets():
                if isinstance(pkt, PoopHandshakePacket):
                    if self.state==1 and pkt.status==PoopHandshakePacket.SUCCESS and is_set(pkt.syn, pkt.ack):
                        if pkt.ack==increment_mod(self.syn):
                            self.ack = pkt.syn
                            p = PoopHandshakePacket(status=PoopHandshakePacket.SUCCESS)
                            p.syn = increment_mod(self.syn)
                            p.ack = increment_mod(self.ack)
                            logger.debug('{} side sending packet:\nsyn: {}\nack: {}\nstatus: {}\nerror: {}'.format(self._mode, p.syn, p.ack, p.status, p.error))
                            self.transport.write(p.__serialize__())
                            logger.debug('{} side setting state to {}'.format(self._mode, self.state+1))
                            self.state += 1
                            logger.debug('{} side setting handshakeComplete to True'.format(self._mode))
                            self.handshakeComplete = True
                            # should this go back in connection_made() ?
                            logger.debug('{} side calling self.higherProtocol().connection_made()'.format(self._mode))
                            higher_transport = PoopTransport(self.transport)
                            higher_transport.setMode(self._mode)
                            higher_transport.setSeq(self.syn)
                            self.higherProtocol().connection_made(higher_transport)
                        else:
                            # TODO error
                            # ack does not match syn+1
                            # I don't think this is part of milestone 2 yet
                            pass
                    else:
                        # TODO error
                        # either state != 1 or status != SUCCESS or syn not set or ack not set
                        pass
                else:
                    # TODO error
                    # not the PoopHandshakePacket
                    """
                    if we want to retry the whole handshake on an error, we need to:
                    reset self.state to 0
                    reset self.syn, self.ack to None, None
                    reset handshakeComplete to False (may not be necessary?)
                    send error packet?
                    maybe other things I'm forgetting?
                    """
                    pass

    def connection_lost(self, exc):
        logger.debug("{} POOP connection lost. Shutting down higher layer.".format(self._mode))
        self.higherProtocol().connection_lost(exc)

class PoopHandshakeServerProtocol(StackingProtocol):
    def __init__(self):
        super().__init__()
        self._mode = "SERVER"
        self.deserializer = PoopPacketType.Deserializer()
        # self.syn = Y
        self.syn = None # will be used to sequence outbound packets... by feeding original syn value to a transport which will store the value and do the arithmetic for the client
        # self.ack = X
        self.ack = None # will be used to sequence of incoming packets
        self.handshakeComplete = False
        self.state = 0 # increments by 1 for each packet sent during the handshake

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        logger.debug("{} POOP received a buffer of size {}".format(self._mode, len(data)))
        logger.debug("{} POOP current state: {}".format(self._mode, self.state))
        self.deserializer.update(data)
        if self.handshakeComplete:
            # logger.debug("{} mode, data: {}".format(self._mode, data))
            # self.higherProtocol().data_received(data)
            # TODO do something
            for pkt in self.deserializer.nextPackets():
                if isinstance(pkt, PoopDataPacket):
                    logger.debug('{} side packet received:\nseq: {}'.format(self._mode, pkt.seq))
                    # check if packets in order
                    logger.debug('{} side checking {} == {}'.format(self._mode, pkt.seq, increment_mod(self.ack)))
                    if pkt.seq == increment_mod(self.ack):
                        logger.debug('{} side setting ack to {}'.format(self._mode, increment_mod(self.ack)))
                        self.ack = increment_mod(self.ack)
                        self.higherProtocol().data_received(pkt.data)
                    else:
                        # TODO error
                        # got a seq number that doesnt match self.ack + 1
                        # I don't think this is part of milestone 2 yet
                        pass
                else:
                    # TODO error
                    # got something other than a PoopDataPacket
                    pass
        # do handshake
        else:
            for pkt in self.deserializer.nextPackets():
                if isinstance(pkt, PoopHandshakePacket):
                    logger.debug('{} side packet received:\nsyn: {}\nack: {}\nstatus: {}\nerror: {}'.format(self._mode, pkt.syn, pkt.ack, pkt.status, pkt.error))
                    # should receive syn = X
                    if self.state==0 and pkt.status==PoopHandshakePacket.NOT_STARTED and is_set(pkt.syn):
                        self.ack = pkt.syn
                        self.syn = random.randint(0, MAX_UINT32)
                        p = PoopHandshakePacket(status=PoopHandshakePacket.SUCCESS)
                        p.syn = self.syn
                        p.ack = increment_mod(self.ack)
                        logger.debug('{} side setting state to {}'.format(self._mode, self.state+1))
                        self.state += 1
                        logger.debug('{} side sending packet:\nsyn: {}\nack: {}\nstatus: {}\nerror: {}'.format(self._mode, p.syn, p.ack, p.status, p.error))
                        self.transport.write(p.__serialize__())
                    # should receive syn = (X+1)mod2^32 and ack = (Y+1)mod2^32
                    elif self.state==1 and pkt.status==PoopHandshakePacket.SUCCESS and is_set(pkt.syn, pkt.ack):
                        # if handshake successful
                        if pkt.ack == increment_mod(self.syn) and pkt.syn == increment_mod(self.ack):
                            logger.debug('{} side setting handshakeComplete to True'.format(self._mode))
                            self.handshakeComplete = True
                            # should this go back in connection_made() ?
                            logger.debug('{} side calling self.higherProtocol().connection_made()'.format(self._mode))
                            higher_transport = PoopTransport(self.transport)
                            higher_transport.setMode(self._mode)
                            higher_transport.setSeq(self.syn)
                            self.higherProtocol().connection_made(higher_transport)
                        else:
                            # TODO error
                            # ack != self.syn + 1 or syn != self.ack + 1
                            pass
                    else:
                        # TODO error
                        # invalid state and PoopHandshakePacket.status combination
                        pass
                else:
                    # TODO error
                    # not the PoopHandshakePacket
                    """
                    if we want to retry the whole handshake on an error, we need to:
                    reset self.state to 0
                    reset self.syn, self.ack to None, None
                    reset handshakeComplete to False (may not be necessary?)
                    send error packet?
                    maybe other things I'm forgetting?
                    """
                    pass

    def connection_lost(self, exc):
        logger.debug("{} POOP connection lost. Shutting down higher layer.".format(self._mode))
        self.higherProtocol().connection_lost(exc)

PoopHandshakeClientFactory = StackingProtocolFactory.CreateFactoryType(PoopHandshakeClientProtocol)

PoopHandshakeServerFactory = StackingProtocolFactory.CreateFactoryType(PoopHandshakeServerProtocol)