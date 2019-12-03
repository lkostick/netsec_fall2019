"""
Escape Room Core
"""

IS_ONLINE = True
import random
import time
import uuid
import getpass, sys, os, asyncio
import random

if IS_ONLINE:
    from playground.common.logging import EnablePresetLogging, PRESET_VERBOSE, PRESET_DEBUG
    from playground.network.packet.fieldtypes import BOOL, STRING
    from playground.network.common import PlaygroundAddress
    from playground.network.packet import PacketType
    from autograder_ex6_packets import *
    from game_packets import *
    from CipherUtil import loadCertFromFile
    from BankCore import LedgerLineStorage, LedgerLine
    from OnlineBank import BankClientProtocol, OnlineBankConfig
    import playground


if IS_ONLINE:
    bankconfig = OnlineBankConfig()
    bank_addr =     bankconfig.get_parameter("CLIENT", "bank_addr")
    bank_port = int(bankconfig.get_parameter("CLIENT", "bank_port"))
    bank_stack     =     bankconfig.get_parameter("CLIENT", "stack","default")
    # bank_username  =     bankconfig.get_parameter("", "username")
    bank_username = 'sabdous1'
    # certPath = os.path.join(bankconfig.path(), "20194_online_bank.cert")
    certPath = os.path.join(bankconfig.path(), "live_fire_bank.cert")
    bank_cert = loadCertFromFile(certPath)

    dst_account = 'sabdous1_account'

    EnablePresetLogging(PRESET_VERBOSE)



def create_container_contents(*escape_room_objects):
    return {obj.name: obj for obj in escape_room_objects}
    
def listFormat(object_list):
    l = ["a "+object.name for object in object_list if object["visible"]]
    return ", ".join(l)

class EscapeRoomObject:
    def __init__(self, name, **attributes):
        self.name = name
        self.attributes = attributes
        self.triggers = []
        
    def do_trigger(self, *trigger_args):
        return [event for trigger in self.triggers for event in [trigger(self, *trigger_args)] if event]
        
    def __getitem__(self, object_attribute):
        return self.attributes.get(object_attribute, False)
        
    def __setitem__(self, object_attribute, value):
        self.attributes[object_attribute] = value
        
    def __repr__(self):
        return self.name
        
