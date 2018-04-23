# -*- coding: utf-8 -*-
"""All playback related functionality for the Sappy Engine.

Attributes
----------
BASE: float
    Base multiplier for calculating MIDI note frequencies from the base 440Hz

"""
import enum
import logging
import math
import os
import random
import sys
import time
import typing

import sappy.parser as parser
import sappy.engine as engine
import sappy.fileio as fileio
import sappy.fmod as fmod

BASE = math.pow(2, 1 / 12)

# Box characters
LIGHT = 0
HEAVY = 1
BOX_STYLE = HEAVY
if BOX_STYLE == LIGHT:
    HORIZONTAL = '─'
    VERTICAL = '│'
    DOWN_AND_RIGHT = '┌'
    DOWN_AND_LEFT = '┐'
    UP_AND_RIGHT = '└'
    UP_AND_LEFT = '┘'
    VERTICAL_AND_RIGHT = '├'
    VERTICAL_AND_LEFT = '┤'
    DOWN_AND_HORIZONTAL = '┬'
    UP_AND_HORIZONTAL = '┴'
    VERTICAL_AND_HORIZONTAL = '┼'
elif BOX_STYLE == HEAVY:
    HORIZONTAL = '━'
    VERTICAL = '┃'
    DOWN_AND_RIGHT = '┏'
    DOWN_AND_LEFT = '┓'
    UP_AND_RIGHT = '┗'
    UP_AND_LEFT = '┛'
    VERTICAL_AND_RIGHT = '┣'
    VERTICAL_AND_LEFT = '┫'
    DOWN_AND_HORIZONTAL = '┳'
    UP_AND_HORIZONTAL = '┻'
    VERTICAL_AND_HORIZONTAL = '╋'
else:
    raise ValueError('Invalid line style.')

TEMPO_TOP = f'{DOWN_AND_HORIZONTAL}{"":{HORIZONTAL}>7}{DOWN_AND_LEFT}'
TEMPO_BOTTOM = f'{VERTICAL_AND_HORIZONTAL}{"":{HORIZONTAL}>7}{VERTICAL_AND_LEFT}'

# Block characters
H_BOX = 0
V_BOX = 1
BLOCK_STYLE = H_BOX
FULL_BLOCK = '█'
if BLOCK_STYLE == H_BOX:
    ONE_EIGHTH_BLOCK = '▏'
    ONE_QUARTER_BLOCK = '▎'
    THREE_EIGHTHS_BLOCK = '▍'
    HALF_BLOCK = '▌'
    FIVE_EIGHTHS_BLOCK = '▋'
    THREE_QUARTERS_BLOCK = '▊'
    SEVEN_EIGHTHS_BLOCK = '▉'
elif BLOCK_STYLE == V_BOX:
    ONE_EIGHTH_BLOCK = '▁'
    ONE_QUARTER_BLOCK = '▂'
    THREE_EIGHTHS_BLOCK = '▃'
    HALF_BLOCK = '▄'
    FIVE_EIGHTHS_BLOCK = '▅'
    THREE_QUARTERS_BLOCK = '▆'
    SEVEN_EIGHTHS_BLOCK = '▇'
else:
    raise ValueError('Invalid block style.')

BLOCK_TABLE = {
    0: FULL_BLOCK,
    1: SEVEN_EIGHTHS_BLOCK,
    2: THREE_QUARTERS_BLOCK,
    3: FIVE_EIGHTHS_BLOCK,
    4: HALF_BLOCK,
    5: THREE_EIGHTHS_BLOCK,
    6: ONE_QUARTER_BLOCK,
    7: ONE_EIGHTH_BLOCK
}


class InstructionSet(enum.IntEnum):
    pass


