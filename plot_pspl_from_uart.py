#!/usr/bin/env python3
import sys
import os
import fcntl
import tty
import termios

import base64
import struct
from collections import namedtuple
import threading
import queue
import math
import time
import socket
import numpy as np

from parse_scari_lines import *

def frequency_given_bin_index(index, iband_start):
    return math.pow(10.0, (index + iband_start) / 10.0)

def bin_index_given_frequency(frequency, iband_start):
    return 10.0 * math.log10(frequency) - iband_start

window_closed = False
def on_close(event):
    global window_closed
    window_closed = True

def pgram_generator():
    global window_closed
    global nmea_checksum_errors
    checksum_errors = 0

    for line in sys.stdin:
        if window_closed: break
        print(line.rstrip(), file=sys.stderr)

        # hack to ignore things on the line before the leading $ in demo code
        if not line.startswith('$'):
            line = line[line.find('$'):]

        pspl = parse_scari_pspl(line)
        if pspl is not None:
            yield pspl

    if nmea_checksum_errors > 0:
        print('nmea checksum errors: %u' % nmea_checksum_errors, file=sys.stderr)

import matplotlib
matplotlib.rcParams['toolbar'] = 'None'

# if text gets piled on top of other text, try messing with this logic. the same settings do
# not seem to give satisfactory results on all combinations of OS and screen dpi. if someone
# knows what to do here that does the right thing unconditionally lmk
# if matplotlib.get_backend() != 'MacOSX': matplotlib.rcParams['figure.dpi'] = 300

import matplotlib.pyplot as plt

to_rgba_func = matplotlib.cm.ScalarMappable(cmap=matplotlib.colormaps['turbo']).to_rgba

# turns a generator into a child thread which yields functions and arguments to main thread
def child_thread(main_thread_work):
    for packet in pgram_generator():
        main_thread_work.put(packet)

    # inform main thread that child generator has reached eof and no more input is coming
    main_thread_work.put(None)

def open_tty_as_stdin(path, speed=None):
    # open tty with O_NONBLOCK flag so that it doesn't hang forever at this line
    fd_tty = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)

    # immediately remove O_NONBLOCK because we only needed it so we could return from open()
    fcntl.fcntl(fd_tty, fcntl.F_SETFL, fcntl.fcntl(fd_tty, fcntl.F_GETFL) & ~os.O_NONBLOCK)

    tty.setraw(fd_tty)

    c_iflag, c_oflag, c_cflag, c_lflag, ispeed, ospeed, c_cc = termios.tcgetattr(fd_tty)

    if speed is not None:
        ispeed = speed
        ospeed = speed

    # ignore modem control lines and enable hupcl
    c_cflag |= termios.HUPCL | termios.CLOCAL

    termios.tcsetattr(fd_tty, termios.TCSANOW, [c_iflag, c_oflag, c_cflag, c_lflag, ispeed, ospeed, c_cc])

    os.dup2(fd_tty, 0)
    os.close(fd_tty)

def main():
    if len(sys.argv) > 1:
        open_tty_as_stdin(sys.argv[1], speed=(int(sys.argv[2]) if len(sys.argv) > 2 else None))

    # do not throw exceptions on bad uart input
    sys.stdin.reconfigure(errors='ignore')

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

    # start a child thread which accept output yielded from one of two possible generators
    # depending on whether stdin is a tty, and safely communicate that generator output
    # and what to do with it back to the main thread via the work queue
    pth = threading.Thread(target=child_thread, args=(main_thread_work,))
    pth.start()

    # event loop which dequeues work from other threads that must be done on main thread
    while True:
        if main_thread_work.empty():
            # there must be a better way to do this
            fig.canvas.start_event_loop(0.016)
            continue
        packet = main_thread_work.get()
        if packet is None: break

        intensity = np.power(10.0, np.array(packet.spls_dB) * 0.1)

        if ax and (intensity.shape[0] != X or iband_start != packet.iband_start or dt != packet.dt):
            fig.clf()
            ax = None

        # do this setup stuff on the first input
        if not ax:
            X = intensity.shape[0]
            Y = (3 * X) // 4 # plot will have an aspect ratio of 3/4
#            df = packet.df
            iband_start = packet.iband_start
            dt = packet.dt

            print('%u total bins' % X, file=sys.stderr)

            bin_centres = [frequency_given_bin_index(x, iband_start) for x in range(X)]

            plotdata = np.zeros([2 * Y, X, 4], dtype=np.uint8)

            ax = fig.add_subplot(1, 1, 1)

            xextent = [-0.5, X - 0.5]
            yextent = [0, packet.dt * Y]

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
        elif intensity.shape[0] != X:
            raise RuntimeError('consecutive packets have different numbers of bins (%u != %u)' % intensity.shape[0], X)

        # convert the values in intensity for the new row of pixels to rgba values
        bins_rgba = to_rgba_func(np.clip((10.0 * np.log10(intensity + 2e-38) - clim[0]) / (clim[1] - clim[0]), 0, 1), bytes=True, norm=False)

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
