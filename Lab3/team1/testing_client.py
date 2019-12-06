import datetime
import time

from CipherUtil import loadCertFromFile
from OnlineBank import BankClientProtocol, OnlineBankConfig

import sys, os, getpass, asyncio
import playground
from game_packets import *
from playground.network.packet import PacketType
from playground.common.logging import EnablePresetLogging, PRESET_VERBOSE

bankconfig = OnlineBankConfig()
certPath = os.path.join(bankconfig.path(), "bank.cert")
bank_cert = loadCertFromFile(certPath)
STACK = "crap"


class GameClientProtocol(asyncio.Protocol):
    def __init__(self, loop, bank_client, bank_addr, bank_port, username, user_acct, commands=None, team_number=None):
        self.loop = loop
        self.bank_client = bank_client
        self.bank_addr = bank_addr
        self.bank_port = bank_port
        self.username = username
        self.user_acct = user_acct
        self.transferResult = None
        self.game_status = None
        self.commands = commands
        self.flyingkeyHit = False
        self.flyingringHit = True
        self.team_number = team_number
        if self.team_number == '3':
            self.flyingringHit = False

        self.loop.add_reader(sys.stdin, self.game_next_input)
        self.deserializer = PacketType.Deserializer()

    def connection_made(self, transport):
        print('Connection made')
        print('Connected to {}'.format(transport.get_extra_info('peername')))
        self.transport = transport

        p = create_game_init_packet(self.username)
        self.transport.write(p.__serialize__())

    def send_next_command(self):
        time.sleep(3)
        print('########################################')
        if "hit flyingkey" in self.commands[0] and not self.flyingkeyHit:
            print('sending {}'.format(self.commands[0]))
            self.write(self.commands[0])
        elif "hit flyingring" in self.commands[0] and not self.flyingringHit:
            print('sending {}'.format(self.commands[0]))
            self.write(self.commands[0])
        else:
            if "hit flyingkey" in self.commands[0] and self.flyingkeyHit:
                self.commands.pop(0)
            if "hit flyingring" in self.commands[0] and self.flyingringHit:
                self.commands.pop(0)
            command = self.commands.pop(0)
            print('sending {}'.format(command))
            self.write(command)

        print('########################################')

    def data_received(self, data):
        print('Something received from {}: {}'.format(self.transport.get_extra_info('peername'), data))
        self.deserializer.update(data)
        for packet in self.deserializer.nextPackets():
            print('Packet Received: ' + str(packet))
            if isinstance(packet, GameRequirePayPacket):
                unique_id, account, amount = process_game_require_pay_packet(packet)
                print('Packet Info: GameRequirePayPacket\n'
                      'unique_id: {}\n'
                      'account: {}\n'
                      'amount: {}\n'.format(unique_id, account, amount))
                asyncio.ensure_future(self.bankTransfer(self.user_acct, account, amount, unique_id))

            elif isinstance(packet, GameResponsePacket):
                game_response, self.game_status = process_game_response(packet)
                print('Packet Info: GameRequirePayPacket\n'
                      'reponse: {}\n'
                      'status: {}\n'.format(game_response, self.game_status))
                if "flyingkey" in game_response and "falls" in game_response:
                    self.flyingkeyHit = True
                if "flyingring" in game_response and "falls" in game_response:
                    self.flyingringHit = True
                game_over = self.game_status == 'escaped' or self.game_status == 'dead'
                print(game_response)
                if self.commands is not None:
                    self.send_next_command()

    def write(self, msg):
        p = create_game_command(msg)
        self.transport.write(p.__serialize__())

    async def bankTransfer(self, src, dst, amt, memo):
        await playground.create_connection(
            lambda: self.bank_client,
            self.bank_addr,
            self.bank_port,
            family=STACK
        )
        print('Connected. Logging in.')

        try:
            await self.bank_client.loginToServer()
        except Exception as e:
            print('Login error. {}'.format(e))
            return False

        print('Logged in')

        try:
            await self.bank_client.switchAccount(src)
        except Exception as e:
            print('Could not set source account as {} because {}'.format(src, e))
            return False

        print('Source account set!')

        try:
            result = await self.bank_client.transfer(dst, amt, memo)
        except Exception as e:
            print('Could not transfer because {}'.format(e))
            return False

        print('Transferred!')

        self.transferResult = result

        if self.transferResult:
            pkt = create_game_pay_packet(self.transferResult.Receipt, self.transferResult.ReceiptSignature)
            self.transport.write(pkt.__serialize__())

        return result

    def game_next_input(self):
        if self.game_status != 'playing':
            self.loop.stop()
        else:
            self.flush_output('>> ', end='')
        if self.commands is None:
            game_input = sys.stdin.readline().strip()
            self.write(game_input)

    def flush_output(self, *args, **kargs):
        print(*args, **kargs)
        sys.stdout.flush()

