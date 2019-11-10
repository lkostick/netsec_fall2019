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

# This variable needs to be sent to the Server so they know how to generate their keys
parameters = dh.generate_parameters(generator=2, key_size=512, backend=default_backend())


### CLIENT SIDE ###
os.system('openssl req -x509 -sha256 -nodes -days 365 -newkey rsa:2048 -keyout clientPrivateKey.pem -out clientCertificate.pem')

dhPrivateKeyClient = parameters.generate_private_key()
dhPublicKeyClient = dhPrivateKeyClient.public_key()

# Load certificate
cert_file = open('clientCertificate.pem', 'r')
cert = cert_file.read()
cert_file.close()
cert = x509.load_pem_x509_certificate(cert, default_backend())

# Load private signing key
key_file = open('clientPrivateKey.pem', 'r')
key_from_file = key_file.read()
key_file.close()
signingKey = crypto.load_privatekey(crypto.FILETYPE_PEM, key_from_file)

# Sign the DH parameter
signature = crypto.sign(signingKey, str(dhPublicKeyClient), 'sha256')

# Verify that the signature is valid (This is on the Server side)
try:
    crypto.verify(cert, signature, str(dhPublicKeyClient), 'sha256')
    print("VERIFIED")
except crypto.Error:
    print("BOOOO")

### SERVER SIDE ###
os.system('openssl req -x509 -sha256 -nodes -days 365 -newkey rsa:2048 -keyout serverPrivateKey.pem -out serverCertificate.pem')

dhPrivateKeyServer = parameters.generate_private_key()
dhPublicKeyServer = dhPrivateKeyServer.public_key()

# Load certificate
cert_file = open('serverCertificate.pem', 'r')
cert = cert_file.read()
cert_file.close()
cert = x509.load_pem_x509_certificate(cert, default_backend())

# Load private signing key
key_file = open('serverPrivateKey.pem', 'r')
key_from_file = key_file.read()
key_file.close()
signingKey = crypto.load_privatekey(crypto.FILETYPE_PEM, key_from_file)

# Sign the DH parameter
signature = crypto.sign(signingKey, str(dhPublicKeyServer), 'sha256')

# Verify that the signature is valid (This is on the Client side)
try:
    crypto.verify(cert, signature, str(dhPublicKeyServer), 'sha256')
    print("VERIFIED")
except crypto.Error:
    print("BOOOO")

### BOTH SIDES ###

clientSharedSecret = dhPrivateKeyClient.exchange(dhPublicKeyServer)
serverSharedSecret = dhPrivateKeyServer.exchange(dhPublicKeyClient)

print("Shared Secrets are equal: " + str(clientSharedSecret == serverSharedSecret))
print("Client Shared Secret: " + clientSharedSecret)
print("Server Shared Secret: " + serverSharedSecret)