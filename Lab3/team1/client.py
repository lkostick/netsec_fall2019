import asyncio
import sys
import time

from playground.common.logging import EnablePresetLogging, PRESET_VERBOSE
from playground.network.packet.fieldtypes import BOOL, STRING
from playground.network.common import PlaygroundAddress
from playground.network.packet import PacketType
import playground
from autograder_ex6_packets import *
from game_packets import *

from CipherUtil import loadCertFromFile
from BankCore import LedgerLineStorage, LedgerLine
from OnlineBank import BankClientProtocol, OnlineBankConfig
import playground
import getpass, sys, os, asyncio

bankconfig = OnlineBankConfig()
bank_addr =     bankconfig.get_parameter("CLIENT", "bank_addr")
bank_port = int(bankconfig.get_parameter("CLIENT", "bank_port"))
bank_stack     =     bankconfig.get_parameter("CLIENT", "stack","default")
# bank_username  =     bankconfig.get_parameter("CLIENT", "username")
bank_username = 'jflynn22'

#src_account = "sabdous1_account"
src_account = "jflynn22_account"

certPath = os.path.join(bankconfig.path(), "bank.cert")
bank_cert = loadCertFromFile(certPath)

EnablePresetLogging(PRESET_VERBOSE)


class ClientProtocol(asyncio.Protocol):
    def __init__(self, loop):
        self.loop = loop
        self.flying_key_is_hit = False
        self.got_hammer = False
        self.deserializer = PacketType.Deserializer()
        self.start_requesting = False

    async def transfer(self, bank_client, src, dst, amount, memo, transport):
        await playground.create_connection(
            lambda: bank_client,
            bank_addr,
            bank_port,
            family='default'
        )
        print("Connected. Logging in.")

        try:
            await bank_client.loginToServer()
        except Exception as e:
            print("Login error. {}".format(e))
            return False

        try:
            await bank_client.switchAccount(src)
        except Exception as e:
            print("Could not set source account as {} because {}".format(
                src,
                e))
            return False

        try:
            result = await bank_client.transfer(dst, amount, memo)
        except Exception as e:
            print("Could not transfer because {}".format(e))
            return False

        receipt = result.Receipt
        receipt_signature = result.ReceiptSignature
        print('Receipt Received: ' + str(receipt) + ' - ' + str(type(receipt)))
        print('Receipt Signature is: ' + str(receipt_signature) + ' - ' + str(type(receipt_signature)))
        new_packet = create_game_pay_packet(receipt=receipt, receipt_signature=receipt_signature)
        self.send_packet(packet=new_packet)
        return result

    def connection_made(self, transport):
        self.transport = transport
        print('Connection Made')

        # startServerPacket = AutogradeStartTest(name = "Sepehr Abdous", team = 1, 
        #     email = "sepehrabdous1375@gmail.com", port = 12381)
        
        # startServerPacketByte = startServerPacket.__serialize__()
        # print('Packet that is going out: ' + str(startServerPacketByte))
        # self.transport.write(startServerPacketByte)

        #new_packet = create_game_init_packet(username="sabdous1")
        new_packet = create_game_init_packet(username="jflynn22")
        self.send_packet(packet=new_packet)

    @asyncio.coroutine
    async def createAndSendCommand(self):
        escaping_command_list = ['look mirror', 'get hairpin', 'unlock chest with hairpin',
                                 'open chest', 'get hammer from chest', 'hit flyingkey with hammer',
                                 'get key', 'unlock door with key', 'open door']
        while escaping_command_list:
            command = escaping_command_list.pop(0)
            while (not self.flying_key_is_hit) and all(x in command for x in ["hammer", "flyingkey"]):
                await asyncio.sleep(5)
            else:
                if not all(x in command for x in ["hammer", "flyingkey"]):
                    if all(x in command for x in ["get", "hammer", "chest"]):
                        self.got_hammer = True
                    new_packet= create_game_command(command=command)
                    self.send_packet(packet=new_packet)
            await asyncio.sleep(5)

    def send_packet(self, packet):
        packet_byte = packet.__serialize__()
        print('Command going out: ' + str(packet_byte))
        self.transport.write(packet_byte)


    def data_received(self, data):
        print('something received: ' + str(data))
        self.deserializer.update(data)
        for packet in self.deserializer.nextPackets():
            print('Packet Received: ' + str(packet))
            
            if isinstance(packet, AutogradeTestStatus):
                # AutogradeTestStatus
                print('Packet Info: AutogradeTestStatus\n' + 
                    'test_id: ' + str(packet.test_id) + ' - ' + str(type(packet.test_id)) +
                    '\nsubmit_status: ' + str(packet.submit_status) + ' - ' + str(type(packet.submit_status)) +
                    '\nclient_status: ' + str(packet.client_status) + ' - ' + str(type(packet.client_status)) +
                    '\nserver_status: ' + str(packet.server_status) + ' - ' + str(type(packet.server_status)) +
                    '\nerror: ' + str(packet.error) + ' - ' + str(type(packet.error)))
                if packet.submit_status == 1 and packet.client_status == 0:
                    new_packet = create_game_init_packet(username="sabdous1")
                    self.send_packet(packet=new_packet)

            elif isinstance(packet, GameRequirePayPacket):
                unique_id, dst, amount = process_game_require_pay_packet(packet)
                print('Packet Info: CreateGameRequirePayPacket\n' +
                    '\nunique_id: ' + str(unique_id) + ' - ' + str(type(packet.unique_id)) +
                    '\naccount: ' + str(dst) + ' - ' + str(type(packet.account)) +
                    '\namount: ' + str(amount) + ' - ' + str(type(packet.amount)))
                src = src_account
                username = bank_username  # could override at the command line
                password = getpass.getpass("Enter password for {}: ".format(username))
                bank_client = BankClientProtocol(bank_cert, username, password)
                self.loop.create_task(self.transfer(bank_client=bank_client, src=src, dst=dst, amount=amount, memo=str(unique_id), transport=self.transport))

            elif isinstance(packet, GameResponsePacket):
                data, status = process_game_response(packet)
                print('Packet Info:\n' +
                    'response: ' + str(data) +
                    '\nstatus: ' + str(status)
                    )

                lines = data.split('\n')

                print('Data received: ' + str(lines))
                
                if not self.start_requesting:
                    self.start_requesting = True
                    self.loop.create_task(self.createAndSendCommand())
                if self.got_hammer and (not self.flying_key_is_hit) and all(x in lines[0] for x in ["to the wall", "flyingkey"]):
                    self.flying_key_is_hit = True
                    command = "hit flyingkey with hammer"
                    new_packet = create_game_command(command=command)
                    self.send_packet(packet=new_packet)
            else:
                raise Exception()

    def connection_lost(self, exc):
        print('Connection Lost!')
        self.loop.stop()

IP = '1376.1.1.1'
PORT = 12345
# IP = "0.0.0.0"
# PORT = "1234"

loop = asyncio.get_event_loop()
coro = playground.create_connection(lambda: ClientProtocol(loop),
                              IP, PORT)
loop.run_until_complete(coro)
loop.run_forever()
loop.close()
