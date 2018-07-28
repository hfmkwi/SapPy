# -*- coding: utf-8 -*-
"""Data-storage containers for internal use."""
import copy
import math
from collections import OrderedDict
from enum import IntEnum
from queue import Queue
from random import random
from typing import Dict, List, NamedTuple, Union, Tuple

from .config import (BASE_FREQUENCY, PSG_SQUARE_FREQUENCY, PSG_SQUARE_VOLUME,
                     PSG_WAVEFORM_FREQUENCY, PSG_WAVEFORM_SIZE, SEMITONE_RATIO)
from .exceptions import InvalidArgument
from .fmod import (get_mute, set_frequency, set_mute, set_panning, set_volume)
from .inst_set import KeyArg, c_v, mxv

NOTES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')


class M4AVoiceMode(IntEnum):
    DIRECTSOUND = 0x0
    PSG_SQUARE1 = 0x1
    PSG_SQUARE2 = 0x2
    PSG_WAVE = 0x3
    PSG_NOISE = 0x4
    FIX_DSOUND = 0x8
    KEY_ZONE = 0x40
    PERCUSSION = 0x80
    NULL = 0xFF


# region VOICE STRUCTS


class M4AVoice(object):
    """Voice base class."""

    def __init__(self, mode: int, root: int, attack: int, decay: int,
                 sustain: int, release: int) -> None:
        self._validate(mode, root)
        self.mode: M4AVoiceMode = mode
        self.root: KeyArg = root
        self.envelope: SoundEnvelope = SoundEnvelope(attack, decay, sustain,
                                                     release)
        self.fmod_handle = None
        self.mode = M4AVoiceMode(self.mode)
        self.root = KeyArg(self.root)

    def __repr__(self):
        return f'M4AVoice(mode=0x{self.mode:<X}, root={self.root}, ' \
               f'envelope={self.envelope})'

    @staticmethod
    def _validate(mode, root) -> None:
        try:
            M4AVoiceMode(mode)
        except ValueError:
            raise InvalidArgument(mode, 'VOICE MODE')
        try:
            KeyArg(root)
        except ValueError:
            raise InvalidArgument(root, 'ROOT KEY')


class M4APSGVoice(M4AVoice):
    """PSG Voice base class."""

    def __init__(self, mode: int, root: int, time_ctrl: int, attack: int,
                 decay: int, sustain: int, release: int) -> None:
        attack = 255 - attack * 32
        decay *= 32
        sustain *= 16
        release *= 32

        super().__init__(mode, root, attack, decay, sustain, release)
        self._validate(mode, root)

        self.time_ctrl: int = time_ctrl

    def __repr__(self):
        return f'M4APSGVoice(mode=0x{self.mode:<X}, root={self.root}, ' \
               f'time_ctrl={self.time_ctrl}, envelope={self.envelope})'

    @staticmethod
    def _validate(mode, root) -> None:
        M4AVoice._validate(mode, root)
        if mode in (0x0, 0x8):
            raise InvalidArgument(mode, 'PSG MODE')


class M4ADirectSound(M4AVoice):
    """M4A DirectSound voice entry."""

    def __init__(self, mode: int, root: int, panning: int, sample_ptr: int,
                 attack: int, decay: int, sustain: int, release: int) -> None:
        super().__init__(mode, root, attack, decay, sustain, release)
        self.fixed: bool = self.mode == M4AVoiceMode.FIX_DSOUND
        self.panning: int = panning
        self.sample_ptr: int = sample_ptr


class M4ASquare1(M4APSGVoice):
    """M4A PSG Square1 entry."""

    def __init__(self, root: int, time_ctrl: int, sweep: int,
                 duty_cycle: int, attack: int, decay: int, sustain: int,
                 release: int) -> None:
        super().__init__(M4AVoiceMode.PSG_SQUARE1, root, time_ctrl, attack,
                         decay, sustain, release)
        self.sweep: int = sweep
        self.duty_cycle: int = duty_cycle
        self.sample_ptr: str = f'square{self.duty_cycle}'

    def __repr__(self):
        return f'M4ASquare1(root={self.root}, time_ctrl={self.time_ctrl}, ' \
               f'sweep={self.sweep}, envelope={self.envelope})'


class M4ASquare2(M4APSGVoice):
    """M4A PSG Square2 entry."""

    def __init__(self, root: int, time_ctrl: int, duty_cycle: int,
                 attack: int, decay: int, sustain: int, release: int) -> None:
        super().__init__(M4AVoiceMode.PSG_SQUARE2, root, time_ctrl, attack,
                         decay, sustain, release)
        self.duty_cycle: int = duty_cycle
        self.sample_ptr: str = f'square{self.duty_cycle}'


