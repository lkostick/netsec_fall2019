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
    def __init__(self, loop, bank_client, bank_addr, bank_port, username, user_acct):
        self.loop = loop
        self.bank_client = bank_client
        self.bank_addr = bank_addr
        self.bank_port = bank_port
        self.username = username
        self.user_acct = user_acct
        self.transferResult = None
        self.game_status = None

        self.loop.add_reader(sys.stdin, self.game_next_input)
        self.deserializer = PacketType.Deserializer()

    def connection_made(self, transport):
        print('Connection made')
        print('Connected to {}'.format(transport.get_extra_info('peername')))
        self.transport = transport

        p = create_game_init_packet(self.username)
        self.transport.write(p.__serialize__())

    def data_received(self, data):
        print('Something received from {}: {}'.format(self.transport.get_extra_info('peer_name'), data))
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
                game_over = self.game_status == 'escaped' or self.game_status == 'dead'
                print(game_response)

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
        game_input = sys.stdin.readline().strip()
        self.write(game_input)
        if self.game_status != 'playing':
            self.loop.stop()
        else:
            self.flush_output('>> ', end='')

    def flush_output(self, *args, **kargs):
        print(*args, **kargs)
        sys.stdout.flush()


def main(args):
    EnablePresetLogging(PRESET_VERBOSE)

    host = args[0]
    port = int(args[1])
    print('host:', host)
    print('port:', port)
    bank_addr = '20194.0.1.1'
    bank_port = 888
    username = input('Enter username: ')
    # username = "sabdous1"
    password = getpass.getpass('Enter password for {}: '.format(username))
    user_acct = input('Enter account name: ')
    # user_acct = "sabdous1_account"
    bank_client = BankClientProtocol(bank_cert, username, password)
    loop = asyncio.get_event_loop()

    coro = playground.create_connection(
        lambda: GameClientProtocol(loop, bank_client, bank_addr, bank_port, username, user_acct), host=host, port=port, family=STACK)
    client = loop.run_until_complete(coro)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    loop.close()


if __name__ == '__main__':
    main(sys.argv[1:])
