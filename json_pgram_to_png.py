#!/usr/bin/env python3

import os
import sys
import math
import base64
import json
import numpy as np
import matplotlib.pyplot

climit = (-130, -40)
cmap = 'turbo'

# loop over pairs of arguments. some of these do something for each occurrence, in order
for key, value in zip(sys.argv[1::2], sys.argv[2::2]):
    if key == 'climit': climit = [float(x) for x in value.split(',', 1)]
    if key == 'cmap': cmap = value

cstep = 0.75
clow = -256.0 * cstep

iframe = 0

for line in sys.stdin:
    try: message = json.loads(line)
    except: continue

    if not 'pgram' in message: continue

    try: pixels = base64.b64decode(message['pgram'])
    except: continue

    pixels = np.frombuffer(base64.b64decode(message['pgram']), dtype=np.uint8)

    df = float(message['df'])
    dt = float(message['dt'])
    bins_per_octave = int(message['bins_per_octave'])

    power_dB = pixels.astype(np.single) * cstep + clow

    if 0 == iframe:
        # first packet
        linear_bins_from_dc = math.ceil(bins_per_octave / math.log(2))
        print('lowest %u bins are linearly spaced every %.2f Hz, starting at %.2f Hz' % (linear_bins_from_dc - 2, df, 2 * df), file=sys.stderr)
        print('first log-spaced bin is centered at %g Hz' % (linear_bins_from_dc * df), file=sys.stderr)

        data = np.zeros((1, len(pixels)), dtype=np.single)

    if iframe >= data.shape[0]: data.resize([data.shape[0] * 2, data.shape[1]])
    data[iframe, :] = power_dB

    iframe += 1

# resize data down to the final size after repeated doubling
data.resize((iframe, data.shape[1]))

matplotlib.pyplot.imsave('/tmp/out.png' if sys.stdout.isatty() else sys.stdout, data, cmap=cmap, vmin=climit[0], vmax=climit[1])
if sys.stdout.isatty(): os.system('open /tmp/out.png')
