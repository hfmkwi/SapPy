# PySappy
## What is this?
This is a Python port of Kawa and DJ Bouche's Sappy 2006.

This program seeks to emulate the functionality of the GBA's sound engine - 
formally known as the M4A engine or colloquially as Sappy - as close as
possible.

This project is still heavily in development. However, playback with a high 
degree of accuracy can be achieved with this emulator in its current state.

## How do I use this?
To use SapPy, simply call it from the command line:
```
python .\sap.py .\foo.gba -st 0x0x800CAFE 1
```

Full command line usage is as follows:
```
usage: sap.py [-h] [-st SONG_TABLE] path song_num

positional arguments:
  path                  path to the ROM to play
  song_num

optional arguments:
  -h, --help            show this help message and exit
  -st SONG_TABLE, --song_table SONG_TABLE
                        address of song table in rom
```


## System Requirements
* x86 or 32-bit Python (3.6+).
* curses (2.2+)
* A Windows distribution or Wine environment
