import unittest
import random
import asyncio

from playground.network.testing import MockTransportToStorageStream as MockTransport
from playground.asyncio_lib.testing import TestLoopEx
from playground.common.logging import EnablePresetLogging, PRESET_DEBUG

from protocol import *
from packets import *

# def pop_packets(storage, deserializer, rx, tx, reorder=False, error_rate=0):
#     while storage:
#         if reorder:
#             next_packet = storage.pop(random.randint(0,len(storage)-1))
#         else:
#             next_packet = storage.pop(0)
#         deserializer.update(next_packet)
#     for packet in deserializer.nextPackets():
#         if isinstance(packet, AckPacket):
#             tx.ack(packet.ack)
#         else:
#             if error_rate > 0:
#                 if random.random() < ((error_rate/102400.0)*len(packet.data)):
#                     # just drop the packet
#                     print("Drop packet")
#                     continue
#             rx.recv(packet)
            
class ListWriter:
    def __init__(self, l):
        self.l = l
        
    def write(self, data):
        self.l.append(data)
        
class DummyApplication(asyncio.Protocol):
    def __init__(self):
        self._connection_made_called = 0
        self._connection_lost_called = 0
        self._data = []
        self._transport = None
        
    def connection_made(self, transport):
        self._transport = transport
        self._connection_made_called += 1
        
    def connection_lost(self, reason=None):
        self._connection_lost_called += 1
        
    def data_received(self, data):
        self._data.append(data)
        
    def pop_all_data(self):
        data = b""
        while self._data:
            data += self._data.pop(0)
        return data
        
# class TestPoopDataHandling(unittest.TestCase):
#     def setUp(self):
#         asyncio.set_event_loop(TestLoopEx())
        
#         self.dummy_client = DummyApplication()
#         self.dummy_server = DummyApplication()
        
#         self.client_write_storage = []
#         self.server_write_storage = []
        
#         self.client_deserializer = PoopPacketType.Deserializer()
#         self.server_deserializer = PoopPacketType.Deserializer()
        
#         client_transport = MockTransport(ListWriter(self.client_write_storage))
#         server_transport = MockTransport(ListWriter(self.server_write_storage))
        
#         self.client_tx = PoopTx(client_transport, 1000)
#         self.client_rx = PoopRx(self.dummy_client, client_transport, 9000)
        
#         self.server_tx = PoopTx(server_transport, 9000)
#         self.server_rx = PoopRx(self.dummy_server, server_transport, 1000)
        
#     def test_simple_transmission(self):
#         msg = b"this is a test"
    
#         self.client_tx.send(msg)
        
#         self.assertEqual(len(self.client_tx.tx_window), 1)
        
#         pop_packets(self.client_write_storage, self.server_deserializer, self.server_rx, self.server_tx)
#         # this sends back an ack packet
#         pop_packets(self.server_write_storage, self.client_deserializer, self.client_rx, self.client_tx)
        
#         self.assertEqual(len(self.client_tx.tx_window), 0)
        
#         self.assertEqual(self.dummy_server.pop_all_data(), msg)
        
#     def test_large_transmission(self):
#         msg = (b"1"*2048)+(b"2"*2048)+(b"3"*2048)+(b"4"*100)
    
#         self.client_tx.send(msg)
        
#         while self.client_tx.tx_window:
#             cur_seq = self.client_tx.tx_window[0].seq
#             pop_packets(self.client_write_storage, self.server_deserializer, self.server_rx, self.server_tx, reorder=True, error_rate=3)
#             # this sends back an ack packet
#             pop_packets(self.server_write_storage, self.client_deserializer, self.client_rx, self.client_tx)
#             self.client_tx.resend(cur_seq)
            
#         self.assertEqual(len(self.client_tx.tx_window), 0)
        
#         self.assertEqual(self.dummy_server.pop_all_data(), msg)
        

# class TestPoopHandshake(unittest.TestCase):
#     def setUp(self):
#         self.client_poop = PoopHandshakeClientProtocol()
#         self.server_poop = PoopHandshakeServerProtocol()
        
#         self.client = DummyApplication()
#         self.server = DummyApplication()
        
#         self.client_poop.setHigherProtocol(self.client)
#         self.server_poop.setHigherProtocol(self.server)
        
#         self.client_write_storage = []
#         self.server_write_storage = []
        
#         self.client_transport = MockTransport(ListWriter(self.client_write_storage))
#         self.server_transport = MockTransport(ListWriter(self.server_write_storage))
        
#     def tearDown(self):
#         pass

#     def test_no_error_handshake(self):
#         self.server_poop.connection_made(self.server_transport)
#         self.client_poop.connection_made(self.client_transport)
        
#         self.assertEqual(self.client._connection_made_called, 0)
#         self.assertEqual(self.server._connection_made_called, 0)
        
#         # there should only be 1 blob of bytes for the SYN
#         self.assertEqual(len(self.client_write_storage), 1)
#         self.server_poop.data_received(self.client_write_storage.pop())
        
