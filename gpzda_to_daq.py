#!/usr/bin/env python3
# usage: ./gpzda_to_daq.py /dev/tty.usbserial-XXXXX 115200"

# copyright 2024- applied ocean sciences
# isc license
# point of contact: richard campbell

from datetime import datetime, timezone
import os
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

# every ten seconds
interval_ns = 10000000000

fd = os.timerfd_create(time.CLOCK_REALTIME)

now_ns = time.clock_gettime_ns(time.CLOCK_REALTIME)

# at least half an interval in the future, aligned with one interval in absolute time
time_in_future_ns = ((now_ns + interval_ns // 2 + interval_ns - 1) // interval_ns) * interval_ns

os.timerfd_settime_ns(fd, initial=time_in_future_ns, interval=interval_ns, flags=os.TFD_TIMER_ABSTIME)

while True:
    _ = os.read(fd, 8)
    create_and_send_one_gpzda_packet(ser)
