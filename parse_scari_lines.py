#!/usr/bin/env python3
import sys
import base64
from collections import namedtuple
import numpy as np
nmea_checksum_errors = 0

def unpack_nibble(bytes, inibble_abs):
    ibyte = inibble_abs // 2
    inibble = inibble_abs % 2
    return (int)(bytes[ibyte] >> (4 * inibble)) & 0xF

def unpack_three_nibbles(bytes, inibble_abs):
    return (unpack_nibble(bytes, inibble_abs + 0) << 0 |
            unpack_nibble(bytes, inibble_abs + 1) << 4 |
            unpack_nibble(bytes, inibble_abs + 2) << 8)

def validate_nmea(payload, suffix):
    global nmea_checksum_errors
    checksum = 0
    for byte in payload:
        checksum ^= ord(byte)

    if int(suffix, 16) != checksum:
        nmea_checksum_errors += 1
        print('nmea checksum errors: %u' % nmea_checksum_errors, file=sys.stderr)
        return False
    return True

def parse_scari_pspl_data_segment(base64_string):
    try: raw_bytes = base64.b64decode(base64_string)
    except: return None

    chigh = 0
    cstep = 0.046875 # dB
    clow = chigh - 4096.0 * cstep # dB

    # number of decidecade bands
    D = (len(raw_bytes) * 2) // 3

    # extract number between 0 and 4095 inclusive from packed bytes, scale and shift
    spls_dB = [unpack_three_nibbles(raw_bytes, 3 * id) * cstep + clow for id in range(D)]
    return spls_dB

def parse_scari_pspl(line):
    if not line.startswith('$PSPL,'): return None

    try: payload, suffix = line[1:].split('*')
    except: return None

    if not validate_nmea(payload, suffix): return None

    try: prefix, dt_text, iband_start_text, base64_string = payload.split(',')
    except: return None

    spls_dB = parse_scari_pspl_data_segment(base64_string)
    if spls_dB is None: return None

    pspl_tuple = namedtuple('pspl_tuple', [ 'spls_dB', 'iband_start', 'dt' ])
    return pspl_tuple(spls_dB = spls_dB,
                      iband_start = int(iband_start_text),
                      dt=float(dt_text))

def parse_scari_pgram(line):
    if not '$PGRAM,' in line: return None

    try: payload, suffix = line[1:].split('*')
    except: return None

    if not validate_nmea(payload, suffix): return None

    try:
        prefix, dt_text, df_text, bins_per_octave_text, encoded_pixels = payload.split(',')
        pixels = base64.b64decode(encoded_pixels)
    except: return None

    chigh = 0
    cstep = 0.75
    clow = chigh - 256.0 * cstep

    pgram_tuple = namedtuple('pgram_tuple', [ 'spl_dB', 'df', 'bins_per_octave', 'dt' ])

    return pgram_tuple(spl_dB = [q * cstep + clow for q in pixels],
                       df = float(df_text),
                       dt = float(dt_text),
                       bins_per_octave = float(bins_per_octave_text))

if __name__ == '__main__':
    for line in sys.stdin:
        line = line.rstrip()
        np.savetxt(sys.stdout, np.expand_dims(parse_scari_pspl(line).spls_dB, axis=0), delimiter=',', fmt='%.2f')