#         # server still should not be connected
#         self.assertEqual(self.server._connection_made_called, 0)
        
#         # there should be 1 blob of bytes from the server for the SYN ACK
#         self.assertEqual(len(self.server_write_storage), 1)
        
#         self.client_poop.data_received(self.server_write_storage.pop())
        
#         # now client should be connected
#         self.assertEqual(self.client._connection_made_called, 1)
        
#         # there should be 1 blob of bytes for the SYN ACK ACK storage
#         self.assertEqual(len(self.client_write_storage), 1)
#         self.server_poop.data_received(self.client_write_storage.pop())
        
#         # server should be connected
#         self.assertEqual(self.server._connection_made_called, 1)


class TestPoopShutdown(unittest.TestCase):
	def setUp(self):
		self.deserializer = PoopPacketType.Deserializer()

		self.client_poop = PoopHandshakeClientProtocol()
		self.server_poop = PoopHandshakeServerProtocol()

		self.client = DummyApplication()
		self.server = DummyApplication()

		self.client_poop.setHigherProtocol(self.client)
		self.server_poop.setHigherProtocol(self.server)

		self.client_write_storage = []
		self.server_write_storage = []

		self.client_transport = MockTransport(ListWriter(self.client_write_storage))
		self.server_transport = MockTransport(ListWriter(self.server_write_storage))

		self.server_poop.connection_made(self.server_transport)
		self.client_poop.connection_made(self.client_transport)

		self.assertEqual(self.client._connection_made_called, 0)
		self.assertEqual(self.server._connection_made_called, 0)

		# there should only be 1 blob of bytes for the SYN
		# self.assertEqual(len(self.client_write_storage), 1)
		self.server_poop.data_received(self.client_write_storage.pop())

		# server still should not be connected
		# self.assertEqual(self.server._connection_made_called, 0)

		# there should be 1 blob of bytes from the server for the SYN ACK
		# self.assertEqual(len(self.server_write_storage), 1)

		self.client_poop.data_received(self.server_write_storage.pop())

		# now client should be connected
		# self.assertEqual(self.client._connection_made_called, 1)

		# there should be 1 blob of bytes for the SYN ACK ACK storage
		# self.assertEqual(len(self.client_write_storage), 1)
		self.server_poop.data_received(self.client_write_storage.pop())

		# server should be connected
		# self.assertEqual(self.server._connection_made_called, 1)

	def test_server_inits_shutdown(self):
		# server application initiates the shutdown sequence
		self.server._transport.close()
		self.assertEqual(self.server._connection_lost_called, 0)

		# the poop server should write a fin packet
		self.assertEqual(len(self.server_write_storage), 1)
		finpkt = self.server_write_storage.pop()
		self.deserializer.update(finpkt)
		for pkt in self.deserializer.nextPackets():
			print(pkt.DEFINITION_IDENTIFIER)
			self.assertTrue(isinstance(pkt, ShutdownPacket))

		# the poop client should receive a fin packet and write a fin/ack packet
		self.client_poop.data_received(finpkt) # connection_lost should be called here
		self.assertEqual(len(self.client_write_storage), 1)
		finackpkt = self.client_write_storage.pop()
		self.deserializer.update(finpkt)
		for pkt in self.deserializer.nextPackets():
			print(pkt.DEFINITION_IDENTIFIER)
			self.assertTrue(isinstance(pkt, ShutdownPacket))

		# the client connection should be terminated
		self.assertEqual(self.client._connection_lost_called, 1)

		# the poop server should receive a fin/ack packet, and terminate the connection
		self.server_poop.data_received(finackpkt)
		self.assertEqual(self.server._connection_lost_called, 1)

	def test_client_inits_shutdown(self):
		# client application initiates the shutdown sequence
		self.client._transport.close()
		self.assertEqual(self.client._connection_lost_called, 0)

		# the poop client should write a fin packet
		self.assertEqual(len(self.client_write_storage), 1)
		finpkt = self.client_write_storage.pop()
		self.deserializer.update(finpkt)
		for pkt in self.deserializer.nextPackets():
			print(pkt.DEFINITION_IDENTIFIER)
			self.assertTrue(isinstance(pkt, ShutdownPacket))

		# the poop server should receive a fin packet and write a fin/ack packet
		self.server_poop.data_received(finpkt) # connection_lost should be called here
		self.assertEqual(len(self.server_write_storage), 1)
		finackpkt = self.server_write_storage.pop()
		self.deserializer.update(finpkt)
		for pkt in self.deserializer.nextPackets():
			print(pkt.DEFINITION_IDENTIFIER)
			self.assertTrue(isinstance(pkt, ShutdownPacket))

		# the server connection should be terminated
		self.assertEqual(self.server._connection_lost_called, 1)

		# the poop client should receive a fin/ack packet, and terminate the connection
		self.client_poop.data_received(finackpkt)
		self.assertEqual(self.client._connection_lost_called, 1)


        
    
        
if __name__ == '__main__':
    EnablePresetLogging(PRESET_DEBUG)
    unittest.main()