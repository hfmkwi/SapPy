#-*- coding: utf-8 -*-
"""Data-storage containers for internal use."""
import collections
import enum
import typing

import sappy.fileio as fileio

NOTES = {
    0: 'C',
    1: '#C',
    2: 'D',
    3: '#D',
    4: 'E',
    5: 'F',
    6: '#F',
    7: 'G',
    8: '#G',
    9: 'A',
    10: '#A',
    11: 'B'
}

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


class ChannelTypes(enum.IntEnum):
    """Possible output types for each sound channel."""

    DIRECT = 0
    SQUARE1 = 1
    SQUARE2 = 2
    WAVE = 3
    NOISE = 4
    UNK5 = 5
    UNK6 = 6
    UNK7 = 7
    MULTI = 8
    DRUMKIT = 9
    NULL = 255


class DirectTypes(enum.IntEnum):
    """Possible outputs for DirectSound note."""

    DIRECT = 0
    SQUARE1 = 1
    SQUARE2 = 2
    WAVEFORM = 3
    NOISE = 4
    UNK5 = 5
    UNK6 = 6
    UNK7 = 7


class NoteTypes(enum.IntEnum):
    """Declare possible outputs for the Note object."""

    DIRECT = 0
    SQUARE1 = 1
    SQUARE2 = 2
    WAVEFORM = 3
    NOISE = 4
    UNK5 = 5
    UNK6 = 6
    UNK7 = 7


class NotePhases(enum.IntEnum):
    """Declare possible phases for the Note object."""

    INITIAL = 0
    ATTACK = 1
    DECAY = 2
    SUSTAIN = 3
    RELEASE = 4
    NOTEOFF = 5


class Type(object):
    """Custom type object"""
    __slots__ = ()

    def __str__(self):
        attr = []
        for name in self.__slots__:
            obj = getattr(self, name)
            try:
                value = repr(obj)
            except:
                value = str(obj)
            attr.append(f'{name}={value}, ')
        attr = ''.join(attr)

        template = f'{self.__class__.__name__}({attr})'
        return template

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class Channel(Type):
    """Sound channel"""

    def __init__(self):
        self.is_enabled: bool = True
        self.is_muted: bool = False
        self.in_subroutine: bool = False
        self.is_sustain: bool = False
        self.wait_ticks: float = -1.0
        self.loop_ptr: int = 0
        self.main_volume: int = 100
        self.panning: int = 0x40
        self.patch_num: int = 0x00
        self.pitch_bend: int = 0x40
        self.pitch_range: int = 2
        self.program_ctr: int = 0
        self.priority: int = 0
        self.return_ptr: int = 0
        self.subroutine_ctr: int = 0
        self.subroutine_loop_cnt: int = 1
        self.track_len: int = 0
        self.track_ptr: int = 0
        self.transpose: int = 0
        self.vib_depth: int = 0
        self.vib_rate: int = 0
        self.output_volume: int = 0
        self.notes_playing: list = []
        self.key: str = ''
        self.output_type: ChannelTypes = ChannelTypes.DIRECT
        self.event_queue: typing.List = []
        self.notes: typing.Dict = {}
        self.subroutines: typing.List = []


class Direct(Type):
    """DirectSound instrument."""
    __slots__ = ('reverse', 'fix_pitch', 'env_atck', 'env_dcy', 'env_sus',
                 'env_rel', 'raw0', 'raw1', 'gb1', 'gb2', 'gb3', 'gb4',
                 'drum_key', 'key', 'smp_id', 'output')

    def __init__(self):
        self.reverse: bool = False
        self.fix_pitch: bool = False
        self.env_atck: int = 0x00
        self.env_dcy: int = 0x00
        self.env_sus: int = 0x00
        self.env_rel: int = 0x00
        self.raw0: int = 0x00
        self.raw1: int = 0x00
        self.gb1: int = 0x00
        self.gb2: int = 0x00
        self.gb3: int = 0x00
        self.gb4: int = 0x00
        self.drum_key: int = 0x3C
        self.smp_id: str = ''
        self.output: int = DirectTypes.DIRECT