class Team:
    def __init__(self, host, port, team_number = None, commands=None):
        self.team_number = team_number
        self.commands = commands
        self.host = host
        self.port = port


def main(args):
    EnablePresetLogging(PRESET_VERBOSE)

    team_list = []

    '''
    commands to win team to:
    1) "enter code to the coded lock"
    2) enter current time on your laptop
    3) "open chest"
    4) "get hammer from chest"
    5) "hit flyingkey with hammer" (do it till you hit it)
    6) "get key"
    7) "unlock door with key"
    8) "open door"
    '''
    commands = ["enter code to the coded lock", datetime.datetime.now().strftime("%H%M"), "open chest", "get hammer from chest", "hit flyingkey with hammer",
                "get key", "unlock door with key", "open door"]
    team_list.append(Team(team_number='2', host='20194.2.57.98', port=2222, commands=commands))

    '''
    commands to win team to:
    1) "look mirror"
    2) "look puzzle"
    3) "answer 368.2"
    4) "look mirror"
    5) "get hairpin"
    6) "unlock chest with hairpin"
    7) "open chest"
    8) "get hammer from chest"
    9) "get spear from chest"
    10) "hit flyingkey with hammer" (do it till you hit it)
    11) "hit flyingring with spear" (do it till you hit it)
    12) "get flyingkey"
    13) "get flyingring"
    14) "get glue"
    15) "combine flyingkey with flyingring using glue"
    16) "get key"
    17) "unlock door with key"
    18) "hit monster with hammer"
    19) "open door"
    
    '''
    commands = ["look mirror", "look puzzle", "answer 368.2", "look mirror",
                "get hairpin", "unlock chest with hairpin", "open chest",
                "get hammer from chest", "get spear from chest", "hit flyingkey with hammer",
                "hit flyingring with spear", "get flyingkey", "get flyingring",
                "get glue", "combine flyingkey with flyingring using glue", "get key",
                "unlock door with key", "hit monster with hammer", "open door"]
    team_list.append(Team(team_number='3', host='20194.3.6.9', port=333, commands=commands))

    '''
    commands to win team to:
    1) "look mirror"
    2) 

    '''
    team_list.append(Team(team_number='4', host='20194.4.4.4', port=8666))

    '''
    commands to win team to:
    1) "look mirror"
    2) "get hairpin"
    3) "unlock chest with hairpin"
    4) "open chest"
    5) "get hammer from chest"
    6) "hit flyingkey with hammer" (do it till you hit it)
    7) "get key"
    8) "unlock door with key"
    9) "open door"

    '''
    commands = ["look mirror", "get hairpin", "unlock chest with hairpin", "open chest",
                "get hammer from chest", "hit flyingkey with hammer", "get key",
                "unlock door with key", "open door"]
    team_list.append(Team(team_number='5', host='20194.5.20.30', port=8989, commands=commands))

    '''
    commands to win team to:
    1) "hit flyingkey with hammer" (do it till you hit it)
    2) "get key"
    3) "unlock door with key"
    4) "open door"

    '''
    commands = ["hit flyingkey with hammer", "get key", "unlock door with key", "open door"]
    team_list.append(Team(team_number='6', host='20194.6.20.30', port=16666, commands=commands))

    '''
    commands to win team to:
    0) "get shield"
    1) "look mirror"
    2) "get hairpin"
    3) "unlock chest with hairpin"
    4) "open chest"
    5) "get hammer from chest"
    6) "hit flyingkey with hammer" (do it till you hit it)
    7) "get key"
    8) "unlock door with key"
    9) "open door"

    '''
    commands = ["get shield", "look mirror", "get hairpin",
                "unlock chest with hairpin", "open chest", "get hammer from chest",
                "hit flyingkey with hammer", "get key", "unlock door with key", "open door"]
    team_list.append(Team(team_number='9', host='20194.9.1.1', port=7826, commands=commands))

    while True:
        team_number = input("Enter team number escaperoom you want to play: ")
        if team_number not in ['2', '3', '4', '5', '6', '9']:
            print('Invalid team number!')
            continue
        break

    for i in team_list:
        if team_number == i.team_number:
            host = i.host
            port = i.port
            commands = i.commands
            break

    print('host:', host)
    print('port:', port)
    bank_addr = '20194.0.1.1'
    bank_port = 888
    username = input('Enter username: ')
    username = "sabdous1"
    password = getpass.getpass('Enter password for {}: '.format(username))
    user_acct = input('Enter account name: ')
    user_acct = "sabdous1_account"
    bank_client = BankClientProtocol(bank_cert, username, password)
    loop = asyncio.get_event_loop()

    coro = playground.create_connection(
        lambda: GameClientProtocol(loop, bank_client, bank_addr, bank_port, username, user_acct, commands=commands, team_number=team_number), host=host, port=port, family=STACK)
    client = loop.run_until_complete(coro)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    loop.close()


if __name__ == '__main__':
    main(sys.argv[1:])
