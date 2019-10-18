import playground
from .protocol import HandshakeClientFactory, HandshakeServerFactory

passthroughConnector = playground.Connector(protocolStack=(
    HandshakeClientFactory(),
    HandshakeServerFactory()))
playground.setConnector("handshake", passthroughConnector)
