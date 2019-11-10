from OpenSSL import crypto, SSL
from os.path import join
import random
import os
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


os.system('openssl req -x509 -sha256 -nodes -days 365 -newkey rsa:2048 -keyout privateKey.pem -out certificate.pem')
os.system('openssl x509 -in certificate.pem -noout -pubkey > publicKey.pem')

parameters = dh.generate_parameters(generator=2, key_size=512, backend=default_backend())

dhPrivateKey = parameters.generate_private_key()
dhPublicKey = dhPrivateKey.public_key()

#b_private_key = parameters.generate_private_key()
#b_peer_public_key = b_private_key.public_key()

#a_shared_key = a_private_key.exchange(b_peer_public_key)
#b_shared_key = b_private_key.exchange(a_peer_public_key)

#print 'a_secret: '+dhPublicKey
#print 'b_secret: '+b_shared_key

# Load certificate
cert_file = open('certificate.pem', 'r')
cert = cert_file.read()
cert_file.close()
cert = x509.load_pem_x509_certificate(cert, default_backend())
print(cert.public_key())

# Load private signing key
key_file = open('privateKey.pem', 'r')
key_from_file = key_file.read()
key_file.close()
signingKey = crypto.load_privatekey(crypto.FILETYPE_PEM, key_from_file)
print(signingKey)

# Load public verification key
key_file = open('publicKey.pem', 'r')
key_from_file = key_file.read()
key_file.close()
verificationKey = crypto.load_publickey(crypto.FILETYPE_PEM, key_from_file)
signature = crypto.sign(signingKey, str(dhPublicKey), 'sha256')
try:
    crypto.verify(verificationKey, signature, str(dhPublicKey), 'sha256')
    print("VERIFIED")
except crypto.Error:
    print("BOOOO")