#!/usr/bin/env python3
import sys
import base64
from collections import namedtuple

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

def parse_scari_pspls_data_segment(base64_string):
    try: raw_bytes = base64.b64decode(base64_string)
    except: return None

    chigh = 0
    cstep = 0.046875 # dB
    clow = chigh - 4096.0 * cstep # dB

    # number of percentiles
    K = 5

    # number of decidecade bands
    D = (len(raw_bytes) * 2) // (3 * K)

    # extract number between 0 and 4095 inclusive from packed bytes, scale and shift
    tmp = [unpack_three_nibbles(raw_bytes, 3 * id) * cstep + clow for id in range(D * K)]

    # reshape into length-D list of length-K lists
    reshaped = [tmp[i:(i + K)] for i in range(0, K * D, K)]
    return reshaped

def parse_scari_pspls(line):
    if not line.startswith('$PSPLS,'):
        return None

    try: payload, suffix = line[1:].split('*')
    except: return None

    if not validate_nmea(payload, suffix):
        return None

    try: prefix, dt_text, dt_report_text, iband_start_text, base64_string = payload.split(',')
    except: return None

    spl_percentiles_dB = parse_scari_pspls_data_segment(base64_string)
    if spl_percentiles_dB is None: return None

    pspls_tuple = namedtuple('pspls_tuple', [ 'spl_percentiles_dB', 'iband_start', 'dt', 'dt_report' ])
    return pspls_tuple(spl_percentiles_dB = spl_percentiles_dB,
                       iband_start = int(iband_start_text),
                       dt = float(dt_text),
                       dt_report = float(dt_report_text))

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
