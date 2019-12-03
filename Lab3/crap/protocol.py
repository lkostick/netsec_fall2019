import datetime

from playground.network.common import StackingProtocol, StackingTransport
from playground.network.packet import PacketType, FIELD_NOT_SET
from cryptography.x509.oid import NameOID
import logging
import random
from .packets import *
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
import os
from cryptography.hazmat.primitives.serialization import PublicFormat, PrivateFormat, NoEncryption, Encoding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography import x509
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger("playground.__connector__." + __name__)

SIGNING_KEY_SIZE = 2048
NONCE_SIZE = 30
PLAYGROUND_ADDRESS = "20194.1.1.200"

def generate_nonce():
    return random.randint(0, 2**NONCE_SIZE)


def is_set(*fields):
    for field in fields:
        if field == FIELD_NOT_SET:
            return False
    return True


def not_set(*fields):
    for field in fields:
        if is_set(field):
            return False
    return True


def serialize_public(key):
    return key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)


def deserialize_public(key_bytes):
    return serialization.load_pem_public_key(key_bytes, backend=default_backend())


def serialize_private(key):
    return key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption())


def deserialize_private(key_bytes):
    return serialization.load_pem_private_key(key_bytes, password=None, backend=default_backend())


def serialize_cert(cert):
    return cert.public_bytes(Encoding.PEM)


def deserialize_cert(cert_bytes):
    return x509.load_pem_x509_certificate(cert_bytes, default_backend())


def increment_large_binary(large_binary):
    large_int = int.from_bytes(large_binary, "big")
    large_int += 1
    return large_int.to_bytes(12, "big")


class CrapTransport(StackingTransport):

    def __init__(self, transport, mode, protocol):
        super().__init__(transport)
        self.mode = mode
        self.protocol = protocol
        self.self_IV = None
        self.other_side_IV = None
        self.enc_key = None
        self.dec_key = None

    def assign_gcm_values(self):
        logger.debug('CRAP: {} side assigning gcm ivs and keys'.format(self.mode))
        shared_key = self.protocol.shared_key
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(shared_key)
        hash1 = digest.finalize()

        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(hash1)
        hash2 = digest.finalize()

        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(hash2)
        hash3 = digest.finalize()

        if self.mode == "client":
            self.self_IV = hash1[:12]
            self.other_side_IV = hash1[12:24]
            self.enc_key = hash2[:16]
            self.dec_key = hash3[:16]
        else:
            self.other_side_IV = hash1[:12]
            self.self_IV = hash1[12:24]
            self.dec_key = hash2[:16]
            self.enc_key = hash3[:16]

        logger.debug('CRAP: {} side gcm values created. Info:\n'
                     'self IV: {}\n'
                     'other side IV: {}\n'
                     'enc key: {}\n'
                     'dec key: {}\n'.format(self.mode, self.self_IV, self.other_side_IV, self.enc_key, self.dec_key))

    def write(self, data):
        logger.debug('CRAP: {} side transport.write() data of len {}'.format(self.mode, len(data)))

        aes_gcm = AESGCM(self.enc_key)

        logger.debug('CRAP: {} side Encrypting the data received from higher layer: {}\n'.format(self.mode, data))
        encrypted_data = aes_gcm.encrypt(self.self_IV, data, None)

        logger.debug('CRAP: {} side incrementing self_IV by one from {} to {}'.format(self.mode, self.self_IV, increment_large_binary(self.self_IV)))
        self.self_IV = increment_large_binary(self.self_IV)

        packet = DataPacket(data=encrypted_data)
        packet_bytes = packet.__serialize__()
        logger.debug('CRAP: {} side sending data packet. Info:\n'
                     'data: {}\n'.format(self.mode, packet.data))
        self.lowerTransport().write(packet_bytes)


