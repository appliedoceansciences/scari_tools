#!/usr/bin/env python3
import sys
import base64
import json
import math
from datetime import datetime, timestamp
import numpy as np

def datestr_from_unix_microseconds(microseconds):
    integer_portion = microseconds // 1000000
    remainder = microseconds % 1000000
    return '%s.%06uZ' % (datetime.fromtimestamp(integer_portion, timestamp.utc).strftime('%Y%m%dT%H%M%S'), remainder)

def bin_index_given_frequency(frequency, df, bins_per_octave):
    linear_bins_from_dc = math.ceil(bins_per_octave / math.log(2))
    linear_index_from_dc = frequency / df

    if linear_index_from_dc < linear_bins_from_dc:
        return linear_index_from_dc - 2
    else:
        return linear_bins_from_dc - 2 + math.log2(linear_index_from_dc / linear_bins_from_dc) * bins_per_octave

def main():
    full_scale = 0
    desired_bin_frequency = None

    # loop over pairs of arguments
    for key, value in zip(sys.argv[1::2], sys.argv[2::2]):
        if key == 'full_scale': full_scale = float(value)
        if key == 'freq': desired_bin_frequency = float(value)

    for line in sys.stdin:
        try: message = json.loads(line)
        except: continue

        if not 'pgram' in message: continue

        if 'pgram' in message and not 'b' in message:
            try: pixels = base64.b64decode(message['pgram'])
            except: continue

            df = float(message['df'])
            bins_per_octave = int(message['bins_per_octave'])

            chigh = 0
            cstep = 0.75
            clow = chigh - 256.0 * cstep

            spl_dB = np.frombuffer(pixels, dtype=np.uint8) * cstep + clow + full_scale

            if desired_bin_frequency is not None:
                print('%s, %.1f' % (datestr_from_unix_microseconds(float(message['time']) * 1e6), spl_dB[round(bin_index_given_frequency(desired_bin_frequency, df, bins_per_octave))]))
            else:
                np.savetxt(sys.stdout, np.expand_dims(spl_dB, axis=0), fmt='%.1f', delimiter=', ')

            sys.stdout.flush()

main()
