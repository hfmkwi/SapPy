# -*- coding: utf-8 -*-
"""All playback related functionality for the Sappy Engine.

Attributes
----------
config.SEMITONE_RATIO: float
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

import sappy.engine as engine
import sappy.fileio as fileio
import sappy.fmod as fmod
import sappy.parser as parser
import sappy.config as config
from sappy.instructions import Command, Key, Note, Velocity, Wait
import sappy.instructions as instructions

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

    WIDTH = 33

    logging.basicConfig(level=logging.DEBUG)
    PROCESSOR_LOGGER = logging.getLogger('PROCESSOR')
    FMOD_LOGGER = logging.getLogger('FMOD')
    if not config.SHOW_PROCESSOR_EXECUTION:
        PROCESSOR_LOGGER.setLevel(logging.WARNING)
    if not config.SHOW_FMOD_EXECUTION:
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
        self.note_arr = [engine.Note(*[0] * 5)] * 32
        self.channels = []
        self.direct_samples = {}
        self.drumkits = {}
        self.multi_samples = {}
        self.note_queue = []
        self.fmod_samples = {}

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
            f'| FMOD | CODE: {fmod.getError():2} | {action:<16} |{"|".join([f" {arg:<16}" for arg in args]) + "|" if args else "":<100}'
        )

    def debug_fmod_playback(self, action: str, channel_id: int, note_id: int,
                            *args: typing.List[str]):
        """Output playback debug information."""
        self.FMOD_LOGGER.log(
            logging.DEBUG,
            f'| FMOD | CODE: {fmod.getError():2} | CHAN: {channel_id:2} | NOTE: {note_id:2} | {action:<16} |{"|".join([f" {arg:<15}" for arg in args]) + "|" if args else "":<100}'
        )

    def show_processor_exec(self, action: str, channel_id: int,
                            *args: typing.List[str]):
        """Output processor execution information."""
        arg_str = "|".join([f" {arg:<15} " for arg in args
                           ]) + "|" if args else ""
        self.PROCESSOR_LOGGER.log(
            logging.DEBUG,
            f' {action:^32} | CHANNEL: {channel_id:2} | {arg_str:<100}')

    def reset_player(self) -> None:
        """Reset the player to a clean state.

        This function clears all virtual channels and samples disables all
        notes, resets all PSG channel, and resets the tempo to 120 BPM.

        """
        self.channels.clear()
        self.drumkits.clear()
        self.fmod_samples.clear()
        self.multi_samples.clear()
        self.direct_samples.clear()
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
                if type(sample.smp_data) == list:
                    with open('temp.raw', 'wb') as f:
                        f.write(bytes(sample.smp_data))
                    sample.fmod_id = self.load_sample('temp.raw', 0,
                                                      sample.size)
                    os.remove('temp.raw')
                else:
                    sample.fmod_id = self.load_sample(
                        file_path, sample.smp_data, sample.size)
                if sample.loop:
                    fmod.setLoopPoints(sample.fmod_id, 0, 31)
            else:
                if type(sample.smp_data) == list:
                    with open('temp.raw', 'wb') as f:
                        f.write(bytes(sample.smp_data))
                    sample.fmod_id = self.load_sample(
                        'temp.raw', 0, sample.size, sample.loop, False)
                    os.remove('temp.raw')
                else:
                    sample.fmod_id = self.load_sample(
                        file_path, sample.smp_data, sample.size, sample.loop,
                        False)
                if sample.loop:
                    fmod.setLoopPoints(sample.fmod_id, sample.loop_start,
                                       sample.size - 1)
            fmod.setDefaults(sample.fmod_id, sample.frequency, 0, -1, -1)

    def load_square(self, sample_pool: typing.Dict) -> None:
        """Load in all square waves into the sample pool.

        There are 4 square waves loaded into memory by ascending duty
        cycle. The duty cycle is determined by a ratio of (high:low)
        periods out of 32 total periods.

        The square waves have duty cycles of: 12.5%, 25%, 50%, 75%

        """
        high = round(0x80 + 0x7F * config.PSG_VOLUME / 2)
        low = round(0x80 - 0x7F * config.PSG_VOLUME / 2)

        SQUARE_WAVES = [high] * 4 + [low] * 28, [high] * 8 + [low] * 24, [
            high
        ] * 16 + [low] * 16, [high] * 24 + [low] * 8

        for duty_cycle, smp_data in enumerate(SQUARE_WAVES):
            frequency = 7040
            size = 32

            square = f'square{duty_cycle}'
            filename = f'{square}.raw'
            with open(filename, 'wb') as f:
                f.write(bytes(smp_data))
            fmod_id = self.load_sample(filename, gb_wave=True)
            fmod.setLoopPoints(fmod_id, 0, 31)
            sample_pool[square] = engine.Sample(smp_data, size, frequency,
                                                fmod_id)
            fmod.setDefaults(fmod_id, frequency, 0, -1, -1)

            os.remove(filename)

    def load_noise(self, sample_pool: typing.Dict) -> None:
        """Load all noise waves into the sample pool.

        There are two types of samples noise waves loaded into memory: a
        4096-sample (normal) wave and a 256-sample (metallic) wave. 10 of
        each are loaded in. Each sample has a base frequency of 7040 Hz.

        """
        for i in range(10):
            noise_data = [
                int(random.random() * round(64 * config.PSG_VOLUME / 2))
                for _ in range(32767)
            ]
            frequency = 7040
            size = 32767

            noise = f'noise0{i}'
            filename = f'{noise}.raw'
            with open(filename, 'wb') as f:
                f.write(bytes(noise_data))
            fmod_id = self.load_sample(filename)
            fmod.setLoopPoints(fmod_id, 0, 32766)
            sample_pool[noise] = engine.Sample(noise_data, size, frequency,
                                               fmod_id)
            fmod.setDefaults(fmod_id, 7040, 0, -1, -1)

            os.remove(filename)

            noise_data = [
                int(random.random() * round(64 * config.PSG_VOLUME / 2))
                for _ in range(127)
            ]
            frequency = 7040
            size = 127

            noise = f'noise1{i}'
            filename = f'{noise}.raw'
            with open(filename, 'wb') as f:
                f.write(bytes(noise_data))
            fmod_id = self.load_sample(filename)
            fmod.setLoopPoints(fmod_id, 0, 126)

            sample_pool[noise] = engine.Sample(noise_data, size, frequency,
                                               fmod_id)
            fmod.setDefaults(fmod_id, 7040, 0, -1, -1)

            os.remove(filename)

    def init_player(self, fpath: str) -> None:
        """Iniate the FMOD player and load in all samples.

        The sound output is initially set to WINSOUND and the FMOD player
        is then initiated with 64 channels at a sample rate of 44100 Hz.

        """
        fmod.setOutput(1)
        self.debug_fmod('SET OUTPUT')

        fmod.systemInit(32768, 64, 0)
        self.debug_fmod('INIT PLAYER')

        fmod.setMasterVolume(self.global_vol)
        self.debug_fmod('SET VOLUME', f'VOLUME: {self.global_vol}')

        self.load_directsound(self.fmod_samples, fpath)
        self.load_noise(self.fmod_samples)
        self.load_square(self.fmod_samples)

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
            channel = self.channels[note.parent_channel]
            if not channel.enabled or channel.lfo_speed == 0 or channel.mod_depth == 0:
                continue

            delta_freq = math.sin(
                math.pi * note.lfos_position / 127) * channel.mod_depth
            pitch = (channel.pitch_bend - 0x40 + delta_freq) / 0x40
            frequency = round(
                note.frequency * math.pow(config.SEMITONE_RATIO, pitch))
            fmod.setFrequency(note.fmod_channel, frequency)

            note.lfos_position += channel.lfo_speed
            note.lfos_position %= 254

    def advance_notes(self) -> None:
        """Advance each note 1 tick and release all 0-tick notes."""
        for note in self.note_arr:
            note: engine.Note
            if note.wait_ticks > 0:
                note.wait_ticks -= 1
            self.disable_notes(self.channels[note.parent_channel])

    def disable_notes(self, channel: engine.Channel) -> None:
        for note_id in channel.notes_playing:
            note = self.note_arr[note_id]

            if note.enable and not note.note_off and note.wait_ticks == 0:
                note.note_off = True
                self.show_processor_exec(f'NOTE {note_id} OFF',
                                         note.parent_channel)

    def update_channels(self) -> None:
        """Advance each channel 1 tick and continue processor execution for all 0-tick channels."""
        for channel_id, channel in enumerate(self.channels):
            if not channel.enabled:
                continue
            if channel.wait_ticks > 0:
                channel.wait_ticks -= 1
            while channel.wait_ticks <= 0 and channel.enabled:
                event: engine.Event = channel.event_queue[channel.program_ctr]
                cmd_byte = event.cmd_byte
                args = event.arg1, event.arg2

                if cmd_byte in (Command.FINE, Command.PREV):
                    channel.enabled = False
                    self.show_processor_exec('FINE', channel_id)
                    self.show_processor_exec('MEMACC', channel_id)
                elif cmd_byte == Command.PRIO:
                    channel.priority = args[0]
                    self.show_processor_exec(f'PRIO {channel.priority}',
                                             channel_id)
                elif cmd_byte == Command.TEMPO:
                    self.tempo = args[0] * 2
                    self.show_processor_exec(f'TEMPO {self.tempo}', channel_id)
                elif cmd_byte == Command.KEYSH:
                    channel.transpose = args[0]
                    self.show_processor_exec(f'KEYSH {channel.transpose}',
                                             channel_id)
                elif cmd_byte == Command.VOICE:
                    channel.instrument_id = args[0]
                    if channel.instrument_id in self.direct_samples:
                        channel.output_type = self.direct_samples[
                            channel.instrument_id].output_type
                    elif channel.instrument_id in self.multi_samples:
                        channel.output_type = engine.ChannelTypes.MULTI
                    elif channel.instrument_id in self.drumkits:
                        channel.output_type = engine.ChannelTypes.DRUMKIT
                    else:
                        channel.output_type = engine.ChannelTypes.NULL
                    self.show_processor_exec(
                        f'VOICE {channel.instrument_id} ({channel.output_type.name})',
                        channel_id)
                elif cmd_byte == Command.VOL:
                    channel.volume = args[0]
                    self.show_processor_exec(f'VOL {channel.volume}',
                                             channel_id)
                    output_volume = []
                    for note_id in channel.notes_playing:
                        note: engine.Note = self.note_arr[note_id]
                        if not note.enable or note.parent_channel != channel_id:
                            continue
                        dav = 0
                        if not channel.muted:
                            vel = note.velocity / 0x7F
                            vol = channel.volume / 0x7F
                            pos = note.env_pos / 0xFF
                            dav = round(vel * vol * pos * 255)
                        output_volume.append(dav)
                        fmod.setVolume(note.fmod_channel, dav)
                        self.debug_fmod_playback(f'NOTE VOLUME {dav}',
                                                 channel_id, note_id)
                    channel.output_volume = self.average_volumes(output_volume)
                elif cmd_byte == Command.PAN:
                    channel.panning = args[0]
                    panning = channel.panning * 2
                    self.show_processor_exec(f'PAN {channel.panning}',
                                             channel_id, channel.panning)
                    for note_id in channel.notes_playing:
                        note = self.note_arr[note_id]
                        if not note.enable or note.parent_channel != channel_id:
                            continue
                        fmod.setPan(note.fmod_channel, panning)
                        self.debug_fmod_playback('SET NOTE PANNING', channel_id,
                                                 note_id, panning)
                elif cmd_byte in (Command.BEND, Command.BENDR):
                    if cmd_byte == Command.BEND:
                        channel.pitch_bend = args[0]
                        self.show_processor_exec(f'BEND {channel.pitch_bend}',
                                                 channel_id)
                    else:
                        channel.pitch_range = args[0]
                        self.show_processor_exec(f'BENDR {channel.pitch_range}',
                                                 channel_id)
                    for note_id in channel.notes_playing:
                        note: engine.Note = self.note_arr[note_id]
                        if not note.enable or note.parent_channel != channel_id:
                            continue
                        pitch = (channel.pitch_bend - 0x40
                                ) / 0x40 * channel.pitch_range
                        frequency = round(note.frequency * math.pow(
                            config.SEMITONE_RATIO, pitch))
                        fmod.setFrequency(note.fmod_channel, frequency)
                        self.debug_fmod_playback('SET NOTE FREQ', channel_id,
                                                 note_id, frequency)
                elif cmd_byte == Command.LFOS:
                    channel.lfo_speed = args[0]
                    self.show_processor_exec(f'LFOS {channel.lfo_speed}',
                                             channel_id)
                elif cmd_byte == Command.MOD:
                    channel.mod_depth = args[0]
                    self.show_processor_exec(f'MOD {channel.mod_depth}',
                                             channel_id)
                elif cmd_byte == Note.EOT:
                    for note_id in channel.notes_playing:
                        note: engine.Note = self.note_arr[note_id]
                        if note.note_num != args[0] and args[0] != 0:
                            continue
                        note.note_off = True
                        self.show_processor_exec(
                            f'EOT {Key(args[0]).name} ({note_id})', channel_id)
                elif cmd_byte == Command.GOTO:
                    self.looped = True
                    channel.program_ctr = channel.loop_ptr
                    self.show_processor_exec(f'GOTO 0x{channel.loop_ptr:X}',
                                             channel_id)
                    continue
                elif Note.N96 >= cmd_byte >= Note.TIE:
                    if cmd_byte == Note.TIE:
                        ll = -1
                    else:
                        ll = int(Note(cmd_byte).name[1:])  # pylint: disable=E1136
                    nn, vv = event.arg1, event.arg2
                    self.note_queue.append(
                        engine.Note(nn, vv, channel_id, ll,
                                    channel.instrument_id))
                    self.show_processor_exec(
                        f'{Note(cmd_byte).name} {Key(nn).name} {Velocity(vv).name}',
                        channel_id)
                elif Wait.W00 <= cmd_byte <= Wait.W96:
                    channel.wait_ticks = int(Wait(cmd_byte).name[1:])
                    self.show_processor_exec(f'WAIT {channel.wait_ticks}',
                                             channel_id)
                elif cmd_byte == 0xCD:
                    if args[0] == 0x08:
                        self.show_processor_exec(f'XCMD xIECV {args[1]}',
                                                 channel_id)
                    elif args[0] == 0x09:
                        self.show_processor_exec(f'XCMD xIECL {args[1]}',
                                                 channel_id)
                else:
                    try:
                        com = Command(cmd_byte)
                        self.show_processor_exec(com.name, channel_id)
                    except:
                        self.show_processor_exec(f'UNKNOWN (0x{cmd_byte:X})',
                                                 channel_id)
                channel.program_ctr += 1

    def set_note(self, note: engine.Note, direct: engine.Direct):
        """Assign a Direct's output and environment properties to a note."""
        note.output_type = direct.output_type
        note.attack = direct.attack
        note.decay = direct.decay
        note.sustain = direct.sustain
        note.release = direct.release

    def get_playback_data(self, note: engine.Note):
        """Get the sample ID and frequency of a note from the sample pool."""
        instrument_id = note.instrument_id
        note_num = note.note_num
        sample_id = 0
        base_freq = 0
        standard = (engine.DirectTypes.DIRECT, engine.DirectTypes.WAVEFORM)
        square = (engine.DirectTypes.SQUARE1, engine.DirectTypes.SQUARE2)
        if instrument_id in self.direct_samples:
            direct: engine.Direct = self.direct_samples[instrument_id]
            note.set_mixer_props(direct)
            midi_notenum = note_num + (60 - direct.drum_key)
            if direct.output_type in standard:
                sample_id = direct.bound_sample
                base_freq = engine.get_frequency(
                    midi_notenum, -1 if self.fmod_samples[sample_id].gb_wave
                    else self.fmod_samples[sample_id].frequency)
                if self.fmod_samples[sample_id].gb_wave:
                    base_freq /= 2
            else:
                if direct.output_type in square:
                    sample_id = f'square{direct.psg_flag % 4}'
                elif direct.output_type == engine.DirectTypes.NOISE:
                    sample_id = f'noise{direct.psg_flag % 2}{random.randint(0, 9)}'
                base_freq = engine.get_frequency(midi_notenum)
        elif instrument_id in self.multi_samples:
            multi_sample: engine.Instrument = self.multi_samples[instrument_id]
            direct: engine.Direct = multi_sample.directs[multi_sample.keymaps[
                note_num]]
            note.set_mixer_props(direct)
            if direct.output_type in standard:
                sample_id = direct.bound_sample
                sample: engine.Sample = self.fmod_samples[sample_id]
                if direct.fix_pitch:
                    base_freq = sample.frequency
                else:
                    base_freq = engine.get_frequency(note_num, -2
                                                     if sample.gb_wave else
                                                     sample.frequency)
            elif direct.output_type in square:
                sample_id = f'square{direct.psg_flag % 4}'
                base_freq = engine.get_frequency(note_num)
        elif instrument_id in self.drumkits:
            direct: engine.Direct = self.drumkits[instrument_id].directs[
                note_num]
            note.set_mixer_props(direct)
            if direct.output_type in standard:
                sample_id = direct.bound_sample
                sample: engine.Sample = self.fmod_samples[sample_id]
                if direct.fix_pitch and not sample.gb_wave:
                    base_freq = sample.frequency
                else:
                    base_freq = engine.get_frequency(direct.drum_key, -2
                                                     if sample.gb_wave else
                                                     sample.frequency)
            elif direct.output_type in square:
                sample_id = f'square{direct.psg_flag % 4}'
                base_freq = engine.get_frequency(direct.drum_key)
            elif direct.output_type == engine.DirectTypes.NOISE:
                sample_id = f'noise{direct.psg_flag % 2}{random.randint(0, 9)}'
                base_freq = engine.get_frequency(direct.drum_key)
        return sample_id, base_freq

    def reset_psg(self, output_type: engine.NoteTypes):
        psg_note = self.psg_channels.get(output_type)
        if psg_note is not None:
            gb_note = self.note_arr[psg_note]
            fmod.stopSound(gb_note.fmod_channel)
            self.debug_fmod_playback(f'STOP {output_type.name} NOTE {psg_note}',
                                     gb_note.parent_channel, psg_note)
            gb_note.fmod_channel = 0
            self.channels[gb_note.parent_channel].notes_playing.remove(psg_note)
            gb_note.enable = False
        return psg_note

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
        for note in self.note_queue:
            note_id = self.free_note()
            if note_id is None:
                continue

            self.note_arr[note_id] = note
            channel = self.channels[note.parent_channel]
            channel.notes_playing.append(note_id)
            output_type = note.output_type
            self.psg_channels[output_type] = self.reset_psg(output_type)

            sample_id, frequency = self.get_playback_data(note)
            if not sample_id:
                return
            frequency *= math.pow(config.SEMITONE_RATIO, config.TRANSPOSE)
            pitch = (channel.pitch_bend - 0x40) / 0x40 * channel.pitch_range
            self.disable_notes(channel)

            output_frequency = round(
                frequency * math.pow(config.SEMITONE_RATIO, pitch))
            output_panning = channel.panning * 2
            if not channel.muted:
                output_volume = round(
                    (note.velocity / 0x7F) * (channel.volume / 0x7F) * 255)
            else:
                output_volume = 0
            volumes[note.parent_channel].append(output_volume)
            note.frequency = frequency
            note.phase = engine.NotePhases.INITIAL
            note.fmod_channel = fmod.playSound(
                note_id, self.fmod_samples[sample_id].fmod_id, None, True)
            self.debug_fmod_playback('PLAY NOTE', note.parent_channel, note_id)
            fmod.setFrequency(note.fmod_channel, output_frequency)
            self.debug_fmod_playback('SET FREQUENCY', note.parent_channel,
                                     note_id, f'{output_frequency} Hz')
            fmod.setPan(note.fmod_channel, output_panning)
            self.debug_fmod_playback('SET PANNING', note.parent_channel,
                                     note_id)
            fmod.setPaused(note.fmod_channel, False)
            self.debug_fmod_playback('UNPAUSE NOTE', note.parent_channel,
                                     note_id)

        for chan_id, vol in enumerate(map(self.average_volumes, volumes)):
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
        volumes = [[] for i in range(len(self.channels))]
        for note_id, note in enumerate(self.note_arr):
            channel = self.channels[note.parent_channel]
            if not note.enable:
                continue

            if note.note_off and note.phase < engine.NotePhases.RELEASE:
                note.env_step = 0
                note.phase = engine.NotePhases.RELEASE

            if note.env_step == 0 or (note.env_pos == note.env_dest) or (
                    note.env_step <= 0 and note.env_pos <= note.env_dest) or (
                        note.env_step >= 0 and note.env_pos >= note.env_dest):
                output, phase = note.output_type, note.phase
                if phase == engine.NotePhases.INITIAL:
                    note.phase = engine.NotePhases.ATTACK
                    note.env_pos = 0
                    note.env_dest = 255
                    if output > engine.NoteTypes.DIRECT:
                        note.env_step = (0x8 - note.attack) * 32 * (0x7F / (
                            note.velocity + 1))
                    else:
                        note.env_step = note.attack
                elif phase == engine.NotePhases.ATTACK:
                    note.phase = engine.NotePhases.DECAY
                    note.env_dest = note.sustain
                    if output > engine.NoteTypes.DIRECT:
                        note.env_dest *= 17
                        if not note.decay:
                            note.env_step = 0
                        else:
                            note.env_step = (note.decay - 0x8) * 32 * (
                                0x7F / note.velocity)
                    else:
                        note.env_step = (note.decay - 0x100)
                elif phase == engine.NotePhases.DECAY:
                    note.phase = engine.NotePhases.SUSTAIN
                    note.env_step = 0
                elif phase == engine.NotePhases.SUSTAIN:
                    note.env_step = 0
                elif phase == engine.NotePhases.RELEASE:
                    note.phase = engine.NotePhases.NOTEOFF
                    note.env_dest = 0
                    if output > engine.NoteTypes.DIRECT:
                        if not note.release:
                            note.env_step = -255
                        else:
                            note.env_step = (note.release - 0x8) * 32 * (
                                0x7F / note.velocity)
                    else:
                        note.env_step = (note.release - 0x100) * (
                            self.echo / 127)
                elif phase == engine.NotePhases.NOTEOFF:
                    if output > engine.NoteTypes.DIRECT:
                        self.psg_channels[output] = None
                    fmod.stopSound(note.fmod_channel)
                    self.debug_fmod_playback('STOP NOTE', note.parent_channel,
                                             note_id,
                                             f'FCHAN: {note.fmod_channel}')
                    note.fmod_channel = 0
                    note.enable = False
                    note.lfos_position = 0
                    note.parent_channel = -1
                    channel.notes_playing.remove(note_id)

            delta_pos = note.env_pos + note.env_step
            if delta_pos > note.env_dest and note.env_step > 0 or delta_pos < note.env_dest and note.env_step < 0:
                delta_pos = note.env_dest
            note.env_pos = delta_pos

            if channel.muted:
                continue

            vel = note.velocity / 0x7F
            vol = channel.volume / 0x7F
            pos = note.env_pos / 0xFF
            volume = round(vel * vol * pos * 255)
            volumes[note.parent_channel].append(volume)
            fmod.setVolume(note.fmod_channel, volume)
            self.debug_fmod_playback('SET NOTE VOLUME', note.parent_channel,
                                     note_id, volume)

        for channel_id, channel in enumerate(self.channels):
            channel.output_volume = self.average_volumes(volumes[channel_id])

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
        self.update_channels()
        self.play_notes()
        self.update_notes()
        self.advance_notes()
        self.update_vibrato()
        for channel in self.channels:
            if channel.enabled:
                return 1
        fmod.systemClose()
        return 0

    def average_volumes(self, volumes: typing.List[int]) -> int:
        if not len(volumes):
            return 0
        return round(sum(volumes) / len(volumes))

    def get_player_header(self, meta_data: parser.MetaData) -> str:
        """Construct the interface header.

        Constructs a column-based display, with each column representing one
        channel. Each column contains the channel's ID and output type.

        """
        TITLE_TOP = f'{DOWN_AND_RIGHT}{"":{HORIZONTAL}>20}{DOWN_AND_LEFT}'
        TITLE = f'{VERTICAL} SAPPY M4A EMULATOR {VERTICAL}'
        TITLE_BOTTOM = f'{UP_AND_RIGHT}{"":{HORIZONTAL}>20}{UP_AND_LEFT}'
        HEADER_TOP = f'{DOWN_AND_RIGHT}{"":{HORIZONTAL}>16}{DOWN_AND_LEFT}'
        HEADER_ROM = f'{VERTICAL} {meta_data.rom_name:^14} {VERTICAL}'
        HEADER_CODE = f'{VERTICAL} {meta_data.code:^14} {VERTICAL}'
        TOP = f'{VERTICAL_AND_RIGHT}{"":{HORIZONTAL}>16}{VERTICAL_AND_HORIZONTAL}{"":{HORIZONTAL}>10}{DOWN_AND_LEFT}'
        TABLE_POINTER = f'{VERTICAL} TABLE POINTER: {VERTICAL} {f"0x{meta_data.song_ptr:X}":<8} {VERTICAL}'
        SONG_PTR = f'{VERTICAL}  SONG POINTER: {VERTICAL} {f"0x{meta_data.header_ptr:X}":<8} {VERTICAL}'
        VOICE_PTR = f'{VERTICAL} VOICE POINTER: {VERTICAL} {f"0x{meta_data.voice_ptr:X}":<8} {VERTICAL}'
        ECHO = f'{VERTICAL}        REVERB: {VERTICAL} {f"{(meta_data.echo-128)/127 if meta_data.echo_enabled else 0:<2.0%}":<8} {VERTICAL}'
        BOTTOM = f'{UP_AND_RIGHT}{"":{HORIZONTAL}>16}{UP_AND_HORIZONTAL}{"":{HORIZONTAL}>10}{UP_AND_LEFT}'
        info = '\n'.join((TITLE_TOP, TITLE, TITLE_BOTTOM, HEADER_TOP,
                          HEADER_ROM, HEADER_CODE, TOP, TABLE_POINTER, SONG_PTR,
                          VOICE_PTR, ECHO, BOTTOM)) + '\n'
        header = []
        for chan_id in range(len(self.channels)):
            header.append(f' CHANNEL {chan_id:<{self.WIDTH+1}} ')
        header.append(f' TEMPO ')
        header = VERTICAL + VERTICAL.join(header) + VERTICAL

        top_seperator = [f'{"":{HORIZONTAL}>{self.WIDTH+11}}'] * len(
            self.channels)
        bot_seperator = [
            f'{"":{HORIZONTAL}>10}{DOWN_AND_HORIZONTAL}{"":{HORIZONTAL}>{self.WIDTH}}'
        ] * len(self.channels)
        top_seperator = DOWN_AND_RIGHT + DOWN_AND_HORIZONTAL.join(
            top_seperator) + TEMPO_TOP
        bot_seperator = VERTICAL_AND_RIGHT + VERTICAL_AND_HORIZONTAL.join(
            bot_seperator) + TEMPO_BOTTOM
        return info + top_seperator + '\n' + header + '\n' + bot_seperator

    def display(self) -> None:
        """Update and display the interface."""
        out = self.update_interface()
        sys.stdout.write(out + '\r')
        sys.stdout.flush()
        return 0

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
        MAX_VOLUME = 255
        lines = []
        for channel in self.channels:
            channel: engine.Channel

            base, end = divmod(channel.output_volume, MAX_VOLUME / self.WIDTH)
            if not end:
                end = ''
            else:
                eighth_ticks = MAX_VOLUME / self.WIDTH / 8
                end = BLOCK_TABLE.get(8 - (end // eighth_ticks), '')
            vol_bar = f'{"":{FULL_BLOCK}>{base}}'
            column = f'{vol_bar}{end}'

            notes = []
            playing = [
                self.note_arr[note_id].note_num
                for note_id in channel.notes_playing
                if not self.note_arr[note_id].note_off
            ]
            for note in map(engine.get_note, playing):
                notes.append(f'{note:^4}')
            notes = notes[:self.WIDTH // 4 - 1]
            notes.append(f'{channel.wait_ticks:^3}')
            notes = ''.join(notes)

            column = list(f'{column}{" ":<{abs(self.WIDTH - len(column))}}')
            column[self.WIDTH // 2] = '|'

            insert_pt = round(channel.panning / (instructions.mxv /
                                                 (self.WIDTH - 1)))
            column[insert_pt] = chr(0x2573)

            insert_pt = self.WIDTH - len(notes)
            column[insert_pt:] = notes

            column = ''.join(column)
            lines.append(
                f' {channel.output_type.name:^8} {VERTICAL}{column:^{self.WIDTH - 1}}'
            )

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
        self.fmod_samples = song.samples
        self.multi_samples = song.insts
        self.direct_samples = song.directs
        self.echo_enabled = song.meta_data.echo_enabled  # pylint: disable=E1101
        if self.echo_enabled:
            self.echo = 127 - (song.meta_data.echo - 128)
        else:
            self.echo = 127
        self.init_player(fpath)

        header = self.get_player_header(song.meta_data)
        sys.stdout.write(header + '\n')
        self.execute_processor()

    def print_exit_message(self) -> None:
        sys.stdout.write('\n')
        seperator = [
            f'{"":{HORIZONTAL}>10}{UP_AND_HORIZONTAL}{"":{HORIZONTAL}>{self.WIDTH}}'
        ] * len(self.channels)
        exit_str = UP_AND_RIGHT + UP_AND_HORIZONTAL.join(
            seperator) + f'{UP_AND_HORIZONTAL}{"":{HORIZONTAL}>7}{UP_AND_LEFT}'
        sys.stdout.write('\n'.join((exit_str, 'Exiting...')))
        return

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
        FRAME_DELAY = 1 / config.PLAYBACK_FRAMERATE

        # Local function copies
        d = self.display
        e = self.update_processor
        f = math.fabs
        t = time.perf_counter
        s = time.sleep
        tick_ctr = 0.0
        playing = True
        try:
            while playing:
                prev_ticks_per_frame = int(tick_ctr)
                tick_ctr += round((self.tempo / 2) / (config.TICKS_PER_SECOND / config.PLAYBACK_SPEED),
                                  2)
                ticks_per_frame = int(tick_ctr - prev_ticks_per_frame)
                tick_ctr = math.fmod(tick_ctr, config.TICKS_PER_SECOND)
                start_time = t()
                d()
                for _ in range(ticks_per_frame):
                    if not e():
                        playing = False
                    d()
                if round(FRAME_DELAY - (t() - start_time), 3) < 0:
                    continue
                s(f(round(FRAME_DELAY - (t() - start_time), 3)))
        except KeyboardInterrupt:
            pass
        finally:
            self.print_exit_message()

    def stop_song(self):
        """Stop playback and reset the player."""
        self.reset_player()
        fmod.systemClose()