class EscapeRoomCommandHandler:
    def __init__(self, room, player, transport, output=print):
        self.room = room
        self.player = player
        self.output = output
        self.transport = transport
        
    def _run_triggers(self, object, *trigger_args):
        for event in object.do_trigger(*trigger_args):
            self.output(event, 'playing', transport=self.transport)
        
    def _cmd_look(self, look_args):
        look_result = None
        if len(look_args) == 0:
            object = self.room
        else:
            object = self.room["container"].get(look_args[-1], self.player["container"].get(look_args[-1], None))
        
        if not object or not object["visible"]:
            look_result = "You don't see that here."
        elif object["container"] != False and look_args and "in" == look_args[0]:
            if not object["open"]:
                look_result = "You can't do that! It's closed!"
            else:
                look_result = "Inside the {} you see: {}".format(object.name, listFormat(object["container"].values()))
                if object.name == 'safe':
                    look_result += "! There is 500 billion dollars cash in the safe but The bomb may explode if you try to get the money, but it's a 50-50 chance. Are you brave enough to accept the risk? :)"
        else:
            self._run_triggers(object, "look")
            look_result = object.attributes.get("description","You see nothing special")
        self.output(look_result, 'playing', transport=self.transport)
        
    def _cmd_unlock(self, unlock_args):
        unlock_result = None
        if len(unlock_args) == 0:
            unlock_result = "Unlock what?!"
        elif len(unlock_args) == 1:
            unlock_result = "Unlock {} with what?".format(unlock_args[0])
        
        else:
            object = self.room["container"].get(unlock_args[0], None)
            unlock = False
            
            if not object or not object["visible"]:
                unlock_result = "You don't see that here."
            elif not object["keyed"] and not object["keypad"]:
                unlock_result = "You can't unlock that!"
            elif not object["locked"]:
                unlock_result = "It's already unlocked"
            
            elif object["keyed"]:
                unlocker = self.player["container"].get(unlock_args[-1], None)
                if not unlocker:
                    unlock_result = "You don't have a {}".format(unlock_args[-1])                    
                elif unlocker not in object["unlockers"]:
                    unlock_result = "It doesn't unlock."
                else:
                    if random.randint(0, 1) < 1:
                        unlock_result =  "Your tool is rusty and your attempt is unsuccessful at this time. Try again please."
                    else:
                        unlock = True
                    # unlock = True
                    
            elif object["keypad"]:
                # TODO: For later Exercise
                # I've added this. I hope this works. -Justin
                unlocker = unlock_args[-1]
                if unlocker == object["code"]:
                    unlock = True
                else:
                    unlock_result = "It doesn't unlock."
                # pass
            
            if unlock:
                unlock_result = "You hear a click! It worked!"
                object["locked"] = False
                self._run_triggers(object, "unlock", unlocker)
        self.output(unlock_result, 'playing', transport=self.transport)
        
    def _cmd_open(self, open_args):
        """
        Let's demonstrate using some ands instead of ifs"
        """
        if len(open_args) == 0:
            return self.output("Open what?", 'playing', transport=self.transport)
        object = self.room["container"].get(open_args[-1], None)
        
        success_result = "You open the {}.".format(open_args[-1])
        open_result = (
            ((not object or not object["visible"]) and "You don't see that.") or
            ((object["open"])                      and "It's already open!") or
            ((object["locked"])                    and "It's locked") or
            ((not object["openable"])              and "You can't open that!") or
                                                       success_result)
        if open_result == success_result:
            object["open"] = True
            self._run_triggers(object, "open")
        self.output(open_result, 'playing', transport=self.transport)

    def _cmd_get(self, get_args):

        GET_MONEY = 1
        EXPLODE = 2
        status = 'playing'

        if len(get_args) == 0:
            get_result = "Get what?"
        elif self.player["container"].get(get_args[0], None) != None:
            get_result = "You already have that"
        else:
            if len(get_args) > 1:
                container = self.room["container"].get(get_args[-1], None)
            else:
                container = self.room
            object = container["container"] and container["container"].get(get_args[0], None) or None
            
            success_result = "You got it"
            get_result = (
                ((not container or container["container"] == False)and "You can't get something out of that!") or
                ((container["openable"] and not container["open"]) and "It's not open.") or
                ((not object or not object["visible"])             and "You don't see that") or
                ((not object["gettable"])                          and "You can't get that.") or
                                                                   success_result)
            
            if get_result == success_result:
                container["container"].__delitem__(object.name)
                self.player["container"][object.name] = object
                self._run_triggers(object, "get",container)
                if object.name == "money":
                    chance = random.randint(1, 2)
                    if chance == EXPLODE:
                        get_result = 'BOOM!!!! You should\'ve left the money in the escaperoom, I guess you just touched the forbidden treasure!'
                        status = 'dead'
                        self.room["container"].__delitem__(self.player.name)
                        self.player["alive"] = False
                    elif chance == GET_MONEY:
                        get_result += 'and the bomb didn\'t explode. Now you\'re rich and you can escape, but still do you have enough time? '
                if object.name == "doll":
                    get_result = "WHY DID YOU GRAB THE DOLL?? YOU FOOL!!"
                    status = 'dead'
                    self.room["container"].__delitem__(self.player.name)
                    self.player["alive"] = False

        self.output(get_result, status, transport=self.transport)
        
    def _cmd_hit(self, hit_args):
        if not hit_args:
            return self.output("What do you want to hit?", 'playing', 'playing', transport=self.transport)
        target_name = hit_args[0]
        with_what_name = None
        if len(hit_args) != 1:
            with_what_name = hit_args[-1]
        
        target = self.room["container"].get(target_name, None)
        if not target or not target["visible"]:
            return self.output("You don't see a {} here.".format(target_name), 'playing', transport=self.transport)
        if with_what_name:
            with_what = self.player["container"].get(with_what_name, None)
            if not with_what:
                return self.output("You don't have a {}".format(with_what_name), 'playing', transport=self.transport)
        else:
            with_what = None
        
        if not target["hittable"]:
            return self.output("You can't hit that!", 'playing', transport=self.transport)
        elif random.randint(0,99) < 85:
            return self.output("You swing your hammer and MISS!", 'playing', transport=self.transport)
        else:
            self.output("You hit the {} with the {}".format(target_name, with_what_name), 'playing', transport=self.transport)
            self._run_triggers(target, "hit", with_what)
        
    def _cmd_inventory(self, inventory_args):
        """
        Use return statements to end function early
        """
        if len(inventory_args) != 0:
            self.output("What?!", 'playing', transport=self.transport)
            return
            
        items = ", ".join(["a "+item for item in self.player["container"]])
        self._run_triggers(object, "inventory")
        self.output("You are carrying {}".format(items), 'playing', transport=self.transport)
        
    def command(self, command_string):
        # no command
        if command_string.strip == "":
            return self.output("", 'playing', transport=self.transport)
            
        command_args = command_string.split(" ")
        function = "_cmd_"+command_args[0]
        
        # unknown command
        if not hasattr(self, function):
            return self.output("You don't know how to do that.", 'playing', 'playing', transport=self.transport)
            
        # execute command dynamically
        getattr(self, function)(command_args[1:])
        self._run_triggers(self.room, "_post_command_", *command_args)
        
