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
        ("seq", UINT32),
        ("hash", UINT32),
        ("data", BUFFER({Optional: True})),
        ("ACK", UINT32({Optional: True})),
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
        ("last_valid_sequence", UINT32({Optional: True}))
    ]


class StartupPacket(HandshakePacket):
    DEFINITION_IDENTIFIER = "poop.startuppacket"
    DEFINITION_VERSION = "1.0"


class ShutdownPacket(HandshakePacket):
    DEFINITION_IDENTIFIER = "poop.shutdownpacket"
    DEFINITION_VERSION = "1.0"
