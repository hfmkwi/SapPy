#!python
# -*- coding: utf-8 -*-
# TODO: Either use the original FMOD dlls or find a sound engine.
"""Main file."""
import typing

import sappy.engine as engine
import sappy.fileio as fileio
import sappy.fmod as fmod

gba_ptr_to_addr = fileio.gba_ptr_to_addr


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
        return bin(self.echo).lstrip('0b')[0] == 1

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
        self.directs = {}
        self.drumkits = {}
        self.insts = {}
        self.note_queue = {}
        self.samples = {}
        self.meta_data = MetaData()


class Parser(object):
    """Parser/interpreter for Sappy code."""

    GB_WAV_MULTI = 0.5 / 2
    GB_WAV_BASE_FREQ = 8372

    def __init__(self):
        """Initialize all data containers for relevant channel and sample data."""
        self.fpath = ''

        self.file = None

    def patch_exists(self, song: Song, id: int) -> bool:
        """Check if a ."""
        return id in song.directs or id in song.insts or id in song.drumkits

    def new_direct(self, inst_head: fileio.InstrumentHeader,
                   dct_head: fileio.DirectHeader,
                   gb_head: fileio.NoiseHeader) -> engine.Direct:
        """Initialize a direct with the relevant fileio."""
        direct = engine.Direct()
        direct.drum_key = inst_head.drum_pitch
        direct.output = engine.DirectTypes(inst_head.channel & 7)
        direct.env_atck = dct_head.attack
        direct.env_dcy = dct_head.hold
        direct.env_sus = dct_head.is_sustain
        direct.env_rel = dct_head.release
        direct.raw0 = dct_head.b0
        direct.raw1 = dct_head.b1
        direct.gb1 = gb_head.b2
        direct.gb2 = gb_head.b3
        direct.gb3 = gb_head.b4
        direct.gb4 = gb_head.b5
        direct.fix_pitch = (inst_head.channel & 0x08) == 0x08
        direct.reverse = (inst_head.channel & 0x10) == 0x10
        return direct

    def get_smp(self, song: Song, direct: engine.Direct, dct_head: fileio.DirectHeader,
                smp_head: fileio.SampleHeader, use_readstr: bool) -> None:
        """Load a sample from ROM into memory."""
        sid = direct.smp_id = dct_head.smp_head
        if sid in song.samples:
            return
        smp_head = self.file.rd_smp_head(gba_ptr_to_addr(sid))
        if direct.output == engine.DirectTypes.DIRECT:
            size = smp_head.size
            frequency = smp_head.frequency * 64
            loop_start = smp_head.loop
            loop = smp_head.flags == 0x40
            gb_wave = False
            smp_data = self.file._file.tell()
        else:
            size = 32
            frequency = self.GB_WAV_BASE_FREQ
            loop_start = 0
            loop = True
            gb_wave = True
            tsi = self.file.rd_str(16, gba_ptr_to_addr(sid))
            temp_str = []
            for ai in range(32):
                bi = ai % 2
                l = int(ai / 2)
                data = ord(tsi[l])
                data /= 16**bi
                data %= 16
                data *= self.GB_WAV_MULTI * 16
                char = chr(int(data))
                temp_str.append(char)
            smp_data = ''.join(temp_str)
        song.samples[sid] = engine.Sample(
            smp_data,
            size,
            frequency,
            loop_start=loop_start,
            loop=loop,
            gb_wave=gb_wave)

    get_mul_smp = get_smp

    def get_loop_offset(self, program_ctr: int):
        """Determine the looping address of a track/channel."""
        loop_offset = -1
        while True:
            self.file.address = program_ctr
            cmd = self.file.rd_byte()
            if 0 <= cmd <= 0xB0 or cmd in (0xCE, 0xCF, 0xB4):
                program_ctr += 1
            elif cmd == 0xB9:
                program_ctr += 4
            elif 0xB5 <= cmd <= 0xCD:
                program_ctr += 2
            elif cmd == 0xB2:
                loop_offset = self.file.rd_gba_ptr()
                program_ctr += 5
                break
            elif cmd == 0xB3:
                program_ctr += 5
            elif 0xD0 <= cmd <= 0xFF:
                program_ctr += 1
                while self.file.rd_byte() < 0x80:
                    program_ctr += 1

            if cmd == 0xb1:
                break

        return loop_offset

    def load_song(self, header_ptr: int, table_ptr: int,
                     num_tracks: int) -> engine.Channel:
        """Load all track data for a channel."""
        out = (engine.DirectTypes.DIRECT, engine.DirectTypes.WAVEFORM)
        song = Song()
        for track_num in range(num_tracks):
            channel = engine.Channel()
            program_ctr = self.file.rd_gba_ptr(header_ptr + 4 + (track_num + 1) * 4)
            loop_addr = self.get_loop_offset(program_ctr)

            instrument_head = fileio.InstrumentHeader()
            drum_head = fileio.DrumKitHeader()
            direct_head = fileio.DirectHeader()
            sample_head = fileio.SampleHeader()
            multi_head = fileio.MultiHeader()
            noise_head = fileio.NoiseHeader()

            cticks = 0
            last_cmd = 0xBE
            last_notes = [0] * 66
            last_velocity = [0] * 66
            last_unknown = [0] * 66
            last_patch = 0
            insub = 0
            transpose = 0
            channel.loop_ptr = -1
            event_queue = channel.event_queue
            while True:
                self.file.address = program_ctr
                if program_ctr >= loop_addr and channel.loop_ptr == -1 and loop_addr != -1:
                    channel.loop_ptr = len(event_queue)

                cmd = self.file.rd_byte()
                if (cmd != 0xB9 and 0xB5 <= cmd < 0xC5) or cmd == 0xCD:
                    arg1 = self.file.rd_byte()
                    if cmd == 0xBC:
                        transpose = engine.to_int(arg1)
                    elif cmd == 0xBD:
                        last_patch = arg1
                    elif cmd in (0xBE, 0xBF, 0xC0, 0xC4, 0xCD):
                        last_cmd = cmd
                    event_queue.append(engine.Event(cticks, cmd, arg1))
                    program_ctr += 2
                elif 0xC4 < cmd < 0xCF:
                    event_queue.append(engine.Event(cticks, cmd))
                    program_ctr += 1
                elif cmd == 0xb9:
                    arg1 = self.file.rd_byte()
                    arg2 = self.file.rd_byte()
                    arg3 = self.file.rd_byte()
                    event_queue.append(engine.Event(cticks, cmd, arg1, arg2, arg3))
                    program_ctr += 4
                elif cmd == 0xb4:
                    if insub == 1:
                        program_ctr = rpc # pylint: disable=E0601
                        insub = 0
                    else:
                        program_ctr += 1
                elif cmd == 0xb3:
                    rpc = program_ctr + 5
                    insub = 1
                    program_ctr = self.file.rd_gba_ptr()

                elif 0x00 <= cmd < 0x80 or 0xCF <= cmd <= 0xFF:
                    if 0xCF <= cmd <= 0xFF:
                        program_ctr += 1
                        last_cmd = cmd
                    else:
                        if last_cmd < 0xCF:
                            event_queue.append(engine.Event(cticks, last_cmd, cmd))
                            program_ctr += 1
                            continue
                        else:
                            cmd = last_cmd
                    g = False
                    cmd_num = 0
                    while not g:
                        self.file.address = program_ctr
                        arg1 = self.file.rd_byte()
                        if arg1 >= 0x80:
                            if cmd_num == 0:
                                patch = last_notes[cmd_num] + transpose
                                event_queue.append(engine.Event(cticks, cmd, patch, last_velocity[cmd_num],
                                                last_unknown[cmd_num]))
                            g = True
                        else:
                            last_notes[cmd_num] = arg1
                            program_ctr += 1
                            arg2 = self.file.rd_byte()
                            if arg2 < 0x80:
                                last_velocity[cmd_num] = arg2
                                program_ctr += 1
                                arg3 = self.file.rd_byte()
                                if arg3 >= 0x80:
                                    arg3 = last_unknown[cmd_num]
                                    g = True
                                else:
                                    last_unknown[cmd_num] = arg3
                                    program_ctr += 1
                                    cmd_num += 1
                            else:
                                arg2 = last_velocity[cmd_num]
                                arg3 = last_unknown[cmd_num]
                                g = True
                            patch = arg1 + transpose
                            event_queue.append(engine.Event(cticks, cmd, patch, arg2, arg3))
                        if not self.patch_exists(song, last_patch):
                            instrument_head = self.file.rd_inst_head(table_ptr + last_patch * 12)

                            if instrument_head.channel & 0x80 == 0x80:
                                direct_ptr = self.file.rd_drmkit_head().dct_tbl

                                patch_ptr = gba_ptr_to_addr(direct_ptr + patch * 12)
                                instrument_head = self.file.rd_inst_head(patch_ptr)
                                direct_head = self.file.rd_dct_head()
                                noise_head = self.file.rd_nse_head(patch_ptr + 2)

                                direct = self.new_direct(instrument_head, direct_head, noise_head)
                                directs = {patch: direct}

                                song.drumkits[last_patch] = engine.DrumKit(directs)
                                if direct.output in out:
                                    self.get_smp(song, direct, direct_head, sample_head, False)

                            elif instrument_head.channel & 0x40 == 0x40:
                                multi_head = self.file.rd_mul_head()

                                keymap_ptr = gba_ptr_to_addr(multi_head.kmap)
                                cdr = self.file.rd_byte(keymap_ptr + patch)
                                cdr_ptr = gba_ptr_to_addr(multi_head.dct_tbl + cdr * 12)
                                instrument_head = self.file.rd_inst_head(cdr_ptr)
                                direct_head = self.file.rd_dct_head()
                                noise_head = self.file.rd_nse_head(cdr_ptr + 2)

                                args = instrument_head, direct_head, noise_head
                                keymaps = {patch: cdr}
                                direct = self.new_direct(*args)
                                directs = {cdr: direct}
                                instrument = engine.Instrument(directs, keymaps)
                                song.insts[last_patch] = instrument
                                if direct.output in out:
                                    self.get_smp(song, direct, direct_head, sample_head,
                                    False)
                            else:
                                direct_head = self.file.rd_dct_head()
                                noise_head = self.file.rd_nse_head(table_ptr + last_patch * 12 + 2)
                                direct = self.new_direct(instrument_head, direct_head,
                                                        noise_head)
                                song.directs[last_patch] = direct
                                if direct.output in out:
                                    self.get_smp(song, direct, direct_head, sample_head,
                                    False)
                        else:
                            instrument_head = self.file.rd_inst_head(table_ptr + last_patch * 12)
                            if instrument_head.channel & 0x80 == 0x80:
                                drum_head = self.file.rd_drmkit_head()
                                patch_ptr = gba_ptr_to_addr(drum_head.dct_tbl + patch * 12)
                                instrument_head = self.file.rd_inst_head(patch_ptr)
                                direct_head = self.file.rd_dct_head()
                                noise_head = self.file.rd_nse_head(patch_ptr + 2)
                                if patch not in song.drumkits[last_patch].directs:
                                    direct = self.new_direct(instrument_head, direct_head, noise_head)
                                    song.drumkits[last_patch].directs[patch] = direct
                                    if direct.output in out:
                                        self.get_smp(song, direct, direct_head, sample_head, False)
                            elif instrument_head.channel & 0x40 == 0x40:
                                multi_head = self.file.rd_mul_head()
                                if patch not in song.insts[last_patch].keymaps:
                                    keymap_ptr = gba_ptr_to_addr(multi_head.kmap)
                                    direct_id = self.file.rd_byte(keymap_ptr + patch)
                                    song.insts[last_patch].keymaps[patch] = direct_id
                                cdr = song.insts[last_patch].keymaps[patch]
                                cdr_ptr = gba_ptr_to_addr(multi_head.dct_tbl + cdr * 12)
                                instrument_head = self.file.rd_inst_head(cdr_ptr)
                                direct_head = self.file.rd_dct_head()
                                noise_head = self.file.rd_nse_head(cdr_ptr + 2)
                                if cdr not in song.insts[last_patch].directs:
                                    direct = self.new_direct(instrument_head, direct_head, noise_head)
                                    song.insts[last_patch].directs[cdr] = direct
                                    if direct.output in out:
                                        self.get_smp(song, direct, direct_head, sample_head, False)
                elif 0x80 <= cmd <= 0xB0:
                    event_queue.append(engine.Event(cticks, cmd))
                    cticks += engine.to_ticks(cmd - 0x80)
                    program_ctr += 1
                if cmd in (0xB1, 0xB2, 0xB6):
                    break
            event_queue.append(engine.Event(cticks, cmd))
            song.channels.append(channel)
        return song

    def get_song(self, fpath: str, song_num: int, song_list_ptr: int = None) -> Song:
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

        return song
