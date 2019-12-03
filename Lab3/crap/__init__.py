import playground
from .protocol import CrapProtocol
from .poop.protocol import PoopHandshakeClientProtocol, PoopHandshakeServerProtocol
from playground.network.common import StackingProtocolFactory

ClientFactory = StackingProtocolFactory.CreateFactoryType(PoopHandshakeClientProtocol, lambda: CrapProtocol(mode="client"))
ServerFactory = StackingProtocolFactory.CreateFactoryType(PoopHandshakeServerProtocol, lambda: CrapProtocol(mode="server"))


Connector = playground.Connector(protocolStack=(
    ClientFactory(),
    ServerFactory()))
playground.setConnector("crap", Connector)
playground.setConnector("CRAP", Connector)