class CrapProtocol(StackingProtocol):

    def __init__(self, mode):
        super().__init__()
        self.shared_key = None
        self.mode = mode
        self.deserializer = CrapPacketType.Deserializer()
        self.handshakeComplete = False
        self.higher_transport = None

        # Private Key
        self.private_key = ec.generate_private_key(ec.SECP384R1(), default_backend())
        self.private_key_bytes = serialize_private(self.private_key)

        # Public Key
        self.public_key = self.private_key.public_key()
        self.public_key_bytes = serialize_public(self.public_key)

        # Nonce
        self.nonce = generate_nonce()
        self.nonce_bytes = str(self.nonce).encode()


        #cert

        self.signing_key, self.cert = self.generate_cert(PLAYGROUND_ADDRESS)
        self.cert_bytes = serialize_cert(self.cert)
        self.signing_key_bytes = serialize_private(self.signing_key)

    def generate_cert(self, common_name):
        logger.debug('CRAP: {} side generating a signed certificate for common name: {}\n'.format(self.mode, common_name))

        self.check_common_name(common_name)

        logger.debug(
            'CRAP: {} side reading signed certificate.\n'.format(self.mode))
        with open('team1csr_signed.cert', 'rb') as f:
            signer_cert_bytes = f.read()
            signer_cert = deserialize_cert(signer_cert_bytes)

        # In the cert chain, the subject of first, is the issuer of second
        logger.debug(
            'CRAP: {} putting new cert\n'.format(self.mode))
        issuer = signer_cert.subject

        with open('team1key.key', 'rb') as f:
            signing_key_bytes = f.read()
            signing_key = deserialize_private(signing_key_bytes)

        # common_name should be unicode like u"20194.1.something.something"
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Maryland"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, u"Baltimore"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"jhu"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name)
        ])
        cert = x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(
            signing_key.public_key()).serial_number(x509.random_serial_number()
                                                         ).not_valid_before(datetime.datetime.utcnow()).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=10)).add_extension(
            x509.SubjectAlternativeName([x509.DNSName(u"localhost")]), critical=False, ).sign(signing_key,
                                                                                              hashes.SHA256(),
                                                                                              default_backend())
        return signing_key, cert

    def check_common_name(self, common_name):
        logger.debug('CRAP: {} side checking common name: {}\n'.format(self.mode, common_name))
        if not isinstance(common_name, str):
            logger.debug('CRAP: {} side common name not string!\n'.format(self.mode))
            raise Exception('common name not string!')
        try:
            splited_common_name = common_name.split('.')
        except:
            logger.debug('CRAP: {} side common name could not be splited by . !\n'.format(self.mode))
            raise Exception('common name could not be splited by . !')

        if len(splited_common_name) != 4:
            logger.debug('CRAP: {} side something is wrong with this common name!\n'.format(self.mode))
            raise Exception('something is wrong with this common name!')

        try:
            int(splited_common_name[2])
            int(splited_common_name[3])
        except:
            logger.debug('CRAP: {} side not int values in common name!\n'.format(self.mode))
            raise Exception('not int values in common name!')

    def verify_common_name(self, cert):
        expected_common_name = self.transport.get_extra_info("peername")[0]
        common_name = None
        subject = cert.subject.rfc4514_string()
        subject = subject.split(',')
        for i in subject:
            if 'CN=' in i:
                common_name = i.split('CN=')[1]
                break

        logger.debug('CRAP: {} side verifying common name: {} == {}\n'.format(self.mode, common_name, expected_common_name))
        self.check_common_name(common_name)
        if expected_common_name == common_name:
            logger.debug('CRAP: {} common name verified\n'.format(self.mode))
            return True
        logger.debug('CRAP: {} common name not verified\n'.format(self.mode))
        return False

    def connection_made(self, transport):
        logger.debug('CRAP: {} side connection made\n'.format(self.mode))
        self.transport = transport
        if self.mode == 'client':
            signature = self.signing_key.sign(self.public_key_bytes, padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                                              salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())

            with open('team1csr_signed.cert', 'rb') as f:
                signer_cert_bytes = f.read()

            cert_chain = [signer_cert_bytes]

            packet = HandshakePacket(status=HandshakePacket.NOT_STARTED, pk=self.public_key_bytes, signature=signature, cert=self.cert_bytes, nonce=self.nonce, certChain=cert_chain)
            packet_bytes = packet.__serialize__()
            logger.debug('CRAP: {} side sending handshake packet. Info:\n'
                         'status: {}\n'
                         'pk: {}\n'
                         'signature: {}\n'
                         'cert: {}\n'
                         'nonce: {}\n'
                         'nonce_signature: {}\n'
                         'cert_chain: {}\n'.format(self.mode, packet.status, packet.pk, packet.signature, packet.cert, packet.nonce, packet.nonceSignature, packet.certChain))
            self.transport.write(packet_bytes)

    def handle_handshake_error(self):
        self.handshakeComplete = False

    def verify_chain_of_trust(self, cert, cert_chain):
        cert_list = [cert]

        for i in cert_chain:
            cert = deserialize_cert(i)
            cert_list.append(cert)

        with open('20194_root.cert', 'rb') as f:
            cert_bytes = f.read()
            cert = deserialize_cert(cert_bytes)
            cert_list.append(cert)

        for i in range(len(cert_list) - 1):
            cert = cert_list[i]
            parent_cert = cert_list[i+1]
            issuer = cert.issuer.rfc4514_string()
            subject = parent_cert.subject.rfc4514_string()
            logger.debug("CRAP: {} side for verifying the chain of trust is checking if {} == {}".format(self.mode, issuer, subject))
            if issuer != subject:
                return False
        return True

    def data_received(self, data):
        logger.debug("CRAP: {} side received a data of size {}".format(self.mode, len(data)))
        self.deserializer.update(data)
        if self.handshakeComplete:
            for packet in self.deserializer.nextPackets():
                if isinstance(packet, DataPacket):
                    logger.debug('CRAP: {} side received data packet. Info:\n'
                                 'data: {}\n'.format(self.mode, packet.data))

                    logger.debug('CRAP: {} side decrypting data.\n'.format(self.mode))
                    aes_gcm = AESGCM(self.higher_transport.dec_key)
                    decrypted_data = aes_gcm.decrypt(self.higher_transport.other_side_IV, packet.data, None)
                    logger.debug('CRAP: {} side decrypted data is: {}\n'.format(self.mode, decrypted_data))

                    logger.debug(
                        'CRAP: {} side incrementing other_side_IV by one from {} to {}'.format(self.mode, self.higher_transport.other_side_IV,
                                                                                         increment_large_binary(
                                                                                             self.higher_transport.other_side_IV)))
                    self.higher_transport.other_side_IV = increment_large_binary(self.higher_transport.other_side_IV)

                    logger.debug('CRAP: {} sending decrypted data to higher protocol, data: {}\n'.format(self.mode, decrypted_data))
                    self.higherProtocol().data_received(decrypted_data)

                elif isinstance(packet, ErrorPacket):
                    logger.debug('CRAP: {} side received error packet. Info:\n'
                                 'data: {}\n'.format(self.mode, packet.message))

                else:
                    logger.debug('CRAP: {} side expected data/error got something else: ignore'.format(self.mode))


        else:
            # handshake
            for packet in self.deserializer.nextPackets():
                if isinstance(packet, HandshakePacket):
                    logger.debug('CRAP: {} side received handshake packet. Info:\n'
                                 'status: {}\n'
                                 'pk: {}\n'
                                 'signature: {}\n'
                                 'cert: {}\n'
                                 'nonce: {}\n'
                                 'nonce_signature: {}\n'
                                 'cert chain: {}\n'.format(self.mode, packet.status, packet.pk, packet.signature, packet.cert, packet.nonce, packet.nonceSignature, packet.certChain))
                    if packet.status == HandshakePacket.NOT_STARTED:
                        try:
                            cert = deserialize_cert(packet.cert)
                            logger.debug('CRAP: {} side verifying certificate common_name!\n'.format(self.mode))
                            self.verify_common_name(cert)
                            logger.debug('CRAP: {} side certificate common name verified!\n'.format(self.mode))

                            logger.debug('CRAP: {} side verifying certificate chain of trust!\n'.format(self.mode))
                            self.verify_chain_of_trust(cert, packet.certChain)
                            logger.debug('CRAP: {} side chain of trust verified!\n'.format(self.mode))

                            logger.debug('CRAP: {} side verifying signature received from other side!\n'.format(self.mode))
                            verification_key = cert.public_key()
                            verification_key.verify(packet.signature, packet.pk, padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                                              salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
                            logger.debug('CRAP: {} side signature verified!\n'.format(self.mode))

                            logger.debug('CRAP: {} side creating shared key\n'.format(self.mode))
                            self.shared_key = self.private_key.exchange(ec.ECDH(), deserialize_public(packet.pk))

                            logger.debug('CRAP: {} side signing the sent nonce with signature key\n'.format(self.mode))
                            nonce_bytes = str(packet.nonce).encode()
                            nonce_signature = self.signing_key.sign(nonce_bytes, padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                                              salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())

                            logger.debug('CRAP: {} side creating signature\n'.format(self.mode))
                            signature = self.signing_key.sign(self.public_key_bytes, padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                                              salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())

                            with open('team1csr_signed.cert', 'rb') as f:
                                signer_cert_bytes = f.read()

                            cert_chain = [signer_cert_bytes]

                            packet = HandshakePacket(status=HandshakePacket.SUCCESS, pk=self.public_key_bytes, signature=signature, cert=self.cert_bytes, nonce=self.nonce, nonceSignature=nonce_signature, certChain=cert_chain)
                            packet_bytes = packet.__serialize__()
                            logger.debug('CRAP: {} side sending handshake packet. Info:\n'
                                         'status: {}\n'
                                         'pk: {}\n'
                                         'signature: {}\n'
                                         'cert: {}\n'
                                         'nonce: {}\n'
                                         'nonce_signature: {}\n'
                                         'cert chain: {}'.format(self.mode, packet.status, packet.pk, packet.signature, packet.cert, packet.nonce, packet.nonceSignature, packet.certChain))
                            self.transport.write(packet_bytes)
                        except:
                            error = 'Verification failed!'
                            logger.debug('CRAP: {} side encountered error: {}\n'.format(self.mode, error))
                            self.handle_handshake_error()
                            packet = HandshakePacket(status=HandshakePacket.ERROR)
                            packet_bytes = packet.__serialize__()
                            logger.debug('CRAP: {} side sending handshake packet. Info:\n'
                                         'status: {}\n'
                                         'pk: {}\n'
                                         'signature: {}\n'
                                         'cert: {}\n'
                                         'nonce: {}\n'
                                         'nonce_signature: {}\n'
                                         'cert chain: {}\n'.format(self.mode, packet.status, packet.pk, packet.signature,
                                                             packet.cert, packet.nonce, packet.nonceSignature, packet.certChain))
                            self.transport.write(packet_bytes)

                            self.connection_lost()

                    elif packet.status == HandshakePacket.SUCCESS:
                        if not_set(packet.pk, packet.nonce, packet.signature) and is_set(packet.nonceSignature, packet.cert):
                            try:
                                cert = deserialize_cert(packet.cert)
                                verification_key = cert.public_key()
                                logger.debug('CRAP: {} side verifying nonce signature received from other side!\n'.format(self.mode))
                                verification_key.verify(packet.nonceSignature, self.nonce_bytes,
                                                        padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                                                    salt_length=padding.PSS.MAX_LENGTH),
                                                        hashes.SHA256())
                                logger.debug('CRAP: {} side nonce signature verified!\n'.format(self.mode))
                                self.handshakeComplete = True
                                logger.debug(
                                    'CRAP: {} set handshakeComplete to True'.format(self.mode))
                                higher_transport = CrapTransport(self.transport, mode=self.mode, protocol=self)
                                higher_transport.assign_gcm_values()
                                self.higher_transport = higher_transport
                                logger.debug('Crap: {} side calling self.higherProtocol().connection_made()'.format(self.mode))
                                self.higherProtocol().connection_made(higher_transport)
                            except:
                                logger.debug(
                                    'CRAP: {} verifying nonce failed'.format(self.mode))
                                self.connection_lost()
                        elif is_set(packet.pk, packet.cert, packet.signature, packet.nonce, packet.nonceSignature):
                            try:
                                cert = deserialize_cert(packet.cert)
                                logger.debug('CRAP: {} side verifying certificate common_name!\n'.format(self.mode))
                                self.verify_common_name(cert)
                                logger.debug('CRAP: {} side certificate common name verified!\n'.format(self.mode))

                                logger.debug('CRAP: {} side verifying certificate chain of trust!\n'.format(self.mode))
                                self.verify_chain_of_trust(cert, packet.certChain)
                                logger.debug('CRAP: {} side chain of trust verified!\n'.format(self.mode))

                                logger.debug('CRAP: {} side verifying signature received from other side!\n'.format(self.mode))
                                verification_key = cert.public_key()
                                verification_key.verify(packet.signature, packet.pk,
                                                        padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                                                    salt_length=padding.PSS.MAX_LENGTH),
                                                        hashes.SHA256())
                                logger.debug('CRAP: {} side signature verified!\n'.format(self.mode))

                                logger.debug('CRAP: {} side verifying nonce signature received from other side!\n'.format(self.mode))
                                verification_key.verify(packet.nonceSignature, self.nonce_bytes,
                                                        padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                                                    salt_length=padding.PSS.MAX_LENGTH),
                                                        hashes.SHA256())
                                logger.debug('CRAP: {} side nonce signature verified!\n'.format(self.mode))

                                logger.debug('CRAP: {} side creating shared key\n'.format(self.mode))
                                self.shared_key = self.private_key.exchange(ec.ECDH(), deserialize_public(packet.pk))

                                logger.debug(
                                    'CRAP: {} side signing the sent nonce with signature key\n'.format(self.mode))
                                nonce_bytes = str(packet.nonce).encode()
                                nonce_signature = self.signing_key.sign(nonce_bytes, padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                                              salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())

                                self.handshakeComplete = True
                                logger.debug(
                                    'CRAP: {} set handshakeComplete to True'.format(self.mode))

                                packet = HandshakePacket(status=HandshakePacket.SUCCESS, nonceSignature=nonce_signature,
                                                         cert=self.cert_bytes)
                                packet_bytes = packet.__serialize__()
                                logger.debug('CRAP: {} side sending handshake packet. Info:\n'
                                             'status: {}\n'
                                             'pk: {}\n'
                                             'signature: {}\n'
                                             'cert: {}\n'
                                             'nonce: {}\n'
                                             'nonce_signature: {}\n'
                                             'cert chain: {}'.format(self.mode, packet.status, packet.pk,
                                                                     packet.signature, packet.cert, packet.nonce,
                                                                     packet.nonceSignature, packet.certChain))

                                self.transport.write(packet_bytes)

                                higher_transport = CrapTransport(self.transport, mode=self.mode, protocol=self)
                                higher_transport.assign_gcm_values()
                                self.higher_transport = higher_transport
                                logger.debug(
                                    'Crap: {} side calling self.higherProtocol().connection_made()'.format(self.mode))
                                self.higherProtocol().connection_made(higher_transport)



                            except:
                                error = 'Verification failed!'
                                logger.debug('CRAP: {} side encountered error: {}\n'.format(self.mode, error))
                                self.handle_handshake_error()
                                packet = HandshakePacket(status=HandshakePacket.ERROR)
                                packet_bytes = packet.__serialize__()
                                logger.debug('CRAP: {} side sending handshake packet. Info:\n'
                                             'status: {}\n'
                                             'pk: {}\n'
                                             'signature: {}\n'
                                             'cert: {}\n'
                                             'nonce: {}\n'
                                             'nonce_signature: {}\n'
                                             'cert chain: {}'.format(self.mode, packet.status, packet.pk, packet.signature, packet.cert, packet.nonce, packet.nonceSignature, packet.certChain))
                                self.transport.write(packet_bytes)

                                self.connection_lost()
                        else:
                            error = 'handshake fields does not match!'
                            logger.debug('CRAP: {} side encountered error: {}\n'.format(self.mode, error))
                            self.handle_handshake_error()

                            self.connection_lost()
                    elif packet.status == HandshakePacket.ERROR:
                        # Error detected on the other side
                        error = 'an error reported from the other side'
                        logger.debug('CRAP: {} side encountered error: {}\n'.format(self.mode, error))
                        self.handle_handshake_error()

                        self.connection_lost()
                    else:
                        self.handle_handshake_error()

                        self.connection_lost()

                elif isinstance(packet, ErrorPacket):
                    logger.debug('CRAP: {} side received error packet. Info:\n'
                                 'data: {}\n'.format(self.mode, packet.message))

                else:
                    error = 'Expected handshake/error packet and got s.th else!'
                    logger.debug('CRAP: {} side encountered error: {}\n'.format(self.mode, error))
                    self.handle_handshake_error()

    def connection_lost(self, exc=None):
        logger.debug('CRAP: {} connection_lost called\n'.format(self.mode))
        self.higherProtocol().connection_lost(exc)

# all tests passed for test_id 40d20d0cec714691a1a9567d5570db599c91259a0ece703ff8b7b2e4d1061340