class Player(object):
    """Front-end class for simulating Sappy engine playback.

    Attributes
    ----------
    DEBUG : bool
        Toggles the output of debug text by the logger
    GB_SQ_MULTI : float
        A number in the range 0.0 - 1.0 controlling the peaks of the high and
        low periods of square waves.
    SAPPY_PPQN : int
        A number controlling the number of ticks/second the processor runs at
    WIDTH : int
        A number greater than 17 controlling the column width per channel for
        the front-end user interface

    """

    SHOW_PROCESSOR_EXECUTION = False
    SHOW_FMOD_EXECUTION = False
    DISPLAY_NOTES = False

    INSTRUCTIONS_PER_CYCLE = 2.5
    INSTRUCTIONS_PER_ = 24

    GB_SQ_MULTI = .5
    WIDTH = 33

    logging.basicConfig(level=logging.DEBUG)
    PROCESSOR_LOGGER = logging.getLogger('PROCESSOR')
    FMOD_LOGGER = logging.getLogger('FMOD')
    if not SHOW_PROCESSOR_EXECUTION:
        PROCESSOR_LOGGER.setLevel(logging.WARNING)
    if not SHOW_FMOD_EXECUTION:
        FMOD_LOGGER.setLevel(logging.WARNING)

    def __init__(self, volume=255):
        """Initialize all relevant playback data to default values.

        Parameters
        ----------
        volume : int
            An integer in the range 0 - 255 to initialize the global volume.

        Attributes
        ----------
        looped : bool
            A flag set when the song jumps to a valid address in the track
            data and 'loops'.

        _global_vol : int
            An integer in the range 0 - 255 holding the current volume
            level for the delegate public property.

        gb1_channel : int
            An integer in the range -1 - 31 representing the last note
            played on the PSG Square 1 channel.

        gb2_channel : int
            An integer in the range -1 - 31 representing the last note
            played on the PSG Square 2 channel.

        gb3_channel : int
            An integer in the range -1 - 31 representing the last note
            played on the PSG Programmable Waveform channel.

        gb4_channel : int
            An integer in the range -1 - 31 representing the last note
            played on the PSG Noise channel.

        tempo : int
            A positive integer representing the tempo in BPM
            of the current notes_playing song.

        transpose : int
            An integer representing the number of whole pitch-tones to
            shift the base frequency calculation.

        noise_waves : typing.List[typing.List[str]]
            An array of 2 nested arrays containing 16383-sample and
            256-sample noise waves, respectively, in string form.

        note_arr : engine.Collection[engine.Note]
            An array of 32 programmable notes utilized during playback.

        channels : typing.List[engine.Channel]
            A VB6 collection containing all virtual tracks utilized during
            playback.

        directs : engine.DirectQueue[engine.Direct]
            A VB6 collection containing all virtual DirectSound samples
            utilized during playback.

        drumkits : engine.DrumKitQueue[engine.DrumKit]
            A VB6 collection containing all virtual DirectSound drumkit
            samples utilized during playback.

        insts : engine.InstrumentQueue[engine.Instrument]
            A VB6 collection containing all virtual instruments
            (DirectSound sample wrappers) utilized during playback.

        note_queue : engine.NoteQueue[engine.NoteID]
            A VB6 collection containing the IDs of all virtual notes
            currently in playback.

        samples : typing.Dict[engine.Sample]
            A VB6 collection containing all runtime samples utilized
            during playback.


        """
        self._global_vol = volume
        self.looped = False
        self.psg_channels = {
            engine.NoteTypes.SQUARE1: None,
            engine.NoteTypes.SQUARE2: None,
            engine.NoteTypes.WAVEFORM: None,
            engine.NoteTypes.NOISE: None,
        }
        self.tempo = 0
        self.note_arr = [engine.Note(*[0] * 6)] * 32
        self.channels = []
        self.directs = {}
        self.drumkits = {}
        self.insts = {}
        self.note_queue = []
        self.samples = {}
        self.transpose = 0

    @property
    def global_vol(self) -> int:
        """Global volume of the player.

        The volume must be in the range (0 - 255). Anything above 255 will
        truncate down to 255; similarly, anything below 0 will truncate to 0.

        """
        return self._global_vol

    @global_vol.setter
    def global_vol(self, volume: int) -> None:
        if volume < 0:
            volume = 0
        elif volume > 255:
            volume = 255
        self._global_vol = volume
        fmod.setMasterVolume(self._global_vol)

    def debug_fmod(self, action: str, *args: typing.List[str]):
        """Output FMOD debug information."""
        self.FMOD_LOGGER.log(
            logging.DEBUG,
            f'| FMOD | CODE: {fmod.getError():2} | {action:<16} |{"|".join([f" {arg:<16}" for arg in args]) + "|" if args else ""}'
        )

    def debug_fmod_playback(self, action: str, channel_id: int, note_id: int,
                            *args: typing.List[str]):
        """Output playback debug information."""
        self.FMOD_LOGGER.log(
            logging.DEBUG,
            f'| FMOD | CODE: {fmod.getError():2} | CHAN: {channel_id:2} | NOTE: {note_id:2} | {action:<16} |{"|".join([f" {arg:<15}" for arg in args]) + "|" if args else ""}'
        )

    def show_processor_exec(self, action: str, channel_id: int,
                            *args: typing.List[str]):
        """Output processor execution information."""
        arg_str = "|".join([f" {arg:<15}" for arg in args
                           ]) + "|" if args else ""
        self.PROCESSOR_LOGGER.log(
            logging.DEBUG,
            f' {action:20} | CHANNEL: {channel_id:2} | {arg_str}')

    def reset_player(self) -> None:
        """Reset the player to a clean state.

        This function clears all virtual channels and samples disables all
        notes, resets all PSG channel, and resets the tempo to 120 BPM.

        """
        self.channels.clear()
        self.drumkits.clear()
        self.samples.clear()
        self.insts.clear()
        self.directs.clear()
        self.note_queue.clear()

        for i in range(31, -1, -1):
            self.note_arr[i].enable = False

        self.psg_channels = {
            engine.NoteTypes.SQUARE1: None,
            engine.NoteTypes.SQUARE2: None,
            engine.NoteTypes.WAVEFORM: None,
            engine.NoteTypes.NOISE: None,
        }

        self.tempo = 120

    def free_note(self) -> int:
        """Check for the first disabled note in the global note array and return its ID.

        Notes
        -----
            Actual hardware supports only the playback of 32 notes at one
            moment. However, because we aren't running on hardware, any
            arbitrary limit higher than 32 notes can be set.

        Returns
        -------
        int
            An ID in the range of 0 - 31.
            On failure, None.

        """
        for i in range(31, -1, -1):
            item = self.note_arr[i]
            if item.enable is False:
                return i
        return None

    def load_sample(self,
                    fpath: str,
                    offset: typing.Union[int, str] = 0,
                    size: int = 0,
                    loop: bool = True,
                    gb_wave: bool = True) -> int:
        """Load a sample into the FMOD library.

        Parameters
        ----------
        fpath
            File path to the raw PCM8 sound sample
        offset
            Starting address of the PCM8 sample
        size
            Data size of the PCM8 sample
        loop
            Specify if the sample loops
        gb_wave
            Specify if the sample is signed PCM8

        Returns
        -------
        int
            A 32-bit pointer to the loaded sample.

        """
        mode = fmod.FSoundModes._8BITS + fmod.FSoundModes.LOADRAW + fmod.FSoundModes.MONO
        if loop:
            mode += fmod.FSoundModes.LOOP_NORMAL
        if gb_wave:
            mode += fmod.FSoundModes.UNSIGNED
        else:
            mode += fmod.FSoundModes.SIGNED
        fpath = fpath.encode('ascii')
        index = fmod.FSoundChannelSampleMode.FREE
        return fmod.sampleLoad(index, fpath, mode, offset, size)

    def load_directsound(self, sample_pool: typing.Dict,
                         file_path: str) -> None:
        """Load in all PCM8 samples into the FMOD library.

        Notes
        -----
        This function is to be called after `load_song` and before
        `load_square` and `load_noise`.

        All samples are loaded in either directly from the ROM itself or from
        preloaded sample data in string form.

        Parameters
        ----------
        sample_pool
            The sample pool to load the samples into.

        file_path
            The file path to the GBA ROM.

        """
        for sample in sample_pool.values():
            sample: engine.Sample
            if sample.gb_wave:
                sample.fmod_smp = self.load_sample(file_path, sample.smp_data,
                                                   sample.size)
                fmod.setLoopPoints(sample.fmod_smp, 0, 31)
            else:
                sample.fmod_smp = self.load_sample(
                    file_path, sample.smp_data, sample.size, sample.loop, False)
                fmod.setLoopPoints(sample.fmod_smp, sample.loop_start,
                                   sample.size - 1)

    def load_square(self, sample_pool: typing.Dict) -> None:
        """Load in all square waves into the sample pool.

        There are 4 square waves loaded into memory by ascending duty
        cycle. The duty cycle is determined by a ratio of (high:low)
        periods out of 32 total periods.

        The square waves have duty cycles of: 12.5%, 25%, 50%, 75%

        """

        high = chr(int(0x80 + 0x7F * self.GB_SQ_MULTI))
        low = chr(int(0x80 - 0x7F * self.GB_SQ_MULTI))

        for duty_cycle in range(4):
            if duty_cycle < 3:
                l = [high] * (2**(duty_cycle + 2))
                r = [low] * (32 - 2**(duty_cycle + 2))
            else:
                l = [high] * 24
                r = [low] * 8
            smp_data = "".join(l + r)
            frequency = 7040
            size = 32

            square = f'square{duty_cycle}'
            filename = f'{square}.raw'
            with open(filename, 'w') as f:
                f.write(smp_data)
            fmod_smp = self.load_sample(filename, 0, 0)
            fmod.setLoopPoints(fmod_smp, 0, 31)
            sample_pool[square] = engine.Sample(smp_data, size, frequency,
                                                fmod_smp)

            os.remove(filename)

    def load_noise(self, sample_pool: typing.Dict) -> None:
        """Load all noise waves into the sample pool.

        There are two types of samples noise waves loaded into memory: a
        4096-sample (normal) wave and a 256-sample (metallic) wave. 10 of
        each are loaded in. Each sample has a base frequency of 7040 Hz.

        """
        for i in range(10):
            wave_data = ''.join(
                map(chr, [random.randint(0, 152) for _ in range(4096)]))
            smp_data = wave_data
            frequency = 7040
            size = 4096

            noise = f'noise0{i}'
            filename = f'{noise}.raw'
            with fileio.open_new_file(filename) as f:
                f.wr_str(smp_data)
            fmod_smp = self.load_sample(filename)
            fmod.setLoopPoints(fmod_smp, 0, 16383)
            sample_pool[noise] = engine.Sample(smp_data, size, frequency,
                                               fmod_smp)

            os.remove(filename)

            wave_data = ''.join(
                map(chr, [random.randint(0, 152) for _ in range(256)]))
            smp_data = wave_data
            frequency = 7040
            size = 256

            noise = f'noise1{i}'
            filename = f'{noise}.raw'
            with fileio.open_new_file(filename) as f:
                f.wr_str(smp_data)
            fmod_smp = self.load_sample(filename)
            fmod.setLoopPoints(fmod_smp, 0, 255)

            sample_pool[noise] = engine.Sample(smp_data, size, frequency,
                                               fmod_smp)
            os.remove(filename)

    def init_player(self, fpath: str) -> None:
        """Iniate the FMOD player and load in all samples.

        The sound output is initially set to WINSOUND and the FMOD player
        is then initiated with 64 channels at a sample rate of 44100 Hz.

        """
        fmod.setOutput(1)
        self.debug_fmod('SET OUTPUT')

        fmod.systemInit(41800, 32, 0)
        self.debug_fmod('INIT PLAYER')

        fmod.setMasterVolume(self.global_vol)
        self.debug_fmod('SET VOLUME', f'VOLUME: {self.global_vol}')

        self.load_directsound(self.samples, fpath)
        self.load_noise(self.samples)
        self.load_square(self.samples)

    def update_vibrato(self) -> None:
        """Update the vibrato position for each note of each vibrato-enabled channel.

        A channel with both a vibrato rate and depth set are considered
        "vibrato" enabled and are subsequently processed.

        Vibrato is simulated using a sine wave with a domain of
        { x | x < 2} - representing the vibrato position - and range of
        {y | -depth < y < depth} - representing the delta frequency
        multiplier. A sine wave rather than a cosine wave is used to
        initialize the base delta frequency of each note at 0.

        The delta frequency is calculated using the following equation:

        SIN(POS * π) * DEPTH

        """
        for note in self.note_arr:
            if not note.enable:
                continue
            chan = self.channels[note.parent]
            if not chan.is_enabled or chan.vib_rate == 0 or chan.vib_depth == 0:
                continue

            delta_freq = math.sin(math.pi * note.vib_pos) * chan.vib_depth
            pitch = (
                chan.pitch_bend - 0x40 + delta_freq) / 0x40 * chan.pitch_range
            frequency = int(note.frequency * math.pow(BASE, pitch))
            fmod.setFrequency(note.fmod_channel, frequency)

            note.vib_pos += chan.vib_rate / 96
            note.vib_pos = math.fmod(note.vib_pos, 2)

    def advance_notes(self) -> None:
        """Advance each note 1 tick and release all 0-tick notes."""
        for note in self.note_arr:
            note: engine.Note
            if note.wait_ticks > 0:
                note.wait_ticks -= 1
            if note.wait_ticks <= 0 and not note.note_off:
                if not self.channels[note.parent].is_sustain:
                    self.reset_note(note)

    def update_channels(self) -> None:
        """Advance each channel 1 tick and continue processor execution for all 0-tick channels."""
        for chan_id, chan in enumerate(self.channels):
            if not chan.is_enabled:
                continue
            if chan.wait_ticks > 0:
                chan.wait_ticks -= 1
            while chan.wait_ticks <= 0:
                event: engine.Event = chan.event_queue[chan.program_ctr]
                cmd_byte = event.cmd_byte
                args = event.arg1, event.arg2, event.arg3

                if cmd_byte in (0xB1, 0xB6):
                    chan.is_enabled = False
                    chan.is_sustain = False
                    self.show_processor_exec('STOP EXECUTION', chan_id)
                    break
                elif cmd_byte == 0xB9:
                    chan.program_ctr += 1
                    self.show_processor_exec('CONDITIONAL JUMP (UNUSED)',
                                             chan_id, '')
                elif cmd_byte == 0xBA:
                    chan.priority = args[0]
                    chan.program_ctr += 1
                    self.show_processor_exec('SET PRIORITY', chan_id,
                                             chan.priority)
                elif cmd_byte == 0xBB:
                    self.tempo = args[0] * 2
                    self.show_processor_exec('SET TEMPO', chan_id, self.tempo)
                    chan.program_ctr += 1
                elif cmd_byte == 0xBC:
                    chan.transpose = engine.to_int(args[0])
                    self.show_processor_exec('SET TRANSPOSE', chan_id,
                                             chan.transpose)
                    chan.program_ctr += 1
                elif cmd_byte == 0xBD:
                    chan.patch_num = args[0]
                    if chan.patch_num in self.directs:
                        chan.output_type = self.directs[chan.patch_num].output
                    elif chan.patch_num in self.insts:
                        chan.output_type = engine.ChannelTypes.MULTI
                    elif chan.patch_num in self.drumkits:
                        chan.output_type = engine.ChannelTypes.DRUMKIT
                    else:
                        chan.output_type = engine.ChannelTypes.NULL
                    self.show_processor_exec('SET OUTPUT', chan_id,
                                             chan.output_type.name)
                    chan.program_ctr += 1
                elif cmd_byte == 0xBE:
                    chan.main_vol = args[0]
                    self.show_processor_exec('SET CHANNEL VOLUME', chan_id,
                                             chan.main_vol)
                    output_volume = []
                    for nid in chan.notes.values():
                        note: engine.Note = self.note_arr[nid]
                        if not note.enable or note.parent != chan_id:
                            continue
                        dav = 0
                        if not chan.is_muted:
                            vel = note.velocity / 0x7F
                            vol = chan.main_vol / 0x7F
                            pos = note.env_pos / 0xFF
                            dav = round(vel * vol * pos * 255)
                        output_volume.append(dav)
                        fmod.setVolume(note.fmod_channel, dav)
                        self.debug_fmod_playback('SET NOTE VOLUME', chan_id,
                                                 nid, dav)
                    if not len(output_volume):
                        output_volume = [0]
                    chan.output_volume = round(
                        sum(output_volume) / len(output_volume))
                    chan.program_ctr += 1
                elif cmd_byte == 0xBF:
                    chan.panning = args[0]
                    panning = chan.panning * 2
                    self.show_processor_exec('SET CHANNEL PANNING', chan_id,
                                             chan.panning)
                    for nid in chan.notes.values():
                        note = self.note_arr[nid]
                        if not note.enable or note.parent != chan_id:
                            continue
                        fmod.setPan(note.fmod_channel, panning)
                        self.debug_fmod_playback('SET NOTE PANNING', chan_id,
                                                 nid, panning)
                    chan.program_ctr += 1
                elif cmd_byte in (0xC0, 0xC1):
                    if cmd_byte == 0xC0:
                        chan.pitch_bend = args[0]
                        self.show_processor_exec('SET PITCH BEND', chan_id,
                                                 chan.pitch_bend)
                    else:
                        chan.pitch_range = engine.to_int(args[0])
                        self.show_processor_exec('SET PITCH RANGE', chan_id,
                                                 chan.pitch_range)
                    chan.program_ctr += 1
                    for nid in chan.notes.values():
                        note: engine.Note = self.note_arr[nid]
                        if not note.enable or note.parent != chan_id:
                            continue
                        pitch = (
                            chan.pitch_bend - 0x40) / 0x40 * chan.pitch_range
                        frequency = int(note.frequency * math.pow(BASE, pitch))
                        fmod.setFrequency(note.fmod_channel, frequency)
                        self.debug_fmod_playback('SET NOTE FREQ', chan_id, nid,
                                                 frequency)
                elif cmd_byte == 0xC2:
                    chan.vib_rate = args[0]
                    self.show_processor_exec('SET VIBRATO RATE', chan_id,
                                             chan.vib_rate)
                    chan.program_ctr += 1
                elif cmd_byte == 0xC4:
                    chan.vib_depth = args[0]
                    self.show_processor_exec('SET VIBRATO RNGE', chan_id,
                                             chan.vib_depth)
                    chan.program_ctr += 1
                elif cmd_byte == 0xCE:
                    chan.is_sustain = False
                    self.show_processor_exec('DISABLE SUSTAIN', chan_id)
                    for nid in chan.notes.values():
                        note: engine.Note = self.note_arr[nid]
                        self.reset_note(note)
                        self.show_processor_exec('RELEASE NOTE', chan_id, nid)
                    chan.program_ctr += 1
                elif cmd_byte == 0xB3:
                    chan.program_ctr = event.evt_q_ptr
                    self.show_processor_exec('DEFINE SUBROUTINE', chan_id,
                                             chan.program_ctr)
                    chan.sub_ctr += 1
                    chan.rtn_ptr += 1
                    chan.in_sub = True
                elif cmd_byte == 0xB4:
                    if chan.in_sub:
                        chan.program_ctr = chan.rtn_ptr
                        chan.in_sub = False
                        self.show_processor_exec('END SUBROUTINE', chan_id,
                                                 chan.program_ctr)
                    else:
                        self.show_processor_exec('NOP (NO OPERATION)', chan_id)
                        chan.program_ctr += 1
                    for nid in chan.notes.values():
                        note: engine.Note = self.note_arr[nid]
                        self.reset_note(note)
                        self.show_processor_exec('RELEASE NOTE', chan_id, nid)
                elif cmd_byte == 0xB2:
                    self.looped = True
                    chan.in_sub = False
                    chan.program_ctr = chan.loop_ptr
                    chan.is_sustain = False
                    self.show_processor_exec('JUMP TO ADDRESS', chan_id,
                                             chan.program_ctr)
                    for nid in chan.notes.values():
                        note: engine.Note = self.note_arr[nid]
                        self.reset_note(note)
                        self.show_processor_exec('RELEASE NOTE', chan_id, nid)
                elif cmd_byte >= 0xCF:
                    ll = engine.to_ticks(cmd_byte - 0xCF) + 1
                    if cmd_byte == 0xCF:
                        chan.is_sustain = True
                        ll = -1
                    nn, vv, uu = args
                    self.note_queue.append(
                        engine.Note(nn, vv, chan_id, uu, ll, chan.patch_num))
                    self.show_processor_exec(
                        'QUEUE NEW NOTE', chan_id, f'{ll:2} ticks',
                        engine.to_name(nn), f'VOL: {vv:3}', f'UNK: {uu:3}')
                    chan.program_ctr += 1
                elif cmd_byte <= 0xB0:
                    if self.looped:
                        self.looped = False
                        chan.wait_ticks = 0
                        continue
                    chan.program_ctr += 1
                    n_event_queue = chan.event_queue[chan.program_ctr]
                    if chan.program_ctr > 0:
                        chan.wait_ticks = n_event_queue.ticks - event.ticks
                    else:
                        chan.wait_ticks = n_event_queue.ticks
                    self.show_processor_exec(f'TIMEOUT {chan.wait_ticks} TICKS',
                                             chan_id)
                elif cmd_byte == 0xCD:
                    if args[0] == 0x08:
                        self.show_processor_exec('SET PSEUDO ECHO VOLUME',
                                                 chan_id)
                    elif args[0] == 0x09:
                        self.show_processor_exec('SET PSEUDO ECHO LENGTH',
                                                 chan_id)
                    chan.program_ctr += 1
                else:
                    self.show_processor_exec('UNKNOWN OP CODE', chan_id,
                                             f'{cmd_byte:x}')
                    chan.program_ctr += 1

    def set_note(self, note: engine.Note, direct: engine.Direct):
        """Assign a Direct's output and environment properties to a note."""
        note.output = direct.output
        note.env_atck = direct.env_atck
        note.env_dcy = direct.env_dcy
        note.env_sus = direct.env_sus
        note.env_rel = direct.env_rel

    def get_playback_data(self, note: engine.Note):
        """Get the sample ID and frequency of a note from the sample pool."""
        patch = note.patch_num
        note_num = note.note_num
        sample_id = 0
        base_freq = 0
        standard = (engine.DirectTypes.DIRECT, engine.DirectTypes.WAVEFORM)
        square = (engine.DirectTypes.SQUARE1, engine.DirectTypes.SQUARE2)
        direct = self.directs.get(patch)
        if direct is not None:
            self.set_note(note, direct)
            self.show_processor_exec(
                'NEW DIRECT NOTE', note.parent, note_num,
                f'ATTN: {note.env_atck:3}', f'DECAY: {note.env_dcy:3}',
                f'SUSTAIN: {note.env_sus:3}', f'RELEASE: {note.env_rel:3}')
            if direct.output in standard:
                sample_id = self.directs[patch].smp_id
                base_freq = engine.to_frequency(
                    note_num + (60 - self.directs[patch].drum_key),
                    self.samples[sample_id].frequency)
                if self.samples[sample_id].gb_wave:
                    base_freq /= 2
            elif direct.output in square:
                sample_id = f'square{self.directs[patch].gb1 % 4}'
                base_freq = engine.to_frequency(
                    note_num + (60 - self.directs[patch].drum_key))
            elif direct.output == engine.DirectTypes.NOISE:
                sample_id = f'noise{self.directs[patch].gb1 % 2}{int(random.random() * 3)}'
                base_freq = engine.to_frequency(
                    note_num + (60 - self.directs[patch].drum_key))
        elif patch in self.insts:
            direct: engine.Direct = self.insts[patch].directs[self.insts[
                patch].keymaps[note_num]]
            self.set_note(note, direct)
            self.show_processor_exec(
                'NEW MULTI NOTE', note.parent, note_num,
                f'ATTN: {note.env_atck:3}', f'DECAY: {note.env_dcy:3}',
                f'SUSTAIN: {note.env_sus:3}', f'RELEASE: {note.env_rel:3}')
            if direct.output in standard:
                sample_id = direct.smp_id
                if direct.fix_pitch:
                    base_freq = self.samples[sample_id].frequency
                else:
                    base_freq = engine.to_frequency(
                        note_num, -2 if self.samples[sample_id].gb_wave else
                        self.samples[sample_id].frequency)
            elif direct.output in square:
                sample_id = f'square{direct.gb1 % 4}'
                base_freq = engine.to_frequency(note_num)
        elif patch in self.drumkits:
            direct: engine.Direct = self.drumkits[patch].directs[note_num]
            self.set_note(note, direct)
            self.show_processor_exec(
                'NEW DRUMKIT NOTE', note.parent, note_num,
                f'ATTN: {note.env_atck:3}', f'DECAY: {note.env_dcy:3}',
                f'SUSTAIN: {note.env_sus:3}', f'RELEASE: {note.env_rel:3}')
            if direct.output in standard:
                sample_id = direct.smp_id
                if direct.fix_pitch and not self.samples[sample_id].gb_wave:
                    base_freq = self.samples[sample_id].frequency
                else:
                    base_freq = engine.to_frequency(
                        direct.drum_key, -2 if self.samples[sample_id].gb_wave
                        else self.samples[sample_id].frequency)
            elif direct.output in square:
                sample_id = f'square{direct.gb1 % 4}'
                base_freq = engine.to_frequency(direct.drum_key)
            elif direct.output == engine.DirectTypes.NOISE:
                sample_id = f'noise{direct.gb1 % 2}{int(random.random() * 10)}'
                base_freq = engine.to_frequency(direct.drum_key)
        self.show_processor_exec(note.output.name.upper(), note.parent,
                                 f'SMP: {sample_id}', f'{base_freq} Hz')

        return sample_id, base_freq

    def play_notes(self) -> None:
        """Start playback of all notes in the note queue.

        All notes added during channel execution are appended to the global
        note queue. Each note in the queue is assigned a free note ID from the
        `free_note` function; if no free note is found, the note is ignored
        and execution continues. The note's parent channel is then purged of
        all currently playing sustained and timeout notes. The relevant sample
        and playback sample is retrieved from the sample pool. Player
        frequency, volume, and panning are calculated, and the relevant
        note is played by the FMOD player.

        """
        volumes = [[] for i in range(len(self.channels))]
        for item in self.note_queue:
            note_num = self.free_note()
            if note_num is None:
                continue
            self.show_processor_exec('GET FREE NOTE', item.parent, note_num)

            self.note_arr[note_num] = item
            chan = self.channels[item.parent]

            for note_id in chan.notes.values():
                note = self.note_arr[note_id]

                if note.enable is True and not note.note_off:
                    if note.wait_ticks == -1 and not chan.is_sustain:
                        self.reset_note(note)
                        self.show_processor_exec('SUSTAIN NOTE OFF',
                                                 item.parent, note_id)
                    elif note.wait_ticks in (0, 1):
                        self.reset_note(note)
                        self.show_processor_exec('TIMEOUT NOTE OFF',
                                                 item.parent, note_id)
            chan.notes[note_num] = note_num
            if self.note_arr[note_num].note_num not in chan.notes_playing:
                chan.notes_playing.append(self.note_arr[note_num].note_num)
            sample_id, frequency = self.get_playback_data(item)
            if not sample_id:
                return
            frequency *= math.pow(BASE, self.transpose)
            dav = (item.velocity / 0x7F) * (chan.main_vol / 0x7F) * 255
            out_type = self.note_arr[note_num].output

            psg_note = self.psg_channels.get(out_type)
            if psg_note is not None:
                gb_note = self.note_arr[psg_note]
                fmod.stopSound(gb_note.fmod_channel)
                self.debug_fmod_playback(f'STOP {out_type.name}', item.parent,
                                         psg_note)
                gb_note.fmod_channel = 0
                del self.channels[gb_note.parent].notes[psg_note]
                gb_note.enable = False
            self.psg_channels[out_type] = psg_note

            pitch = (chan.pitch_bend - 0x40) / 0x40 * chan.pitch_range
            out_frequency = int(frequency * math.pow(BASE, pitch))
            panning = chan.panning * 2
            volume = 0 if chan.is_muted else int(dav)
            volumes[item.parent].append(volume)
            note: engine.Note = self.note_arr[note_num]
            note.frequency = frequency
            note.phase = engine.NotePhases.INITIAL
            if note.output == engine.NoteTypes.NOISE:
                continue

            note.fmod_channel = fmod.playSound(
                note_num, self.samples[sample_id].fmod_smp, None, True)
            self.debug_fmod_playback('PLAY NOTE', note.parent, note_num)
            fmod.setFrequency(note.fmod_channel, out_frequency)
            self.debug_fmod_playback('SET FREQUENCY', note.parent, note_num,
                                     f'{out_frequency} Hz')
            fmod.setVolume(note.fmod_channel, volume)
            self.debug_fmod_playback('SET VOLUME', note.parent, note_num,
                                     volume)
            fmod.setPan(note.fmod_channel, panning)
            self.debug_fmod_playback('SET PANNING', note.parent, note_num)
            fmod.setPaused(note.fmod_channel, False)
            self.debug_fmod_playback('UNPAUSE NOTE', note.parent, note_num)
        for chan_id, vol in enumerate(map(self.get_output_volume, volumes)):
            self.channels[chan_id].output_volume = vol
        self.note_queue.clear()

    def update_notes(self) -> None:
        """Update the position of all enabled notes.

        Each note has an attenuation, decay, sustain, and release value set
        upon processor execution. These 4 attributes directly affect the
        step increment, which in turn modifies the note's position in relation
        to the destination.

        During the initial phase, the position is initially set at 0 and slowly
        de-attenuates to the maximum possible destination (255).

        During the attack phase, the position is slowly stepped towards the
        sustain.

        During both the sustain and decay phases, the position is fixed and
        all effects applied to the note are executed during channel execution,
        including vibrato, pitch-bending, volume adjusts, priority sets, and
        note-offs.

        During the release phase, the position is slowly stepped towards 0.

        During the note-off phase, the note is removed from the channel's note
        queue and playback from the FMOD player is halted.

        Throughout execution, the delta volume is calculated per note and
        changed in the player.

        Notes
        -----
            Delta volume equation:
            INT((VELOCITY / 0x7F) *  (CHANNEL_VOL / 0x7F) * (POS / 0xFF) * 255)

        """
        for channel in self.channels:
            volumes = []
            for note_id in channel.notes.copy():
                note = self.note_arr[note_id]

                if not note.enable:
                    continue

                channel = self.channels[note.parent]
                if note.note_off and note.phase < engine.NotePhases.RELEASE:
                    note.env_step = 0
                    note.phase = engine.NotePhases.RELEASE

                if note.env_step == 0 or (note.env_pos == note.env_dest) or (
                        note.env_step <= 0 and note.env_pos <= note.env_dest
                ) or (note.env_step >= 0 and note.env_pos >= note.env_dest):
                    output, phase = note.output, note.phase
                    if phase == engine.NotePhases.INITIAL:
                        note.phase = engine.NotePhases.ATTACK
                        note.env_pos = 0
                        note.env_dest = 255
                        note.env_step = note.env_atck
                        if output > engine.NoteTypes.DIRECT:
                            note.env_step *= 8
                    elif phase == engine.NotePhases.ATTACK:
                        note.phase = engine.NotePhases.DECAY
                        note.env_dest = note.env_sus
                        if output > engine.NoteTypes.DIRECT:
                            note.env_dest *= 8
                            note.env_step = (note.env_dcy - 0x08) * 16
                        else:
                            note.env_step = (note.env_dcy - 0x100) / 2
                    elif phase == engine.NotePhases.DECAY:
                        note.phase = engine.NotePhases.SUSTAIN
                        note.env_step = 0
                    elif phase == engine.NotePhases.SUSTAIN:
                        note.env_step = 0
                    elif phase == engine.NotePhases.RELEASE:
                        note.phase = engine.NotePhases.NOTEOFF
                        note.env_dest = 0
                        if output > engine.NoteTypes.DIRECT:
                            note.env_step = (note.env_rel - 0x08) * 8
                        else:
                            note.env_step = (note.env_rel - 0x100)
                    elif phase == engine.NotePhases.NOTEOFF:
                        if output > engine.NoteTypes.DIRECT:
                            self.psg_channels[note.output] = None
                        self.reset_note(note)
                        fmod.stopSound(note.fmod_channel)
                        self.debug_fmod_playback('STOP NOTE', note.parent,
                                                 note_id,
                                                 f'FCHAN: {note.fmod_channel}')
                        note.fmod_channel = 0
                        del channel.notes[note_id]
                        if note.note_num in channel.notes_playing:
                            channel.notes_playing.remove(note.note_num)
                        note.enable = False

                delta_pos = note.env_pos + note.env_step
                if delta_pos > note.env_dest and note.env_step > 0 or delta_pos < note.env_dest and note.env_step < 0:
                    delta_pos = note.env_dest
                note.env_pos = delta_pos

                if not channel.is_muted:
                    vel = note.velocity / 0x7F
                    vol = channel.main_vol / 0x7F
                    pos = note.env_pos / 0xFF
                    volume = round(vel * vol * pos * 255)
                    volumes.append(volume)
                else:
                    volume = 0

                fmod.setVolume(note.fmod_channel, volume)
                self.debug_fmod_playback('SET NOTE VOLUME', note.parent,
                                         note_id, volume)

                channel.output_volume = self.get_output_volume(volumes)

    def update_processor(self) -> int:
        """Execute one tick of the event processor.

        The processor updates the vibrato positions of each channel, resets
        all notes in the NOTEOFF phase, executes the next set of instructions
        in the channel event queue, starts playback of any necessary notes,
        and updates the position of any notes in playback, in this order.

        The processor halts execution when all channels have been disabled.

        Returns
        -------
        int
            If at least one channel is enabled, 1.
            Otherwise, 0.

        """
        self.update_vibrato()
        self.advance_notes()
        self.update_channels()
        self.play_notes()
        self.update_notes()
        for channel in self.channels:
            if channel.is_enabled:
                return 1
        fmod.systemClose()
        return 0

    def get_output_volume(self, volumes: typing.List[int]) -> int:
        l = len(volumes)
        if not len(volumes):
            l = 1
        return round(sum(volumes) / l)

    def get_player_header(self, meta_data: parser.MetaData,
                          channel_queue: typing.List) -> str:
        """Construct the interface header.

        Constructs a column-based display, with each column representing one
        channel. Each column contains the channel's ID and output type.

        Notes
        -----
            An implicit call to 'update_channels' is made to force the
            player to internally set the output types (typically this is
            the first instruction).

        """
        self.update_channels()
        sappy_top = f'{DOWN_AND_RIGHT}{"":{HORIZONTAL}>7}{DOWN_AND_LEFT}'
        sappy = f'{VERTICAL} SAPPY {VERTICAL}'
        sappy_bottom = f'{UP_AND_RIGHT}{"":{HORIZONTAL}>7}{UP_AND_LEFT}'
        header_top = f'{DOWN_AND_RIGHT}{"":{HORIZONTAL}>16}{DOWN_AND_LEFT}'
        header = f'{VERTICAL} {meta_data.rom_name:^14} {VERTICAL}'
        top = f'{VERTICAL_AND_RIGHT}{"":{HORIZONTAL}>16}{VERTICAL_AND_HORIZONTAL}{"":{HORIZONTAL}>14}{DOWN_AND_LEFT}'
        table_ptr = f'{VERTICAL} TABLE POINTER: {VERTICAL} {"0x":>4}{meta_data.song_ptr:0>8x} {VERTICAL}'
        song_ptr = f'{VERTICAL}  SONG POINTER: {VERTICAL} {"0x":>4}{meta_data.voice_ptr:0>8x} {VERTICAL}'
        voice_ptr = f'{VERTICAL} VOICE POINTER: {VERTICAL} {"0x":>4}{meta_data.header_ptr:0>8x} {VERTICAL}'
        code = f'{VERTICAL}          CODE: {VERTICAL} {meta_data.code} {VERTICAL}'
        bottom = f'{UP_AND_RIGHT}{"":{HORIZONTAL}>16}{UP_AND_HORIZONTAL}{"":{HORIZONTAL}>14}{UP_AND_LEFT}'
        info = '\n'.join((sappy_top, sappy, sappy_bottom, header_top, header, top, table_ptr, song_ptr, voice_ptr, code, bottom))+'\n'
        header = []
        for chan_id, chan in enumerate(channel_queue):
            header.append(
                f'{VERTICAL} CHAN{chan_id:<2}{chan.output_type.name:>{self.WIDTH - 8}} '
            )
        header.append(f'{VERTICAL} TEMPO {VERTICAL}')
        header = ''.join(header)

        seperator = [f'{"":{HORIZONTAL}>{self.WIDTH}}'] * len(self.channels)
        top_seperator = DOWN_AND_RIGHT + DOWN_AND_HORIZONTAL.join(
            seperator) + TEMPO_TOP
        bot_seperator = VERTICAL_AND_RIGHT + VERTICAL_AND_HORIZONTAL.join(
            seperator) + TEMPO_BOTTOM
        return info + top_seperator + '\n' + header + '\n' + bot_seperator

    def display(self) -> None:
        """Update and display the interface."""
        out = self.update_interface()
        sys.stdout.write(out + '\r')
        sys.stdout.flush()

    def update_interface(self) -> str:
        """Update the user interface with the player data.

        The interface is divided into columns representing a channel each.
        Each column contains the current note volume, a visual representaion
        of the volume, all notes playing, and the number of remaining ticks.

        Notes
        -----
            The Z-order of the elements in ascending order is:
            bar, vol, note/ticks, pan

            Sample interface column:

            | [VOL] [  BAR  ] [NOTES] [TICKS] |

        """
        lines = []
        for chan in self.channels:
            chan: engine.Channel

            base, end = divmod(chan.output_volume, 256 // self.WIDTH)
            if not end:
                end = ''
            else:
                incr = 256 / self.WIDTH / 8
                end = BLOCK_TABLE.get(8-(end//incr), '')
            vol_bar = f'{"":{FULL_BLOCK}>{base}}'
            column = f'{vol_bar}{end}'

            notes = []
            for note in map(engine.to_name, chan.notes_playing):
                notes.append(f'{note:^4}')
            notes = notes[:self.WIDTH//4-1]
            notes.append(f'{chan.wait_ticks:^3}')
            notes = ''.join(notes)

            column = list(f'{column}{" ":<{self.WIDTH - len(column)}}')
            column[self.WIDTH // 2] = '|'

            insert_pt = self.WIDTH - len(notes)
            column[insert_pt:] = notes

            insert_pt = round(chan.panning / (128 / (self.WIDTH - 1)))
            column[insert_pt] = chr(0x2573)

            column = ''.join(column)
            lines.append(f'{column:^{self.WIDTH - 1}}')

        out = ['']
        for line in lines:
            out.append(f'{line:{self.WIDTH - 1}}')
        out.append('')
        out = f'{VERTICAL.join(out)} {self.tempo:{" "}^5} {VERTICAL}'
        return out

    def play_song(self, fpath: str, song_num: int,
                  song_table: int = None) -> None:
        """Play a song in the specified ROM."""
        d = parser.Parser()
        song = d.get_song(fpath, song_num, song_table)
        if song == -1:
            print('Invalid/Unsupported ROM.')
            return
        elif song == -2:
            print('Invalid song number.')
            return
        elif song == -3:
            print('Empty track.')
            return
        self.reset_player()
        self.channels = song.channels
        self.drumkits = song.drumkits
        self.samples = song.samples
        self.insts = song.insts
        self.directs = song.directs
        self.init_player(fpath)

        header = self.get_player_header(song.meta_data, song.channels)
        sys.stdout.write(header + '\n')
        self.execute_processor()

    def execute_processor(self) -> None:
        """Execute the event processor and update the user display.

        Notes
        -----
            The loop delay is calculate based on the current tempo of the
            event processor. In the event that the event processor's
            runtime exceeds this delay, the loop immediately cycles and no
            delay is.

            The loop delay is calculated based on the following equation:

            ROUND(FLOOR((1/TEMPO*2.5 - ELAPSED) * 1000) / 1000, 3)

            Additionally, all functions used within the mainloop are
            assigned local copies to avoid the global function
            lookup upon a function call.

        """
        e = self.update_processor
        s = time.sleep
        f = math.floor
        r = round
        t = time.time
        d = self.display
        m = self.INSTRUCTIONS_PER_CYCLE
        try:
            while True:
                st = t()
                if not e() or d():
                    break
                if r(f((1 / self.tempo * m - (t() - st)) * 1000) / 1000, 3) < 0:
                    continue
                s(r(f((1 / self.tempo * m - (t() - st)) * 1000) / 1000, 3))
        except KeyboardInterrupt:
            sys.stdout.write('\n')
            seperator = [f'{"":{HORIZONTAL}>{self.WIDTH}}'] * len(self.channels)
            exit_str = UP_AND_RIGHT + UP_AND_HORIZONTAL.join(seperator) + f'{UP_AND_HORIZONTAL}{"":{HORIZONTAL}>7}{UP_AND_LEFT}'
            sys.stdout.write(exit_str+'\n'+'Exiting...\n')
            return

    def stop_song(self):
        """Stop playback and reset the player."""
        self.reset_player()
        fmod.systemClose()

    def reset_note(self, note: engine.Note):
        """Revert a note to default state and remove it from the interface."""
        note.note_off = True
        note.vib_pos = 0.0
