# -*- coding: utf-8 -*-
"""Data-storage containers for internal use."""
import collections
import enum
import math
import typing

import sappy.fileio as fileio
import sappy.instructions as instructions
import sappy.config as config

NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


class ChannelTypes(enum.IntEnum):
    """Possible output types for each sound channel."""

    DIRECT = 0
    SQUARE1 = 1
    SQUARE2 = 2
    WAVEFORM = 3
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
    """Base class offering string representation found in NamedTuple."""
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


class Channel(Type):
    """Sound channel"""

    def __init__(self):
        self.enabled: bool = True
        self.muted: bool = False
        self.loop_ptr: int = 0
        self.volume: int = instructions.mxv
        self.panning: int = instructions.c_v
        self.instrument_id: int = 0x00
        self.pitch_bend: int = instructions.c_v
        self.pitch_range: int = 2
        self.program_ctr: int = 0
        self.priority: int = 0
        self.wait_ticks: int = 0
        self.track_len: int = 0
        self.track_ptr: int = 0
        self.transpose: int = 0
        self.mod_depth: int = 0
        self.lfo_speed: int = 0
        self.output_volume: int = 0
        self.output_type: ChannelTypes = ChannelTypes.DIRECT
        self.event_queue: typing.List = []
        self.notes_playing: typing.List = []

        # Unused
        self.in_subroutine: bool = False
        self.subroutine_ctr: int = 0
        self.subroutine_loop_cnt: int = 1
        self.subroutines: typing.List = []
        self.return_ptr: int = 0


class Direct(Type):
    """DirectSound instrument."""
    __slots__ = ('reverse', 'fix_pitch', 'attack', 'decay', 'sustain',
                 'release', 'raw0', 'raw1', 'psg_flag', 'gb2', 'gb3', 'gb4',
                 'drum_key', 'bound_sample', 'output_type')

    def __init__(self):
        self.fix_pitch: bool = False
        self.attack: int = 0x00
        self.decay: int = 0x00
        self.sustain: int = 0x00
        self.release: int = 0x00
        self.psg_flag: int = 0x00
        self.drum_key: int = 0x3C
        self.bound_sample: str = ''
        self.output_type: int = DirectTypes.DIRECT

        # Unused
        self.reverse: bool = False
        self.raw0: int = 0x00
        self.raw1: int = 0x00
        self.gb2: int = 0x00
        self.gb3: int = 0x00
        self.gb4: int = 0x00


class DrumKit(Type):
    """Represents a drumkit; contains a queue of DirectSound instruments."""
    __slots__ = ('directs')

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

    def __str__(self):
        return f'0x{self.cmd_byte:X} 0x{self.arg1:X} 0x{self.arg2:X} 0x{self.arg3:X}'


class Instrument(Type):
    """Represents an instrument; uses a DirectSound queue to hold sound samples."""
    __slots__ = ('directs', 'keymaps')

    def __init__(self, directs: typing.Dict = {}, keymaps: typing.Dict = {}):
        self.directs = directs
        self.keymaps = keymaps


class Note(Type):
    """Container representing a single note in the AGB sound engine."""
    __slots__ = ('enable', 'note_off', 'env_dest', 'env_pos', 'env_step',
                 'lfos_position', 'wait_ticks', 'attack', 'decay', 'release',
                 'sustain', 'fmod_channel', 'frequency', 'note_num',
                 'parent_channel', 'instrument_id', 'bound_sample',
                 'output_type', 'phase', 'fmod_fx', 'velocity')

    def __init__(self,
                 note_num: int = 0,
                 velocity: int = 0,
                 parent: int = 0,
                 wait_ticks: float = 0.0,
                 patch_num: int = 0):
        self.enable: bool = True
        self.note_off: bool = False
        self.env_dest: float = 0.0
        self.env_pos: float = 0.0
        self.env_step: float = 0.0
        self.lfos_position: float = 0.0
        self.wait_ticks: float = wait_ticks
        self.attack: int = 0x00
        self.decay: int = 0x00
        self.release: int = 0x00
        self.sustain: int = 0x00
        self.fmod_channel: int = 0
        self.fmod_fx: int = 0
        self.frequency: int = 0
        self.note_num: int = note_num
        self.parent_channel: int = parent
        self.instrument_id: int = patch_num
        self.bound_sample: str = ''
        self.output_type: NoteTypes = NoteTypes.DIRECT
        self.phase: NotePhases = NotePhases.INITIAL
        self.velocity: int = velocity

    def set_mixer_props(self, direct_sound: Direct) -> None:
        props = direct_sound.output_type, direct_sound.attack, direct_sound.decay, direct_sound.sustain, direct_sound.release
        self.output_type, self.attack, self.decay, self.sustain, self.release = props


class Sample(Type):
    """Sound sample for use during playback."""

    def __init__(self,
                 smp_data: str,
                 size: int,
                 freq: int = 0,
                 fmod_id: int = 0,
                 loop_start: int = 0,
                 loop: bool = True,
                 gb_wave: bool = True):
        self.gb_wave: bool = gb_wave
        self.loop: bool = loop
        self.fmod_id: int = fmod_id
        self.frequency: int = freq
        self.loop_start: int = loop_start
        self.size: int = size
        self.smp_data: str = smp_data


def get_note(midi_note: int) -> str:
    """Retrieve the string name of a MIDI note from its byte representation."""
    octave, note = divmod(midi_note + config.TRANSPOSE, 12)
    octave -= 2
    return f'{NOTES[note]}{"M" if octave < 0 else ""}{abs(octave)}' # pylint: disable=E1101


def get_frequency(midi_note: int, midc_freq: int = -1) -> int:
    """Retrieve the sound frequency in Hz of a MIDI note relative to C3."""

    note = midi_note - instructions.Key.Cn3
    if midc_freq == -1:  # is A8 or A7
        base_freq = config.A8_FREQUENCY
        c_freq = base_freq * math.pow(config.SEMITONE_RATIO, 3)
    elif midc_freq == -2:
        base_freq = config.A8_FREQUENCY // 2
        c_freq = base_freq * math.pow(config.SEMITONE_RATIO, 3)
    else:
        c_freq = midc_freq

    freq = c_freq * math.pow(config.SEMITONE_RATIO, note)
    return round(freq)
