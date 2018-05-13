#!python
# -*- coding: utf-8 -*-
# TODO: Either use the original FMOD dlls or find a sound engine.
"""Main file."""
import typing

import sappy.config as config
import sappy.engine as engine
import sappy.romio as romio
import sappy.fmod as fmod
from sappy.instructions import *

to_addr = romio.to_address


class MetaData(typing.NamedTuple):
    """Meta-data for a ROM."""

    REGION = {
        'J': 'JAP',
        'E': 'USA',
        'P': 'EUR',
        'D': 'GER',
        'F': 'FRE',
        'I': 'ITA',
        'S': 'SPA'
    }

    rom_name: str = ...
    rom_code: str = ...
    tracks: int = ...
    echo: int = ...
    priority: int = ...
    header_ptr: int = ...
    voice_ptr: int = ...
    song_ptr: int = ...
    unknown: int = ...

    @property
    def echo_enabled(self):
        """Return whether the track has echo/reverb enabled."""
        return bin(self.echo)[2:][0] == '1'

    @property
    def code(self):
        """Return the full production ID of the ROM."""
        return f'AGB-{self.rom_code}-{self.region}'

    @property
    def region(self):
        """Return region code of the ROM.

        The region code is determined by the 4th character in the game's ID.

        """
        return self.REGION.get(self.rom_code[3], 'UNK')


class Song(object):
    """A wrapper around a Sappy engine song."""

    def __init__(self):
        self.channels = []
        self.note_queue = {}
        self.samples = {}
        self.voices = {}
        self.meta_data = MetaData()


