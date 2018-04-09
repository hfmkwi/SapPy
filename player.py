#!/usr/bin/env python3
#-*- coding: utf-8 -*-
# pylint: disable=C0326,E1120,R0903
"""Player types"""
import math
from struct import unpack, pack
from typing import NamedTuple

from fileio import VirtualFile

__all__ = ('DirectHeader', 'DrumKitHeader', 'InstrumentHeader', 'InvalidHeader',
           'MasterTableEntry', 'MasterTableEntry', 'MultiHeader', 'NoiseHeader',
           'NoiseHeader', 'SampleHeader', 'SongHeader', 'SquareOneHeader',
           'SquareTwoHeader', 'WaveHeader', 'note_to_name', 'note_to_freq',
           'rd_dct_head', 'rd_drmkit_head', 'rd_inst_head', 'rd_inv_head',
           'rd_nse_head', 'rd_mul_head', 'rd_smp_head', 'rd_sng_head',
           'rd_sq1_head', 'rd_sq2_head', 'rd_wav_head', 'sbyte_to_int',
           'stlen_to_ticks')

# yapf: disable
NOTES = {
    0:  'C',
    1:  'C#',
    2:  'D',
    3:  'D#',
    4:  'E',
    5:  'F',
    6:  'F#',
    7:  'G',
    8:  'G#',
    9:  'A',
    10: 'A#',
    11: 'B'
}
# yapf: enable
STLEN = {
    0x0: 0x0,
    0x1: 0x1,
    0x2: 0x2,
    0x3: 0x3,
    0x4: 0x4,
    0x5: 0x5,
    0x6: 0x6,
    0x7: 0x7,
    0x8: 0x8,
    0x9: 0x9,
    0xA: 0xA,
    0xB: 0xB,
    0xC: 0xC,
    0xD: 0xD,
    0xE: 0xE,
    0xF: 0xF,
    0x10: 0x10,
    0x11: 0x11,
    0x12: 0x12,
    0x13: 0x13,
    0x14: 0x14,
    0x15: 0x15,
    0x16: 0x16,
    0x17: 0x17,
    0x18: 0x18,
    0x19: 0x1C,
    0x1A: 0x1E,
    0x1B: 0x20,
    0x1C: 0x24,
    0x1D: 0x28,
    0x1E: 0x2A,
    0x1F: 0x2C,
    0x20: 0x30,
    0x21: 0x34,
    0x22: 0x36,
    0x23: 0x38,
    0x24: 0x3C,
    0x25: 0x40,
    0x26: 0x42,
    0x27: 0x44,
    0x28: 0x48,
    0x29: 0x4C,
    0x2A: 0x4E,
    0x2B: 0x50,
    0x2C: 0x54,
    0x2D: 0x58,
    0x2E: 0x5A,
    0x2F: 0x5C,
    0x30: 0x60
}


class DirectHeader(NamedTuple):
    """Data for a DirectSound instrument."""
    # yapf: disable
    b0:       int = int()
    b1:       int = int()
    smp_head: int = int()
    attack:   int = int()
    hold:     int = int()
    sustain:  int = int()
    release:  int = int()
    # yapf: enable


class DrumKitHeader(NamedTuple):
    """Data for a Drumkit instrument."""
    # yapf: disable
    b0:      int = int()
    b1:      int = int()
    dct_tbl: int = int()
    b6:      int = int()
    b7:      int = int()
    b8:      int = int()
    b9:      int = int()
    # yapf: enable


class InstrumentHeader(NamedTuple):
    """Data for a standard instrument."""
    # yapf: disable
    channel:    int = int()
    drum_pitch: int = int()
    # yapf: enable


class InvalidHeader(NamedTuple):
    """Data for an invalid data."""
    b0: int = int()
    b1: int = int()
    b2: int = int()
    b3: int = int()
    b4: int = int()
    b5: int = int()
    b6: int = int()
    b7: int = int()
    b8: int = int()
    b9: int = int()


class MasterTableEntry(NamedTuple):
    """Song entry as read from ROM."""
    # yapf: disable
    song: int = int()
    pri1: int = int()
    pri2: int = int()
    # yapf: enable


class MultiHeader(NamedTuple):
    """Data for MultiSample instrument."""
    # yapf: disable
    b0:      int = int()
    b1:      int = int()
    dct_tbl: int = int()
    kmap: int = int()
    # yapf: enable


