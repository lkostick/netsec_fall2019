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
print('Client Bank Addr: ' + str(bank_addr))
bank_port = int(bankconfig.get_parameter("CLIENT", "bank_port"))
print('Client Bank Port: ' + str(bank_port))
bank_stack     =     bankconfig.get_parameter("CLIENT", "stack","default")
# bank_username  =     bankconfig.get_parameter("CLIENT", "username")
