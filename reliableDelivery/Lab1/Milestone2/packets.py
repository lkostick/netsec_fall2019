from playground.network.packet.fieldtypes import UINT8, UINT32, STRING, BUFFER
from playground.network.packet.fieldtypes.attributes import Optional
from playground.network.packet import PacketType


class PoopPacketType(PacketType):
    DEFINITION_IDENTIFIER = "poop"
    DEFINITION_VERSION = "1.0"


class DataPacket(PoopPacketType):
    DEFINITION_IDENTIFIER = "poop.datapacket"
    DEFINITION_VERSION = "1.0"

    DEFAULT_DATAHASH = 0

    FIELDS = [
        ("seq", UINT32({Optional: True})),
        ("hash", UINT32),
        ("data", BUFFER({Optional: True})),
        ("ACK", UINT32({Optional: True})),
    ]

class ShutdownPacket(PoopPacketType):
    DEFINITION_IDENTIFIER = 'poop.shutdownpacket'
    DEFINITION_VERSION = '1.0'

    DEFAULT_DATAHASH = 0

    FIELDS = [
        ("FIN", UINT32({Optional: True})),
        ("FACK", UINT32({Optional: True})),
        ("hash", UINT32({Optional: True})) # not in prfc, but we can do this in our implementation
    ]


class HandshakePacket(PoopPacketType):
    DEFINITION_IDENTIFIER = "poop.handshakepacket"
    DEFINITION_VERSION = "1.0"

    NOT_STARTED = 0
    SUCCESS = 1
    ERROR = 2

    FIELDS = [
        ("status", UINT8),
        ("SYN", UINT32({Optional: True})),
        ("ACK", UINT32({Optional: True})),
        ("error", STRING({Optional: True})),
        ("last_valid_sequence", UINT32({Optional: True})) # never used even in the prfc, but fuck it
    ]