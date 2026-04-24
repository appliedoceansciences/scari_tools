#!/usr/bin/env python3
import sys
import base64
import threading
import queue
import json
import math
import numpy as np

import matplotlib
#matplotlib.rcParams['toolbar'] = 'None'

# if text gets piled on top of other text, try messing with this logic. the same settings do
# not seem to give satisfactory results on all combinations of OS and screen dpi. if someone
# knows what to do here that does the right thing unconditionally lmk
# if matplotlib.get_backend() != 'MacOSX': matplotlib.rcParams['figure.dpi'] = 300

import matplotlib.pyplot as plt

def frequency_given_bin_index(index, iband_start):
    return math.pow(10.0, (index + iband_start) / 10.0)

def bin_index_given_frequency(frequency, iband_start):
    return 10.0 * math.log10(frequency) - iband_start

window_closed = False
def on_close(event):
    global window_closed
    window_closed = True

def child_thread(main_thread_work):
    global window_closed

    for line in sys.stdin:
        if window_closed: break

        try: message = json.loads(line)
        except: continue

        if not 'pspl' in message: continue

        main_thread_work.put(message)

    # inform main thread that child generator has reached eof and no more input is coming
    main_thread_work.put(None)

def unpack_nibble(bytes, inibble_abs):
    ibyte = inibble_abs // 2
    inibble = inibble_abs % 2
    return (int)(bytes[ibyte] >> (4 * inibble)) & 0xF

def unpack_three_nibbles(bytes, inibble_abs):
    return (unpack_nibble(bytes, inibble_abs + 0) << 0 |
            unpack_nibble(bytes, inibble_abs + 1) << 4 |
            unpack_nibble(bytes, inibble_abs + 2) << 8)

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

def main():
    data = None
    X = 0
    T = 0
    ax = None
    lines = []
    bin_centres = None
    iband_start = None
    full_scale_square_wave_dB_re_uPa_squared = None

    # loop over pairs of arguments
    for key, value in zip(sys.argv[1::2], sys.argv[2::2]):
        if key == 'full_scale': full_scale_square_wave_dB_re_uPa_squared = float(value)

    if full_scale_square_wave_dB_re_uPa_squared is None:
        print('assuming scari v1 default calibration, specify full scale square wave dB re uPa^2 using "full_scale" to override', file=sys.stderr)
        full_scale_square_wave_dB_re_uPa_squared = 185.642


    # constants you might want to fiddle with. TODO: allow main() to modify these
    clim=(-123, -3)

    # create an empty figure but don't show it yet
    fig = plt.figure()

    fig.canvas.mpl_connect('close_event', on_close)

    # thread-safe fifo between rx thread and main thread
    main_thread_work = queue.Queue()

    pth = threading.Thread(target=child_thread, args=(main_thread_work,))
    pth.start()

    while True:
        try:
            message = main_thread_work.get(timeout=0.016)
        except queue.Empty:
            fig.canvas.flush_events()
            continue
        if message is None: break

        if 'pspl' in message:
            spls_dB = parse_scari_pspl_data_segment(message['pspl'])
            if spls_dB is None: continue

        spls_dB = np.array(spls_dB) + full_scale_square_wave_dB_re_uPa_squared

        iband_start_this = int(message['iband_start'])

        if ax and (spls_dB.shape[0] != X or iband_start != iband_start_this):
            fig.clf()
            ax = None

        # do this setup stuff on the first input
        if not ax:
            X = spls_dB.shape[0]
            iband_start = iband_start_this

            bin_centres = [frequency_given_bin_index(x, iband_start) for x in range(X)]

            ax = fig.add_subplot(1, 1, 1)

            data = spls_dB
            data.shape = [X, 1]
            T = 1

            linedata = spls_dB[:, (np.arange(5, 105, 10) * T) // 100]
            lines = ax.plot(bin_centres, linedata, color='black', alpha=0.2)

            # label the x axis for the subplots on the bottom
            ax.set(xlabel='Frequency (Hz)')
            ax.set_xscale('log')

            ax.set(ylabel='Band power (dB re uPa$^2$), 5th-95th percentiles')

            ax.grid(True, which='major')
            ax.grid(True, which='minor', alpha=0.5)

            fig.show()
        else:
            # if not the first call, sanity check that X has not changed
            if spls_dB.shape[0] != X:
                raise RuntimeError('consecutive packets have different numbers of bins (%u != %u)' % spls_dB.shape[0], X)

            olddata = data
            data = np.zeros((X, T + 1))

            for iband in range(X):
                prior = olddata[iband, 0:T]
                data[iband, :] = np.insert(prior, np.searchsorted(prior, spls_dB[iband]), spls_dB[iband])

            T += 1
            linedata = data[:, (np.arange(5, 105, 10) * T) // 100]

            for ipercentile in range(10):
                lines[ipercentile].set_ydata(linedata[:, ipercentile])

        ax.set(title='Distribution of %.0f s decidecade band SPLs for %.0f s' % (float(message['dt']), T * float(message['dt'])))

        fig.canvas.draw()
        fig.canvas.flush_events()

    # if we get here, we got to eof on stdin
    pth.join()

main()

# keep plot open after eof
plt.show()
