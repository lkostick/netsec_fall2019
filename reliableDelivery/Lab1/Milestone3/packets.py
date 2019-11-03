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


class HandshakePacket(PoopPacketType):
    DEFINITION_IDENTIFIER = "poop.handshakepacket"
    DEFINITION_VERSION = "1.0"

    DEFAULT_HANDSHAKE_HASH = 0

    NOT_STARTED = 0
    SUCCESS = 1
    ERROR = 2

    FIELDS = [
        ("SYN", UINT32({Optional: True})),
        ("ACK", UINT32({Optional: True})),
        ("status", UINT8),
        ("hash", UINT32)
    ]


class ShutdownPacket(PoopPacketType):
    DEFINITION_IDENTIFIER = "poop.shutdownpacket"
    DEFINITION_VERSION = "1.0"

    DEFAULT_SHUTDOWN_HASH = 0

    SUCCESS = 0
    ERROR = 1

    FIELDS = [
        ("FIN", UINT32),
        ("status", UINT8({Optional: True})),
        ("hash", UINT32)
    ]
