# Scrip de teste do Servidor RDT-UnB
#  
# executar:  python3 teste_rdt_unb.py 
# A saída esperada deve ser algo como: 
''' ------
HELLO: OK|file_size=1048576|checksum=f5adc7ebd10d3997cfa18c8a73a7f9
DATA seq=0: 533 bytes
DATA seq=1: 31 bytes
Servidor OK
'''

import socket, time

srv = ('137.131.178.229', 8080)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(5)

# HELLO
s.sendto(b'HELLO|grupo=teste|segment_size=512|file=small', srv)
ok = s.recvfrom(65507)[0].decode()
print('HELLO:', ok[:60])

# REQ seg 0
s.sendto(b'REQ|seq=0', srv)
data = s.recvfrom(65507)[0]
print('DATA seq=0:', len(data), 'bytes')

# ACK e REQ seg 1
s.sendto(b'ACK|seq=0', srv)
s.sendto(b'REQ|seq=1', srv)
data2 = s.recvfrom(65507)[0]
print('DATA seq=1:', len(data2), 'bytes')

print('Servidor OK')
s.close()