class NoiseHeader(NamedTuple):
    """Data for simulated AGB noise."""
    # yapf: disable
    b0:      int = int()
    b1:      int = int()
    b2:      int = int()
    b3:      int = int()
    b4:      int = int()
    b5:      int = int()
    attack:  int = int()
    decay:   int = int()
    sustain: int = int()
    release: int = int()
    # yapf: enable


class SampleHeader(NamedTuple):
    """Data for an AGB sound sample."""
    # yapf: disable
    flags:     int = int()
    b4:        int = int()
    fine_tune: int = int()
    freq:      int = int()
    loop:      int = int()
    size:      int = int()
    # yapf: enable


class SongHeader(NamedTuple):
    """Data for an AGB song."""
    # yapf: disable
    tracks:    int = int()
    blks:      int = int()
    pri:       int = int()
    reverb:    int = int()
    inst_bank: int = int()
    # yapf: enable


class SquareOneHeader(NamedTuple):
    """Data for a Square1 instrument."""
    # yapf: disable
    raw1:       int = int()
    raw2:       int = int()
    duty_cycle: int = int()
    b3:         int = int()
    b4:         int = int()
    b5:         int = int()
    attack:     int = int()
    decay:      int = int()
    sustain:    int = int()
    release:    int = int()
    # yapf: enable


class SquareTwoHeader(NamedTuple):
    """Data for a Square2 instrument."""
    # yapf: disable
    b0:         int = int()
    b1:         int = int()
    duty_cycle: int = int()
    b3:         int = int()
    b4:         int = int()
    b5:         int = int()
    attack:     int = int()
    decay:      int = int()
    sustain:    int = int()
    release:    int = int()
    # yapf: enable


class WaveHeader(NamedTuple):
    """Data for a Wave instrument."""
    # yapf: disable
    b0:      int = int()
    b1:      int = int()
    sample:  int = int()
    attack:  int = int()
    decay:   int = int()
    sustain: int = int()
    release: int = int()
    # yapf: enable


def note_to_name(midi_note: int) -> str:
    """Retrieve the string name of a MIDI note from its byte representation."""
    x = midi_note % 12
    o = midi_note // 12
    return NOTES.get(x) + str(o)


def note_to_freq(midi_note: int, midc_freq: int = -1) -> int:
    """Retrieve the sound frequency of a MIDI note relative to C3."""
    import math
    magic = math.pow(2, 1.0 / 12.0)
    X = midi_note - 0x3C
    if midc_freq == -1:
        a = 7040
        c = a * math.pow(magic, 3)
    elif midc_freq == -2:
        a = 7040 / 2
        c = a * math.pow(magic, 3)
    else:
        c = midc_freq
        #print(c)

    x = c * math.pow(magic, X)
    #print(note_to_name(midi_note), x)
    return int(x)


def rd_dct_head(file_id: int, addr: int = None) -> DirectHeader:
    """Read int from a specified file into a Direct header."""
    w_file = VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = DirectHeader(
        b0       = w_file.rd_byte(),
        b1       = w_file.rd_byte(),
        smp_head = w_file.rd_ltendian(4),
        attack   = w_file.rd_byte(),
        hold     = w_file.rd_byte(),
        sustain  = w_file.rd_byte(),
        release  = w_file.rd_byte()
    )
    # yapf: enable
    return header


def rd_drmkit_head(file_id: int, addr: int = None) -> DrumKitHeader:
    """Read int from a specified file into a DrumKit header."""
    w_file = VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = DrumKitHeader(
        b0      = w_file.rd_byte(),
        b1      = w_file.rd_byte(),
        dct_tbl = w_file.rd_ltendian(4),
        b6      = w_file.rd_byte(),
        b7      = w_file.rd_byte(),
        b8      = w_file.rd_byte(),
        b9      = w_file.rd_byte()
    )
    # yapf: enable
    return header


def rd_inst_head(file_id: int, addr: int = None) -> InstrumentHeader:
    """Read int from a specified file into a Instrument header."""
    w_file = VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = InstrumentHeader(
        channel    = w_file.rd_byte(),
        drum_pitch = w_file.rd_byte()
    )
    # yapf: enable
    return header


def rd_inv_head(file_id: int, addr: int = None) -> InvalidHeader:
    """Read int from a specified file into a Invalid header."""
    w_file = VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = InvalidHeader(
        b0 = w_file.rd_byte(),
        b1 = w_file.rd_byte(),
        b2 = w_file.rd_byte(),
        b3 = w_file.rd_byte(),
        b4 = w_file.rd_byte(),
        b5 = w_file.rd_byte(),
        b6 = w_file.rd_byte(),
        b7 = w_file.rd_byte(),
        b8 = w_file.rd_byte(),
        b9 = w_file.rd_byte()
    )
    # yapf: enable
    return header


