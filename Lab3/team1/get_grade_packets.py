from playground.network.packet import PacketType
from playground.network.packet.fieldtypes import UINT8, STRING, BUFFER, UINT16, BOOL

class GameCommandPacket(PacketType):
    DEFINITION_IDENTIFIER = "20194.exercise6.gamecommand"
    DEFINITION_VERSION = "1.0"

    FIELDS = [
        ("cmd", STRING)
    ]

    
    @classmethod
    def create_game_command_packet(cls, s):
        return cls(cmd=s)
    
    def command(self):
        return self.cmd
    


class GameResponsePacket(PacketType):
    DEFINITION_IDENTIFIER = "20194.exercise6.gameresponse"
    DEFINITION_VERSION = "1.0"

    FIELDS = [
        ("rsp", STRING),
        ("stat", STRING)
    ]

    @classmethod
    def create_game_response_packet(cls, response, status):
        return cls(rsp=response, stat=status)
    
    def game_over(self):
        return self.stat == "escaped" or self.stat == "dead"
    
    def status(self):
        return self.stat
    
    def response(self):
        return self.rsp

