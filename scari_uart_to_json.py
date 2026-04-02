#!/usr/bin/env python3

# copyright 2026- applied ocean sciences
# isc license
# point of contact: richard campbell

# This script reads newline-delimited NMEA-like messages from SCARI on either an actual
# uart or stdin, and emits newline-delimited JSON messages on stdout, suitable for plotting
# with one of the scrolling gram plotters, or for further analysis by other code.

# Example usage when SCARI is directly attached to a laptop:
# ./scari_uart_to_json.py /dev/tty.usbserial-A104OK4B 115200 | ./scroll_spl_from_json.py

# Example usage when SCARI is attached to a remote host accessible via ssh:
# example: ssh remotehost './scari_uart_to_json.py /dev/ttyAMA0 115200' | ./scroll_spl_from_json.py

import sys
import os
import fcntl
import tty
import termios
from datetime import datetime, timezone

import math
import time
import json

nmea_checksum_errors = 0

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

def open_tty_as_stdin(path, speed=None):
    # open tty with O_NONBLOCK flag so that it doesn't hang forever at this line
    fd_tty = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)

    # immediately remove O_NONBLOCK because we only needed it so we could return from open()
    fcntl.fcntl(fd_tty, fcntl.F_SETFL, fcntl.fcntl(fd_tty, fcntl.F_GETFL) & ~os.O_NONBLOCK)

    tty.setraw(fd_tty)

    c_iflag, c_oflag, c_cflag, c_lflag, ispeed, ospeed, c_cc = termios.tcgetattr(fd_tty)

    if speed is not None:
        ispeed = getattr(termios, 'B' + str(speed))
        ospeed = ispeed

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

    for line in sys.stdin:
        if not '$' in line: continue

        # hack to ignore things on the line before the leading $ in demo code
        if not line.startswith('$'):
            line = line[line.find('$'):]

        try: payload, suffix = line[1:].split('*')
        except: continue

        if not validate_nmea(payload, suffix): continue

        # get current time and round to nearest millisecond
        timestamp = round(datetime.now(timezone.utc).timestamp() * 1e3) / 1e3

        if line.startswith('$PGRAM,'):
            try: prefix, dt_text, df_text, bins_per_octave_text, encoded_pixels = payload.split(',')
            except: continue

            print(json.dumps({ 'time': timestamp, 'dt': float(dt_text), 'df': float(df_text), 'bins_per_octave': int(bins_per_octave_text), 'pgram': encoded_pixels }), flush=True)

        elif line.startswith('$PSPL,'):
            try: prefix, dt_text, iband_start_text, base64_string = payload.split(',')
            except: continue

            print(json.dumps({ 'time': timestamp, 'dt': float(dt_text), 'iband_start': int(iband_start_text), 'pspl': base64_string }), flush=True)

    if nmea_checksum_errors > 0:
        print('nmea checksum errors: %u' % nmea_checksum_errors, file=sys.stderr)

main()
