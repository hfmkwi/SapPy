#!python
# -*- coding: utf-8 -*-
# TODO: Either use the original FMOD dlls or find a sound engine.
"""Main file."""
import struct
import typing

import sappy.config as config
import sappy.engine as engine
import sappy.fmod as fmod
import sappy.romio as romio
from sappy.cmdset import Command, Gate, Note, Wait, mxv

to_addr = romio.to_addr


class Parser(object):
    """Parser/interpreter for Sappy code."""

    def get_sample(self, song: engine.Song, voice: engine.Voice) -> None:
        """Load voice sample from ROM."""
        voice_sample = voice.sample_ptr
        voice_ptr = to_addr(voice_sample)
        if voice_ptr == -1:
            return
        smp_head = self.file.read_sample(voice_ptr)

        if voice.type == engine.SampleType.DSOUND:
            data = memoryview(bytes(self.file._file.read(smp_head.size)))
            sample = engine.Sample(
                sample_data=data,
                freq=smp_head.frequency >> 10,
                loops=smp_head.is_looped == 0x40,
                loop_start=smp_head.loop,
                size=smp_head.size,
            )
        else:
            wave_data = self.file.read_string(config.PSG_WAVEFORM_SIZE, voice_ptr)
            data = []
            for byte_ind in range(32):
                wave_ind, power = divmod(byte_ind, 2)
                byte = ord(wave_data[wave_ind]) / (16 ** power) % 16
                byte *= config.PSG_WAVEFORM_VOLUME
                data.append(int(byte))
            sample = engine.Sample(
                size=config.PSG_WAVEFORM_SIZE,
                freq=config.PSG_WAVEFORM_FREQUENCY,
                sample_data=data,
                is_wave=True
            )

        song.samples.setdefault(voice_sample, sample)

    def get_loop_ptr(self, program_ctr: int):
        """Get loop address of GOTO call."""
        cmd = 0
        while True:
            self.file.address = program_ctr
            cmd = self.file.read()
            program_ctr += 1
            if Wait.W00 <= cmd <= Wait.W96: # Wxx
                continue
            elif cmd == Command.PATT: # PATT(ADDRESS) [NON-REPEATABLE]
                program_ctr += 4
            elif cmd == Command.PEND: # PEND [NON-REPEATABLE]
                program_ctr += 4
            elif cmd == Command.GOTO: # GOTO(ADDRESS) [NON-REPEATABLE]
                program_ctr += 4
                loop_offset = self.file.read_gba_ptr()
                break
            elif Command.PRIO <= cmd <= Command.TUNE: # cmd(ARG) [REPEATABLE]
                program_ctr += 1
            elif cmd == Command.REPT: # REPT(COUNT, ADDRESS) [REPEATBLE]
                program_ctr += 5
            elif cmd == Command.MEMACC: # MEMACC(MEMACC_COM, ADDRESS, DATA) [REPEATABLE]
                program_ctr += 3
            elif cmd == Command.XCMD:
                program_ctr += 3
            elif Note.EOT <= cmd <= Note.N96: # Nxx(KEY, [VELOCITY, [GROUP]])
                while self.file.read() < 0x80:
                    program_ctr += 1
            elif 0 <= cmd < 128: # REPEAT LAST COMMAND
                pass
            elif cmd == Command.FINE or cmd == Command.PREV:
                pass
            else:
                program_ctr += 1

        return loop_offset

    def load_voice(self, voice_type: int, voice_ptr: int):
        """Load a M4A voice."""
        if 0x01 <= voice_type <= 0x5 or 0x9 <= voice_type <= 0xD: # Is PSG
            data = self.file.read_psg_instrument(voice_ptr, voice_type in (0x3, 0x0B))
        else: # Anything else.
            data = self.file.read_directsound(voice_ptr)
        return engine.Voice(data)

    def load_inst(self, song: engine.Song, table_ptr: int, voice_id: int, midi_key: int):
        """Create an M4A voice surrogate."""
        HAS_SAMPLE = (engine.SampleType.DSOUND, engine.SampleType.PSG_WAVE)

        voice_ptr = table_ptr + voice_id * 12
        voice_type = self.file.read(voice_ptr)
        if voice_type == 0x80: # Percussion
            voice_table = self.file.read_dword(self.file.address + 4)
            midi_voice_ptr = to_addr(voice_table + midi_key * 12)
            midi_voice_type = self.file.read(midi_voice_ptr)
            voice = self.load_voice(midi_voice_type, midi_voice_ptr)
            if voice_id not in song.voices:
                song.voices[voice_id] = engine.DrumKit({midi_key: voice})
            else:
                song.voices[voice_id].voice_table[midi_key] = voice
        elif voice_type == 0x40: # Multi
            voice_table = self.file.read_dword(self.file.address + 4)
            keymap_ptr = to_addr(self.file.read_dword())
            midi_note = self.file.read(keymap_ptr + midi_key)
            midi_voice_ptr = to_addr(voice_table + midi_note * 12)
            midi_voice_type = self.file.read(midi_voice_ptr)
            voice = self.load_voice(midi_voice_type, midi_voice_ptr)
            if voice_id not in song.voices:
                song.voices[voice_id] = engine.Instrument({midi_note: voice}, {midi_key: midi_note})
            else:
                song.voices[voice_id].voice_table[midi_note] = voice
                song.voices[voice_id].keymap[midi_key] = midi_note
        else: # Everything else
            if voice_id in song.voices:
                return
            voice = self.load_voice(voice_type, voice_ptr)
            song.voices[voice_id] = voice
        if voice.type in HAS_SAMPLE:
            self.get_sample(song, voice)

    def load_tracks(self, main_ptr: int, table_ptr: int, num_tracks: int) -> engine.Track:
        """Load all track data for a song."""
        song = engine.Song()

        keysh = 0
        for track_num in range(num_tracks):
            track = engine.Track()
            track.priority = num_tracks - track_num
            track_pos = self.file.read_gba_ptr(main_ptr + 8 + track_num * 4)
            loop_ptr = self.get_loop_ptr(track_pos)

            last_cmd = None
            last_key = None
            last_velocity = None
            last_group = None
            last_ext = None
            voice = 0
            last_midi_key = 1
            in_patt = False
            track_data = track.track_data
            while True:
                self.file.address = track_pos
                if track_pos >= loop_ptr and track.loop_ptr == -1 and loop_ptr != -1:
                    track.loop_ptr = len(track_data)

                cmd = self.file.read()
                if Command.PRIO <= cmd <= Command.TUNE:
                    arg = self.file.read()
                    if cmd == Command.KEYSH:
                        keysh = arg
                    elif Command.VOICE <= cmd <= Command.TUNE:
                        if cmd == Command.VOICE:
                            last_cmd = cmd
                            voice = arg
                            self.load_inst(song, table_ptr, voice, last_midi_key)
                        last_cmd = cmd
                    track_data.append(engine.Command(cmd, arg))
                    track_pos += 2
                elif cmd == Command.MEMACC:
                    op = self.file.read()
                    addr = self.file.read()
                    data = self.file.read()
                    track_data.append(engine.Command(cmd, op, addr, data))
                    track_pos += 4
                elif cmd == Command.PEND:
                    if in_patt:
                        track_pos = rpc  # pylint: disable=E0601
                        in_patt = False
                    else:
                        track_pos += 1
                    track_data.append(engine.Command(cmd))
                elif cmd == Command.PATT:
                    rpc = track_pos + 5
                    in_patt = True
                    track_pos = self.file.read_gba_ptr()
                    track_data.append(engine.Command(cmd))
                elif cmd == Command.XCMD:
                    last_cmd = cmd
                    ext = self.file.read()
                    arg = self.file.read()
                    last_ext = ext
                    track_data.append(engine.Command(cmd, ext, arg))
                    track_pos += 3
                elif cmd == Note.EOT:
                    last_cmd = cmd
                    arg = self.file.read()
                    track_pos += 1
                    if arg <= mxv:
                        track_pos += 1
                        track_data.append(engine.Command(cmd, arg))
                    else:
                        track_data.append(engine.Command(cmd, 0))
                elif 0x00 <= cmd < 0x80 or Note.TIE <= cmd <= Note.N96:
                    if Note.TIE <= cmd <= Note.N96:
                        track_pos += 1
                        last_cmd = cmd
                    else:
                        if last_cmd <= Note.EOT:
                            if last_cmd == Note.EOT:
                                track_data.append(engine.Command(last_cmd, cmd))
                            elif last_cmd == Command.VOICE:
                                voice = cmd
                                self.load_inst(song, table_ptr, voice, last_midi_key)
                                track_data.append(engine.Command(last_cmd, voice))
                            elif last_cmd == Command.XCMD:
                                track_data.append(engine.Command(last_cmd, last_ext, cmd))
                            else:
                                track_data.append(engine.Command(last_cmd, cmd))
                            track_pos += 1
                            continue
                        else:
                            cmd = last_cmd

                    self.file.address = track_pos
                    note = self.file.read()
                    if note <= mxv:
                        last_key = note
                        track_pos += 1
                        velocity = self.file.read()
                        if velocity <= mxv:
                            last_velocity = velocity
                            track_pos += 1
                            group = self.file.read()
                            if group <= Gate.gtp3:
                                last_group = group
                                track_pos += 1
                            elif group > mxv:
                                group = last_group
                        else:
                            velocity = last_velocity
                            group = last_group
                        last_midi_key = note + keysh
                    else:
                        last_midi_key = last_key + keysh
                        velocity, group = last_velocity, last_group
                    track_data.append(engine.Command(cmd, last_midi_key, velocity, group))

                    self.load_inst(song, table_ptr, voice, last_midi_key)
                elif Wait.W00 <= cmd <= Wait.W96:
                    track_data.append(engine.Command(cmd))
                    track_pos += 1
                if cmd in (Command.FINE, Command.GOTO, Command.PREV):
                    break

            track_data.append(engine.Command(cmd))
            song.tracks.append(track)
        return song

    def load_song(self, path: str, song: int, song_table_ptr: int = None) -> engine.Song:
        """Load a song from ROM."""
        self.file = romio.GBARom(path)

        if song_table_ptr is None:
            song_table_ptr = self.file.get_song_table()
            if song_table_ptr == -1:
                return -1

        main_ptr = self.file.read_gba_ptr(song_table_ptr + song * 8)
        if main_ptr == -1:
            return -2

        num_tracks = self.file.read(main_ptr)
        if num_tracks == 0:
            return -3

        unk = self.file.read()
        priority = self.file.read()
        reverb = self.file.read()
        voice_table_ptr = self.file.read_gba_ptr()
        game_name = self.file.read_string(12, 0xA0)
        game_code = self.file.read_string(4, 0xAC)

        song = self.load_tracks(main_ptr, voice_table_ptr, num_tracks)
        song.meta_data = engine.MetaData(
            rom_code=game_code,
            rom_name=game_name,
            tracks=num_tracks,
            reverb=reverb,
            priority=priority,
            main_ptr=main_ptr,
            voice_ptr=voice_table_ptr,
            song_ptr=song_table_ptr,
            unknown=unk)

        return song
