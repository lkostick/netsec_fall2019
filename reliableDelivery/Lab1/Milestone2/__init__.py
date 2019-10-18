import playground
from .protocol import PoopHandshakeClientFactory, PoopHandshakeServerFactory

poopConnector = playground.Connector(protocolStack=(
    PoopHandshakeClientFactory(),
    PoopHandshakeServerFactory()))
playground.setConnector("handshake", poopConnector)
playground.setConnector("poop", poopConnector)
playground.setConnector("POOP", poopConnector)