def create_room_description(room):
    room_data = {
        "mirror": room["container"]["mirror"].name,
        "clock_time": room["container"]["clock"]["time"],
        "interesting":""
    }
    for item in room["container"].values():
        if item["interesting"]:
            room_data["interesting"]+= "\n\t"+short_description(item)
    if room_data["interesting"]:
        room_data["interesting"] = "\nIn the room you see:"+room_data["interesting"]
    return """You are in a locked room. There is only one door
and it is locked. Above the door is a clock that reads {clock_time}.
Across from the door is a large {mirror}. Below the mirror is an old chest.
At the corner of the room there is a safe, unlike the chest, the safe is brand new!
Next to that safe is a padlocksafe. There is also a creepy doll in the opposite corner.
How peculiar...

The room is old and musty and the floor is creaky and warped.{interesting}""".format(**room_data)

def create_door_description(door):
    description = "The door is strong and highly secured."
    if door["locked"]:
        description += " The door is locked."
    return description

def create_safe_description(safe):
    description = "The safe is really heavy, could be something inside, may be money..."
    if safe["locked"]:
        description += " The safe is locked."
    elif safe["open"]:
        description += " The safe is open."
    return description

def create_doll_description(doll):
    description= "Pick me up and play with me!"
    return description

def create_mirror_description(mirror, room):
    description = "You look in the mirror and see yourself."
    if "hairpin" in room["container"]:
        description += ".. wait, there's a hairpin in your hair. Where did that come from?"
    return description
    
def create_chest_description(chest):
    description = "An old chest. It looks worn, but it's still sturdy."
    if chest["locked"]:
        description += " And it appears to be locked."
    elif chest["open"]:
        description += " The chest is open."
    return description

def create_flyingkey_description(flyingkey):
    description = "A golden flying key with silver wings shimmering in the light"
    description += " is currently resting on the " + flyingkey["location"]
    return description
    
def create_flyingkey_short_description(flyingkey):
    return "A flying key on the " + flyingkey["location"]

def create_padlocksafe_description(padlocksafe, padlocksafe_code):
    description = "A sturdy safe with a number combination padlock. Wait, there's something written on top.\n"
    description += "The numbers " + padlocksafe_code + " are scribbled in messy penmanship."
    if padlocksafe["locked"]:
        description += " It's locked."
    elif padlocksafe["open"]:
        description += " The padlocksafe is open."
    return description

def create_memo_description(memo):
    haiku = """
    Are you the player?
    Are you being played by the game?
    This is a haiku."""
    description = "A memo with some writing on it. It looks to be a haiku. It reads:"
    description += haiku
    description += "\n\n... This doesn't make much sense."
    return description

def advance_time(room, clock):
    event = None
    clock["time"] = clock["time"] - 1
    if clock["time"] == 0:
        for object in room["container"].values():
            if object["alive"]:
                object["alive"] = False
        event = "Oh no! The clock reaches 0 and a deadly gas fills the room!"
    room["description"] = create_room_description(room)
    return event
    