class Parser(object):
    """Parser/interpreter for Sappy code."""

    def get_sample(self, song: Song, voice: engine.Voice) -> None:
        """Load a sample from ROM into memory."""
        voice_sample = voice.sample_ptr

        smp_head = self.file.read_sample(to_addr(voice_sample))
        if voice.type == engine.DirectTypes.DIRECT:
            sample = engine.Sample(
                smp_data=self.file._file.tell(),
                freq=smp_head.frequency >> 10,
                loop=smp_head.is_looped == 0x40,
                loop_start=smp_head.loop,
                size=smp_head.size,
            )
        else:
            wave_data = self.file.read_string(config.PSG_WAVEFORM_SIZE // 2, to_addr(voice_sample))
            smp_data = []
            for byte_ind in range(32):
                wave_ind, power = divmod(byte_ind, 2)
                data = ord(wave_data[wave_ind]) / 16**power % 16
                data *= config.PSG_WAVEFORM_VOLUME
                smp_data.append(int(data))
            sample = engine.Sample(
                size=config.PSG_WAVEFORM_SIZE,
                freq=config.PSG_WAVEFORM_FREQUENCY,
                smp_data=smp_data
            )

        song.samples.setdefault(voice_sample, sample)

    def get_loop_address(self, program_ctr: int):
        """Determine the looping address of a track/channel."""
        loop_offset = -1
        cmd = 0
        while cmd != Command.FINE:
            self.file.address = program_ctr
            cmd = self.file.read()
            program_ctr += 1
            if Wait.W00 <= cmd <= Wait.W96: # Wxx
                pass
            elif cmd == Command.PATT: # PATT(ADDRESS) [NON-REPEATABLE]
                program_ctr += 4
            elif cmd == Command.PEND: # PEND [NON-REPEATABLE]
                program_ctr += 4
            elif cmd == Command.GOTO: # GOTO(ADDRESS) [NON-REPEATABLE]
                program_ctr += 4
                loop_offset = self.file.read_gba_pointer()
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
                break
            else:
                raise ValueError('invalid track')

        return loop_offset

    def load_voice(self, voice_type: int, voice_ptr: int):
        SAMPLE_RANGE = range(0x1, 0x5)
        UNSAMPLE_RANGE = range(0x9, 0xD)
        if voice_type in SAMPLE_RANGE or voice_type in UNSAMPLE_RANGE:
            data = self.file.read_psg_instrument(voice_ptr, voice_type in (0x3, 0x0B))
        else:
            data = self.file.read_directsound(voice_ptr)

        return engine.Voice(data)

    def load_instrument(self, song: Song, table_ptr: int, voice_id: int, sub_voice_id: int):
        HAS_SAMPLE = (engine.DirectTypes.DIRECT, engine.DirectTypes.WAVEFORM)

        voice_ptr = table_ptr + voice_id * 12
        voice_type = self.file.read(voice_ptr)
        if voice_type == 0x80: # Percussion
            table_ptr = self.file.read_dword(self.file.address + 4)
            sub_voice_ptr = to_addr(table_ptr + sub_voice_id * 12)
            sub_voice_type = self.file.read(sub_voice_ptr)
            voice = self.load_voice(sub_voice_type, sub_voice_ptr)
            if voice_id not in song.voices:
                song.voices[voice_id] = engine.DrumKit({sub_voice_id: voice})
            else:
                song.voices[voice_id].voice_table[sub_voice_id] = voice
            if voice.type in HAS_SAMPLE:
                self.get_sample(song, voice)
        elif voice_type == 0x40: # Multi
            voice_table = self.file.read_dword(self.file.address + 4)
            keymap_ptr = to_addr(self.file.read_dword())
            sub_voice_ind = self.file.read(keymap_ptr + sub_voice_id)
            sub_voice_ptr = to_addr(voice_table + sub_voice_ind * 12)
            sub_voice_type = self.file.read(sub_voice_ptr)
            voice = self.load_voice(sub_voice_type, sub_voice_ptr)
            if voice_id not in song.voices:
                song.voices[voice_id] = engine.Instrument({sub_voice_ind: voice}, {sub_voice_id: sub_voice_ind})
            else:
                song.voices[voice_id].voice_table[sub_voice_ind] = voice
                song.voices[voice_id].keymap[sub_voice_id] = sub_voice_ind
            if voice.type in HAS_SAMPLE:
                self.get_sample(song, voice)
        else: # Everything else
            if voice_id in song.voices:
                return
            voice = self.load_voice(voice_type, voice_ptr)
            song.voices[voice_id] = voice
            if voice.type in HAS_SAMPLE:
                self.get_sample(song, voice)

    def load_tracks(self, header_ptr: int, table_ptr: int,
                  num_tracks: int) -> engine.Channel:
        """Load all track data for a channel."""

        song = Song()

        transpose = 0
        for track_num in range(num_tracks):
            channel = engine.Channel()
            channel.priority = track_num
            track_pos = self.file.read_gba_pointer(header_ptr + 8 + track_num * 4)
            loop_address = self.get_loop_address(track_pos)

            last_cmd = None
            last_notes = [0] * 256
            last_velocity = [0] * 256
            last_group = [0] * 256
            cmd_num = 0
            voice = 0
            insub = False
            channel.loop_address = -1
            event_queue = channel.event_queue
            sub_voice = 0
            while True:
                self.file.address = track_pos
                if track_pos >= loop_address and channel.loop_address == -1 and loop_address != -1:
                    channel.loop_address = len(event_queue)

                cmd = self.file.read()
                if Command.PRIO <= cmd <= Command.TUNE:
                    arg = self.file.read()
                    if cmd == Command.KEYSH:
                        transpose = arg
                    elif Command.VOICE <= cmd <= Command.TUNE:
                        if cmd == Command.VOICE:
                            last_cmd = cmd
                            voice = arg
                            self.load_instrument(song, table_ptr, voice, sub_voice)
                        last_cmd = cmd
                    event_queue.append(engine.Event(cmd, arg))
                    track_pos += 2
                elif cmd == Command.MEMACC:
                    op = self.file.read()
                    addr = self.file.read()
                    data = self.file.read()
                    event_queue.append(engine.Event(cmd, op, addr, data))
                    track_pos += 4
                elif cmd == Command.PEND:
                    if insub:
                        track_pos = rpc  # pylint: disable=E0601
                        insub = False
                    else:
                        track_pos += 1
                    event_queue.append(engine.Event(cmd))
                elif cmd == Command.PATT:
                    rpc = track_pos + 5
                    insub = True
                    track_pos = self.file.read_gba_pointer()
                    event_queue.append(engine.Event(cmd))
                elif cmd == Command.XCMD:
                    last_cmd = cmd
                    ext = self.file.read()
                    arg = self.file.read()
                    event_queue.append(engine.Event(cmd, ext, arg))
                    track_pos += 2
                elif cmd == Note.EOT:
                    last_cmd = cmd
                    arg = self.file.read()
                    track_pos += 1
                    if arg < 0x80:
                        track_pos += 1
                        event_queue.append(
                            engine.Event(cmd, arg))
                    else:
                        event_queue.append(engine.Event(cmd, 0))
                elif 0x00 <= cmd < 0x80 or Note.TIE <= cmd <= Note.N96:
                    if Note.TIE <= cmd <= Note.N96:
                        track_pos += 1
                        last_cmd = cmd
                    else:
                        if last_cmd <= Note.EOT:
                            if last_cmd == Note.EOT:
                                event_queue.append(engine.Event(last_cmd, cmd))
                            elif last_cmd == Command.VOICE:
                                voice = cmd
                                self.load_instrument(song, table_ptr, voice, sub_voice)
                                event_queue.append(
                                    engine.Event(last_cmd,
                                                 voice))
                            elif last_cmd == Command.XCMD:
                                arg = self.file.read()
                                event_queue.append(engine.Event(last_cmd, cmd, arg))
                            else:
                                event_queue.append(engine.Event(last_cmd, cmd))
                            track_pos += 1
                            continue
                        else:
                            cmd = last_cmd
                    read_command = False
                    cmd_num = 0
                    while not read_command:
                        self.file.address = track_pos
                        note = self.file.read()
                        if note <= mxv:
                            last_notes[cmd_num] = note
                            track_pos += 1
                            velocity = self.file.read()
                            if velocity <= mxv:
                                last_velocity[cmd_num] = velocity
                                track_pos += 1
                                group = self.file.read()
                                if group <= Gate.gtp3:
                                    last_group[cmd_num] = group
                                    track_pos += 1
                                    cmd_num += 1
                                    read_command = True
                                elif Gate.gtp3 < group <= mxv:
                                    read_command = True
                                else:
                                    group = last_group[cmd_num]
                                    read_command = True
                            else:
                                velocity = last_velocity[cmd_num]
                                group = last_group[cmd_num]
                                read_command = True
                            sub_voice = note + transpose
                            event = engine.Event(cmd,
                                                 sub_voice, velocity,
                                                 group)
                            event_queue.append(event)
                        else:
                            if not cmd_num:
                                sub_voice = last_notes[cmd_num] + transpose
                                event_queue.append(
                                    engine.Event(cmd,
                                                 sub_voice,
                                                 last_velocity[cmd_num]))
                            read_command = True

                        self.load_instrument(song, table_ptr, voice, sub_voice)
                elif Wait.W00 <= cmd <= Wait.W96:
                    event_queue.append(engine.Event(cmd))
                    track_pos += 1
                if cmd in (Command.FINE, Command.GOTO, Command.PREV):
                    break

            event_queue.append(engine.Event(cmd))

            song.channels.append(channel)
        return song

    def load_song(self, path: str, song: int, song_table_ptr: int = None) -> Song:
        """Load a song from ROM into memory.

        Loads all samples within the song's voice table and assigns them to
        instruments. Subsequently loads all event_queue commands the Sappy engine
        uses into an event queue for playback processing. Is repeatable.
        """
        self.file = romio.GBARom(path)

        if song_table_ptr is None:
            song_table_ptr = self.file.get_song_table(song)
            if song_table_ptr == -1:
                return -1
        header_ptr = self.file.read_gba_pointer(song_table_ptr + song * 8)

        if header_ptr == -1:
            return -2

        num_tracks = self.file.read(header_ptr)
        if num_tracks == 0:
            return -3

        unk = self.file.read()
        priority = self.file.read()
        echo = self.file.read()
        inst_table_ptr = self.file.read_gba_pointer()
        game_name = self.file.read_string(12, 0xA0)
        game_code = self.file.read_string(4, 0xAC)

        song = self.load_tracks(header_ptr, inst_table_ptr, num_tracks)
        song.meta_data = MetaData(
            rom_code=game_code,
            rom_name=game_name,
            tracks=num_tracks,
            echo=echo,
            priority=priority,
            header_ptr=header_ptr,
            voice_ptr=inst_table_ptr,
            song_ptr=song_table_ptr,
            unknown=unk)

        return song