class M4AWaveform(M4APSGVoice):
    """M4A PSG Waveform entry."""

    def __init__(self, root: int, time_ctrl: int, sample_ptr: int, attack: int,
                 decay: int, sustain: int, release: int) -> None:
        super().__init__(M4AVoiceMode.PSG_WAVE, root, time_ctrl, attack, decay,
                         sustain, release)
        self.sample_ptr: int = sample_ptr


class M4ANoise(M4APSGVoice):
    """M4A PSG Noise entry."""

    def __init__(self, root: int, time_ctrl: int, period: int, attack: int,
                 decay: int, sustain: int, release: int) -> None:
        super().__init__(M4AVoiceMode.PSG_NOISE, root, time_ctrl, attack, decay,
                         sustain, release)
        self.period: int = period
        self.sample_ptr: str = f'noise{self.period}'


class M4ADrum(M4AVoice):
    """M4A Percussion voice entry."""

    def __init__(self, voice_table: Dict) -> None:
        """Initialize every key-split instrument using track data."""
        super().__init__(M4AVoiceMode.PERCUSSION, 0x0, 0x0, 0x0, 0x00, 0x0)
        self.voice_table: Dict[int, M4AVoice] = voice_table


class M4AKeyZone(M4AVoice):
    """M4A Key-zone voice entry."""

    def __init__(self, voice_table: Dict, keymap: Dict) -> None:
        """Initialize key-split instrument using track data."""
        super().__init__(M4AVoiceMode.KEY_ZONE, 0x0, 0x0, 0x0, 0x00, 0x0)
        self.voice_table: Dict[int, M4AVoice] = voice_table
        self.keymap: Dict[int, int] = keymap


# endregion

# region SAMPLE STRUCTS


class M4ASample(object):
    """Sample base class."""

    def __init__(self, looped: bool, frequency: int, loop_start: int,
                 sample_data: bytes) -> None:
        self.looped = looped
        self.frequency = frequency
        self.loop_start = loop_start
        self.sample_data = sample_data

        self.fmod_handle = None

    def __repr__(self):
        return f'{self.__class__.__name__}(looped=0x{self.looped:X}, ' \
               f'frequency=0x{self.frequency:X}, ' \
               f'loop_start={self.loop_start}, size={self.size})'

    @property
    def size(self):
        return len(self.sample_data)


class M4ADirectSoundSample(M4ASample):
    """PCM8 DirectSound sample."""

    def __init__(self, looped: int, frequency: int, loop_start: int,
                 sample_data: bytes) -> None:
        self._valid = self._is_valid(looped, loop_start, sample_data)
        super().__init__(looped == 0x40, frequency // 1024, loop_start,
                         sample_data)

    @staticmethod
    def _is_valid(looped, loop_start, sample_data):
        c_loop = looped in (0x0, 0x40)
        c_loop_st = 0 <= loop_start <= len(sample_data)
        return all((c_loop, c_loop_st))

    def is_valid(self):
        return self._valid


class M4ASquareSample(M4ASample):
    """PSG Square1/Square2 sample."""

    VARIANCE = int(0x7F * PSG_SQUARE_VOLUME)
    SQUARE_SIZE = 8
    CYCLES = tuple(map(int, (SQUARE_SIZE * .125, SQUARE_SIZE * .25,
                             SQUARE_SIZE * .5, SQUARE_SIZE * .75)))

    def __init__(self, duty_cycle: int):
        self.duty_cycle = duty_cycle
        data = self.square_wave(duty_cycle)
        super().__init__(True, PSG_SQUARE_FREQUENCY, 0, data)

    def __repr__(self):
        return f'M4ASquareSample(duty_cycle={self.duty_cycle})'

    @staticmethod
    def square_wave(duty_cycle: int) -> bytes:
        h_cycle = M4ASquareSample.CYCLES[duty_cycle]
        l_cycle = M4ASquareSample.SQUARE_SIZE - h_cycle
        high = h_cycle * [0x80 + M4ASquareSample.VARIANCE]
        low = l_cycle * [0x80 - M4ASquareSample.VARIANCE]
        wave = (high + low)
        return bytes(wave)


class M4AWaveformSample(M4ASample):
    """PSG Programmable Waveform sample."""

    def __init__(self, sample_data: bytes) -> None:
        super().__init__(True, PSG_WAVEFORM_FREQUENCY, 0, sample_data)

    @property
    def is_looped(self) -> bool:
        return True

    @property
    def size(self) -> int:
        return PSG_WAVEFORM_SIZE


