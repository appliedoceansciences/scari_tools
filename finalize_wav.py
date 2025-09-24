#!/usr/bin/env python3

# copyright 2024- applied ocean sciences
# isc license
# point of contact: richard campbell

import sys
import struct
import os

f = open(sys.argv[1], 'r+b')

riff, filesize_minus_eight_bytes, wave = struct.unpack('4sI4s', f.read(12))
if riff != b'RIFF' or wave != b'WAVE': exit(1)

f.truncate(filesize_minus_eight_bytes + 8)
f.close()

os.rename(sys.argv[1], os.path.splitext(sys.argv[1])[0] + '.wav')