class DrumKit(Type):
    """Represents a drumkit; contains a queue of DirectSound instruments."""
    __slots__ = ('key', 'directs')

    def __init__(self, directs: typing.Dict = {}):
        self.directs = directs


class Event(Type):
    """Internal event."""
    __slots__ = ('cmd_byte', 'arg1', 'arg2', 'arg3', 'ticks')

    def __init__(
            self,
            ticks: int = 0,
            cmd_byte: int = 0,
            arg1: int = 0,
            arg2: int = 0,
            arg3: int = 0,
    ):
        self.cmd_byte: int = cmd_byte
        self.arg1: int = arg1
        self.arg2: int = arg2
        self.arg3: int = arg3
        self.ticks: int = ticks


class Instrument(Type):
    """Represents an instrument; uses a DirectSound queue to hold sound samples."""
    __slots__ = ('directs', 'keymaps')

    def __init__(self, directs: typing.Dict = {}, keymaps: typing.Dict = {}):
        self.directs = directs
        self.keymaps = keymaps


class Note(Type):
    """Container representing a single note in the AGB sound engine."""
    __slots__ = ('enable', 'note_off', 'env_dest', 'env_pos', 'env_step',
                 'vib_pos', 'wait_ticks', 'env_atck', 'env_dcy', 'env_rel',
                 'env_sus', 'fmod_channel', 'frequency', 'note_num', 'parent',
                 'patch_num', 'unk_val', 'smp_id', 'output',
                 'phase', 'fmod_fx', 'velocity')

    def __init__(self, note_num: int, velocity: int, parent: int, unk_val: int,
                 wait_ticks: float, patch_num: int):
        self.enable: bool = True
        self.note_off: bool = False
        self.env_dest: float = 0.0
        self.env_pos: float = 0.0
        self.env_step: float = 0.0
        self.vib_pos: float = 0.0
        self.wait_ticks: float = wait_ticks
        self.env_atck: int = 0x00
        self.env_dcy: int = 0x00
        self.env_rel: int = 0x00
        self.env_sus: int = 0x00
        self.fmod_channel: int = 0
        self.fmod_fx: int = 0
        self.frequency: int = 0
        self.note_num: int = note_num
        self.parent: int = parent
        self.patch_num: int = patch_num
        self.unk_val: int = unk_val
        self.smp_id: str = ''
        self.output: NoteTypes = NoteTypes.DIRECT
        self.phase: NotePhases = NotePhases.INITIAL
        self.velocity: int = velocity


class Sample(Type):
    """Sound sample for use during playback."""

    def __init__(self,
                 smp_data: str,
                 size: int,
                 freq: int = 0,
                 fmod_smp: int = 0,
                 loop_start: int = 0,
                 loop: bool = True,
                 gb_wave: bool = True):
        self.gb_wave: bool = gb_wave
        self.loop: bool = loop
        self.fmod_smp: int = fmod_smp
        self.frequency: int = freq
        self.loop_start: int = loop_start
        self.size: int = size
        self.smp_data: str = smp_data


def to_int(sbyte: int) -> int:
    """Convert a signed byte into a signed 4-byte integer."""
    return sbyte - 0x100 if sbyte >= 0x80 else sbyte


def to_ticks(short_len: int) -> int:
    """Convert short length to MIDI ticks."""
    return STLEN.get(short_len)


def to_name(midi_note: int) -> str:
    """Retrieve the string name of a MIDI note from its byte representation."""
    x = midi_note % 12
    o = midi_note // 12
    return NOTES.get(x) + str(o)


def to_frequency(midi_note: int, midc_freq: int = -1) -> int:
    """Retrieve the sound frequency in Hz of a MIDI note relative to C3."""
    import math
    magic = math.pow(2, 1 / 12)
    X = midi_note - 0x3C
    if midc_freq == -1:
        a = 7040
        c = a * math.pow(magic, 3)
    elif midc_freq == -2:
        a = 7040 / 2
        c = a * math.pow(magic, 3)
    else:
        c = midc_freq

    x = c * math.pow(magic, X)
    return int(x)
