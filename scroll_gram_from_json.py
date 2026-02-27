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

def frequency_given_bin_index(index, df, bins_per_octave):
    # by basic arithmetic, this is the first log-spaced bin guaranteed to have a local
    # spacing between output bins that is not less than the spacing of the linear fft bins
    linear_bins_from_dc = math.ceil(bins_per_octave / math.log(2))

    # and by convention (because of Hann window) we omit the bottom two frequency bins
    # as they are typically dominated by DC content and therefore uninteresting
    index_from_dc = index + 2

    if index_from_dc < linear_bins_from_dc:
        return df * index_from_dc
    else:
        return df * linear_bins_from_dc * pow(2, (index_from_dc - linear_bins_from_dc) / bins_per_octave)

def bin_index_given_frequency(frequency, df, bins_per_octave):
    linear_bins_from_dc = math.ceil(bins_per_octave / math.log(2))
    linear_index_from_dc = frequency / df

    if linear_index_from_dc < linear_bins_from_dc:
        return linear_index_from_dc - 2
    else:
        return linear_bins_from_dc - 2 + math.log2(linear_index_from_dc / linear_bins_from_dc) * bins_per_octave

window_closed = False
def on_close(event):
    global window_closed
    window_closed = True

def child_thread(main_thread_work):
    global window_closed

    for line in sys.stdin:
        if window_closed: break

        print(line.strip(), file=sys.stderr)
        try: message = json.loads(line)
        except: continue

        if not 'pgram' in message: continue

        main_thread_work.put(message)

    # inform main thread that child generator has reached eof and no more input is coming
    main_thread_work.put(None)

def main():
    Y = 0

    gram_ring = None
    gram_X = 0
    gram_ax = None
    gram_im = None
    gram_iy = 0

    dt_prior = None
    df_prior = None
    bins_per_octave_prior = None

    gram_clim=(70, 150)

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

        if 'pgram' in message and not 'b' in message:
            try: pixels = np.asarray(list(base64.b64decode(message['pgram'])))
            except: continue

            chigh = 180
            cstep = 0.75
            clow = chigh - 256.0 * cstep

            spl_dB = np.array([q * cstep + clow for q in pixels])

            if not gram_X:
                gram_X = spl_dB.shape[0]
                Y = (2 * gram_X) // 3

                df = float(message['df'])
                dt = float(message['dt'])
                bins_per_octave = int(message['bins_per_octave'])

                linear_bins_from_dc = math.ceil(bins_per_octave / math.log(2))
                print('%u total bins' % gram_X, file=sys.stderr)
                print('lowest %u bins are linearly spaced every %.2f Hz, starting at %.2f Hz' % (linear_bins_from_dc - 2, df, 2 * df), file=sys.stderr)
                print('first log-spaced bin is centered at %g Hz' % (linear_bins_from_dc * df), file=sys.stderr)

                bin_centres = [frequency_given_bin_index(x, df, bins_per_octave) for x in range(gram_X)]

                gram_ring = np.zeros([2 * Y, gram_X, 4], dtype=np.uint8)

                gram_ax = fig.add_subplot(1, 1, 1)

                xextent = [-0.5, gram_X - 0.5]
                yextent = [0, dt * Y]

                gram_im = gram_ax.imshow(gram_ring[0:Y, :, :],
                    interpolation='nearest',
                    origin='lower',
                    extent=[xextent[0], xextent[1], yextent[0], yextent[1]],
                    aspect=(((xextent[1] - xextent[0]) * Y) / ((yextent[1] - yextent[0]) * gram_X)), animated=True)
                gram_ax.set(title='gram')

                # label the x axis for the subplots on the bottom
                gram_ax.set(xlabel='Frequency (Hz)')

                # TODO: figure out how to set this programmatically
                tick_positions_Hz = [ 50, 100, 150, 200, 300, 400, 500, 600, 800, 1000, 1500, 2000, 3000, 4000, 5000, 6000, 8000, 10000, 15000, 20000, 30000]
                while tick_positions_Hz[0] < bin_centres[0] - 0.5 * df: tick_positions_Hz = tick_positions_Hz[1:]
                while tick_positions_Hz[-1] > bin_centres[-1]: tick_positions_Hz = tick_positions_Hz[0:-1]

                tick_positions_bins = [bin_index_given_frequency(x, df, bins_per_octave) for x in tick_positions_Hz]
                gram_ax.set_xticks(tick_positions_bins)
                gram_ax.set_xticklabels(tick_positions_Hz, rotation=45)

                fig.show()

                fig.canvas.blit(fig.bbox)
                fig.canvas.draw()

            # if not the first call, sanity check that X has not changed
            elif spl_dB.shape[0] != gram_X or dt_prior != dt or df_prior != df or bins_per_octave_prior != bins_per_octave:
                    raise RuntimeError('consecutive packets have different parameters')

            dt_prior = dt
            df_prior = df
            bins_per_octave_prior = bins_per_octave

            # convert the values in intensity for the new row of pixels to rgba values
            bins_rgba = gram_to_rgba_func(np.clip((spl_dB - gram_clim[0]) / (gram_clim[1] - gram_clim[0]), 0, 1), bytes=True, norm=False)

            # advance the ring buffer cursor (decrements w/ wraparound, as newest time is at bottom)
            gram_iy = (gram_iy + Y - 1) % Y

            # insert the new row of pixels into two places within the doubled ring buffer, so that a
            # contiguous slice of it can always be plotted, ending at the most recent row
            gram_ring[gram_iy + 0, :, :] = bins_rgba
            gram_ring[gram_iy + Y, :, :] = bins_rgba

        if main_thread_work.empty():
            if gram_im:
                # update which subset of the doubled ring buffer will be shown
                gram_im.set_data(gram_ring[gram_iy:(gram_iy + Y), :])

                gram_ax.draw_artist(gram_im)
                fig.canvas.blit(gram_ax.bbox)

            fig.canvas.flush_events()

    # if we get here, we got to eof on stdin
    pth.join()

main()