class M4ANoiseSample(M4ASample):
    """PSG Noise sample."""

    VARIANCE = int(0x7F * PSG_SQUARE_VOLUME)

    def __init__(self, period: int):
        self.validate(period)
        data = self.noise(period)
        super().__init__(True, 7040, 0, data)

    @staticmethod
    def validate(period: int) -> None:
        if not 0 <= period <= 1:
            raise InvalidArgument(period, 'NOISE PERIOD')

    @staticmethod
    def noise(period: int) -> bytes:
        """Generate noise sample."""
        if period == 0:
            samples = 32767
        elif period == 1:
            samples = 127
        else:
            raise InvalidArgument(period, 'NOISE PERIOD')
        high = 0x80 + M4ASquareSample.VARIANCE
        low = 0x80 - M4ASquareSample.VARIANCE
        noise_data = [high if random() > .5 else low for _ in range(samples)]
        return bytes(noise_data)


# endregion


class SoundDriverMode(NamedTuple):
    """GBA SoundDriverMode call."""

    reverb: int = 0
    reverb_enabled: bool = False
    polyphony: int = 8
    volume_ind: int = 15
    freq_ind: int = 4
    dac_ind: int = 9

    _DEFAULT = 0x0094F800
    _FREQUENCY_TABLE = {
        1:  5734,
        2:  7884,
        3:  10512,
        4:  13379,
        5:  15768,
        6:  18157,
        7:  21024,
        8:  26758,
        9:  31536,
        10: 36314,
        11: 40137,
        12: 42048
    }
    _DAC_TABLE = {
        8:  9,
        9:  8,
        10: 7,
        11: 6
    }

    @property
    def volume(self):
        """Return volume."""
        return self.volume_ind * 17

    @property
    def frequency(self):
        """Return sample rate."""
        return self._FREQUENCY_TABLE[self.freq_ind]

    @property
    def dac(self):
        """Return D/A converter bits."""
        return self._DAC_TABLE[self.dac_ind]


class SoundEnvelope(object):
    """M4A ADSR sound envelope."""

    ATTACK = 0
    DECAY = 1
    SUSTAIN = 2
    RELEASE = 3
    NOTE_OFF = 4

    def __init__(self, attack: int, decay: int, sustain: int,
                 release: int) -> None:
        """Initialize envelope to M4AVoice ADSR settings."""
        self.phase = self.ATTACK

        self.attack = attack
        self.decay = decay
        self.sustain = sustain
        self.release = release

        self._rate = self.attack
        self.env_pos = 0

    def __repr__(self):
        return f'SoundEnvelope({self.attack}, {self.decay}, {self.sustain}, ' \
               f'{self.release})'

    def note_off(self) -> None:
        """Switch to RELEASE phase on note-off."""
        if self.phase >= self.RELEASE:
            return
        self.phase = self.RELEASE
        self._rate = self.release / 256

    def update(self) -> int:
        """Update sound envelope phase."""
        if self.phase == self.ATTACK:
            self.env_pos += self._rate
            if self.env_pos >= 255:
                self.phase = self.DECAY
                self.env_pos = 255
                self._rate = self.decay / 256
        if self.phase == self.DECAY:
            self.env_pos = int(self.env_pos * self._rate)
            if self.env_pos <= self.sustain:
                self.phase = self.SUSTAIN
                self.env_pos = self.sustain
        if self.phase == self.SUSTAIN:
            pass
        if self.phase == self.RELEASE:
            self.env_pos = int(self.env_pos * self._rate)
            if self.env_pos <= 0:
                self.phase = self.NOTE_OFF
        if self.phase == self.NOTE_OFF:
            return -1
        return self.env_pos


class MetaData(NamedTuple):
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
    def echo_enabled(self) -> bool:
        """Track reverb flag."""
        return bin(self.reverb)[2:][0] == '1'

    @property
    def code(self) -> str:
        """ROM production code."""
        return f'AGB-{self.rom_code}-{self.region}'

    @property
    def region(self) -> str:
        """ROM region code."""
        return self.REGION.get(self.rom_code[3], 'UNK')


class FMODNote(object):
    """FMOD note."""

    def __init__(self, ticks: int, midi_note: int, velocity: int,
                 voice: int) -> None:
        """Initialize note from track data."""
        self.note_off: bool = False

        self.voice: int = voice
        self.midi_note: int = midi_note
        self.velocity: int = velocity
        self.ticks: int = ticks
        self.lfo_pos: float = 0.0

        self.frequency: int = 0
        self.envelope: SoundEnvelope = ...
        self.fmod_handle: int = 0

    def __repr__(self):
        return f'Note({self.midi_note}, {self.velocity}, {self.ticks}, ' \
               f'{self.voice})'

    __str__ = __repr__

    # region PROPERTIES

    @property
    def volume(self) -> float:
        """Return volume of note."""
        return self.velocity / 0x7F * self.envelope.env_pos / 0xFF

    @property
    def muted(self) -> bool:
        """Return mute state in FMOD."""
        return get_mute(self.fmod_handle)

    # endregion

    def reset_mixer(self, voice: M4AVoice) -> None:
        """Install new voice envelope."""
        self.envelope = copy.copy(voice.envelope)

    def release(self) -> None:
        """Change note state to note-off."""
        self.envelope.note_off()
        self.note_off = True

    def update(self) -> None:
        """Update note state."""
        if self.ticks > 0:
            self.ticks -= 1
        if self.ticks == 0:
            self.release()

    def update_envelope(self) -> None:
        """Update sound envelope for this note."""
        pos = self.envelope.update()
        if pos == -1:
            self.set_mute(True)

    # region FMOD FUNCTIONS

    def set_panning(self, panning: int) -> None:
        set_panning(self.fmod_handle, panning)

    def set_volume(self, volume: int) -> None:
        set_volume(self.fmod_handle, volume)

    def set_frequency(self, frequency: int) -> None:
        set_frequency(self.fmod_handle, frequency)

    def set_mute(self, state: bool) -> None:
        set_mute(self.fmod_handle, state)

    # endregion


