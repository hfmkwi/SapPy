# -*- coding: utf-8 -*-
"""All playback related functionality for the Sappy Engine.

Attributes
----------
BASE: float
    Base multiplier for calculating MIDI note frequencies from the base 440Hz

"""
import logging
import math
import os
import random
import sys
import time
import typing

import sappy.decoder as decoder
import sappy.engine as engine
import sappy.fileio as fileio
import sappy.fmod as fmod

BASE = math.pow(2, 1 / 12)


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

    DEBUG = False
    GB_SQ_MULTI = 0.5 / 4
    SAPPY_PPQN = 24
    WIDTH = 33

    if DEBUG:
        logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger(name=__name__)

    if WIDTH < 17:
        WIDTH = 17

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

        channels : engine.ChannelQueue[engine.Channel]
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

        samples : engine.SampleQueue[engine.Sample]
            A VB6 collection containing all runtime samples utilized
            during playback.


        """
        self._global_vol = volume
        self.looped = False
        self.gb1_channel = None
        self.gb2_channel = None
        self.gb3_channel = None
        self.gb4_channel = None
        self.tempo = 0
        self.note_arr = engine.Collection([engine.Note(*[0] * 6)] * 32)
        self.noise_wavs = [[[] for i in range(10)] for i in range(2)]
        self.channels = engine.ChannelQueue()
        self.directs = engine.DirectQueue()
        self.drumkits = engine.DrumKitQueue()
        self.insts = engine.InstrumentQueue()
        self.note_queue = engine.NoteQueue()
        self.samples = engine.SampleQueue()
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
        self.log.debug(
            f'| FMOD | CODE: {fmod.getError():2} | {action:<16} |{"|".join([f" {arg:<16}" for arg in args]) + "|" if args else ""}'
        )

    def debug_fmod_playback(self, action: str, channel_id: int, note_id: int,
                            *args: typing.List[str]):
        """Output playback debug information."""
        self.log.debug(
            f'| FMOD | CODE: {fmod.getError():2} | CHAN: {channel_id:2} | NOTE: {note_id:2} | {action:<16} |{"|".join([f" {arg:<15}" for arg in args]) + "|" if args else ""}'
        )

    def debug_processor(self, action: str, channel_id: int,
                        *args: typing.List[str]):
        """Output processor execution information."""
        self.log.debug(
            f'| EXEC | CHAN: {channel_id:2} | {action:^38} |{"|".join([f" {arg:<15}" for arg in args]) + "|" if args else ""}'
        )

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

        # Reset the current note on each PSG channel to None
        self.gb1_channel = None
        self.gb2_channel = None
        self.gb3_channel = None
        self.gb4_channel = None

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

    def direct_exists(self, directs: engine.DirectQueue, id: int) -> bool:
        """Check if a direct exists in a specfied direct ID.

        Notes
        -----
        Locally overrides the builtin `id` function, although it is unused here.

        Parameters
        ----------
        directs
            A queue of directs to check
        id
            The ID of the direct to check for

        Returns
        -------
        bool
            True if the queue contains a direct with the corresponding ID.
            False otherwise.

        """
        id = str(id)
        for direct in directs:
            direct: engine.Direct
            if direct.key == id:
                return True
        return False

    def drm_exists(self, id: int) -> bool:
        """Check if a drumkit exists with the corresponding ID.

        Notes
        -----
        Locally overrides the builtin `id` function, although it is unused here.

        Parameters
        ----------
        id
            The ID of the drumkit to check for

        Returns
        -------
            True if the queue contains an drumkit with the corresponding ID.
            False otherwise.

        """
        id = str(id)
        for drm in self.drumkits:
            if drm.key == id:
                return True
        return False

    def inst_exists(self, id: int) -> bool:
        """Check if an instrument exists with the corresponding ID.

        Notes
        -----
        Locally overrides the builtin `id` function, although it is unused here.

        Parameters
        ----------
        id
            The ID of the instrument to check for

        Returns
        -------
            True if the queue contains an instrument with the corresponding ID.
            False otherwise.

        """
        for inst in self.insts:
            if inst.key == str(id):
                return True
        return False

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
        mode = fmod.FSoundModes._8BITS + fmod.FSoundModes.LOADRAW + fmod.FSoundModes.MONO  # PCM8 Mono sample
        if loop:  # Is looping sample?
            mode += fmod.FSoundModes.LOOP_NORMAL
        if gb_wave:  # Is signed PCM8?
            mode += fmod.FSoundModes.UNSIGNED  # PSG sample
        else:
            mode += fmod.FSoundModes.SIGNED  # Signed PCM8
        fpath = fpath.encode('ascii')
        index = fmod.FSoundChannelSampleMode.FREE
        return fmod.sampleLoad(index, fpath, mode, offset, size)

    def load_directsound(self, sample_pool: engine.SampleQueue,
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
        for sample in sample_pool:
            sample: engine.Sample

            # Check if the sample if a PSG sample
            if sample.gb_wave is True:
                # Check if the sample is in string form
                if not self.val(sample.smp_data):
                    # Write sample data to temp file, load into the FMOD player, and remove the temp file.
                    with fileio.open_new_file('temp.raw', 2) as f:
                        f.wr_str(sample.smp_data)
                    sample.fmod_smp = self.load_sample('temp.raw')

                    # Remove temporary file
                    os.remove('temp.raw')
                else:
                    # Load the sample data directly from the ROM
                    sample.fmod_smp = self.load_sample(
                        file_path, sample.smp_data, sample.size)
                self.debug_fmod('LOAD SAMPLE', f'ID: {sample.fmod_smp}',
                                f'SIZE: {sample.size}')

                # Set the loop points as a 32-byte sample
                fmod.setLoopPoints(sample.fmod_smp, 0, 31)
                self.debug_fmod('SET LOOP POINTS', f'0 - 31')
                continue

            # Check if the sample is in string form
            if self.val(sample.smp_data) == 0:
                # Write sample data to temp file, load into the FMOD player, and remove the temp file.
                with fileio.open_new_file('temp.raw', 2) as f:
                    f.wr_str(sample.smp_data)
                sample.fmod_smp = self.load_sample(
                    'temp.raw', loop=sample.loop, gb_wave=False)
                os.remove('temp.raw')
            else:
                # Load the sample directly from the ROM
                sample.fmod_smp = self.load_sample(
                    file_path, sample.smp_data, sample.size, sample.loop, False)
            self.debug_fmod('LOAD SAMPLE', f'ID: {sample.fmod_smp}',
                            f'SIZE: {sample.size}')

            # Set the loop points to the arbitrary points dictated by the sample
            fmod.setLoopPoints(sample.fmod_smp, sample.loop_start,
                               sample.size - 1)
            self.debug_fmod('SET LOOP POINTS',
                            f'{sample.loop_start} - {sample.size - 1}')

    def load_square(self, sample_pool: engine.SampleQueue) -> None:
        """Load in all square waves into the sample pool.

        There are 4 square waves loaded into memory by ascending duty
        cycle. The duty cycle is determined by a ratio of (high:low)
        periods out of 32 total periods.

        The square waves have duty cycles of: 12.5%, 25%, 50%, 75%

        """
        # Construct the high and low period samples
        high = chr(int(0x80 + 0x7F * self.GB_SQ_MULTI))
        low = chr(int(0x80 - 0x7F * self.GB_SQ_MULTI))

        for duty_cycle in range(4):
            # Construct a square wave sample
            square = f'square{duty_cycle}'
            sample_pool.add(square)
            sample: engine.Sample = sample_pool[square]
            if duty_cycle < 3:
                l = [high] * (2**(duty_cycle + 2))  # Possible values: 4, 8, 16
                r = [low] * (32 - 2**
                             (duty_cycle + 2))  # Possible values; 28, 24, 16
            else:
                l = [high] * 24
                r = [low] * 8
            sample.smp_data = "".join(l + r)
            sample.frequency = 7040
            sample.size = 32

            # Write sample data to temporary file
            filename = f'{square}.raw'
            with fileio.open_new_file(filename, 2) as f:
                f.wr_str(sample.smp_data)

            # Load square wave into the FMOD player and set its loop points
            sample.fmod_smp = self.load_sample(filename, 0, 0)
            self.debug_fmod(f'LOAD SQUARE {duty_cycle}',
                            f'ID: {sample.fmod_smp}')
            fmod.setLoopPoints(sample.fmod_smp, 0, 31)
            self.debug_fmod('SET LOOP POINTS', '0 - 31')

            # Remove temporary file
            os.remove(filename)

    def load_noise(self, sample_pool: engine.SampleQueue) -> None:
        """Load all noise waves into the sample pool.

        There are two types of samples noise waves loaded into memory: a
        4096-sample (normal) wave and a 256-sample (metallic) wave. 10 of
        each are loaded in. Each sample has a base frequency of 7040 Hz.

        """
        for i in range(10):
            # Construct normal wave data
            wave_data = ''.join(
                map(chr, [random.randint(0, 152) for _ in range(4096)]))

            # Add a 4096-sample 7040Hz normal wave
            noise = f'noise0{i}'
            sample_pool.add(noise)
            sample = sample_pool[noise]
            sample.smp_data = wave_data
            sample.frequency = 7040
            sample.size = 4096

            # Write wave data to temporary file
            filename = f'{noise}.raw'
            with fileio.open_new_file(filename, 2) as f:
                f.wr_str(sample.smp_data)

            # Load in normal wave and set its loop points
            sample.fmod_smp = self.load_sample(filename)
            self.log.debug(
                f'| FMOD | CODE: {fmod.getError():4} | LOAD NSE0{i} | S{sample.fmod_smp}'
            )
            fmod.setLoopPoints(sample.fmod_smp, 0, 16383)
            self.log.debug(
                f'| FMOD | CODE: {fmod.getError():4} | SET LOOP   | (0, 16383)')

            # Remove the temporary file
            os.remove(filename)

            # Construct metallic wave data
            wave_data = ''.join(
                map(chr, [random.randint(0, 152) for _ in range(256)]))

            # Add a 256-sample 7040 Hz metallic wave
            noise = f'noise1{i}'
            sample_pool.add(noise)
            sample = sample_pool[noise]
            sample.smp_data = wave_data
            sample.frequency = 7040
            sample.size = 256

            # Write wave data to temporary file
            filename = f'{noise}.raw'
            with fileio.open_new_file(filename, 2) as f:
                f.wr_str(sample.smp_data)

            # Load in metallic wave and set its loop points
            sample.fmod_smp = self.load_sample(filename)
            self.log.debug(
                f'| FMOD | CODE: {fmod.getError():4} | LOAD NSE1{i} | S{sample.fmod_smp}'
            )
            fmod.setLoopPoints(sample.fmod_smp, 0, 255)
            self.log.debug(
                f'| FMOD | CODE: {fmod.getError():4} | SET LOOP   | (0, 255)')
            os.remove(filename)

    def init_player(self, fpath: str) -> None:
        """Iniate the FMOD player and load in all samples.

        The sound output is initially set to WINSOUND and the FMOD player
        is then initiated with 64 channels at a sample rate of 44100 Hz.

        """
        self.debug_fmod('START')

        # Set the output of the FMOD library to WINSOUND (0).
        fmod.setOutput(1)
        self.debug_fmod('SET OUTPUT')

        # Initialize FMOD @44100 Hz and a maximum of 64 possible playback channels.
        fmod.systemInit(44100, 64, 0)
        self.debug_fmod('INIT PLAYER')

        # Set the volume to the current default (255).
        fmod.setMasterVolume(self.global_vol)
        self.debug_fmod('SET VOLUME', f'VOLUME: self.global_vol')

        # Load in all samples
        self.load_directsound(self.samples, fpath)
        self.load_noise(self.samples)
        self.load_square(self.samples)

        self.debug_fmod('FINISH')

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
        for chan in self.channels:
            # Check if the channel is enabled and if vibrato is enabled
            if not chan.is_enabled or chan.vib_rate == 0 or chan.vib_depth == 0:
                continue

            for note_id in chan.notes:
                note = self.note_arr[note_id.note_id]

                # Skip note if disabled or not notes_playing
                if not note.enable or note.note_off:
                    continue

                # Calculate and apply the frequency shift
                delta_freq = math.sin(math.pi * note.vib_pos) * chan.vib_depth
                pitch = (chan.pitch_bend - 0x40 + delta_freq
                        ) / 0x40 * chan.pitch_range
                frequency = int(note.frequency * math.pow(BASE, pitch))
                fmod.setFrequency(note.fmod_channel, frequency)

                # Advance the vibrato position by the vibrato rate
                note.vib_pos += 1 / (96 / chan.vib_rate)
                note.vib_pos = math.fmod(note.vib_pos, 2)

    def advance_notes(self) -> None:
        """Advance each note 1 tick and release all 0-tick notes."""
        for note in self.note_arr:
            note: engine.Note
            if note.enable:
                if note.wait_ticks > 0:
                    note.wait_ticks -= 1
                if note.wait_ticks <= 0 and note.note_off is False:
                    chan = self.channels[note.parent]
                    if chan.is_sustain is False:
                        self.reset_note(note)

    def update_channels(self) -> None:
        """Advance each channel 1 tick and continue processor execution for all 0-tick channels."""
        in_for = True
        for chan_id, chan in enumerate(self.channels):
            if chan.is_enabled is False:
                self.log.debug(f'| CHAN: {chan_id:>4} | SKIP EXEC  |')
                continue
            if chan.wait_ticks > 0:
                chan.wait_ticks -= 1
            while chan.wait_ticks <= 0:
                event_queue: engine.Event = chan.event_queue[chan.program_ctr]
                cmd_byte = event_queue.cmd_byte
                args = event_queue.arg1, event_queue.arg2, event_queue.arg3

                if cmd_byte in (0xB1, 0xB6):
                    chan.is_enabled = False
                    chan.is_sustain = False
                    in_for = False
                    self.debug_processor('STOP EXECUTION', chan_id)
                    return
                elif cmd_byte == 0xB9:
                    chan.program_ctr += 1
                    self.debug_processor('CONDITIONAL JUMP (UNUSED)', chan_id,
                                         '')
                elif cmd_byte == 0xBA:
                    chan.priority = args[0]
                    chan.program_ctr += 1
                    self.debug_processor('SET PRIORITY', chan_id, chan.priority)
                elif cmd_byte == 0xBB:
                    self.tempo = args[0] * 2
                    self.debug_processor('SET TEMPO', chan_id, self.tempo)
                    chan.program_ctr += 1
                elif cmd_byte == 0xBC:
                    chan.transpose = engine.sbyte_to_int(args[0])
                    self.debug_processor('SET TRANSPOSE', chan_id,
                                         chan.transpose)
                    chan.program_ctr += 1
                elif cmd_byte == 0xBD:
                    chan.patch_num = args[0]
                    if self.direct_exists(self.directs, chan.patch_num):
                        chan.output_type = self.directs[str(
                            chan.patch_num)].output
                    elif self.inst_exists(chan.patch_num):
                        chan.output_type = engine.ChannelTypes.MULTI
                    elif self.drm_exists(chan.patch_num):
                        chan.output_type = engine.ChannelTypes.DRUMKIT
                    else:
                        chan.output_type = engine.ChannelTypes.NULL
                    self.debug_processor('SET OUTPUT', chan_id,
                                         chan.output_type.name)
                    chan.program_ctr += 1
                elif cmd_byte == 0xBE:
                    chan.main_vol = args[0]
                    self.debug_processor('SET CHANNEL VOLUME', chan_id,
                                         chan.main_vol)
                    for nid in chan.notes:
                        note: engine.Note = self.note_arr[nid.note_id]
                        if not note.enable or note.parent != chan_id:
                            continue
                        dav = 0
                        if not chan.is_muted:
                            vel = note.velocity / 0x7F
                            vol = chan.main_vol / 0x7F
                            pos = note.env_pos / 0xFF
                            dav = int(vel * vol * pos * 255)
                        chan.output_volume = dav
                        fmod.setVolume(note.fmod_channel, dav)
                        self.debug_fmod_playback('SET NOTE VOLUME', chan_id,
                                                 nid.note_id, dav)
                    chan.program_ctr += 1
                elif cmd_byte == 0xBF:
                    chan.panning = args[0]
                    panning = chan.panning * 2
                    self.debug_processor('SET CHANNEL PANNING', chan_id,
                                         chan.panning)
                    for nid in chan.notes:
                        note = self.note_arr[nid.note_id]
                        if not note.enable or note.parent != chan_id:
                            continue
                        fmod.setPan(note.fmod_channel, panning)
                        self.debug_fmod_playback('SET NOTE PANNING', chan_id,
                                                 nid.note_id, panning)
                    chan.program_ctr += 1
                elif cmd_byte in (0xC0, 0xC1):
                    if cmd_byte == 0xC0:
                        chan.pitch_bend = args[0]
                        self.debug_processor('SET PITCH BEND', chan_id,
                                             chan.pitch_bend)
                    else:
                        chan.pitch_range = engine.sbyte_to_int(args[0])
                        self.debug_processor('SET PITCH RANGE', chan_id,
                                             chan.pitch_range)
                    chan.program_ctr += 1
                    for nid in chan.notes:
                        note: engine.Note = self.note_arr[nid.note_id]
                        if not note.enable or note.parent != chan_id:
                            continue
                        pitch = (
                            chan.pitch_bend - 0x40) / 0x40 * chan.pitch_range
                        frequency = int(note.frequency * math.pow(BASE, pitch))
                        fmod.setFrequency(note.fmod_channel, frequency)
                        self.debug_fmod_playback('SET NOTE FREQ', chan_id,
                                                 nid.note_id, frequency)
                elif cmd_byte == 0xC2:
                    chan.vib_rate = args[0]
                    self.debug_processor('SET VIBRATO RATE', chan_id,
                                         chan.vib_rate)
                    chan.program_ctr += 1
                elif cmd_byte == 0xC4:
                    chan.vib_depth = args[0]
                    self.debug_processor('SET VIBRATO RNGE', chan_id,
                                         chan.vib_depth)
                    chan.program_ctr += 1
                elif cmd_byte == 0xCE:
                    chan.is_sustain = False
                    self.debug_processor('DISABLE SUSTAIN', chan_id)
                    for nid in chan.notes:
                        note: engine.Note = self.note_arr[nid.note_id]
                        if not note.enable or note.note_off:
                            continue
                        self.reset_note(note)
                        self.debug_processor('RELEASE NOTE', chan_id,
                                             nid.note_id)
                    chan.program_ctr += 1
                elif cmd_byte == 0xB3:
                    chan.program_ctr = event_queue.evt_q_ptr
                    self.debug_processor('DEFINE SUBROUTINE', chan_id,
                                         chan.program_ctr)
                    chan.sub_ctr += 1
                    chan.rtn_ptr += 1
                    chan.in_sub = True
                elif cmd_byte == 0xB4:
                    if chan.in_sub:
                        chan.program_ctr = chan.rtn_ptr
                        chan.in_sub = False
                        self.debug_processor('END SUBROUTINE', chan_id,
                                             chan.program_ctr)
                    else:
                        self.debug_processor('NOP (NO OPERATION)', chan_id)
                        chan.program_ctr += 1
                    for nid in chan.notes:
                        note: engine.Note = self.note_arr[nid.note_id]
                        self.reset_note(note)
                        self.debug_processor('RELEASE NOTE', chan_id,
                                             nid.note_id)
                elif cmd_byte == 0xB2:
                    self.looped = True
                    chan.in_sub = False
                    chan.program_ctr = chan.loop_ptr
                    chan.is_sustain = False
                    self.debug_processor('JUMP TO ADDRESS', chan_id,
                                         chan.program_ctr)
                    for nid in chan.notes:
                        note: engine.Note = self.note_arr[nid.note_id]
                        self.reset_note(note)
                        self.debug_processor('RELEASE NOTE', chan_id,
                                             nid.note_id)
                elif cmd_byte >= 0xCF:
                    ll = engine.stlen_to_ticks(cmd_byte - 0xCF) + 1
                    if cmd_byte == 0xCF:
                        chan.is_sustain = True
                        ll = -1
                    nn, vv, uu = args
                    self.note_queue.add(nn, vv, chan_id, uu, ll, chan.patch_num)
                    self.debug_processor(
                        'QUEUE NEW NOTE', chan_id, f'{ll:2} ticks',
                        engine.note_to_name(nn), f'VOL: {vv:3}', f'UNK: {uu:3}')
                    chan.program_ctr += 1
                elif cmd_byte <= 0xB0:
                    if self.looped:
                        self.looped = False
                        chan.wait_ticks = 0
                        continue
                    n_event_queue = chan.event_queue[chan.program_ctr + 1]
                    if chan.program_ctr > 0:
                        chan.wait_ticks = n_event_queue.ticks - event_queue.ticks
                    else:
                        chan.wait_ticks = n_event_queue.ticks
                    self.debug_processor('UNKNOWN OP FUNCTION', chan_id,
                                         f'{chan.wait_ticks:<2} ticks')
                    chan.program_ctr += 1
                else:
                    self.debug_processor('UNKNOWN OP CODE', chan_id,
                                         f'{cmd_byte:x}')
                    chan.program_ctr += 1
            if not in_for:
                self.log.debug(f'| CHAN: {chan_id:>4} | STOP EXEC  | ')
                break

    def set_note(self, note: engine.Note, direct: engine.Direct):
        """Assign a Direct's output and environment properties to a note."""
        note.output = direct.output
        note.env_attn = direct.env_attn
        note.env_dcy = direct.env_dcy
        note.env_sus = direct.env_sus
        note.env_rel = direct.env_rel

    def get_delta_smp_freq(self, item: engine.Note):
        """Get the sample ID and frequency of a note from the sample pool."""
        patch = str(item.patch_num)
        note_num = item.note_num
        delta_sample = ''
        delta_frequency = 0
        standard = (engine.DirectTypes.DIRECT, engine.DirectTypes.WAVEFORM)
        square = (engine.DirectTypes.SQUARE1, engine.DirectTypes.SQUARE2)
        if self.direct_exists(self.directs, patch):
            direct: engine.Direct = self.directs[patch]
            self.set_note(item, direct)
            self.debug_processor(
                'NEW DIRECT NOTE', item.parent, note_num,
                f'ATTN: {item.env_attn:3}', f'DECAY: {item.env_dcy:3}',
                f'SUSTAIN: {item.env_sus:3}', f'RELEASE: {item.env_rel:3}')
            if direct.output in standard:
                delta_sample = str(self.directs[patch].smp_id)
                delta_frequency = engine.note_to_freq(
                    note_num + (60 - self.directs[patch].drum_key),
                    self.samples[delta_sample].frequency)
                if self.samples[delta_sample].gb_wave:
                    delta_frequency /= 2
                self.debug_processor('DIRECT/WAVEFORM', item.parent,
                                     f'SMP: {delta_sample}',
                                     f'{delta_frequency} Hz')
            elif direct.output in square:
                delta_sample = f'square{self.directs[patch].gb1 % 4}'
                delta_frequency = engine.note_to_freq(
                    note_num + (60 - self.directs[patch].drum_key))
                self.debug_processor('SQUARE1/SQUARE2', item.parent,
                                     f'SMP: {delta_sample}',
                                     f'{delta_frequency} Hz')
            elif direct.output == engine.DirectTypes.NOISE:
                delta_sample = f'noise{self.directs[patch].gb1 % 2}{int(random.random() * 3)}'
                delta_frequency = engine.note_to_freq(
                    note_num + (60 - self.directs[patch].drum_key))
                self.debug_processor('PSG NOISE', item.parent,
                                     f'SMP: {delta_sample}',
                                     f'{delta_frequency} Hz')
        elif self.inst_exists(patch):
            direct: engine.Direct = self.insts[patch].directs[str(
                self.insts[patch].kmaps[str(note_num)].assign_dct)]
            self.set_note(item, direct)
            self.debug_processor(
                'NEW MULTI NOTE', item.parent, note_num,
                f'ATTN: {item.env_attn:3}', f'DECAY: {item.env_dcy:3}',
                f'SUSTAIN: {item.env_sus:3}', f'RELEASE: {item.env_rel:3}')
            if direct.output in standard:
                delta_sample = str(direct.smp_id)
                if direct.fix_pitch:
                    delta_frequency = self.samples[delta_sample].frequency
                else:
                    delta_frequency = engine.note_to_freq(
                        note_num, -2 if self.samples[delta_sample].gb_wave else
                        self.samples[delta_sample].frequency)
                self.debug_processor('DIRECT/WAVEFORM', item.parent,
                                     f'SMP: {delta_sample}',
                                     f'{delta_frequency} Hz')
            elif direct.output in square:
                delta_sample = f'square{direct.gb1 % 4}'
                delta_frequency = engine.note_to_freq(note_num)
                self.debug_processor('SQUARE1/SQUARE2', item.parent,
                                     f'SMP: {delta_sample}',
                                     f'{delta_frequency} Hz')
        elif self.drm_exists(patch):
            direct: engine.Direct = self.drumkits[patch].directs[str(note_num)]
            self.set_note(item, direct)
            self.debug_processor(
                'NEW DRUMKIT NOTE', item.parent, note_num,
                f'ATTN: {item.env_attn:3}', f'DECAY: {item.env_dcy:3}',
                f'SUSTAIN: {item.env_sus:3}', f'RELEASE: {item.env_rel:3}')
            if direct.output in standard:
                delta_sample = str(direct.smp_id)
                if direct.fix_pitch and not self.samples[delta_sample].gb_wave:
                    delta_frequency = self.samples[delta_sample].frequency
                else:
                    delta_frequency = engine.note_to_freq(
                        direct.drum_key, -2
                        if self.samples[delta_sample].gb_wave else
                        self.samples[delta_sample].frequency)
                self.debug_processor('DIRECT/WAVEFORM', item.parent,
                                     f'SMP: {delta_sample}',
                                     f'{delta_frequency} Hz')
            elif direct.output in square:
                delta_sample = f'square{direct.gb1 % 4}'
                delta_frequency = engine.note_to_freq(direct.drum_key)
                self.debug_processor('SQUARE1/SQUARE2', item.parent,
                                     f'SMP: {delta_sample}',
                                     f'{delta_frequency} Hz')
            elif direct.output == engine.DirectTypes.NOISE:
                delta_sample = f'noise{direct.gb1 % 2}{int(random.random() * 10)}'
                delta_frequency = engine.note_to_freq(direct.drum_key)
                self.debug_processor('PSG NOISE', item.parent,
                                     f'SMP: {delta_sample}',
                                     f'{delta_frequency} Hz')

        return delta_sample, delta_frequency

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
        for item in self.note_queue:
            note_num = self.free_note()
            self.debug_processor('GET FREE NOTE', item.parent, note_num)
            if note_num is None:
                continue

            self.note_arr[note_num] = item
            chan = self.channels[item.parent]

            # Reset all sustain or timeout notes that have
            for note_id in chan.notes:
                note = self.note_arr[note_id.note_id]
                if note.enable is True and note.note_off is False:
                    if note.wait_ticks == -1:
                        if not chan.is_sustain:
                            self.reset_note(note)
                            self.debug_processor('SUSTAIN NOTE OFF',
                                                 item.parent, note_id.note_id)
                    elif note.wait_ticks in (0, 1):
                        if chan.is_sustain:
                            self.reset_note(note)
                            self.debug_processor('TIMEOUT NOTE OFF',
                                                 item.parent, note_id.note_id)

            chan.notes.add(note_num, str(note_num))
            if self.note_arr[note_num].note_num not in chan.notes_playing:
                chan.notes_playing.append(self.note_arr[note_num].note_num)
            delta_sample, delta_frequency = self.get_delta_smp_freq(item)
            if not delta_sample:
                return
            delta_frequency *= math.pow(BASE, self.transpose)
            dav = (item.velocity / 0x7F) * (chan.main_vol / 0x7F) * 255
            out_type = self.note_arr[note_num].output

            if out_type == engine.NoteTypes.SQUARE1:
                if self.gb1_channel is not None:
                    gb_note = self.note_arr[self.gb1_channel]
                    fmod.stopSound(gb_note.fmod_channel)
                    self.debug_fmod_playback('STOP SQUARE1', item.parent,
                                             self.gb1_channel)
                    gb_note.fmod_channel = 0
                    self.channels[gb_note.parent].notes.remove(
                        str(self.gb1_channel))
                    gb_note.enable = False
                    if gb_note.note_num in chan.notes_playing:
                        chan.notes_playing.remove(gb_note.note_num)
                self.gb1_channel = note_num
            elif out_type == engine.NoteTypes.SQUARE2:
                if self.gb2_channel is not None:
                    gb_note = self.note_arr[self.gb2_channel]
                    fmod.stopSound(gb_note.fmod_channel)
                    self.debug_fmod_playback('STOP SQUARE2', item.parent,
                                             self.gb2_channel)
                    gb_note.fmod_channel = 0
                    self.channels[gb_note.parent].notes.remove(
                        str(self.gb2_channel))
                    gb_note.enable = False
                    if gb_note.note_num in chan.notes_playing:
                        chan.notes_playing.remove(gb_note.note_num)
                self.gb2_channel = note_num
            elif out_type == engine.NoteTypes.WAVEFORM:
                if self.gb3_channel is not None:
                    gb_note = self.note_arr[self.gb3_channel]
                    fmod.stopSound(gb_note.fmod_channel)
                    self.debug_fmod_playback('STOP WAVE', item.parent,
                                             self.gb3_channel)
                    gb_note.fmod_channel = 0
                    self.channels[gb_note.parent].notes.remove(
                        str(self.gb3_channel))
                    gb_note.enable = False
                    if gb_note.note_num in chan.notes_playing:
                        chan.notes_playing.remove(gb_note.note_num)
                self.gb3_channel = note_num
            elif out_type == engine.NoteTypes.NOISE:
                if self.gb4_channel is not None:
                    gb_note = self.note_arr[self.gb4_channel]
                    fmod.stopSound(gb_note.fmod_channel)
                    self.debug_fmod_playback('STOP NOISE', item.parent,
                                             self.gb4_channel)
                    gb_note.fmod_channel = 0
                    self.channels[gb_note.parent].notes.remove(
                        str(self.gb4_channel))
                    gb_note.enable = False
                    if gb_note.note_num in chan.notes_playing:
                        chan.notes_playing.remove(gb_note.note_num)
                self.gb4_channel = note_num

            pitch = (chan.pitch_bend - 0x40) / 0x40 * chan.pitch_range
            frequency = int(delta_frequency * math.pow(BASE, pitch))
            panning = chan.panning * 2
            volume = 0 if chan.is_muted else int(dav)
            chan.output_volume = volume
            note: engine.Note = self.note_arr[note_num]
            note.frequency = delta_frequency
            note.phase = engine.NotePhases.INITIAL
            if note.output == engine.NoteTypes.NOISE:
                continue

            note.fmod_channel = fmod.playSound(
                note_num, self.samples[delta_sample].fmod_smp, None, True)
            self.debug_fmod_playback('PLAY NOTE', note.parent, note_num)
            note.fmod_fx = fmod.enableFX(-3, 3)
            self.debug_fmod_playback('ENABLE FX', note.parent, note_num)
            fmod.setEcho(note.fmod_fx, 0.0, 0.0, 500.0, 500.0, False)
            self.debug_fmod_playback('SET ECHO', note.parent, note_num,
                                     f'{500} ms')
            fmod.setFrequency(note.fmod_channel, frequency)
            self.debug_fmod_playback('SET FREQUENCY', note.parent, note_num,
                                     f'{delta_frequency} Hz')
            fmod.setVolume(note.fmod_channel, volume)
            self.debug_fmod_playback('SET VOLUME', note.parent, note_num,
                                     volume)
            fmod.setPan(note.fmod_channel, panning)
            self.debug_fmod_playback('SET PANNING', note.parent, note_num)
            fmod.setPaused(note.fmod_channel, False)
            self.debug_fmod_playback('UNPAUSE NOTE', note.parent, note_num)
            assert fmod.getError() == 0
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
        for note_id, note in enumerate(self.note_arr):
            # Ignore note if disabled
            if not note.enable:
                continue

            # If note is off and phase is SUSTAIN/DECAY
            if note.note_off and note.phase < engine.NotePhases.RELEASE:
                note.env_step = 0
                note.phase = engine.NotePhases.RELEASE

            if note.env_step == 0 or (note.env_pos == note.env_dest) or (
                    note.env_step == 0 and note.env_pos <= note.env_dest) or (
                        note.env_step >= 0 and note.env_pos >= note.env_dest):
                if note.output == engine.NoteTypes.DIRECT:
                    if note.phase == engine.NotePhases.INITIAL:
                        note.phase = engine.NotePhases.ATTACK
                        note.env_pos = 0
                        note.env_dest = 255
                        note.env_step = note.env_attn
                    elif note.phase == engine.NotePhases.ATTACK:
                        note.phase = engine.NotePhases.DECAY
                        note.env_dest = note.env_sus
                        note.env_step = (note.env_dcy - 0x100) / 2
                    elif note.phase in (engine.NotePhases.DECAY,
                                        engine.NotePhases.SUSTAIN):
                        note.phase = engine.NotePhases.SUSTAIN
                        note.env_step = 0
                    elif note.phase == engine.NotePhases.RELEASE:
                        note.phase = engine.NotePhases.NOTEOFF
                        note.env_dest = 0
                        note.env_step = note.env_rel - 0x100
                    elif note.phase == engine.NotePhases.NOTEOFF:
                        fmod.setPaused(note.fmod_channel, True)
                        fmod.disableFX(note.fmod_channel)
                        self.debug_fmod_playback('DISABLE FX', note.parent,
                                                 note_id)
                        fmod.stopSound(note.fmod_channel)
                        self.debug_fmod_playback('STOP NOTE', note.parent,
                                                 note_id,
                                                 f'FCHAN: {note.fmod_channel}')
                        note.fmod_channel = 0
                        self.channels[note.parent].notes.remove(str(note_id))
                        note.enable = False
                else:
                    if note.phase == engine.NotePhases.INITIAL:
                        note.phase = engine.NotePhases.ATTACK
                        note.env_pos = 0
                        note.env_dest = 255
                        note.env_step = 0x100 - (note.env_attn * 8)
                    elif note.phase == engine.NotePhases.ATTACK:
                        note.phase = engine.NotePhases.DECAY
                        note.env_dest = 255 / note.env_sus * 2
                        note.env_step = (-note.env_dcy) / 2
                    elif note.phase == engine.NotePhases.RELEASE:
                        note.phase = engine.NotePhases.NOTEOFF
                        note.env_dest = 0
                        note.env_step = (0x8 - note.env_rel) * 2
                    elif note.phase in (engine.NotePhases.DECAY,
                                        engine.NotePhases.SUSTAIN):
                        note.phase = engine.NotePhases.SUSTAIN
                        note.env_step = 0
                    elif note.phase == engine.NotePhases.NOTEOFF:
                        if note.output == engine.NoteTypes.SQUARE1:
                            self.gb1_channel = None
                        elif note.output == engine.NoteTypes.SQUARE2:
                            self.gb2_channel = None
                        elif note.output == engine.NoteTypes.WAVEFORM:
                            self.gb3_channel = None
                        elif note.output == engine.NoteTypes.NOISE:
                            self.gb4_channel = None
                        fmod.setPaused(note.fmod_channel, True)
                        fmod.disableFX(note.fmod_channel)
                        self.debug_fmod_playback('DISABLE FX', note.parent,
                                                 note_id)
                        fmod.stopSound(note.fmod_channel)
                        self.debug_fmod_playback('STOP NOTE', note.parent,
                                                 note_id, note.fmod_channel)
                        note.fmod_channel = 0
                        self.channels[note.parent].notes.remove(str(note_id))
                        note.enable = False

            # Calculate and truncate the delta position
            delta_pos = note.env_pos + note.env_step
            if delta_pos > note.env_dest and note.env_step > 0 or delta_pos < note.env_dest and note.env_step < 0:
                delta_pos = note.env_dest
            note.env_pos = delta_pos

            # Calculate and set player volume; update display volume
            delta_volume = (note.velocity / 0x7F) * (
                self.channels[note.parent].main_vol / 0x7F) * (
                    note.env_pos / 0xFF) * 255
            volume = 0 if self.channels[note.parent].is_muted else int(
                delta_volume)
            self.channels[note.parent].output_volume = volume
            fmod.setVolume(note.fmod_channel, volume)
            self.debug_fmod_playback('SET NOTE VOLUME', note.parent, note_id,
                                     volume)

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

    def get_player_header(self) -> str:
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

        # Construct the top header
        header = []
        for chan_id, chan in enumerate(self.channels):
            header.append(
                f'| CHAN{chan_id:<2}{chan.output_type.name:>{self.WIDTH - 8}} ')
        header.append('| TEMPO |')
        header = ''.join(header)

        # Construct the seperator
        seperator = '+' + '+'.join(
            [f'{"":->{self.WIDTH}}'] * self.channels.count) + '+-------+'
        return header + '\n' + seperator

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

            # Construct the volume bar
            volume = round(chan.output_volume / (512 / (self.WIDTH - 1)))
            column = f'{"":=>{volume}}'

            # Construct the note/tick display
            notes = []
            for note in map(engine.note_to_name, chan.notes_playing):
                notes.append(f'{note:^4}')
            notes.append(f'{chan.wait_ticks:^3}')
            notes = ''.join(notes)

            # Construct the column
            column = list(f'{column + "|" + column:^{self.WIDTH}}')

            # Calculate the volume insertion point and insert into the column
            volume = str(chan.output_volume)
            column[1:len(volume) + 1] = volume

            # Calculate the note name insertion point and insert into the column
            insert_pt = self.WIDTH - len(notes)
            column[insert_pt:] = notes

            # Calculate the pan gauge insertion point and insert into the column
            insert_pt = round(chan.panning / (128 / (self.WIDTH - 1)))
            column[insert_pt] = ':'

            # Construct and append the finalized column
            column = ''.join(column)
            lines.append(f'{column:^{self.WIDTH - 1}}')

        # Format the output into columns
        out = ['']
        for line in lines:
            out.append(f'{line:{self.WIDTH - 1}}')
        out.append('')
        out = f'{"|".join(out)}{self.tempo:>5}  |'
        return out

    def play_song(self, fpath: str, song_num: int, song_table: int) -> None:
        """Play a song in the specified ROM."""
        d = decoder.Decoder()
        self.reset_player()
        self.channels, self.drumkits, self.samples, self.insts, self.directs, self.meta_data = d.load_song(
            fpath, song_num, song_table)
        if len(self.channels) == 0:
            return
        self.init_player(fpath)

        header = self.get_player_header()
        print(self.meta_data)
        print(header)
        self.process()

    def process(self) -> None:
        """Execute the event processor and update the user display.

        Notes
        -----
            The loop delay is calculate based on the current tempo of the
            event processor. In the event that the event processor's
            runtime exceeds this delay, the loop immediately cycles and no
            delay is.

            The loop delay is calculated based on the following equation:

            60.0 / (TEMPO * PPQN)

            where PPQN represents the processor cycles/250 milliseconds.

            Additionally, all functions used within the mainloop are
            assigned local delegates to avoid the global function
            lookup upon a function call.

        """
        e = self.update_processor
        s = time.sleep
        r = round
        t = time.time
        d = self.display
        ppqn = 24
        while True:
            st = t()
            d()
            if not e():
                break
            tm = r(60.0 / (self.tempo * ppqn), 4)
            if r(tm - r(t() - st, 4), 3) <= 0:
                continue
            s(r(tm - r(t() - st, 4), 3))

    @staticmethod
    def val(expr: str) -> typing.Union[float, int]:
        """Mimic the behavior of the builtin VB 2006 `Val` function.

        This function finds the first occurrence of a number in a string.
        The number may be in base-2, base-8, base-10, or base-16 form as
        defined in the Python standard library. The number may also be a
        float. Any encounter of alpha-characters or the null character will
        terminate the parser. An invalid string expressiong will terminate the
        parser. The space character is ignore during parsing.

        The most equivalent behaviour of this function in the Python standard
        library is the `eval` function.

        Parameters
        ----------
        expr
            A valid string expression

        Returns
        -------
        float, int
            On success, a float or an integer.
            On failure, 0.

        """
        if not expr or expr is None:
            return 0
        try:
            f = float(expr)
            i = int(f)
            if f == i:
                return i
            return f
        except ValueError:
            out = []
            is_float = False
            is_signed = False
            is_hex = False
            is_octal = False
            is_bin = False
            sep = 0
            for char in expr:
                if char in '0123456789':
                    out.append(char)
                elif char in '-+':
                    if is_signed:
                        break
                    is_signed = True
                    out.append(char)
                elif char == '.':
                    if is_float:
                        break
                    if char not in out:
                        is_float = True
                        out.append(char)
                elif char == 'x':
                    if is_hex:
                        break
                    if char not in out and len(out) == 1 and out[0] == '0':
                        is_hex = True
                        out.append(char)
                    else:
                        return 0
                elif char == 'o':
                    if is_octal:
                        break
                    if char not in out and len(out) == 1 and out[0] == '0':
                        is_octal = True
                        out.append(char)
                    else:
                        return 0
                elif char == 'b' and not is_hex:
                    if is_bin:
                        break
                    if char not in out and len(out) == 1 and out[0] == '0':
                        is_bin = True
                        out.append(char)
                    else:
                        return 0
                elif char in 'ABCDEF' or char in 'abcdef':
                    if is_hex:
                        out.append(char)
                        sep += 1
                elif char == '_':
                    if sep >= 0:
                        sep = 0
                        out.append(char)
                    else:
                        break
                elif char == ' ':
                    continue
                else:
                    break
            try:
                return eval(''.join(out))
            except SyntaxError:
                return 0

    def stop_song(self):
        """Stop playback and reset the player."""
        self.reset_player()
        fmod.systemClose()

    def reset_note(self, note: engine.Note):
        """Revert a note to default state and remove it from the interface."""
        self.note_off = True
        self.wait_ticks = 0
        self.vib_pos = 0.0
        chan = self.channels[note.parent]
        if note.note_num in chan.notes_playing:
            chan.notes_playing.remove(note.note_num)