def flyingkey_hit_trigger(room, flyingkey, key, transport, output):
    if flyingkey["location"] == "ceiling":
        output("You can't reach it up there!", 'playing', transport=transport)
    elif flyingkey["location"] == "floor":
        output("It's too low to hit.", 'playing', 'playing', transport=transport)
    else:
        flyingkey["flying"] = False
        del room["container"][flyingkey.name]
        room["container"][key.name] = key
        output("The flying key falls off the wall. When it hits the ground, it's wings break off and you now see an ordinary key.", 'playing', transport=transport)
        
def short_description(object):
    if not object["short_description"]: return "a "+object.name
    return object["short_description"]
                
class EscapeRoomGame:
    def __init__(self, transport=None, command_handler_class=EscapeRoomCommandHandler, output=print):
        self.room, self.player = None, None
        self.output = output
        self.command_handler_class = command_handler_class
        self.command_handler = None
        self.agents = []
        self.status = "void"
        self.transport = transport
        
    def create_game(self, cheat=False):
        padlocksafe_code = str(random.randint(0, 999999)).zfill(6)
        clock =  EscapeRoomObject("clock",  visible=True, time=100)
        mirror = EscapeRoomObject("mirror", visible=True)
        hairpin= EscapeRoomObject("hairpin",visible=False, gettable=True)
        key    = EscapeRoomObject("key",    visible=True, gettable=True, interesting=True)
        door  =  EscapeRoomObject("door",   visible=True, openable=True, open=False, keyed=True, locked=True, unlockers=[key])
        safe = EscapeRoomObject("safe", visible=True, openable=True, open=False, keyed=True, locked=True, unlockers=[key])
        doll = EscapeRoomObject("doll", visible=True, gettable=True)
        chest  = EscapeRoomObject("chest",  visible=True, openable=True, open=False, keyed=True, locked=True, unlockers=[hairpin])
        room   = EscapeRoomObject("room",   visible=True)
        player = EscapeRoomObject("player", visible=False, alive=True)
        hammer = EscapeRoomObject("hammer", visible=True, gettable=True)
        bomb = EscapeRoomObject("bomb", visible=True)
        money = EscapeRoomObject("money", visible=True, gettable=True)
        flyingkey = EscapeRoomObject("flyingkey", visible=True, flying=True, hittable=False, smashers=[hammer], interesting=True, location="ceiling")
        padlocksafe = EscapeRoomObject("padlocksafe", visible=True, openable=True, open=False, keypad=True, locked=True, code=padlocksafe_code)
        memo = EscapeRoomObject("memo", visible=True, gettable=True)

        # setup containers
        player["container"]= {}
        safe["container"] = create_container_contents(bomb, money)
        padlocksafe["container"] = create_container_contents(memo)
        chest["container"] = create_container_contents(hammer)
        room["container"]  = create_container_contents(player, door, clock, mirror, hairpin, chest, flyingkey, safe, doll, padlocksafe)
        
        # set initial descriptions (functions)
        door["description"]    = create_door_description(door)
        safe["description"] = create_safe_description(safe)
        doll["description"] = create_doll_description(doll)
        mirror["description"]  = create_mirror_description(mirror, room)
        chest["description"]   = create_chest_description(chest)
        flyingkey["description"] = create_flyingkey_description(flyingkey)
        flyingkey["short_description"] = create_flyingkey_short_description(flyingkey)
        key["description"] = "a golden key, cruelly broken from its wings."
        padlocksafe["description"] = create_padlocksafe_description(padlocksafe, padlocksafe_code)
        memo["description"] = create_memo_description(memo)
        
        # the room's description depends on other objects. so do it last
        room["description"]    = create_room_description(room)

        mirror.triggers.append(lambda obj, cmd, *args: (cmd == "look") and hairpin.__setitem__("visible",True))
        mirror.triggers.append(lambda obj, cmd, *args: (cmd == "look") and mirror.__setitem__("description", create_mirror_description(mirror, room)))
        door.triggers.append(lambda obj, cmd, *args: (cmd == "unlock") and door.__setitem__("description", create_door_description(door)))
        door.triggers.append(lambda obj, cmd, *args: (cmd == "open") and room["container"].__delitem__(player.name))
        safe.triggers.append(lambda obj, cmd, *args: (cmd == "unlock") and safe.__setitem__("description", create_safe_description(safe)))
        safe.triggers.append(lambda obj, cmd, *args: (cmd == "open") and safe.__setitem__("description", create_chest_description(chest)))
        room.triggers.append(lambda obj, cmd, *args: (cmd == "_post_command_") and advance_time(room, clock))
        flyingkey.triggers.append((lambda obj, cmd, *args: (cmd == "hit" and args[0] in obj["smashers"]) and flyingkey_hit_trigger(room, flyingkey, key, self.transport, self.output)))
        chest.triggers.append(lambda obj, cmd, *args: (cmd == "unlock") and chest.__setitem__("description", create_chest_description(chest)))
        chest.triggers.append(lambda obj, cmd, *args: (cmd == "open") and chest.__setitem__("description", create_chest_description(chest)))
        # doll.triggers.append(
        padlocksafe.triggers.append(lambda obj, cmd, *args: (cmd == "unlock") and padlocksafe.__setitem__("description", create_padlocksafe_description(padlocksafe, padlocksafe_code)))
        # TODO, the chest needs some triggers. This is for a later exercise
        
        self.room, self.player = room, player
        self.command_handler = self.command_handler_class(room, player, self.transport, self.output)
        self.agents.append(self.flyingkey_agent(flyingkey))
        self.status = "created"
        
    async def flyingkey_agent(self, flyingkey):
        random.seed(0) # this should make everyone's random behave the same.
        await asyncio.sleep(5) # sleep before starting the while loop
        while self.status == "playing" and flyingkey["flying"]:
            locations = ["ceiling","floor","wall"]
            locations.remove(flyingkey["location"])
            random.shuffle(locations)
            next_location = locations.pop(0)
            old_location = flyingkey["location"]
            flyingkey["location"] = next_location
            flyingkey["description"] = create_flyingkey_description(flyingkey)
            flyingkey["short_description"] = create_flyingkey_short_description(flyingkey)
            flyingkey["hittable"] = next_location == "wall"
            self.output("The {} flies from the {} to the {}".format(flyingkey.name, old_location, next_location), self.status, transport= self.transport)
            for event in self.room.do_trigger("_post_command_"):
                self.output(event, self.status, transport=self.transport)
            await asyncio.sleep(5)
    
    def start(self):
        self.status = "playing"
        self.output("Where are you? You don't know how you got here... Were you kidnapped? Better take a look around", self.status, transport=self.transport)
        
    def command(self, command_string):
        if self.status == "void":
            self.output("The world doesn't exist yet!", self.status, transport=self.transport)
        elif self.status == "created":
            self.output("The game hasn't started yet!", self.status, transport=self.transport)
        elif self.status == "dead":
            self.output("You already died! Sorry!", self.status, transport=self.transport)
        elif self.status == "escaped":
            self.output("You already escaped! The game is over!", self.status, transport=self.transport)
        else:
            self.command_handler.command(command_string)
            if not self.player["alive"]:
                self.output("You died. Game over!", self.status, transport=self.transport)
                self.status = "dead"
            elif self.player.name not in self.room["container"]:
                self.status = "escaped"
                self.output("VICTORY! You escaped!", self.status, transport=self.transport)
                