class M4ASong(NamedTuple):
    """M4A song."""

    tracks: List['M4ATrack'] = []
    voices: Dict[int, M4AVoice] = {}
    samples: Dict[Union[int, str], M4ASample] = {}
    meta_data: 'MetaData' = MetaData()
    sdm: SoundDriverMode = None


class M4ATrack(object):
    """M4A Track."""

    NO_VOICE = -1
    TEMPO = 75
    KEY_SHIFT = 0

    def __init__(self, track_data: OrderedDict):
        """Initialize blank track."""

        self.enabled: bool = True
        self.track_data: OrderedDict = track_data
        self.cmd_addresses: Tuple[int] = tuple(track_data.keys())
        self.commands: Tuple = tuple(track_data.values())
        self.voices: Tuple[int] = ()
        self.notes: List[FMODNote] = []
        self.note_queue: Queue[FMODNote] = Queue()
        self.call_stack: Queue[int] = Queue(maxsize=3)

        self.type: M4AVoiceMode = M4AVoiceMode.NULL
        self.voice: int = M4ATrack.NO_VOICE

        self.key_shift: int = 0
        self._volume: int = mxv
        self._panning: int = c_v

        self.pitch_bend: int = c_v
        self.pitch_range: int = 2

        self.mod: int = 0
        self.lfo_speed: int = 0
        self.lfo_pos: int = 0

        self.ticks: int = 0
        self.program_ctr: int = 0
        self.return_ctr: int = 0
        self.base_ctr: int = 0
        self.in_patt: bool = False

        self.out_vol: int = 0

    # region PROPERTIES

    @property
    def volume(self) -> float:
        return self._volume / 0x7F

    @volume.setter
    def volume(self, volume: int) -> None:
        self._volume = volume

    @property
    def panning(self) -> int:
        return self._panning * 2

    @panning.setter
    def panning(self, panning: int) -> None:
        self._panning = panning

    @property
    def frequency(self) -> float:
        pitch = (self.pitch_bend - c_v) / c_v * self.pitch_range
        return math.pow(SEMITONE_RATIO, pitch)

    # endregion

    def update(self) -> None:
        """Execute M4A track commands and decrement wait counter."""
        if not self.enabled:
            return
        if self.ticks > 0:
            self.ticks -= 1
        if self.ticks == 0:
            self.base_ctr = self.program_ctr
        while self.ticks == 0 and self.enabled:
            cmd = self.commands[self.program_ctr]
            cmd(self)

        for note in self.notes:
            note.update()

    def update_envelope(self):
        self.out_vol = 0
        for note in self.notes[::]:
            note.update_envelope()
            if note.muted:
                continue
            volume = round(self.volume * note.volume * 255)
            if self.type in (M4AVoiceMode.PSG_SQUARE1, M4AVoiceMode.PSG_SQUARE2,
                             M4AVoiceMode.PSG_NOISE):
                volume = 15 * round(volume / 15)
            self.out_vol = volume
            note.set_volume(volume)


def note_name(midi_note: int) -> str:
    """Retrieve the string name of a MIDI note from its byte representation."""
    octave, note = divmod(midi_note, 12)
    octave -= 2
    return f'{NOTES[note]}{"M" if octave < 0 else ""}{abs(octave)}'


def resample(midi_note: int, relative_c_freq: int = -1) -> int:
    """Retrieve the sound frequency in Hz of a MIDI note relative to C3."""
    note = midi_note - KeyArg.Cn3
    if relative_c_freq < 0:
        base_freq = BASE_FREQUENCY // abs(relative_c_freq)
        relative_c_freq = base_freq * math.pow(SEMITONE_RATIO, 3)
    else:
        relative_c_freq = relative_c_freq

    freq = relative_c_freq * math.pow(SEMITONE_RATIO, note)
    return int(freq)
