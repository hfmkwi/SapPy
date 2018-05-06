#!python
# -*- coding: utf-8 -*-
# TODO: Either use the original FMOD dlls or find a sound engine.
"""Main file."""
import typing

import sappy.config as config
import sappy.engine as engine
import sappy.fileio as fileio
import sappy.fmod as fmod
from sappy.instructions import *

to_addr = fileio.to_addr


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

    def new_direct(self, inst_head: fileio.InstrumentHeader,
                   direct_header: fileio.DirectHeader,
                   noise_header: fileio.NoiseHeader) -> engine.Direct:
        """Initialize a direct with the relevant fileio."""
        direct = engine.Direct()
        direct.drum_key = inst_head.drum_pitch
        direct.output_type = engine.DirectTypes(inst_head.channel & 7)
        direct.attack = direct_header.attack
        direct.decay = direct_header.hold
        direct.sustain = direct_header.sustain
        direct.release = direct_header.release
        direct.raw0 = direct_header.b0
        direct.raw1 = direct_header.b1
        direct.psg_flag = noise_header.b2
        direct.fix_pitch = (inst_head.channel & 0x08) == 0x08
        return direct

    def get_smp(self, song: Song, direct: engine.Direct,
                direct_header: fileio.DirectHeader) -> None:
        """Load a sample from ROM into memory."""
        sid = direct.bound_sample = direct_header.sample_ptr
        if sid in song.samples:
            return
        smp_head = self.file.rd_smp_head(to_addr(sid))
        if direct.output_type == engine.DirectTypes.DIRECT:
            size = smp_head.size
            frequency = smp_head.frequency >> 10
            loop_start = smp_head.loop
            loop = smp_head.is_looped == 0x40
            gb_wave = False
            smp_data = self.file._file.tell()
        else:
            size = config.WAVEFORM_SIZE
            frequency = config.WAVEFORM_FREQUENCY
            loop_start = 0
            loop = True
            gb_wave = True
            tsi = self.file.rd_str(16, to_addr(sid))
            smp_data = []
            for ai in range(32):
                tsi_ind, power = divmod(ai, 2)
                data = ord(tsi[tsi_ind])
                data /= 16**power
                data %= 16
                data *= config.WAVEFORM_VOLUME * 16
                smp_data.append(int(data))
        song.samples[sid] = engine.Sample(
            smp_data,
            size,
            frequency,
            loop_start=loop_start,
            loop=loop,
            gb_wave=gb_wave)

    def get_loop_offset(self, program_ctr: int):
        """Determine the looping address of a track/channel."""
        loop_offset = -1
        cmd = 0
        while cmd != Command.FINE:
            self.file.address = program_ctr
            cmd = self.file.rd_byte()
            if Wait.W00 <= cmd <= Wait.W96:
                program_ctr += 1
            elif cmd in (Command.GOTO, Command.PATT):
                program_ctr += 4
                if cmd == Command.GOTO:
                    return self.file.rd_gba_ptr()
            elif Command.PRIO <= cmd <= 0xC6:
                program_ctr += 1
            elif cmd == Command.REPT:
                program_ctr += 5
            elif cmd == Command.MEMACC:
                program_ctr += 3
            elif Note.EOT <= cmd <= Note.N96:
                program_ctr += 1
                while self.file.rd_byte() < 0x80:
                    program_ctr += 1
            else:
                program_ctr += 1

        return loop_offset

    def load_voice(self, song, table_ptr, last_patch, voice):
        HAS_SAMPLE = (engine.DirectTypes.DIRECT, engine.DirectTypes.WAVEFORM)

        type_head = self.file.rd_inst_head(
                table_ptr + last_patch * 12)
        if type_head.channel == 0x80: # Percussion
            direct_ptr = self.file.rd_drmkit_head().dct_tbl
            patch_ptr = to_addr(direct_ptr + voice * 12)
            type_head = self.file.rd_inst_head(patch_ptr)
            direct_header = self.file.rd_dct_head()
            noise_head = self.file.rd_nse_head(patch_ptr + 2)
            direct = self.new_direct(type_head, direct_header,
                                    noise_head)
            if last_patch not in song.voices:
                directs = {voice: direct}
                song.voices[last_patch] = engine.DrumKit(directs)
            elif voice not in song.voices[last_patch].directs:
                song.voices[last_patch].directs[voice] = direct
            if direct.output_type in HAS_SAMPLE:
                self.get_smp(song, direct, direct_header)
        elif type_head.channel == 0x40: # Multi
            multi_head = self.file.rd_mul_head()

            keymap_ptr = to_addr(multi_head.kmap)
            cdr = self.file.rd_byte(keymap_ptr + voice)
            cdr_ptr = to_addr(multi_head.dct_tbl + cdr * 12)
            type_head = self.file.rd_inst_head(cdr_ptr)
            direct_header = self.file.rd_dct_head()
            noise_head = self.file.rd_nse_head(cdr_ptr + 2)

            direct = self.new_direct(type_head, direct_header,
                                        noise_head)
            if last_patch not in song.voices:
                keymaps = {voice: cdr}
                directs = {cdr: direct}
                instrument = engine.Instrument(directs, keymaps)
                song.voices[last_patch] = instrument
            elif cdr not in song.voices[last_patch].directs:
                song.voices[last_patch].directs[cdr] = direct
            if voice not in song.voices[last_patch].keymaps:
                direct_id = self.file.rd_byte(keymap_ptr + voice)
                song.voices[last_patch].keymaps[voice] = direct_id
            if direct.output_type in HAS_SAMPLE:
                self.get_smp(song, direct, direct_header)
        else: # Everything else
            direct_header = self.file.rd_dct_head()
            noise_head = self.file.rd_nse_head(
                table_ptr + last_patch * 12 + 2)
            direct = self.new_direct(type_head, direct_header,
                                        noise_head)
            song.voices[last_patch] = direct
            if direct.output_type in HAS_SAMPLE:
                self.get_smp(song, direct, direct_header)

    def load_song(self, header_ptr: int, table_ptr: int,
                  num_tracks: int) -> engine.Channel:
        """Load all track data for a channel."""

        song = Song()
        for track_num in range(1, num_tracks + 1):
            channel = engine.Channel()
            program_ctr = self.file.rd_gba_ptr(header_ptr + 4 + track_num * 4)
            loop_addr = self.get_loop_offset(program_ctr)

            elapsed_ticks = 0
            last_cmd = Command.VOL
            last_notes = [0] * 256
            last_velocity = [0] * 256
            last_group = [0] * 256
            cmd_num = 0
            last_patch = 0
            insub = False
            transpose = 0
            channel.loop_ptr = -1
            event_queue = channel.event_queue
            voice = -1
            while True:
                self.file.address = program_ctr
                if program_ctr >= loop_addr and channel.loop_ptr == -1 and loop_addr != -1:
                    channel.loop_ptr = len(event_queue)

                cmd = self.file.rd_byte()
                if cmd != Command.MEMACC and Command.REPT <= cmd <= Command.TUNE:
                    arg1 = self.file.rd_byte()
                    if cmd == Command.KEYSH:
                        transpose = arg1
                    elif Command.VOICE <= cmd <= Command.TUNE:
                        if cmd == Command.VOICE:
                            last_cmd = cmd
                            last_patch = arg1
                            self.load_voice(song, table_ptr, last_patch, voice)
                        last_cmd = cmd
                    event_queue.append(engine.Event(elapsed_ticks, cmd, arg1))
                    program_ctr += 2
                elif cmd == Command.MEMACC:
                    op = self.file.rd_byte()
                    addr = self.file.rd_byte()
                    data = self.file.rd_byte()
                    event_queue.append(
                        engine.Event(elapsed_ticks, cmd, op, addr, data))
                    program_ctr += 4
                elif cmd == Command.PEND:
                    if insub:
                        program_ctr = rpc  # pylint: disable=E0601
                        insub = False
                    else:
                        program_ctr += 1
                    event_queue.append(engine.Event(elapsed_ticks, cmd))
                elif cmd == Command.PATT:
                    rpc = program_ctr + 5
                    insub = True
                    program_ctr = self.file.rd_gba_ptr()
                    event_queue.append(engine.Event(elapsed_ticks, cmd))
                elif cmd == Command.XCMD:
                    last_cmd = cmd
                    ext = self.file.rd_byte()
                    arg = self.file.rd_byte()
                    event_queue.append(
                        engine.Event(elapsed_ticks, cmd, ext, arg))
                    program_ctr += 2
                elif cmd == Note.EOT:
                    last_cmd = cmd
                    arg1 = self.file.rd_byte()
                    program_ctr += 1
                    if arg1 < 0x80:
                        program_ctr += 1
                        event_queue.append(
                            engine.Event(elapsed_ticks, cmd, arg1))
                    else:
                        event_queue.append(engine.Event(elapsed_ticks, cmd, 0))
                elif 0x00 <= cmd < 0x80 or Note.TIE <= cmd <= Note.N96:
                    if Note.TIE <= cmd <= Note.N96:
                        program_ctr += 1
                        last_cmd = cmd
                    else:
                        if last_cmd <= Note.EOT:
                            if last_cmd == Note.EOT:
                                event_queue.append(
                                    engine.Event(elapsed_ticks, last_cmd, cmd))
                            elif last_cmd == Command.VOICE:
                                last_patch = cmd
                                self.load_voice(song, table_ptr,
                                                     last_patch, voice)
                                event_queue.append(
                                    engine.Event(elapsed_ticks, last_cmd,
                                                 last_patch))
                            elif last_cmd == Command.XCMD:
                                arg = self.file.rd_byte()
                                event_queue.append(
                                    engine.Event(elapsed_ticks, last_cmd, cmd,
                                                 arg))
                            else:
                                event_queue.append(
                                    engine.Event(elapsed_ticks, last_cmd, cmd))
                            program_ctr += 1
                            continue
                        else:
                            cmd = last_cmd
                    read_command = False
                    cmd_num = 0
                    while not read_command:
                        self.file.address = program_ctr
                        note = self.file.rd_byte()
                        if note <= mxv:
                            last_notes[cmd_num] = note
                            program_ctr += 1
                            velocity = self.file.rd_byte()
                            if velocity <= mxv:
                                last_velocity[cmd_num] = velocity
                                program_ctr += 1
                                group = self.file.rd_byte()
                                if group <= Gate.gtp3:
                                    last_group[cmd_num] = group
                                    program_ctr += 1
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
                            voice = note + transpose
                            event = engine.Event(elapsed_ticks, cmd,
                                                 voice, velocity,
                                                 group)
                            event_queue.append(event)
                        else:
                            if not cmd_num:
                                voice = last_notes[cmd_num] + transpose
                                event_queue.append(
                                    engine.Event(elapsed_ticks, cmd,
                                                 voice,
                                                 last_velocity[cmd_num]))
                            read_command = True

                    self.load_voice(song, table_ptr, last_patch, voice)
                elif Wait.W00 <= cmd <= Wait.W96:
                    event_queue.append(engine.Event(elapsed_ticks, cmd))
                    elapsed_ticks += int(Wait(cmd).name[1:])  # pylint: disable=E1136
                    program_ctr += 1
                if cmd in (Command.FINE, Command.GOTO, Command.PREV):
                    break
            event_queue.append(engine.Event(elapsed_ticks, cmd))

            song.channels.append(channel)
        return song

    def get_song(self, fpath: str, song_num: int,
                 song_list_ptr: int = None) -> Song:
        """Load a song from ROM into memory.

        Loads all samples within the song's voice table and assigns them to
        instruments. Subsequently loads all event_queue commands the Sappy engine
        uses into an event queue for playback processing. Is repeatable.
        """
        self.file = fileio.open_file(fpath)

        if song_list_ptr is None:
            song_list_ptr = self.file.get_song_table_ptr(song_num)
            if song_list_ptr == -1:
                return -1
        header_ptr = self.file.rd_gba_ptr(song_list_ptr + song_num * 8)

        if header_ptr == -1:
            return -2

        num_tracks = self.file.rd_byte(header_ptr)
        if num_tracks == 0:
            return -3

        unk = self.file.rd_byte()
        priority = self.file.rd_byte()
        echo = self.file.rd_byte()
        inst_table_ptr = self.file.rd_gba_ptr()
        game_name = self.file.rd_str(12, 0xA0)
        game_code = self.file.rd_str(4, 0xAC)

        song = self.load_song(header_ptr, inst_table_ptr, num_tracks)
        song.meta_data = MetaData(
            rom_code=game_code,
            rom_name=game_name,
            tracks=num_tracks,
            echo=echo,
            priority=priority,
            header_ptr=header_ptr,
            voice_ptr=inst_table_ptr,
            song_ptr=song_list_ptr,
            unknown=unk)

        self.file.close()

        return song
