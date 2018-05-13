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
import sappy.romio as romio
import sappy.fmod as fmod
import sappy.interface as interface
import sappy.parser as parser
import sappy.config as config
from sappy.instructions import Command, Key, Note, Velocity, Wait
import sappy.instructions as instructions




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

    logging.basicConfig(level=logging.DEBUG)
    PROCESSOR_LOGGER = logging.getLogger('PROCESSOR')
    FMOD_LOGGER = logging.getLogger('FMOD')
    if not config.SHOW_PROCESSOR_EXECUTION:
        PROCESSOR_LOGGER.setLevel(logging.WARNING)
    if not config.SHOW_FMOD_EXECUTION:
        FMOD_LOGGER.setLevel(logging.WARNING)

    def __init__(self):
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

        tempo : int
            A positive integer representing the tempo in BPM
            of the current notes_playing song.

        transpose : int
            An integer representing the number of whole pitch-tones to
            shift the base frequency calculation.

        note_arr : engine.Collection[engine.Note]
            An array of 32 programmable notes utilized during playback.

        channels : typing.List[engine.Channel]
            A VB6 collection containing all virtual tracks utilized during
            playback.

        note_queue : engine.NoteQueue[engine.NoteID]
            A VB6 collection containing the IDs of all virtual notes
            currently in playback.

        samples : typing.Dict[engine.Sample]
            A VB6 collection containing all runtime samples utilized
            during playback.


        """
        self._global_vol = config.VOLUME
        self.tempo = 0
        self.note_arr = [engine.Note(*[0] * 5)] * config.MAXIMUM_NOTES
        self.song = parser.Song()
        self.song.channels = []
        self.note_queue = []

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
            f' CODE: {fmod.getError():2} | {action:<16} |{"|".join([f" {arg:<16}" for arg in args]) + "|" if args else "":<100}'
        )

    def debug_fmod_playback(self, action: str, channel_id: int, note_id: int,
                            *args: typing.List[str]):
        """Output playback debug information."""
        self.FMOD_LOGGER.log(
            logging.DEBUG,
            f' CODE: {fmod.getError():2} | CHAN: {channel_id:2} | NOTE: {note_id:2} | {action:<16} |{"|".join([f" {arg:<15}" for arg in args]) + "|" if args else "":<100}'
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
        self.song.channels.clear()
        self.song.samples.clear()
        self.song.voices.clear()
        self.note_queue.clear()

        for i in range(config.MAXIMUM_NOTES - 1, -1, -1):
            self.note_arr[i].enable = False

        self.tempo = 120

    def free_note(self, priority: int) -> int:
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
        for note_id, note in enumerate(self.note_arr):
            if not note.enable:
                return note_id
        for channel in self.song.channels:
            if channel.priority > priority or not channel.notes_playing:
                continue
            note_id = channel.notes_playing[0]
            note: engine.Note = self.note_arr[note_id]
            note.wait_ticks = 0
            note.env_pos = 0
            note.enable = False
            channel.notes_playing.remove(note_id)
            fmod.stopSound(note.fmod_channel)
            return note_id
        return None

    def load_sample(self,
                    fpath: str,
                    sample: engine.Sample) -> int:
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
        INDEX = fmod.FSoundChannelSampleMode.FREE
        MODE = fmod.FSoundModes._8BITS + fmod.FSoundModes.LOADRAW + fmod.FSoundModes.MONO
        if sample.loop:
            MODE += fmod.FSoundModes.LOOP_NORMAL
        if sample.gb_wave:
            MODE += fmod.FSoundModes.UNSIGNED
        else:
            MODE += fmod.FSoundModes.SIGNED
        fpath = fpath.encode('ascii')
        if type(sample.smp_data) != int:
            return fmod.sampleLoad(INDEX, fpath, MODE, 0, sample.size)
        return fmod.sampleLoad(INDEX, fpath, MODE, sample.smp_data, sample.size)

    def load_directsound(self, file_path: str) -> None:
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
        TEMP_FILE = 'temp'
        for sample in self.song.samples.values():
            sample: engine.Sample
            if type(sample.smp_data) == list:
                with open(TEMP_FILE, 'wb') as f:
                    f.write(bytes(sample.smp_data))
                sample.fmod_id = self.load_sample(TEMP_FILE, sample)
            else:
                sample.fmod_id = self.load_sample(file_path, sample)
            if sample.loop:
                fmod.setLoopPoints(sample.fmod_id, sample.loop_start, sample.size - 1)
            fmod.setDefaults(sample.fmod_id, sample.frequency, 0, -1, -1)
        try:
            os.remove(TEMP_FILE)
        except FileNotFoundError:
            pass

    def load_square(self) -> None:
        """Load in all square waves into the sample pool.

        There are 4 square waves loaded into memory by ascending duty
        cycle. The duty cycle is determined by a ratio of (high:low)
        periods out of 32 total periods.

        The square waves have duty cycles of: 12.5%, 25%, 50%, 75%

        """
        VARIANT = round(0x7F * config.PSG_SQUARE_VOLUME / 2)
        LOW, HIGH = 0x80 - VARIANT, 0x80 + VARIANT

        SQUARE_WAVES = (
            [HIGH] * 4 + [LOW] * 28,
            [HIGH] * 8 + [LOW] * 24,
            [HIGH] * 16 + [LOW] * 16,
            [HIGH] * 24 + [LOW] * 8
        )

        for duty_cycle, wave_data in enumerate(SQUARE_WAVES):
            square = f'square{duty_cycle}'
            with open(square, 'wb') as f:
                f.write(bytes(wave_data))
            sample = engine.Sample(wave_data, config.PSG_SQUARE_SIZE, config.PSG_SQUARE_FREQUENCY, gb_wave=True)
            sample.fmod_id = self.load_sample(square, sample)
            self.song.samples[square] = sample
            fmod.setLoopPoints(sample.fmod_id, 0, config.PSG_SQUARE_SIZE - 1)
            fmod.setDefaults(sample.fmod_id, config.PSG_SQUARE_FREQUENCY, 0, -1, -1)

            os.remove(square)

    def load_noise(self) -> None:
        """Load all noise waves into the sample pool.

        There are two types of samples noise waves loaded into memory: a
        4096-sample (normal) wave and a 256-sample (metallic) wave. 10 of
        each are loaded in. Each sample has a base frequency of 7040 Hz.

        """
        VOLUME_MULTI = round(64 * config.PSG_SQUARE_VOLUME / 2)
        for noise_ind, sample_size in enumerate((config.PSG_NOISE_NORMAL_SIZE, config.PSG_NOISE_METALLIC_SIZE)):
            for sample_ind in range(config.PSG_NOISE_SAMPLES):
                noise_data = [
                    int(random.random() * VOLUME_MULTI)
                    for _ in range(sample_size)
                ]

                noise = f'noise{noise_ind}{sample_ind}'
                with open(noise, 'wb') as f:
                    f.write(bytes(noise_data))
                sample = engine.Sample(
                    smp_data=noise_data,
                    size=config.PSG_NOISE_NORMAL_SIZE,
                    freq=config.PSG_SQUARE_FREQUENCY,
                    gb_wave=True
                )
                sample.fmod_id = self.load_sample(noise, sample)
                fmod.setLoopPoints(sample.fmod_id, 0, config.PSG_NOISE_NORMAL_SIZE)
                fmod.setDefaults(sample.fmod_id, config.BASE_FREQUENCY, 0, -1, -1)
                self.song.samples[noise] = sample

                os.remove(noise)

    def init_player(self, fpath: str) -> None:
        """Iniate the FMOD player and load in all samples.

        The sound output is initially set to WINSOUND and the FMOD player
        is then initiated with 32 channels at a variable sample rate.

        """
        fmod.setOutput(2)
        self.debug_fmod('SET OUTPUT')

        fmod.systemInit(self.mixer.frequency, config.MAXIMUM_NOTES, 0)
        self.debug_fmod('INIT PLAYER')

        fmod.setMasterVolume(self.mixer.volume * 17)
        self.debug_fmod('SET VOLUME', f'VOLUME: {config.VOLUME}')

        self.load_directsound(fpath)
        self.load_noise()
        self.load_square()

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

        SIN(POS * Ï€) * DEPTH

        """
        for note in self.note_arr:
            if not note.enable:
                continue
            channel = self.song.channels[note.parent_channel]
            if not channel.enabled or channel.lfo_speed == 0 or channel.mod_depth == 0:
                continue

            delta_freq = round(channel.mod_depth // channel.pitch_range * math.sin(math.pi * note.lfos_position / 127))
            pitch = (channel.pitch_bend + delta_freq - 0x40) / 0x40 * channel.pitch_range
            frequency = round(note.frequency * math.pow(config.SEMITONE_RATIO, pitch))
            fmod.setFrequency(note.fmod_channel, frequency)

            note.lfos_position += channel.lfo_speed
            if note.lfos_position >= 254:
                note.lfos_position = 0

    def advance_notes(self) -> None:
        """Advance each note 1 tick and release all 0-tick notes."""
        for note_id, note in enumerate(self.note_arr):
            note: engine.Note
            if note.wait_ticks > 0:
                note.wait_ticks -= 1
            elif note.enable and not note.note_off and note.wait_ticks == 0:
                note.note_off = True
                self.show_processor_exec(f'NOTE {note_id} OFF',
                                         note.parent_channel)

    def update_channels(self) -> None:
        """Advance each channel 1 tick and continue processor execution for all 0-tick channels."""
        for channel_id, channel in enumerate(self.song.channels):
            if not channel.enabled:
                continue
            if channel.wait_ticks > 0:
                channel.wait_ticks -= 1
            while channel.wait_ticks == 0:
                event: engine.Event = channel.event_queue[channel.program_ctr]
                cmd = event.cmd
                args = event.arg1, event.arg2

                if cmd in (Command.FINE, Command.PREV):
                    channel.enabled = False
                    self.show_processor_exec('FINE', channel_id)
                    break
                elif cmd == Command.PRIO:
                    channel.priority = args[0]
                    self.show_processor_exec(f'PRIO {channel.priority}',
                                             channel_id)
                elif cmd == Command.TEMPO:
                    self.tempo = args[0]
                    self.show_processor_exec(f'TEMPO {self.tempo}', channel_id)
                elif cmd == Command.KEYSH:
                    channel.transpose = args[0]
                    self.show_processor_exec(f'KEYSH {channel.transpose}',
                                             channel_id)
                elif cmd == Command.VOICE:
                    channel.voice = args[0]
                    channel.type = self.song.voices[channel.voice].type
                    self.show_processor_exec(
                        f'VOICE {channel.voice} ({channel.type.name})',
                        channel_id)
                elif cmd == Command.VOL:
                    channel.volume = args[0]
                    self.show_processor_exec(f'VOL {channel.volume}',
                                             channel_id)
                    output_volume = []
                    if not channel.muted:
                        for note_id in channel.notes_playing:
                            note: engine.Note = self.note_arr[note_id]
                            vel = note.velocity / 0x7F
                            vol = channel.volume / 0x7F
                            pos = note.env_pos / 0xFF
                            dav = round(vel * vol * pos * 255)
                            output_volume.append(dav)
                            fmod.setVolume(note.fmod_channel, dav)
                            self.debug_fmod_playback(f'NOTE VOLUME {dav}',
                                                    channel_id, note_id)
                        channel.output_volume = self.average_volumes(output_volume)
                elif cmd == Command.PAN:
                    channel.panning = args[0]
                    panning = channel.panning * 2
                    self.show_processor_exec(f'PAN {channel.panning}',
                                             channel_id, channel.panning)
                    for note_id in channel.notes_playing:
                        note = self.note_arr[note_id]
                        fmod.setPan(note.fmod_channel, panning)
                        self.debug_fmod_playback('SET NOTE PANNING', channel_id,
                                                 note_id, panning)
                elif cmd in (Command.BEND, Command.BENDR):
                    if cmd == Command.BEND:
                        channel.pitch_bend = args[0]
                        self.show_processor_exec(f'BEND {channel.pitch_bend}',
                                                 channel_id)
                    else:
                        channel.pitch_range = args[0]
                        self.show_processor_exec(f'BENDR {channel.pitch_range}',
                                                 channel_id)
                    for note_id in channel.notes_playing:
                        note: engine.Note = self.note_arr[note_id]
                        pitch = (channel.pitch_bend - 0x40
                                ) / 0x40 * channel.pitch_range
                        frequency = round(note.frequency * math.pow(
                            config.SEMITONE_RATIO, pitch))
                        fmod.setFrequency(note.fmod_channel, frequency)
                        self.debug_fmod_playback('SET NOTE FREQ', channel_id,
                                                 note_id, frequency)
                elif cmd == Command.LFOS:
                    channel.lfo_speed = args[0]
                    for note_id in channel.notes_playing:
                        note = self.note_arr[note_id]
                        note.lfos_position = 0
                    self.show_processor_exec(f'LFOS {channel.lfo_speed}',
                                             channel_id)
                elif cmd == Command.MOD:
                    channel.mod_depth = args[0]
                    for note_id in channel.notes_playing:
                        note = self.note_arr[note_id]
                        note.lfos_position = 0
                    self.show_processor_exec(f'MOD {channel.mod_depth}',
                                             channel_id)
                elif cmd == Note.EOT:
                    for note_id in channel.notes_playing:
                        note: engine.Note = self.note_arr[note_id]
                        if note.note_num != args[0] and args[0] != 0:
                            continue
                        note.note_off = True
                        self.show_processor_exec(
                            f'EOT {Key(args[0]).name} ({note_id})', channel_id)
                elif cmd == Command.GOTO:
                    channel.program_ctr = channel.loop_address
                    self.show_processor_exec(f'GOTO 0x{channel.loop_address:X}',
                                             channel_id)
                    continue
                elif Note.N96 >= cmd >= Note.TIE:
                    if cmd == Note.TIE:
                        ll = -1
                    else:
                        ll = int(str(Note(cmd).name)[1:])
                    nn, vv = event.arg1, event.arg2
                    self.note_queue.append(
                        engine.Note(nn, vv, channel_id, ll,
                                    channel.voice))
                    self.show_processor_exec(
                        f'{Note(cmd).name} {Key(nn).name} {Velocity(vv).name}',
                        channel_id)
                elif Wait.W00 <= cmd <= Wait.W96:
                    channel.wait_ticks = int(str(Wait(cmd).name)[1:])
                    self.show_processor_exec(f'WAIT {channel.wait_ticks}',
                                             channel_id)
                elif cmd == 0xCD:
                    if args[0] == 0x08:
                        channel.echo_volume = args[1]
                        self.show_processor_exec(f'XCMD xIECV {args[1]}',
                                                 channel_id)
                    elif args[0] == 0x09:
                        channel.echo_len = args[1]
                        self.show_processor_exec(f'XCMD xIECL {args[1]}',
                                                 channel_id)
                else:
                    try:
                        unk_cmd = Command(cmd)
                        self.show_processor_exec(unk_cmd.name, channel_id)
                    except:
                        self.show_processor_exec(f'UNKNOWN (0x{cmd:X})',
                                                 channel_id)
                channel.program_ctr += 1

    def get_playback_data(self, note: engine.Note):
        """Get the sample ID and frequency of a note from the sample pool."""
        SAMPLED = (engine.DirectTypes.DIRECT, engine.DirectTypes.WAVEFORM)
        SQUARE = (engine.DirectTypes.SQUARE1, engine.DirectTypes.SQUARE2)
        voice_id = note.voice
        note_num = note.note_num
        voice = self.song.voices[voice_id]
        out_type = voice.type
        if out_type in (engine.ChannelTypes.MULTI, engine.ChannelTypes.DRUMKIT):
            if out_type == engine.ChannelTypes.MULTI:
                voice: engine.Voice = voice.voice_table[voice.keymap[
                    note_num]]
                if voice.type in SAMPLED:
                    sample_id = voice.sample_ptr
                    sample: engine.Sample = self.song.samples[sample_id]
                    if voice.resampled:
                        base_freq = sample.frequency
                    else:
                        base_freq = engine.resample(note_num, -2 if sample.gb_wave else sample.frequency)
                else:
                    sample_id = f'square{voice.psg_flag % 4}'
                    base_freq = engine.resample(note_num)
            else:
                voice: engine.Voice = self.song.voices[voice_id].voice_table[
                    note_num]
                if voice.type in SAMPLED:
                    sample_id = voice.sample_ptr
                    sample: engine.Sample = self.song.samples[sample_id]
                    if voice.resampled:
                        base_freq = sample.frequency
                    else:
                        base_freq = engine.resample(voice.midi_key, -2 if sample.gb_wave else sample.frequency)
                elif voice.type in SQUARE:
                    sample_id = f'square{voice.psg_flag % 4}'
                    base_freq = engine.resample(voice.midi_key)
                elif voice.type == engine.DirectTypes.NOISE:
                    sample_id = f'noise{voice.psg_flag % 2}{random.randint(0, config.PSG_NOISE_SAMPLES - 1)}'
                    base_freq = engine.resample(voice.midi_key)
            note.set_mixer_props(voice)
        else:
            note.set_mixer_props(voice)
            midi_notenum = note_num + (60 - voice.midi_key)
            if voice.type in SAMPLED:
                sample_id = voice.sample_ptr
                base_freq = engine.resample(
                    midi_notenum, -1 if self.song.samples[sample_id].gb_wave
                    else self.song.samples[sample_id].frequency)
                if self.song.samples[sample_id].gb_wave:
                    base_freq /= 2
            else:
                if voice.type in SQUARE:
                    sample_id = f'square{voice.psg_flag % 4}'
                elif voice.type == engine.DirectTypes.NOISE:
                    sample_id = f'noise{voice.psg_flag % 2}{random.randint(0, config.PSG_NOISE_SAMPLES - 1)}'
                base_freq = engine.resample(midi_notenum)
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
        for note in self.note_queue:
            note_id = self.free_note(self.song.channels[note.parent_channel].priority)
            if note_id is None:
                continue

            self.note_arr[note_id] = note
            channel = self.song.channels[note.parent_channel]
            channel.notes_playing.append(note_id)

            sample_id, frequency = self.get_playback_data(note)
            if not sample_id:
                continue
            frequency *= math.pow(config.SEMITONE_RATIO, config.TRANSPOSE)
            pitch = (channel.pitch_bend - 0x40) / 0x40 * channel.pitch_range

            output_frequency = round(
                frequency * math.pow(config.SEMITONE_RATIO, pitch))
            output_panning = channel.panning * 2
            note.frequency = frequency
            note.phase = engine.NotePhases.INITIAL
            note.fmod_channel = fmod.playSound(note_id, self.song.samples[sample_id].fmod_id, None, True)
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
        self.note_queue.clear()

    def update_envelope(self) -> None:
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
        volumes = [[] for i in range(len(self.song.channels))]
        for note_id, note in enumerate(self.note_arr):
            channel = self.song.channels[note.parent_channel]
            if not note.enable:
                continue

            if note.note_off and note.phase < engine.NotePhases.RELEASE:
                note.env_step = note.release / 256
                if note.type != engine.NoteTypes.DIRECT:
                    note.env_step *= 32
                note.env_dest = 0
                note.phase = engine.NotePhases.RELEASE
            if note.phase == engine.NotePhases.INITIAL:
                note.env_pos = 0
                note.env_dest = 255
                if note.type != engine.NoteTypes.DIRECT:
                    note.env_step = (0x8 - note.attack) * 32
                else:
                    note.env_step = note.attack
                note.phase = engine.NotePhases.ATTACK
            if note.phase == engine.NotePhases.ATTACK:
                note.env_pos += note.env_step
                if note.env_pos >= 255:
                    note.env_pos = 255
                    note.env_dest = note.sustain
                    note.env_step = note.decay / 256

                    if note.type != engine.NoteTypes.DIRECT:
                        note.env_dest *= 17
                        note.env_step *= 32
                    note.phase = engine.NotePhases.DECAY
            if note.phase == engine.NotePhases.DECAY:
                note.env_pos *= note.env_step
                if note.env_pos <= note.sustain:
                    note.env_pos = note.sustain
                    if note.type != engine.NoteTypes.DIRECT:
                        note.env_pos *= 17
                    note.phase = engine.NotePhases.SUSTAIN
            if note.phase == engine.NotePhases.RELEASE:
                note.env_pos *= note.env_step
                if int(note.env_pos) <= 1:
                    note.env_step = 0
                    note.phase = engine.NotePhases.NOTEOFF
            if note.phase == engine.NotePhases.NOTEOFF:
                fmod.stopSound(note.fmod_channel)
                self.debug_fmod_playback('STOP NOTE', note.parent_channel,
                                        note_id,
                                        f'FCHAN: {note.fmod_channel}')
                note.fmod_channel = 0
                note.enable = False
                note.lfos_position = 0
                note.parent_channel = -1
                channel.notes_playing.remove(note_id)
                continue

            vel_ratio = note.velocity / 0x7F
            vol_ratio = channel.volume / 0x7F
            pos_ratio = note.env_pos / 0xFF
            volume = round(vel_ratio * vol_ratio * pos_ratio * 255)
            volumes[note.parent_channel].append(volume)
            fmod.setVolume(note.fmod_channel, volume)
            self.debug_fmod_playback('SET NOTE VOLUME', note.parent_channel,
                                     note_id, volume)

        for channel_id, channel in enumerate(self.song.channels):
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
        self.advance_notes()


    def average_volumes(self, volumes: typing.List[int]) -> int:
        if not len(volumes):
            return 0
        return round(sum(volumes) / len(volumes))

    def play_song(self, fpath: str, song_num: int,
                  song_table: int = None, mixer_override: romio.SoundEngine=None) -> None:
        """Play a song in the specified ROM."""
        d = parser.Parser()
        song = d.load_song(fpath, song_num, song_table)
        if song == -1:
            print('Invalid/Unsupported ROM.')
            return
        elif song == -2:
            print('Invalid song number.')
            return
        elif song == -3:
            print('Empty track.')
            return
        if mixer_override is None:
            mixer = d.file.get_sound_engine()
            if mixer is None:
                print('No mixer detected; using default settings.')
                self.mixer = romio.parse_mixer(config.DEFAULT_MIXER)
            else:
                print('Using ROM mixer.')
                self.mixer = mixer
        else:
            print('Using custom mixer.')
            self.mixer = mixer_override

        d.file.close()
        self.reset_player()
        self.song = song
        self.init_player(fpath)

        interface.print_header(self, self.song.meta_data)
        self.execute_processor()


    def execute_processor(self) -> None:
        """Execute the event processor and update the user display.

        Notes
        -----
            All functions used have assigned local copies.

        """
        FRAME_DELAY = 1 / config.PLAYBACK_FRAMERATE
        END_BUFFER = config.TICKS_PER_SECOND // 2

        # Local function copies
        display = interface.display
        update = self.update_processor
        fabs = math.fabs
        clock = time.perf_counter
        sleep = time.sleep
        tick_ctr = 0
        buffer = 0
        try:
            while buffer < END_BUFFER:
                prev_ticks_per_frame = int(tick_ctr)
                avg_ticks = self.tempo / (config.TICKS_PER_SECOND / config.PLAYBACK_SPEED)
                tick_ctr += avg_ticks
                ticks_per_frame = int(tick_ctr - prev_ticks_per_frame)
                if tick_ctr >= config.TICKS_PER_SECOND:
                    tick_ctr = 0
                start_time = clock()
                display(self)
                if not any(filter(lambda x: x.enabled or x.notes_playing, self.song.channels)):
                    buffer += avg_ticks
                for _ in range(ticks_per_frame):
                    update()
                    display(self)
                self.update_envelope()
                self.update_vibrato()
                if round(FRAME_DELAY - (clock() - start_time), 3) < 0:
                    continue
                sleep(fabs(round(FRAME_DELAY - (clock() - start_time), 3)))
        except KeyboardInterrupt:
            pass
        finally:
            interface.print_exit_message(self)

    def stop_song(self):
        """Stop playback and reset the player."""
        self.reset_player()
        fmod.systemClose()
