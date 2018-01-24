# -*- coding: utf-8 -*-
# !/usr/bin/env python3
# pylint: disable=C0326,R0903
"""Player types"""
from struct import unpack
from typing import NamedTuple

from fileio import File

__all__ = ('DirectHeader', 'DrumKitHeader', 'InstrumentHeader', 'InvalidHeader',
           'MasterTableEntry', 'MasterTableEntry', 'MultiHeader', 'NoiseHeader',
           'NoiseHeader', 'SampleHeader', 'SongHeader', 'SquareOneHeader',
           'SquareTwoHeader', 'WaveHeader', 'note_to_name', 'note_to_frequency',
           'read_direct_head', 'read_drumkit_head', 'read_instrument_head',
           'read_invalid_head', 'read_noise_head', 'read_multi_head',
           'read_sample_head', 'read_song_head', 'read_square1_head',
           'read_square2_head', 'read_wave_head', 'signed_byte_to_integer',
           'slen_to_ticks')

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
SHORT_LEN = {
    0x00: 0x00,
    0x01: 0x01,
    0x02: 0x02,
    0x03: 0x03,
    0x04: 0x04,
    0x05: 0x05,
    0x06: 0x06,
    0x07: 0x07,
    0x08: 0x08,
    0x09: 0x09,
    0x0A: 0x0A,
    0x0B: 0x0B,
    0x0C: 0x0C,
    0x0D: 0x0D,
    0x0E: 0x0E,
    0x0F: 0x0F,
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
    0x1E: 0x2C,
    0x1F: 0x2E,
    0x20: 0x30,
    0x21: 0x34,
    0x22: 0x38,
    0x23: 0x3C,
    0x24: 0x3E,
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
    b0:            int = int()
    b1:            int = int()
    sample_header: int = int()
    attack:        int = int()
    hold:          int = int()
    sustain:       int = int()
    release:       int = int()
    # yapf: enable


class DrumKitHeader(NamedTuple):
    """Data for a Drumkit instrument."""
    # yapf: disable
    b0:           int = int()
    b1:           int = int()
    direct_table: int = int()
    b6:           int = int()
    b7:           int = int()
    b8:           int = int()
    b9:           int = int()
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
    song:      int = int()
    priority1: int = int()
    priority2: int = int()
    # yapf: enable


class MultiHeader(NamedTuple):
    """Data for MultiSample instrument."""
    # yapf: disable
    b0:           int = int()
    b1:           int = int()
    direct_table: int = int()
    key_map:      int = int()
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
    frequency: int = int()
    loop:      int = int()
    size:      int = int()
    # yapf: enable


class SongHeader(NamedTuple):
    """Data for an AGB song."""
    # yapf: disable
    tracks:          int = int()
    blocks:          int = int()
    priority:        int = int()
    reverb:          int = int()
    instrument_bank: int = int()
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


def note_to_name(midi_note: bytes) -> str:
    """Retrieve the string name of a MIDI note from its byte representation."""
    midi_note = unpack('B', midi_note)
    octave, note = divmod(midi_note, 12)
    return NOTES.get(note) + octave


def note_to_frequency(midi_note: int, mid_c_freq: int = -1) -> int:
    """Retrieve the sound frequency of a MIDI note relative to C3."""
    magic = 2 ** (1/12)
    delta_x = midi_note - 0x3C
    if mid_c_freq == -1:
        a_freq = 7040
        c_freq = a_freq * magic**3
    elif mid_c_freq == -2:
        a_freq = 7040 / 2
        c_freq = a_freq * magic**3
    else:
        c_freq = mid_c_freq
    return c_freq * magic**delta_x


def read_direct_head(file_id: int, offset: int = None) -> DirectHeader:
    """Read int from a specified file into a Direct header."""
    w_file = File.get_file_from_id(file_id)
    w_file.read_offset = offset
    # yapf: disable
    header = DirectHeader(
        b0            = w_file.read_byte(),
        b1            = w_file.read_byte(),
        sample_header = w_file.read_little_endian(4),
        attack        = w_file.read_byte(),
        hold          = w_file.read_byte(),
        sustain       = w_file.read_byte(),
        release       = w_file.read_byte(),
    )
    # yapf: enable
    return header


def read_drumkit_head(file_id: int, offset: int = None) -> DrumKitHeader:
    """Read int from a specified file into a DrumKit header."""
    w_file = File.get_file_from_id(file_id)
    w_file.read_offset = offset
    # yapf: disable
    header = DrumKitHeader(
        b0           = w_file.read_byte(),
        b1           = w_file.read_byte(),
        direct_table = w_file.read_little_endian(4),
        b6           = w_file.read_byte(),
        b7           = w_file.read_byte(),
        b8           = w_file.read_byte(),
        b9           = w_file.read_byte()
    )
    # yapf: enable
    return header


def read_instrument_head(file_id: int, offset: int = None) -> InstrumentHeader:
    """Read int from a specified file into a Instrument header."""
    w_file = File.get_file_from_id(file_id)
    w_file.read_offset = offset
    # yapf: disable
    header = InstrumentHeader(
        channel    = w_file.read_byte(),
        drum_pitch = w_file.read_byte()
    )
    # yapf: enable
    return header


def read_invalid_head(file_id: int, offset: int = None) -> InvalidHeader:
    """Read int from a specified file into a Invalid header."""
    w_file = File.get_file_from_id(file_id)
    w_file.read_offset = offset
    # yapf: disable
    header = InvalidHeader(
        b0 = w_file.read_byte(),
        b1 = w_file.read_byte(),
        b2 = w_file.read_byte(),
        b3 = w_file.read_byte(),
        b4 = w_file.read_byte(),
        b5 = w_file.read_byte(),
        b6 = w_file.read_byte(),
        b7 = w_file.read_byte(),
        b8 = w_file.read_byte(),
        b9 = w_file.read_byte()
    )
    # yapf: enable
    return header


def read_noise_head(file_id: int, offset: int = None) -> NoiseHeader:
    """Read int from a specified file into a Noise instrument header."""
    w_file = File.get_file_from_id(file_id)
    w_file.read_offset = offset
    # yapf: disable
    header = NoiseHeader(
        b0      = w_file.read_byte(),
        b1      = w_file.read_byte(),
        b2      = w_file.read_byte(),
        b3      = w_file.read_byte(),
        b4      = w_file.read_byte(),
        b5      = w_file.read_byte(),
        attack  = w_file.read_byte(),
        decay   = w_file.read_byte(),
        sustain = w_file.read_byte(),
        release = w_file.read_byte()
    )
    # yapf: enable
    return header


def read_multi_head(file_id: int, offset: int = None) -> MultiHeader:
    """Read int from a specified file into a Multi-sample instrument header."""
    w_file = File.get_file_from_id(file_id)
    w_file.read_offset = offset
    # yapf: disable
    header = MultiHeader(
        b0           = w_file.read_byte(),
        b1           = w_file.read_byte(),
        direct_table = w_file.read_little_endian(4),
        key_map      = w_file.read_little_endian(4)
    )
    # yapf: enable
    return header


def read_sample_head(file_id: int, offset: int = None) -> SampleHeader:
    """Read int from a specified file into a Sample header."""
    w_file = File.get_file_from_id(file_id)
    w_file.read_offset = offset
    # yapf: disable
    header = SampleHeader(
        tracks          = w_file.read_little_endian(4),
        blocks          = w_file.read_byte(),
        priority        = w_file.read_byte(),
        reverb          = w_file.read_little_endian(4),
        instrument_bank = w_file.read_little_endian(4)
    )
    # yapf: enable
    return header


def read_song_head(file_id: int, offset: int = None) -> SongHeader:
    """Read int from a specified file into a Song header."""
    w_file = File.get_file_from_id(file_id)
    w_file.read_offset = offset
    # yapf: disable
    header = SongHeader(
        tracks          = w_file.read_byte(),
        blocks          = w_file.read_byte(),
        priority        = w_file.read_byte(),
        reverb          = w_file.read_byte(),
        instrument_bank = w_file.read_little_endian(4)
    )
    # yapf: enable
    return header


def read_square1_head(file_id: int, offset: int = None) -> SquareOneHeader:
    """Read int from a specified file into a Square1 instrument header."""
    w_file = File.get_file_from_id(file_id)
    w_file.read_offset = offset
    # yapf: disable
    header = SquareOneHeader(
        raw1       = w_file.read_byte(),
        raw2       = w_file.read_byte(),
        duty_cycle = w_file.read_byte(),
        b3         = w_file.read_byte(),
        b4         = w_file.read_byte(),
        b5         = w_file.read_byte(),
        attack     = w_file.read_byte(),
        decay      = w_file.read_byte(),
        sustain    = w_file.read_byte(),
        release    = w_file.read_byte()
    )
    # yapf: enable
    return header


def read_square2_head(file_id: int, offset: int = None) -> SquareTwoHeader:
    """Read bytes from a specified file into a Square2 instrument header."""
    w_file = File.get_file_from_id(file_id)
    w_file.read_offset = offset
    # yapf: disable
    header = SquareTwoHeader(
        b0         = w_file.read_byte(),
        b1         = w_file.read_byte(),
        duty_cycle = w_file.read_byte(),
        b3         = w_file.read_byte(),
        b4         = w_file.read_byte(),
        b5         = w_file.read_byte(),
        attack     = w_file.read_byte(),
        decay      = w_file.read_byte(),
        sustain    = w_file.read_byte(),
        release    = w_file.read_byte()
    )
    # yapf: enable
    return header


def read_wave_head(file_id: int, offset: int = None) -> WaveHeader:
    """Read bytes from a specified file into a Wave instrument header."""
    w_file = File.get_file_from_id(file_id)
    w_file.read_offset = offset
    # yapf: disable
    header = WaveHeader(
        b0      = w_file.read_byte(),
        b1      = w_file.read_byte(),
        sample  = w_file.read_little_endian(4),
        attack  = w_file.read_byte(),
        decay   = w_file.read_byte(),
        sustain = w_file.read_byte(),
        release = w_file.read_byte()
    )
    # yapf: enable
    return header


def signed_byte_to_integer(signed_byte: int) -> int:
    """Convert a signed 4-byte bytearray into a signed integer."""
    return unpack('i', signed_byte)


def slen_to_ticks(short_len: int) -> int:
    """Convert short length to MIDI ticks."""
    return SHORT_LEN.get(short_len)
