from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

test_key = bytes.fromhex('00112233445566778899AABBCCDDEEFF')



aesCipher = Cipher(algorithms.AES(test_key), modes.ECB(), backend=default_backend())

aesEnc = aesCipher.encryptor()
aesDec = aesCipher.decryptor()

import sys

with open(sys.argv[1], 'rb') as f:
	img = f.read()
	header = img[:54]
	img = img[54:]


rem = len(img) % 16

padding = b'0' * (16 - rem)

img += padding

with open("enc_ts.bmp", 'wb') as f:
	f.write(header + aesEnc.update(img))