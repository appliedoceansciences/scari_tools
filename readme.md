# `scari_tools`

This repository contains a number of scripts useful for working with SCARI output.

## Components

- `scari_uart_to_json.py`: Opens a `/dev/ttyXXXX` serial device, which may be a physical UART directly attached to SCARI, or a USB CDC serial debug device further downstream to which the SCARI output has been forwarded. For each valid `$PSPL` and `$PGRAM` NMEA-like message read on the UART input, a newline-delimited JSON message is emitted on stdout, suitable for piping into one of several visualization or postprocessing routines, either locally or at the far end of an SSH pipe, for example.

- `scroll_gram_from_json.py`: Reads the newline-delimited JSON emitted by the above, or by `shm2pgram.py` in the scrollygram repository, and plots a live-scrolling spectrogram from the PGRAM messages. When run locally and ingesting input from a remote source of JSON lines via SSH or other pipe, this allows a live scrolling spectrogram to be viewed over limited-bandwidth connections.

- `scroll_spl_from_json.py`: Similar, but for the PSPL messages, which encode only the ANSI decidecade bands.

- `spl_distribution_from_json.py`: Similar, but draws a continuously-updating spectrum line plot instead of a scrolling gram view. Useful for quantifying the background noise level.

- `gpzda_to_daq.py`, `.service`: Periodically creates a NMEA `$GPZDA` string and sends it to the UART from a Linux device. Useful for keeping the clock of an attached SCARI synchronized to within a few milliseconds of the Linux SBC's system clock.

- `finalize_wav.py`: Given a large `.tmp` file resulting from a hard poweroff of SCARI, this will truncate the file to the correct length based on the values in the header, and rename it to `.wav`, without requiring that SCARI be powered up again (which would apply this correction in situ).

## Point of contact

Richard Campbell, richard.campbell@appliedoceansciences.com

## License

Unless otherwise specified, the ISC license applies.
