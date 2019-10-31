from playground.network.packet import PacketType
from playground.network.packet.fieldtypes import UINT8, STRING, BUFFER, UINT16, BOOL

# Create game init packet and functions
class GameInitPacket(PacketType):
    DEFINITION_IDENTIFIER = "initpacket"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("username", STRING)
    ]


def create_game_init_packet(username):
    return GameInitPacket(username=username)


def process_game_init(pkt):
    if not isinstance(pkt, GameInitPacket):
        raise Exception()
    return pkt.username


# Create Game Require Pay Packet
class GameRequirePayPacket(PacketType):
    DEFINITION_IDENTIFIER = "requirepaypacket"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("unique_id", STRING),
        ("account", STRING),
        ("amount", UINT8)
    ]


def create_game_require_pay_packet(unique_id, account, amount):
    return GameRequirePayPacket(unique_id=unique_id, account=account, amount=amount)


def process_game_require_pay_packet(pkt):
    if not isinstance(pkt, GameRequirePayPacket):
        raise Exception()
    return pkt.unique_id, pkt.account, pkt.amount


# Create Game Pay Packet
class GamePayPacket(PacketType):
    DEFINITION_IDENTIFIER = "paypacket"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("receipt", BUFFER),
        ("receipt_signature", BUFFER)
    ]


def create_game_pay_packet(receipt, receipt_signature):
    return GamePayPacket(receipt=receipt, receipt_signature=receipt_signature)


def process_game_pay_packet(pkt):
    if not isinstance(pkt, GamePayPacket):
        raise Exception()
    return pkt.receipt, pkt.receipt_signature


# Create Game Response Packet
class GameResponsePacket(PacketType):
    DEFINITION_IDENTIFIER = "responsepacket"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("response", STRING),
        ("status", STRING)
    ]


def create_game_response(response, status):
    return GameResponsePacket(response=response, status=status)


def process_game_response(pkt):
    if not isinstance(pkt, GameResponsePacket):
        raise Exception()
    return pkt.response, pkt.status

# Create Game Command Packet
class GameCommandPacket(PacketType):
    DEFINITION_IDENTIFIER = "commandpacket"
    DEFINITION_VERSION = "1.0"
    FIELDS = [
        ("command", STRING)
    ]


def create_game_command(command):
    return GameCommandPacket(command = command)


def process_game_command(pkt):
    if not isinstance(pkt, GameCommandPacket):
        raise Exception()
    return pkt.command

