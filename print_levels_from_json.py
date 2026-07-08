#!/usr/bin/env python3
import sys
import base64
import json
import numpy as np

def main():
    full_scale = 0

    # loop over pairs of arguments
    for key, value in zip(sys.argv[1::2], sys.argv[2::2]):
        if key == 'full_scale': full_scale = float(value)

    for line in sys.stdin:
        try: message = json.loads(line)
        except: continue

        if not 'pgram' in message: continue

        if 'pgram' in message and not 'b' in message:
            try: pixels = base64.b64decode(message['pgram'])
            except: continue

            chigh = 0
            cstep = 0.75
            clow = chigh - 256.0 * cstep

            spl_dB = np.frombuffer(pixels, dtype=np.uint8) * cstep + clow + full_scale

            np.savetxt(sys.stdout, np.expand_dims(spl_dB, axis=0), fmt='%.1f', delimiter=', ')
            sys.stdout.flush()

main()
