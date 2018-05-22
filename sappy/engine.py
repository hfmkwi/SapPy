# -*- coding: utf-8 -*-
"""Data-storage containers for internal use."""
import collections
import copy
import enum
import math
import typing

import sappy.romio as romio
import sappy.cmdset as cmdset
import sappy.config as config
import sappy.fmod as fmod

NOTES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')


class OutputType(enum.IntEnum):
    """Track output types."""

    DSOUND = 0
    PSG_SQ1 = 1
    PSG_SQ2 = 2
    PSG_WAVE = 3
    PSG_NSE = 4
    MULTI = 8
    DRUM = 9
    NULL = 255


class SampleType(enum.IntEnum):
    """Sample types."""

    DSOUND = 0
    PSG_SQ1 = 1
    PSG_SQ2 = 2
    PSG_WAVE = 3
    PSG_NSE = 4
    NULL = 7


class PrintableType(object):
    """Imitation class for NamedTuple's string output."""

    __slots__ = ()

    def __str__(self):
        """Produce NamedTuple string representation."""
        attr = []
        for name in self.__slots__:
            obj = getattr(self, name)
            try:
                value = str(obj)
            except:
                value = repr(obj)
            attr.append(f'{name}={value}, ')
        attr = ''.join(attr)

        template = f'{self.__class__.__name__}({attr})'
        return template


class Track(PrintableType):
    """M4A Track."""

    def __init__(self):
        """Initialize blank track."""
        self.enabled: bool = True
        self.muted: bool = False
        self.loop_ptr: int = -1
        self.volume: int = cmdset.mxv
        self.panning: int = cmdset.c_v
        self.voice: int = 0
        self.pitch_bend: int = cmdset.c_v
        self.pitch_range: int = 2
        self.program_ctr: int = 0
        self.priority: int = 0
        self.wait_ticks: int = 0
        self.keysh: int = 0
        self.mod: int = 0
        self.lfos: int = 0
        self.out_vol: int = 0
        self.type: OutputType = OutputType.DSOUND
        self.track_data: typing.List = []
        self.used_notes: typing.List = []

    def advance(self) -> None:
        """Decrement tick counter."""
        if self.wait_ticks:
            self.wait_ticks -= 1


class Voice(PrintableType):
    """M4A voice."""

    __slots__ = ('resampled', 'mixer', 'psg_flag', 'midi_key', 'sample_ptr', 'type', 'time_len', 'sweep', 'panning')

    def __init__(self, voice: typing.Union[romio.PSGInstrument, romio.DirectSound]):
        """Intialize M4A voice using track data."""
        self.midi_key = voice.midi_key
        self.resampled = voice.mode == 0x08
        self.type = SampleType(voice.mode & 0b111)
        is_psg = type(voice) == romio.PSGInstrument
        if is_psg:
            self.time_len = voice.time_len
            self.sweep = voice.sweep
            self.psg_flag = voice.flag
            if self.type == SampleType.PSG_WAVE:
                self.sample_ptr = voice.flag
        else:
            self.time_len = None
            self.sweep = None
            self.psg_flag = None
            self.panning = voice.panning
            self.sample_ptr = voice.sample_ptr
        self.mixer = Mixer(voice.attack, voice.decay, voice.sustain, voice.release, is_psg)

class DrumKit(PrintableType):
    """M4A percussion (every key-split) instrument."""

    __slots__ = ('voice_table')

    def __init__(self, voice_table: typing.Dict = {}):
        """Intialize every key-split instrument using track data."""
        self.voice_table = voice_table

    @property
    def type(self):
        """Return output (DRUM)."""
        return OutputType.DRUM


class Command(PrintableType):
    """M4A Command."""

    __slots__ = ('cmd', 'arg1', 'arg2', 'arg3')

    def __init__(self, cmd: int = 0, arg1: int = 0, arg2: int = 0, arg3: int = 0):
        """Initialize command using parsed data."""
        self.cmd: int = cmd
        self.arg1: int = arg1
        self.arg2: int = arg2
        self.arg3: int = arg3

    def __str__(self):
        """Produce DWORD representation."""
        return f'0x{self.cmd:0X}{self.arg1:0X}{self.arg2:0X}{self.arg3:0X}'


class Instrument(PrintableType):
    """M4A key-split instrument."""

    __slots__ = ('voice_table', 'keymap')

    def __init__(self, voice_table: typing.Dict = {}, keymap: typing.Dict = {}):
        """Initialize key-split instrument using track data."""
        self.voice_table = voice_table
        self.keymap = keymap

    @property
    def type(self):
        """Return output (MULTI)."""
        return OutputType.MULTI


