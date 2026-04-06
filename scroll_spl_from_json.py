#!/usr/bin/env python3
import sys
import base64
import threading
import queue
import json
import math
import numpy as np

import matplotlib
matplotlib.rcParams['toolbar'] = 'None'

# if text gets piled on top of other text, try messing with this logic. the same settings do
# not seem to give satisfactory results on all combinations of OS and screen dpi. if someone
# knows what to do here that does the right thing unconditionally lmk
# if matplotlib.get_backend() != 'MacOSX': matplotlib.rcParams['figure.dpi'] = 300

import matplotlib.pyplot as plt

gram_to_rgba_func = matplotlib.cm.ScalarMappable(cmap=matplotlib.colormaps['turbo']).to_rgba

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
    plotdata = None
    X = 0
    Y = 0
    ax = None
    im = None
    iy = 0
    bin_centres = None
    iband_start = None

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
            spls_dB = np.array(spls_dB)

        iband_start_this = int(message['iband_start'])
        dt_this = float(message['dt'])

        if ax and (spls_dB.shape[0] != X or iband_start != iband_start_this or dt != dt_this):
            fig.clf()
            ax = None

        # do this setup stuff on the first input
        if not ax:
            X = spls_dB.shape[0]
            Y = (3 * X) // 4 # plot will have an aspect ratio of 3/4
            iband_start = iband_start_this
            dt = dt_this

            print('%u total bins' % X, file=sys.stderr)

            bin_centres = [frequency_given_bin_index(x, iband_start) for x in range(X)]

            plotdata = np.zeros([2 * Y, X, 4], dtype=np.uint8)

            ax = fig.add_subplot(1, 1, 1)

            xextent = [-0.5, X - 0.5]
            yextent = [-0.5 * dt, (Y - 0.5) * dt]

            im = ax.imshow(plotdata[0:Y, :, :],
                interpolation='nearest',
                origin='lower',
                extent=[xextent[0], xextent[1], yextent[0], yextent[1]],
                aspect=(((xextent[1] - xextent[0]) * Y) / ((yextent[1] - yextent[0]) * X)), animated=True)
            ax.set(title='scari live exfiltrated gram')

            # label the y axis for the subplots on the left side
            ax.set(ylabel='Time (s) in past')

            # label the x axis for the subplots on the bottom
            ax.set(xlabel='Frequency (Hz)')

            if True:
                # TODO: figure out how to set this programmatically
                tick_positions_Hz = [30, 40, 50, 60, 80, 100, 200, 300, 400, 500, 600, 800, 1000, 1500, 2000, 3000, 4000, 5000, 6000, 8000, 10000, 15000, 20000, 30000]
                while tick_positions_Hz[0] < bin_centres[0]: tick_positions_Hz = tick_positions_Hz[1:]
                while tick_positions_Hz[-1] > bin_centres[-1]: tick_positions_Hz = tick_positions_Hz[0:-1]

                tick_positions_bins = [bin_index_given_frequency(x, iband_start) for x in tick_positions_Hz]
                ax.set_xticks(tick_positions_bins)
                ax.set_xticklabels(tick_positions_Hz, rotation=45)

            fig.tight_layout(pad=1.5)
            fig.show()

            fig.canvas.blit(fig.bbox)
            fig.canvas.draw()

        # if not the first call, sanity check that X has not changed
        elif spls_dB.shape[0] != X:
            raise RuntimeError('consecutive packets have different numbers of bins (%u != %u)' % spls_dB.shape[0], X)

        # convert the values in intensity for the new row of pixels to rgba values
        bins_rgba = gram_to_rgba_func(np.clip((spls_dB - clim[0]) / (clim[1] - clim[0]), 0, 1), bytes=True, norm=False)

        # insert the new row of pixels into two places within the doubled ring buffer, so that a
        # contiguous slice of it can always be plotted, ending at the most recent row
        plotdata[iy + 0, :, :] = bins_rgba
        plotdata[iy + Y, :, :] = bins_rgba

        if main_thread_work.empty():
            # update which subset of the doubled ring buffer will be shown
            im.set_data(plotdata[iy:(iy + Y), :])

            ax.draw_artist(im)
            fig.canvas.blit(ax.bbox)
            fig.canvas.flush_events()

        # advance the ring buffer cursor (decrements w/ wraparound, as newest time is at bottom)
        iy = (iy + Y - 1) % Y

    # if we get here, we got to eof on stdin
    pth.join()

main()