def rd_nse_head(file_id: int, addr: int = None) -> NoiseHeader:
    """Read int from a specified file into a Noise instrument header."""
    w_file = VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = NoiseHeader(
        b0      = w_file.rd_byte(),
        b1      = w_file.rd_byte(),
        b2      = w_file.rd_byte(),
        b3      = w_file.rd_byte(),
        b4      = w_file.rd_byte(),
        b5      = w_file.rd_byte(),
        attack  = w_file.rd_byte(),
        decay   = w_file.rd_byte(),
        sustain = w_file.rd_byte(),
        release = w_file.rd_byte()
    )
    # yapf: enable
    return header


def rd_mul_head(file_id: int, addr: int = None) -> MultiHeader:
    """Read int from a specified file into a Multi-sample instrument header."""
    w_file = VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = MultiHeader(
        b0      = w_file.rd_byte(),
        b1      = w_file.rd_byte(),
        dct_tbl = w_file.rd_ltendian(4),
        kmap    = w_file.rd_ltendian(4)
    )
    # yapf: enable
    return header


def rd_smp_head(file_id: int, addr: int = None) -> SampleHeader:
    """Read int from a specified file into a Sample header."""
    w_file = VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = SampleHeader(
        flags     = w_file.rd_ltendian(4),
        b4        = w_file.rd_byte(),
        fine_tune = w_file.rd_byte(),
        freq      = w_file.rd_ltendian(2),
        loop      = w_file.rd_ltendian(4),
        size      = w_file.rd_ltendian(4)
    )
    # yapf: enable
    return header


def rd_sng_head(file_id: int, addr: int = None) -> SongHeader:
    """Read int from a specified file into a Song header."""
    w_file = VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = SongHeader(
        tracks    = w_file.rd_byte(),
        blks      = w_file.rd_byte(),
        pri       = w_file.rd_byte(),
        reverb    = w_file.rd_byte(),
        inst_bank = w_file.rd_ltendian(4)
    )
    # yapf: enable
    return header


def rd_sq1_head(file_id: int, addr: int = None) -> SquareOneHeader:
    """Read int from a specified file into a Square1 instrument header."""
    w_file = VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = SquareOneHeader(
        raw1       = w_file.rd_byte(),
        raw2       = w_file.rd_byte(),
        duty_cycle = w_file.rd_byte(),
        b3         = w_file.rd_byte(),
        b4         = w_file.rd_byte(),
        b5         = w_file.rd_byte(),
        attack     = w_file.rd_byte(),
        decay      = w_file.rd_byte(),
        sustain    = w_file.rd_byte(),
        release    = w_file.rd_byte()
    )
    # yapf: enable
    return header


def rd_sq2_head(file_id: int, addr: int = None) -> SquareTwoHeader:
    """Read bytes from a specified file into a Square2 instrument header."""
    w_file = VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = SquareTwoHeader(
        b0         = w_file.rd_byte(),
        b1         = w_file.rd_byte(),
        duty_cycle = w_file.rd_byte(),
        b3         = w_file.rd_byte(),
        b4         = w_file.rd_byte(),
        b5         = w_file.rd_byte(),
        attack     = w_file.rd_byte(),
        decay      = w_file.rd_byte(),
        sustain    = w_file.rd_byte(),
        release    = w_file.rd_byte()
    )
    # yapf: enable
    return header


def rd_wav_head(file_id: int, addr: int = None) -> WaveHeader:
    """Read bytes from a specified file into a Wave instrument header."""
    w_file = VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = WaveHeader(
        b0      = w_file.rd_byte(),
        b1      = w_file.rd_byte(),
        sample  = w_file.rd_ltendian(4),
        attack  = w_file.rd_byte(),
        decay   = w_file.rd_byte(),
        sustain = w_file.rd_byte(),
        release = w_file.rd_byte()
    )
    # yapf: enable
    return header


def sbyte_to_int(sbyte: int) -> int:
    """Convert a signed 4-byte bytearray into a signed integer."""
    return sbyte - 0x100 if sbyte >= 0x80 else sbyte


def stlen_to_ticks(short_len: int) -> int:
    """Convert short length to MIDI ticks."""
    return STLEN.get(short_len)