class Mixer(PrintableType):
    """M4A sound envelope."""

    __slots__ = ('phase', 'attack', 'decay', 'sustain', 'release', 'pos',
                 '_rate', '_dest', 'notes')

    ATTACK = 0
    DECAY = 1
    SUSTAIN = 2
    RELEASE = 3
    NOTEOFF = 4

    def __init__(self, attack: int, decay: int, sustain: int, release: int, is_psg: bool):
        """Intialize mixer to M4A Voice ADSR."""
        self.phase = self.ATTACK

        self.attack = attack
        self.decay = decay
        self.sustain = sustain
        self.release = release
        if is_psg:
            self.attack = 256 - attack * 32
            self.decay *= 32
            self.sustain *= 16
            self.release *= 32

        self._rate = self.attack
        self._dest = 0
        self.pos = 0
        self.notes = {}

    def reset(self) -> None:
        """Reset mixer to init state."""
        self.phase = self.ATTACK
        self.pos = 0
        self._rate = self.attack

    def note_off(self) -> None:
        """Switch to RELEASE phase on note-off."""
        if self.phase >= self.RELEASE:
            return
        self.phase = self.RELEASE
        self._rate = round(self.release / 256, 4)

    def update(self) -> int:
        """Update the sound envelope according to phase."""
        if self.phase == self.ATTACK:
            self.pos += self._rate
            if self.pos >= 255:
                self.phase = self.DECAY
                self.pos = 255
                self._rate = round(self.decay / 256, 4)
        if self.phase == self.DECAY:
            self.pos = int(self.pos * self._rate)
            if self.pos <= self.sustain:
                self.phase = self.SUSTAIN
                self.pos = self.sustain
        if self.phase == self.SUSTAIN:
            pass
        if self.phase == self.RELEASE:
            self.pos = int(self.pos * self._rate)
            if self.pos <= 1:
                self.phase = self.NOTEOFF
        if self.phase == self.NOTEOFF:
            return None
        return self.pos


class MetaData(typing.NamedTuple):
    """ROM/Track metadata."""

    REGION = {
        'J': 'JPN',
        'E': 'USA',
        'P': 'PAL',
        'D': 'DEU',
        'F': 'FRA',
        'I': 'ITA',
        'S': 'ESP'
    }

    rom_name: str = ...
    rom_code: str = ...
    tracks: int = ...
    reverb: int = ...
    priority: int = ...
    main_ptr: int = ...
    voice_ptr: int = ...
    song_ptr: int = ...
    unknown: int = ...

    @property
    def echo_enabled(self):
        """Track reverb flag."""
        return bin(self.reverb)[2:][0] == '1'

    @property
    def code(self):
        """ROM production code."""
        return f'GBA-{self.rom_code}-{self.region}'

    @property
    def region(self):
        """ROM region code."""
        return self.REGION.get(self.rom_code[3], 'UNK')


class Note(PrintableType):
    """GBA Note."""

    __slots__ = ('note_off', 'lfo_pos', 'wait_ticks', 'fmod_channel',
                 'frequency', 'midi_note', 'track', 'voice',
                 'sample_ptr', 'mixer', 'velocity')

    def __init__(self, midi_note: int, velocity: int, track: int, wait_ticks: int, voice: int):
        """Initialize note using track data."""
        self.reset(midi_note, velocity, track, wait_ticks, voice)
        self.lfo_pos: float = 0.0
        self.fmod_channel: int = 0
        self.frequency: int = 0
        self.sample_ptr: int = 0
        self.mixer: Mixer = ...

    def reset(self, midi_note: int, velocity: int, track: int, wait_ticks: float, voice: int):
        """Reset note using track data."""
        self.note_off = False
        self.midi_note = midi_note
        self.velocity = velocity
        self.track = track
        self.wait_ticks = wait_ticks
        self.voice = voice

    def advance(self) -> None:
        """Decrement tick counter."""
        if self.wait_ticks > 0:
            self.wait_ticks -= 1
        elif not self.note_off and self.wait_ticks == 0:
            self.note_off = True

    def reset_mixer(self, voice: Voice) -> None:
        """Overwrite current mixer with new voice mixer."""
        self.mixer = copy.copy(voice.mixer)
        self.mixer.reset()


class Sample(PrintableType):
    """FMOD Sample."""

    __slots__ = ('is_wave', 'loops', 'fmod_id', 'frequency', 'loop_start',
                 'size', 'sample_data')

    def __init__(self, sample_data: typing.List, size: int, freq: int = 0, fmod_id: int = 0, loop_start: int = 0, loops: bool = True, is_wave: bool = False):
        """Initialize sample using track data."""
        self.is_wave: bool = is_wave
        self.loops: bool = loops
        self.fmod_id: int = fmod_id
        self.frequency: int = freq
        self.loop_start: int = loop_start
        self.size: int = size
        self.sample_data: typing.List[int] = sample_data


class Song(object):
    """M4A song."""

    def __init__(self):
        """Initialize a blank song."""
        self.tracks = []
        self.note_queue = {}
        self.samples = {}
        self.voices = {}
        self.meta_data = MetaData()

    @property
    def used_notes(self):
        """Return used note IDs across all tracks."""
        return [n for c in self.tracks for n in c.used_notes]


def get_note_name(midi_note: int) -> str:
    """Retrieve the string name of a MIDI note from its byte representation."""
    octave, note = divmod(midi_note + config.TRANSPOSE, 12)
    octave -= 2
    return f'{NOTES[note]}{"M" if octave < 0 else ""}{abs(octave)}'


def resample(midi_note: int, midc_freq: int = -1) -> int:
    """Retrieve the sound frequency in Hz of a MIDI note relative to C3."""
    note = midi_note - cmdset.Key.Cn3
    if midc_freq < 0:
        base_freq = config.BASE_FREQUENCY // abs(midc_freq)
        c_freq = base_freq * math.pow(config.SEMITONE_RATIO, 3)
    else:
        c_freq = midc_freq

    freq = c_freq * math.pow(config.SEMITONE_RATIO, note)
    return round(freq)
