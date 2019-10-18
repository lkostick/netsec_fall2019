import playground
from .protocol import HandshakeClientFactory, HandshakeServerFactory

poopConnector = playground.Connector(protocolStack=(
    HandshakeClientFactory(),
    HandshakeServerFactory()))
playground.setConnector("handshake", poopConnector)
playground.setConnector("POOP", poopConnector)
playground.setConnector("poop", poopConnector)