def game_next_input(game):
    input = sys.stdin.readline().strip()
    game.command(input)
    if game.status != 'playing':
        asyncio.get_event_loop().stop()
    else:
        flush_output(">> ", end='')
        
def flush_output(*args, **kargs):
    if IS_ONLINE:
        command = args[0]
        status = args[1]
        game_command_packet = create_game_response(response=command, status=status)
        game_command_packet_byte = game_command_packet.__serialize__()
        print("Command that goes out: " + str(game_command_packet_byte))
        kargs["transport"].write(game_command_packet_byte)
        time.sleep(0.25)
    else:
        if "transport" in kargs:
            del kargs["transport"]
        command, *others = args
        print(command, **kargs)
        sys.stdout.flush()

class ServerProtocol(asyncio.Protocol):

    def __init__(self, args):
        self.args = args
        self.game = None
        self.loop = args[0]
        self.password = args[1]
        self.deserializer = PacketType.Deserializer()
        self.amount = 10
        self.memo = None

    def connection_made(self, transport):
        self.transport = transport
        self.game = EscapeRoomGame(transport=transport, output=flush_output)
        self.game.create_game(cheat=("--cheat" in self.args))

    def send_packet(self, packet):
        packet_byte = packet.__serialize__()
        print('Command going out: ' + str(packet_byte))
        self.transport.write(packet_byte)

    def verify(self, bank_client, receipt_bytes, signature_bytes, dst, amount, memo):
        if not bank_client.verify(receipt_bytes, signature_bytes):
            raise Exception("Bad receipt. Not correctly signed by bank")
        ledger_line = LedgerLineStorage.deserialize(receipt_bytes)
        if ledger_line.getTransactionAmount(dst) != amount:
            raise Exception("Invalid amount. Expected {} got {}".format(amount, ledger_line.getTransactionAmount(dst)))
        elif ledger_line.memo(dst) != memo:
            raise Exception("Invalid memo. Expected {} got {}".format(memo, ledger_line.memo()))
        return True

    def data_received(self, data):
        print('myServer: something received: ' + str(data))
        self.deserializer.update(data)
        for packet in self.deserializer.nextPackets():
            print('Packet Received: ' + str(packet))
            if isinstance(packet, GameInitPacket):
                username = process_game_init(packet)
                print('Packet Info: CreateGameInitPacket\n' +
                      '\nuser_name: ' + str(username) + ' - ' + str(type(username)))
                unique_id = str(uuid.uuid1())
                self.memo = unique_id
                new_packet = create_game_require_pay_packet(unique_id=unique_id, account=dst_account, amount=self.amount)
                self.send_packet(new_packet)
            if isinstance(packet, GamePayPacket):
                receipt, receipt_signature = process_game_pay_packet(packet)
                print('Packet Info: CreateGameInitPacket\n' +
                      '\nreceipt: ' + str(receipt) + ' - ' + str(type(receipt))+
                      '\nreceipt_signature: ' + str(receipt_signature) + ' - ' + str(type(receipt_signature)))
                username = bank_username  # could override at the command line
                password = self.password
                bank_client = BankClientProtocol(bank_cert, username, password)
                if self.verify(bank_client=bank_client, receipt_bytes=receipt, signature_bytes=receipt_signature, dst=dst_account, amount=self.amount, memo=self.memo):
                    self.game.start()
                    asyncio.ensure_future(main(self.game, self.args))
                else:
                    new_packet = create_game_response(response="", status="dead")
                    self.send_packet(new_packet)

            if isinstance(packet, GameCommandPacket):
                command = process_game_command(packet)
                print('Packet Info:\n' +
                    'response: ' + str(command)
                    )
                print("command that comes in: " + command)
                if self.game.status == "playing":
                    output = self.game.command(command)


async def main(game=None, args=None):
    if IS_ONLINE:
        await asyncio.wait([asyncio.ensure_future(a) for a in game.agents])
    else:
        loop = asyncio.get_event_loop()
        game = EscapeRoomGame(output=flush_output)
        game.create_game(cheat=("--cheat" in args))
        game.start()
        flush_output(">> ", end='')
        loop.add_reader(sys.stdin, game_next_input, game)
        await asyncio.wait([asyncio.ensure_future(a) for a in game.agents])



if __name__ == "__main__":
    if IS_ONLINE:
        IP = '1376.1.1.1'
        PORT = "12345"
        args = []
        loop = asyncio.get_event_loop()
        args.append(loop)
        username = bank_username
        password = getpass.getpass("Enter password for {}: ".format(username))
        args.append(password)
        args.append(sys.argv[1:])
        coro = playground.create_server(lambda: ServerProtocol(args), IP, PORT)
        server = loop.run_until_complete(coro)
        print('Serving on {}'.format(server.sockets[0].getsockname()))
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass

        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.close()
    else:
        asyncio.ensure_future(main(args=sys.argv[1:]))
        asyncio.get_event_loop().run_forever()


