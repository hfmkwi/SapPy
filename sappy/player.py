# -*- coding: utf-8 -*-
"""Player and engine emulation functionality."""
import logging
import math
import os
import random
import time
import typing

import sappy.config as config
import sappy.engine as engine
import sappy.fmod as fmod
import sappy.interface as interface
import sappy.parser as parser
import sappy.romio as romio
from sappy.cmdset import Command, Key, Note, Velocity, Wait

TEMP_FILE = 'temp'


class Player(object):
    """M4A Engine Interpreter."""

    logging.basicConfig(level=logging.DEBUG)
    PROCESSOR_LOGGER = logging.getLogger('PROCESSOR')
    FMOD_LOGGER = logging.getLogger('FMOD')
    if not config.SHOW_PROCESSOR_EXECUTION:
        PROCESSOR_LOGGER.setLevel(logging.WARNING)
    if not config.SHOW_FMOD_EXECUTION:
        FMOD_LOGGER.setLevel(logging.WARNING)

    def __init__(self):
        """Intialize the interpreter to default state.

        Attributes
        ----------
        _global_vol : int
            Controls global volume of FMOD player; determined at run-time
            by the SoundDriverMode call.

        tempo : int
            Tempo of song in engine ticks/second.

        note_arr : typing.List[engine.Note]
            Programmable notes used during playback.

        song : engine.Song
            Song loaded by the parser.

        """
        self._global_vol = 0
        self.tempo = 75
        self.note_arr = [engine.Note(*[None] * 5) for _ in range(config.MAXIMUM_NOTES)]
        self.song = engine.Song()

    @property
    def global_vol(self) -> int:
        """Global volume of the FMOD player."""
        return self._global_vol

    @global_vol.setter
    def global_vol(self, volume: int) -> None:
        self._global_vol = volume
        fmod.setMasterVolume(self._global_vol)

    def debug_fmod(self, action: str):
        """Log FMOD debug information."""
        self.FMOD_LOGGER.log(logging.DEBUG, f' Error: {fmod.getError():2} | {action:<16}')

    def show_processor_exec(self, action: str, track_id: int):
        """Log M4A processor information."""
        self.PROCESSOR_LOGGER.log(logging.DEBUG, f' {action:^24} | Track: {track_id:2}')

    def free_note(self, priority: int) -> int:
        """Return the ID of an unused note.

        If there are no more unused notes, disables the first note in
        the track with the lowest priority in comparison to the given
        priority.

        Returns
        -------
        int[0 - 31]

        """
        unused = set(range(config.MAXIMUM_NOTES)).difference(self.song.used_notes)
        if unused:
            return unused.pop()
        tracks = tuple(filter(lambda t: t.priority < priority and t.used_notes, self.song.tracks))
        if tracks:
            track = tracks[0]
            note_id = track.used_notes[0]
            note: engine.Note = self.note_arr[note_id]
            note.mixer.reset()
            track.used_notes.remove(note_id)
            fmod.stopSound(note.fmod_channel)
            return note_id
        return None

    def load_sample(self, fpath: str, sample: engine.Sample) -> int:
        """Load a sample into the FMOD player.

        Parameters
        ----------
        fpath
            File path to the raw PCM8 sound sample
        sample
            Sample information

        Returns
        -------
        int
            FMOD pointer.

        """
        INDEX = fmod.FSoundtracksampleMode.FREE
        MODE = fmod.FSoundModes._8BITS + fmod.FSoundModes.LOADRAW + fmod.FSoundModes.MONO
        if sample.loops:
            MODE += fmod.FSoundModes.LOOP_NORMAL
        if sample.is_wave:
            MODE += fmod.FSoundModes.UNSIGNED
        else:
            MODE += fmod.FSoundModes.SIGNED
        fpath = fpath.encode('ascii')
        sample_id = fmod.sampleLoad(INDEX, fpath, MODE, 0, sample.size)
        if sample.loops:
            fmod.setLoopPoints(sample_id, sample.loop_start, sample.size - 1)
        fmod.setDefaults(sample_id, sample.frequency, 0, -1, -1)
        return sample_id

    # TODO: Add ability to known samples to avoid sample re-import
    def load_directsound(self) -> None:
        """Load requisite DirectSound samples."""
        for sample in self.song.samples.values():
            sample: engine.Sample
            with open(TEMP_FILE, 'wb') as f:
                f.write(bytes(sample.sample_data))
            sample.fmod_id = self.load_sample(TEMP_FILE, sample)
        try:
            os.remove(TEMP_FILE)
        except FileNotFoundError:
            pass

    def load_square(self) -> None:
        """Load GBA PSGSquare1 and PSGSquare2 samples.

        Notes
        -----
            Duty-cycles:
            12.5%, 25%, 50%, 75%

        """
        VARIANT = int(0x7F * config.PSG_SQUARE_VOLUME)
        LOW, HIGH = 0x80 - VARIANT, 0x80 + VARIANT

        SQUARE_WAVES = (
            [HIGH] * 1 + [LOW] * 7, # 12.5%
            [HIGH] * 2 + [LOW] * 6, # 25%
            [HIGH] * 4 + [LOW] * 4, # 50%
            [HIGH] * 6 + [LOW] * 2  # 75%
        )

        for duty_cycle, wave_data in enumerate(SQUARE_WAVES):
            square = f'square{duty_cycle}'
            with open(square, 'wb') as f:
                f.write(bytes(wave_data))
            sample = engine.Sample(wave_data, config.PSG_SQUARE_SIZE, config.PSG_SQUARE_FREQUENCY, is_wave=True)
            sample.fmod_id = self.load_sample(square, sample)
            self.song.samples[square] = sample
            os.remove(square)

    def load_noise(self) -> None:
        """Load GBA PSGNoise samples.

        Notes
        -----
            Noise sample size:
            32767 - normal
            128 - metallic

            10 samples are generated per size.

        """
        VOLUME_MULTI = round(64 * config.PSG_SQUARE_VOLUME)
        for noise_ind, sample_size in enumerate((config.PSG_NOISE_NORMAL_SIZE, config.PSG_NOISE_METALLIC_SIZE)):
            for sample_ind in range(config.PSG_NOISE_SAMPLES):
                noise_data = [int(random.random() * VOLUME_MULTI) for _ in range(sample_size)]

                noise = f'noise{noise_ind}{sample_ind}'
                with open(noise, 'wb') as f:
                    f.write(bytes(noise_data))
                sample = engine.Sample(
                    sample_data=noise_data,
                    size=config.PSG_NOISE_NORMAL_SIZE,
                    freq=config.PSG_SQUARE_FREQUENCY,
                    is_wave=True,
                )
                sample.fmod_id = self.load_sample(noise, sample)
                self.song.samples[noise] = sample

                os.remove(noise)

    def init_player(self) -> None:
        """Initialize FMOD player and load samples."""
        fmod.setOutput(2)
        self.debug_fmod('Set Output: DIRECTSOUND')

        fmod.systemInit(self.engine.frequency, config.MAXIMUM_NOTES, 0)
        self.debug_fmod(f'Init@{self.engine.frequency} Hz, {config.MAXIMUM_NOTES} tracks')

        fmod.setMasterVolume(self.engine.volume * 17)
        self.debug_fmod(f'Set Volume: {self.engine.volume * 17}')

        self.load_directsound()
        self.load_noise()
        self.load_square()

    def update_vibrato(self) -> None:
        """Update note vibrato.

        Notes
        -----
            Notes are only updated if the track
            has LFO speed and depth set to a
            non-zero integer.

        """
        for track in filter(lambda c: c.enabled and c.lfos and c.mod, self.song.tracks):
            for note in [self.note_arr[nid] for nid in track.used_notes]:
                delta_freq = round(track.mod / track.pitch_range * math.sin(math.pi * note.lfo_pos / 127))
                pitch = (track.pitch_bend + delta_freq - 0x40) / 0x40 * track.pitch_range
                frequency = round(note.frequency * math.pow(config.SEMITONE_RATIO, pitch))
                fmod.setFrequency(note.fmod_channel, frequency)
                note.lfo_pos += track.lfos
                if note.lfo_pos >= 254:
                    note.lfo_pos = 0

    def update_tracks(self) -> None:
        """Decrement track tick counter and execute track commands.

        Notes
        -----
            Execution occurs when tick counter = 0.

        """
        # TODO: move all this to Track class
        for track_id, track in enumerate(self.song.tracks):
            if not track.enabled:
                continue
            track.advance()
            while not track.wait_ticks:
                event: engine.Command = track.track_data[track.program_ctr]
                cmd = event.cmd
                args = event.arg1, event.arg2

                if cmd in (Command.FINE, Command.PREV):
                    track.enabled = False
                    self.show_processor_exec('FINE', track_id)
                    break
                elif cmd == Command.PRIO:
                    track.priority = args[0]
                    self.show_processor_exec(f'PRIO {track.priority}',
                                             track_id)
                elif cmd == Command.TEMPO:
                    self.tempo = args[0]
                    self.show_processor_exec(f'TEMPO {self.tempo}', track_id)
                elif cmd == Command.KEYSH:
                    track.keysh = args[0]
                    self.show_processor_exec(f'KEYSH {track.keysh}',
                                             track_id)
                elif cmd == Command.VOICE:
                    track.voice = args[0]
                    track.type = self.song.voices[track.voice].type
                    self.show_processor_exec(
                        f'VOICE {track.voice} ({track.type.name})',
                        track_id)
                elif cmd == Command.VOL:
                    track.volume = args[0]
                    self.show_processor_exec(f'VOL {track.volume}',
                                             track_id)
                    if not track.muted:
                        track.out_vol = 0
                        for note_id in track.used_notes:
                            note: engine.Note = self.note_arr[note_id]
                            vel = note.velocity / 0x7F
                            vol = track.volume / 0x7F
                            pos = note.mixer.pos / 0xFF
                            dav = round(vel * vol * pos * 255)
                            track.out_vol += dav
                            fmod.setVolume(note.fmod_channel, dav)
                            self.debug_fmod(f'Note {note_id:2} Vol: {dav}')
                        if track.used_notes:
                            track.out_vol /= len(track.used_notes)
                elif cmd == Command.PAN:
                    track.panning = args[0]
                    panning = track.panning * 2
                    self.show_processor_exec(f'PAN {track.panning}', track_id)
                    for note_id in track.used_notes:
                        note = self.note_arr[note_id]
                        fmod.setPan(note.fmod_channel, panning)
                        self.debug_fmod(f'Note {note_id:2} Pan: {panning}')
                elif cmd in (Command.BEND, Command.BENDR):
                    if cmd == Command.BEND:
                        track.pitch_bend = args[0]
                        self.show_processor_exec(f'BEND {track.pitch_bend}', track_id)
                    else:
                        track.pitch_range = args[0]
                        self.show_processor_exec(f'BENDR {track.pitch_range}', track_id)
                    for note_id in track.used_notes:
                        note: engine.Note = self.note_arr[note_id]
                        pitch = (track.pitch_bend - 0x40) / 0x40 * track.pitch_range
                        frequency = round(note.frequency * math.pow(config.SEMITONE_RATIO, pitch))
                        fmod.setFrequency(note.fmod_channel, frequency)
                        self.debug_fmod(f'Note {note_id:2} Freq (Hz): {frequency}')
                elif cmd == Command.LFOS:
                    track.lfos = args[0]
                    self.show_processor_exec(f'LFOS {track.lfos}', track_id)
                elif cmd == Command.MOD:
                    track.mod = args[0]
                    self.show_processor_exec(f'MOD {track.mod}', track_id)
                elif cmd == Note.EOT:
                    target_note = args[0]
                    for note_id in track.used_notes:
                        note: engine.Note = self.note_arr[note_id]
                        if note.midi_note != target_note and target_note != 0:
                            continue
                        note.note_off = True
                        self.show_processor_exec(f'EOT {Key(target_note).name} ({note_id})', track_id)
                elif cmd == Command.GOTO:
                    track.program_ctr = track.loop_ptr
                    self.show_processor_exec(f'GOTO 0x{track.loop_ptr:X}', track_id)
                    continue
                elif Note.N96 >= cmd >= Note.TIE:
                    if cmd == Note.TIE:
                        ll = -1
                    else:
                        ll = int(str(Note(cmd).name)[1:])
                    nn, vv = event.arg1, event.arg2
                    note_id = self.free_note(track.priority)
                    self.note_arr[note_id].reset(nn, vv, track_id, ll, track.voice)
                    self.play_note(note_id)
                    track.used_notes.append(note_id)
                    self.show_processor_exec(f'{Note(cmd).name} {Key(nn).name} {Velocity(vv).name}',track_id)
                elif Wait.W00 <= cmd <= Wait.W96:
                    track.wait_ticks = int(str(Wait(cmd).name)[1:])
                    self.show_processor_exec(f'WAIT {track.wait_ticks}', track_id)
                elif cmd == Command.XCMD:
                    ext = args[0]
                    if ext == Command.xIECV:
                        track.echo_volume = args[1]
                        self.show_processor_exec(f'XCMD xIECV {track.echo_volume}', track_id)
                    elif ext == Command.xIECL:
                        track.echo_len = args[1]
                        self.show_processor_exec(f'XCMD xIECL {track.echo_len}', track_id)
                else:
                    try:
                        unimpl_cmd = Command(cmd)
                        self.show_processor_exec(unimpl_cmd.name, track_id)
                    except:
                        self.show_processor_exec(f'UNKNOWN (0x{cmd:X})', track_id)
                track.program_ctr += 1

    def get_voice_data(self, note: engine.Note):
        """Get voice sample and frequency and replace note mixer.

        Notes
        -----
            Note receives a shallow copy of the the voice's mixer.

        """
        midi_note = note.midi_note
        voice = self.song.voices[note.voice]
        square_mod = -4

        if voice.type in (engine.OutputType.MULTI, engine.OutputType.DRUM):
            if voice.type == engine.OutputType.MULTI:
                voice: engine.Voice = voice.voice_table[voice.keymap[midi_note]]
                sample_key = midi_note
            else:
                voice: engine.Voice = voice.voice_table[midi_note]
                sample_key = voice.midi_key
        else:
            sample_key = midi_note + (Key.Cn3 - voice.midi_key)

        note.reset_mixer(voice)

        if voice.type in (engine.SampleType.DSOUND, engine.SampleType.PSG_WAVE):
            sample_ptr = voice.sample_ptr
            sample: engine.Sample = self.song.samples[sample_ptr]
            if voice.resampled:
                base_freq = sample.frequency
            else:
                base_freq = engine.resample(sample_key, square_mod if sample.is_wave else sample.frequency)
        elif voice.type in (engine.SampleType.PSG_SQ1, engine.SampleType.PSG_SQ2):
            sample_ptr = f'square{voice.psg_flag % 4}'
            base_freq = engine.resample(sample_key, square_mod)
        else:
            sample_ptr = f'noise{voice.psg_flag % 2}{int(random.random() * config.PSG_NOISE_SAMPLES)}'
            base_freq = engine.resample(sample_key)
        return sample_ptr, base_freq

    def play_note(self, note_id: int) -> None:
        """Play ."""
        note = self.note_arr[note_id]
        track = self.song.tracks[note.track]

        sample_id, frequency = self.get_voice_data(note)
        if not sample_id:
            return
        frequency *= math.pow(config.SEMITONE_RATIO, config.TRANSPOSE)
        pitch = (track.pitch_bend - 0x40) / 0x40 * track.pitch_range

        output_frequency = round(frequency * math.pow(config.SEMITONE_RATIO, pitch))
        output_panning = track.panning * 2
        note.frequency = frequency
        note.fmod_channel = fmod.playSound(note_id, self.song.samples[sample_id].fmod_id, None, True)
        self.debug_fmod(f'Play Note {note_id:2} Track: {note.track}')
        fmod.setFrequency(note.fmod_channel, output_frequency)
        self.debug_fmod(f'Note {note_id:2} Freq (Hz): {output_frequency}')
        fmod.setPan(note.fmod_channel, output_panning)
        self.debug_fmod(f'Note {note_id:2} Pan: {output_panning}')
        fmod.setPaused(note.fmod_channel, False)
        self.debug_fmod(f'Unpause Note {note_id:2}')

    def update_envelope(self) -> None:
        """Update sound envelope for all notes.

        Notes
        -----
            Volume equation:
            ROUND((NOTE_VOL / 0x7F) *  (TRACK_VOL / 0x7F) * (ENV_POS / 0xFF) * 255)

        """
        for track in self.song.tracks:
            track.out_vol = 0
            for note_id in track.used_notes[::]:
                note = self.note_arr[note_id]
                if note.note_off:
                    note.mixer.note_off()
                pos = note.mixer.update()
                if pos is None:
                    fmod.stopSound(note.fmod_channel)
                    self.debug_fmod(f'Stop Note {note_id:2}')
                    track.used_notes.remove(note_id)
                    continue

                vel_ratio = note.velocity / 0x7F
                vol_ratio = track.volume / 0x7F
                pos_ratio = pos / 0xFF
                volume = round(vel_ratio * vol_ratio * pos_ratio * 255)
                track.out_vol += volume
                fmod.setVolume(note.fmod_channel, volume)
                self.debug_fmod(f'Note {note_id:2} Vol: {volume}')
            if track.used_notes:
                track.out_vol /= len(track.used_notes)

    def update_processor(self) -> int:
        """Execute one tick of the processor.

        Notes
        -----
            Check for processor halt is done in main-loop.

        """
        self.update_tracks()
        for note_id in self.song.used_notes:
            self.note_arr[note_id].advance()

    def play_song(self, path: str, song: int, table_ptr: int = None, engine: romio.SoundDriverMode=None) -> None:
        """Play a song in the specified ROM."""
        d = parser.Parser()
        song = d.load_song(path, song, table_ptr)
        if song == -1:
            print('Invalid/Unsupported ROM.')
            return
        elif song == -2:
            print('Invalid song number.')
            return
        elif song == -3:
            print('Empty track.')
            return
        if engine is None:
            engine = d.file.get_drivermode()
            if engine is None:
                print('No mixer detected; using default settings.')
                self.engine = romio.parse_drivermode(config.DEFAULT_MIXER)
            else:
                print('Using ROM mixer.')
                self.engine = engine
        else:
            print('Using custom mixer.')
            self.engine = engine

        d.file.close()
        self.song = song
        self.init_player()

        interface.print_header(self, self.song.meta_data)
        self.execute_processor()


    def execute_processor(self) -> None:
        """Execute M4A engine and update CLI display.

        Notes
        -----
            All used non-builtin functions have local copies.

        """
        FRAME_DELAY = 1 / config.PLAYBACK_FRAMERATE
        END_BUFFER = config.TICKS_PER_SECOND // 2

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
                avg_ticks = round(self.tempo / round(config.TICKS_PER_SECOND / config.PLAYBACK_SPEED, 4), 4)
                tick_ctr += avg_ticks
                ticks_per_frame = int(tick_ctr - prev_ticks_per_frame)
                if tick_ctr >= config.TICKS_PER_SECOND:
                    tick_ctr = 0
                start_time = clock()
                if not any(filter(lambda x: x.enabled or x.used_notes, self.song.tracks)):
                    buffer += avg_ticks
                for _ in range(ticks_per_frame):
                    update()
                self.update_envelope()
                self.update_vibrato()
                display(self)
                if round(FRAME_DELAY - (clock() - start_time), 3) < 0:
                    continue
                sleep(fabs(round(FRAME_DELAY - (clock() - start_time), 3)))
        except KeyboardInterrupt:
            pass
        finally:
            interface.print_exit_message(self)
            fmod.systemClose()
