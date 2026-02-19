#!/usr/bin/env python3
# usage: ./gpzda.py /dev/tty.usbserial-XXXXX 115200"

# copyright 2024- applied ocean sciences
# isc license
# point of contact: richard campbell

from datetime import datetime, timezone
import sys
from math import floor

import serial
import time

def create_and_send_one_gpzda_packet(ser):
    t = datetime.now(timezone.utc)
    ts = t.timestamp()
    tt = t.timetuple()

    tfrac = ts - floor(ts)
    payload = "GPZDA,%02u%02u%02u.%06u,%02u,%02u,%04u,00,00" % (tt.tm_hour, tt.tm_min, tt.tm_sec, floor(tfrac * 1000000), tt.tm_mday, tt.tm_mon, tt.tm_year)

    cksum = 0
    for byte in bytes(payload, 'utf-8'):
        cksum = cksum ^ byte

    ser.write(("$%s*%02X\r\n" % (payload, cksum)).encode("utf-8"))

    print(ts, file=sys.stderr)

ser = serial.Serial(sys.argv[1], baudrate=sys.argv[2])

# make sure pyserial is fully initted and attempt to put the uart in a known state
ser.write('\r\n'.encode('utf-8'))
time.sleep(0.1)

create_and_send_one_gpzda_packet(ser)

ser.close()
