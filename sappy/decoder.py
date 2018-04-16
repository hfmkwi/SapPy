#!python
#-*- coding: utf-8 -*-
# TODO: Either use the original FMOD dlls or find a sound engine.
"""Main file."""
import logging
import math
import multiprocessing
import os
import random
import sys
import time
import typing

import sappy.engine as engine
import sappy.fileio as fileio
import sappy.fmod as fmod
import sappy.headers as headers

gba_ptr_to_addr = fileio.VirtualFile.gba_ptr_to_addr


class MetaData(typing.NamedTuple):
    """Meta-data for a ROM."""

    rom_name: str
    rom_code: str
    tracks: int
    echo: int
    priority: int
    header_ptr: int
    voice_ptr: int
    unknown: int

    @property
    def echo_enabled(self):
        """Echo flag."""
        return bin(self.echo).lstrip('0b')[0] == 1


class Decoder(object):
    """Decoder/interpreter for Sappy code."""

    DEBUG = False
    GB_WAV_MULTI = 0.5 # 0.0 - 1.0
    GB_WAV_BASE_FREQ = 880 # Frequency in Hertz
    GB_NSE_MULTI = 0.5 # 0.0 - 1.0

    if DEBUG:
        logging.basicConfig(level=DEBUG)
    log = logging.getLogger(name=__name__)

    def __init__(self):
        """Initialize all data containers for relevant channel and sample data."""
        # yapf: disable
        self.fpath:       str                                       = ''
        self.channels:    engine.ChannelQueue[engine.Channel]       = engine.ChannelQueue()
        self.directs:     engine.DirectQueue[engine.Direct]         = engine.DirectQueue()
        self.drumkits:    engine.DrumKitQueue[engine.DrumKit]       = engine.DrumKitQueue()
        self.insts:       engine.InstrumentQueue[engine.Instrument] = engine.InstrumentQueue()
        self.note_queue:  engine.NoteQueue[engine.Note]             = engine.NoteQueue()
        self.samples:     engine.SampleQueue[engine.Sample]         = engine.SampleQueue()
        self.file:        fileio.VirtualFile                        = None
        # yapf:        enable

    def dct_exists(self, direct_queue: engine.DirectQueue, id: int) -> bool:
        """Check if a direct exists for the specified ID."""
        for direct in direct_queue:
            direct: engine.Direct
            if direct.key == str(id):
                return True
        return False

    def kmap_exists(self, keymap_queue: engine.KeyMapQueue, id: int) -> bool:
        """Check if a keymap exists for the specified ID."""
        for kmap in keymap_queue:
            if kmap.key == str(id):
                return True
        return False

    def patch_exists(self, id: int) -> bool:
        """Check if a ."""
        for direct in self.directs:
            if direct.key == str(id):
                return True
        for instrument in self.insts:
            if instrument.key == str(id):
                return True
        for drumkit in self.drumkits:
            if drumkit.key == str(id):
                return True
        return False

    def smp_exists(self, id: int) -> bool:
        """Check if a sample exists for the specified ID."""
        for sample in self.samples:
            if sample.key == str(id):
                return True
        return False

    def set_direct(self, direct: engine.Direct,
                   inst_head: headers.InstrumentHeader,
                   dct_head: headers.DirectHeader,
                   gb_head: headers.NoiseHeader) -> None:
        """Initialize a direct with the relevant headers."""
        # yapf: disable
        direct.drum_key  = inst_head.drum_pitch
        direct.output    = engine.DirectTypes(inst_head.channel & 7)
        direct.env_attn  = dct_head.attack
        direct.env_dcy   = dct_head.hold
        direct.env_sus   = dct_head.is_sustain
        direct.env_rel   = dct_head.release
        direct.raw0      = dct_head.b0
        direct.raw1      = dct_head.b1
        direct.gb1       = gb_head.b2
        direct.gb2       = gb_head.b3
        direct.gb3       = gb_head.b4
        direct.gb4       = gb_head.b5
        direct.fix_pitch = (inst_head.channel & 0x08) == 0x08
        direct.reverse   = (inst_head.channel & 0x10) == 0x10
        # yapf: enable

    def get_smp(self, smp: engine.Sample, dct_head: headers.DirectHeader,
                smp_head: headers.SampleHeader, use_readstr: bool) -> None:
        """Load a sample from ROM into memory."""
        smp.smp_id = dct_head.smp_head
        sid = smp.smp_id
        if self.smp_exists(sid):
            return
        self.samples.add(str(sid))
        w_smp = self.samples[str(sid)]
        smp_head = headers.rd_smp_head(1, gba_ptr_to_addr(sid))
        if smp.output == engine.DirectTypes.DIRECT:
            w_smp.size = smp_head.size
            w_smp.frequency = smp_head.frequency * 64
            w_smp.loop_start = smp_head.loop
            w_smp.loop = smp_head.flags > 0
            w_smp.gb_wave = False
            if use_readstr:
                w_smp.smp_data = self.file.rd_str(smp_head.size)
            else:
                w_smp.smp_data = self.file.rd_addr
        else:
            w_smp.size = 32
            w_smp.frequency = self.GB_WAV_BASE_FREQ
            w_smp.loop_start = 0
            w_smp.loop = True
            w_smp.gb_wave = True
            tsi = self.file.rd_str(16, gba_ptr_to_addr(sid))
            temp_str = []
            for ai in range(32):
                bi = ai % 2
                l = int(ai / 2)
                if tsi[l] == '':
                    data = 0
                else:
                    data = ord(tsi[l])
                data //= 16**bi
                data %= 16
                data *= self.GB_WAV_MULTI * 16
                char = chr(int(data))
                temp_str.append(char)
            w_smp.smp_data = ''.join(temp_str)

    get_mul_smp = get_smp

    def get_loop_offset(self, program_ctr: int):
        """Determine the looping address of a track/channel."""
        loop_offset = -1
        while True:
            self.file.rd_addr = program_ctr
            cmd = self.file.rd_byte()
            if 0 <= cmd <= 0xB0 or cmd == 0xCE or cmd == 0xCF or cmd == 0xB4:
                program_ctr += 1
            elif cmd == 0xB9:
                self.log.debug(
                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | COND JMP |')
                program_ctr += 4
            elif 0xB5 <= cmd <= 0xCD:
                self.log.debug(
                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | CMD  ARG |')
                program_ctr += 2
            elif cmd == 0xB2:
                loop_offset = self.file.rd_gba_ptr()
                self.log.debug(
                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | JMP ADDR | {loop_offset:<#x}'
                )
                program_ctr += 5
                break
            elif cmd == 0xB3:
                self.log.debug(
                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | SUB ADDR |')
                program_ctr += 5
            elif 0xD0 <= cmd <= 0xFF:
                self.log.debug(
                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | BGN NOTE |')
                program_ctr += 1
                while self.file.rd_byte() < 0x80:
                    program_ctr += 1
                self.log.debug(
                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | END NOTE |')

            if cmd == 0xb1:
                break

        return loop_offset

    def load_channel(self, header_ptr: int, table_ptr: int,
                     track_num: int) -> engine.Channel:
        """Load all track data for a channel."""
        channel = engine.Channel()
        program_ctr = self.file.rd_gba_ptr(header_ptr + 4 + (track_num + 1) * 4)
        loop_addr = self.get_loop_offset(program_ctr)

        inst_head = headers.InstrumentHeader()
        drum_head = headers.DrumKitHeader()
        direct_head = headers.DirectHeader()
        samp_head = headers.SampleHeader()
        multi_head = headers.MultiHeader()
        noise_head = headers.NoiseHeader()

        cticks = 0
        last_cmd = 0xBE
        lln = [0] * 66
        llv = [0] * 66
        lla = [0] * 66
        last_patch = 0
        insub = 0
        transpose = 0
        channel.loop_ptr = -1
        event_queue = channel.event_queue

        out = (engine.DirectTypes.DIRECT, engine.DirectTypes.WAVEFORM)

        while True:
            self.file.rd_addr = program_ctr
            if program_ctr >= loop_addr and channel.loop_ptr == -1 and loop_addr != -1:
                channel.loop_ptr = event_queue.count

            cmd = self.file.rd_byte()
            if (cmd != 0xB9 and 0xB5 <= cmd < 0xC5) or cmd == 0xCD:
                arg1 = self.file.rd_byte()
                if cmd == 0xBC:
                    transpose = engine.sbyte_to_int(arg1)
                    self.log.debug(
                        f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | SET TRPS | {transpose:<#x}'
                    )
                elif cmd == 0xBD:
                    last_patch = arg1
                    self.log.debug(
                        f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | SET INST | {last_patch:<#x}'
                    )
                elif cmd in (0xBE, 0xBF, 0xC0, 0xC4, 0xCD):
                    last_cmd = cmd
                    self.log.debug(
                        f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | GET ATTR | {last_cmd:<#x}'
                    )
                event_queue.add(cticks, cmd, arg1)
                self.log.debug(
                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | EVT PLAY | TIME: {cticks:<4} | CTRL: {cmd:<#4x} | ARG1: {arg1:<#4x} | ARG2: 0x00 | ARG3: 0x00'
                )
                program_ctr += 2
            elif 0xC4 < cmd < 0xCF:
                event_queue.add(cticks, cmd)
                self.log.debug(
                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | EVT UNKN | TIME: {cticks:<4} | CTRL: {cmd:<#4x} | ARG1: 0x00 | ARG2: 0x00 | ARG3: 0x00'
                )
                program_ctr += 1
            elif cmd == 0xb9:
                arg1 = self.file.rd_byte()
                arg2 = self.file.rd_byte()
                arg3 = self.file.rd_byte()
                event_queue.add(cticks, cmd, arg1, arg2, arg3)
                self.log.debug(
                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | EVT JUMP | TIME: {cticks:<4} | CTRL: {cmd:<#4x} | ARG1: {arg1:<#4x} | ARG2: {arg2:<#4x} | ARG3: {arg3:<#4x}'
                )
                program_ctr += 4
            elif cmd == 0xb4:
                if insub == 1:
                    self.log.debug(
                        f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | END SUB  |')
                    program_ctr = rpc  # pylint: disable=E0601
                    insub = 0
                else:
                    self.log.debug(
                        f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | RTN EXEC |')
                    program_ctr += 1
            elif cmd == 0xb3:
                self.log.debug(
                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | BGN SUB  |')
                rpc = program_ctr + 5
                insub = 1
                program_ctr = self.file.rd_gba_ptr()
            elif 0xCF <= cmd <= 0xFF:
                program_ctr += 1
                last_cmd = cmd

                g = False
                cmd_num = 0
                while not g:
                    self.file.rd_addr = program_ctr
                    arg1 = self.file.rd_byte()
                    if arg1 >= 0x80:
                        if cmd_num == 0:
                            patch = lln[cmd_num] + transpose
                            event_queue.add(cticks, cmd, patch, llv[cmd_num],
                                            lla[cmd_num])
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | EVT NOTE | TIME: {cticks:<4} | CTRL: {cmd:<#4x} | ARG1: {patch:<#4x} | ARG2: {llv[cmd_num]:<#4x} | ARG3: {lla[cmd_num]:<#4x} | D:    {arg1:<#4x}'
                            )
                        g = True
                    else:
                        lln[cmd_num] = arg1
                        program_ctr += 1
                        arg2 = self.file.rd_byte()
                        if arg2 < 0x80:
                            llv[cmd_num] = arg2
                            program_ctr += 1
                            arg3 = self.file.rd_byte()
                            if arg3 >= 0x80:
                                arg3 = lla[cmd_num]
                                g = True
                            else:
                                lla[cmd_num] = arg3
                                program_ctr += 1
                                cmd_num += 1
                        else:
                            arg2 = llv[cmd_num]
                            arg3 = lla[cmd_num]
                            g = True
                        patch = arg1 + transpose
                        event_queue.add(cticks, cmd, patch, arg2, arg3)
                        self.log.debug(
                            f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | EVT NOTE | TIME: {cticks:<4} | CTRL: {cmd:<#4x} | ARG1: {patch:<#4x} | ARG2: {arg2:<#4x} | ARG3: {arg3:<#4x} | D:    {arg1:<#4x}'
                        )
                    if self.patch_exists(last_patch) is False:
                        inst_head = headers.rd_inst_head(
                            1, table_ptr + last_patch * 12)
                        self.log.debug(
                            f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW PATCH | PREV: {last_patch:<#4x} | PNUM: {patch:<#4x} | HEAD: {inst_head}'
                        )

                        if inst_head.channel & 0x80 == 0x80:  # Drumkit
                            dct_table = headers.rd_drmkit_head(1).dct_tbl
                            patch_addr = gba_ptr_to_addr(dct_table + patch * 12)
                            inst_head = headers.rd_inst_head(1, patch_addr)
                            direct_head = headers.rd_dct_head(1)
                            noise_head = headers.rd_nse_head(1, patch_addr + 2)
                            self.drumkits.add(str(last_patch))
                            directs = self.drumkits[str(last_patch)].directs
                            directs.add(str(patch))
                            self.set_direct(self.drumkits[str(
                                last_patch)].directs[str(patch)], inst_head,
                                            direct_head, noise_head)
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | direct TABLE  | {dct_table}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | INST HEAD  | {inst_head}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | direct HEAD   | {direct_head}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | NOISE HEAD | {noise_head}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | NEW DRMKIT | {self.drumkits[str(last_patch)]}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | NEW DRMKIT | SET DIRECT | {directs[str(patch)]}'
                            )
                            if directs[str(patch)].output in out:
                                self.get_smp(directs[str(patch)], direct_head,
                                             samp_head, False)
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | GET SAMPLE | {directs[str(patch)]}'
                                )
                        elif inst_head.channel & 0x40 == 0x40:  # Multi
                            multi_head = headers.rd_mul_head(1)
                            self.insts.add(str(last_patch))
                            kmaps = self.insts[str(last_patch)].kmaps
                            kmaps.add(0, str(patch))
                            kmaps[str(patch)].assign_dct = self.file.rd_byte(
                                gba_ptr_to_addr(multi_head.kmap) + patch)
                            cdr = kmaps[str(patch)].assign_dct
                            inst_head = headers.rd_inst_head(
                                1,
                                gba_ptr_to_addr(multi_head.dct_tbl + cdr * 12))
                            direct_head = headers.rd_dct_head(1)
                            noise_head = headers.rd_nse_head(
                                1,
                                gba_ptr_to_addr(multi_head.dct_tbl + cdr * 12) +
                                2)
                            self.insts[str(last_patch)].directs.add(str(cdr))
                            self.set_direct(
                                self.insts[str(last_patch)].directs[str(cdr)],
                                inst_head, direct_head, noise_head)
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW MULTI | MULTI HEAD | {multi_head}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW MULTI | NEW INST   | {self.insts[str(last_patch)]}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW MULTI | NEW KEYMAP | {self.insts[str(last_patch)].kmaps.data}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW MULTI | SET ASNDCT | {self.insts[str(last_patch)].kmaps[str(patch)].assign_dct}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW MULTI | INST HEAD  | {inst_head}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW MULTI | direct HEAD   | {direct_head}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW MULTI | NOISE HEAD | {noise_head}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW MULTI | SET DIRECT | {self.insts[str(last_patch)].directs[str(cdr)]}'
                            )
                            if self.insts[str(last_patch)].directs[str(
                                    cdr)].output in out:
                                self.get_smp(self.insts[str(
                                    last_patch)].directs[str(cdr)], direct_head,
                                             samp_head, True)
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW MULTI | GET SAMPLE | {self.insts[str(last_patch)].directs[str(cdr)]}'
                                )
                        else:  # engine.Direct/GB engine.Sample
                            direct_head = headers.rd_dct_head(1)
                            noise_head = headers.rd_nse_head(
                                1, table_ptr + last_patch * 12 + 2)
                            self.directs.add(str(last_patch))
                            self.set_direct(self.directs[str(last_patch)],
                                            inst_head, direct_head, noise_head)
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW direct   | direct HEAD   | {direct_head}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW direct   | NOISE HEAD | {noise_head}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW direct   | SET DIRECT | {self.directs[str(last_patch)]}'
                            )
                            if self.directs[str(last_patch)].output in out:
                                self.get_smp(self.directs[str(last_patch)],
                                             direct_head, samp_head, False)
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW direct   | GET SAMPLE | {self.directs[str(last_patch)]}'
                                )
                    else:  # Patch exists
                        inst_head = headers.rd_inst_head(
                            1, table_ptr + last_patch * 12)
                        self.log.debug(
                            f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | PC.EXIST | PREV: {last_patch:<#4x} | PNUM: {patch:<#4x} | HEAD: {inst_head}'
                        )
                        if inst_head.channel & 0x80 == 0x80:
                            drum_head = headers.rd_drmkit_head(1)
                            inst_head = headers.rd_inst_head(
                                1,
                                gba_ptr_to_addr(drum_head.dct_tbl + patch * 12))
                            direct_head = headers.rd_dct_head(1)
                            noise_head = headers.rd_nse_head(
                                1,
                                gba_ptr_to_addr(drum_head.dct_tbl + patch * 12)
                                + 2)
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | DM EXIST | DRM HEAD   | {drum_head}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | DM EXIST | INST HEAD  | {inst_head}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | DM EXIST | direct HEAD   | {direct_head}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | DM EXIST | NOISE HEAD | {noise_head}'
                            )
                            if self.dct_exists(
                                    self.drumkits[str(last_patch)].directs,
                                    patch) is False:
                                self.drumkits[str(last_patch)].directs.add(
                                    str(patch))
                                self.set_direct(self.drumkits[str(
                                    last_patch)].directs[str(patch)], inst_head,
                                                direct_head, noise_head)
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | DM EXIST | NEW DIRECT | SET DIRECT | {self.drumkits[str(last_patch)].directs[str(patch)]}'
                                )
                                if self.drumkits[str(last_patch)].directs[str(
                                        patch)].output in out:
                                    self.get_mul_smp(self.drumkits[str(
                                        last_patch)].directs[str(patch)],
                                                     direct_head, samp_head,
                                                     False)
                                    self.log.debug(
                                        f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | DM EXIST | NEW DIRECT | GET SAMPLE | {self.drumkits[str(last_patch)].directs[str(patch)]}'
                                    )
                        elif inst_head.channel & 0x40 == 0x40:
                            multi_head = headers.rd_mul_head(1)
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | ML EXIST | MULTI HEAD | {multi_head}'
                            )
                            if self.kmap_exists(
                                    self.insts[str(last_patch)].kmaps,
                                    patch) is False:
                                self.insts[str(last_patch)].kmaps.add(
                                    self.file.rd_byte(
                                        self.file.gba_ptr_to_addr(
                                            multi_head.kmap) + patch),
                                    str(patch))
                            cdr = self.insts[str(last_patch)].kmaps[str(
                                patch)].assign_dct
                            inst_head = headers.rd_inst_head(
                                1,
                                gba_ptr_to_addr(multi_head.dct_tbl + cdr * 12))
                            direct_head = headers.rd_dct_head(1)
                            noise_head = headers.rd_nse_head(
                                1,
                                gba_ptr_to_addr(multi_head.dct_tbl + cdr * 12) +
                                2)
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | {self.insts[str(last_patch)].kmaps[str(patch)]}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | SET CDR    | {cdr}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | INST HEAD  | {inst_head}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | direct HEAD   | {direct_head}'
                            )
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | NSE HEAD   | {noise_head}'
                            )
                            if self.dct_exists(
                                    self.insts[str(last_patch)].directs,
                                    cdr) is False:
                                self.insts[str(last_patch)].directs.add(
                                    str(cdr))
                                self.set_direct(self.insts[str(
                                    last_patch)].directs[str(cdr)], inst_head,
                                                direct_head, noise_head)
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | ML EXIST | SET DIRECT | {self.insts[str(last_patch)].directs[str(cdr)]}'
                                )
                                if self.insts[str(last_patch)].directs[str(
                                        cdr)].output in out:
                                    self.get_mul_smp(self.insts[str(
                                        last_patch)].directs[str(cdr)],
                                                     direct_head, samp_head,
                                                     False)
                                    self.log.debug(
                                        f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | ML EXIST | GET SAMPLE | {self.insts[str(last_patch)].directs[str(cdr)]}'
                                    )

            elif 0x00 <= cmd < 0x80:
                if last_cmd < 0xCF:
                    event_queue.add(cticks, last_cmd, cmd)
                    self.log.debug(
                        f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | PREV CMD | TIME: {cticks:<4} | CTRL: {last_cmd:<#4x} | ARG1: {cmd:<#4x} | ARG2: 0x00 | ARG3: 0x00 '
                    )
                    program_ctr += 1
                else:
                    cmd = last_cmd
                    g = False
                    cmd_num = 0
                    while g is False:
                        self.file.rd_addr = program_ctr
                        arg1 = self.file.rd_byte()
                        if arg1 >= 0x80:
                            if cmd_num == 0:
                                patch = lln[cmd_num] + transpose
                                event_queue.add(cticks, cmd, patch,
                                                llv[cmd_num], lla[cmd_num])
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | PRV NOTE | TIME: {cticks:<4} | CTRL: {cmd:<#4x} | ARG1: {patch:<#4x} | ARG2: {llv[cmd_num]:<#4x} | ARG3: {lla[cmd_num]:<#4x} | D:    {arg1:<#4x}'
                                )
                            g = True
                        else:
                            lln[cmd_num] = arg1
                            program_ctr += 1
                            arg2 = self.file.rd_byte()
                            if arg2 < 0x80:
                                llv[cmd_num] = arg2
                                program_ctr += 1
                                arg3 = self.file.rd_byte()
                                if arg3 >= 0x80:
                                    arg3 = lla[cmd_num]
                                    g = True
                                else:
                                    lla[cmd_num] = arg3
                                    program_ctr += 1
                                    cmd_num += 1
                            else:
                                arg2 = llv[cmd_num]
                                arg3 = lla[cmd_num]
                                g = True
                            patch = arg1 + transpose
                            event_queue.add(cticks, cmd, patch, arg2, arg3)
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | PRV NOTE | TIME: {cticks:<4} | CTRL: {cmd:<#4x} | ARG1: {patch:<#4x} | ARG2: {arg2:<#4x} | ARG3: {arg3:<#4x} | D:    {arg1:<#4x}'
                            )
                        if self.patch_exists(last_patch) is False:
                            inst_head = headers.rd_inst_head(
                                1, table_ptr + last_patch * 12)
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | PV PATCH | PREV: {last_patch:<#4x} | PNUM: {patch:<#4x} | CHAN: {inst_head.channel:<#4x}'
                            )
                            if inst_head.channel & 0x80 == 0x80:
                                drum_head = headers.rd_drmkit_head(1)
                                inst_head = headers.rd_inst_head(
                                    1,
                                    gba_ptr_to_addr(
                                        drum_head.dct_tbl + patch * 12))
                                direct_head = headers.rd_dct_head(1)
                                noise_head = headers.rd_nse_head(
                                    1,
                                    gba_ptr_to_addr(
                                        drum_head.dct_tbl + patch * 12) + 2)
                                self.drumkits.add(str(last_patch))
                                self.drumkits[str(last_patch)].directs.add(
                                    str(patch))
                                self.set_direct(self.drumkits[str(
                                    last_patch)].directs[str(patch)], inst_head,
                                                direct_head, noise_head)
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | DRM HEAD   | {drum_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | INST HEAD  | {inst_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | direct HEAD   | {direct_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | NOISE HEAD | {noise_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | NEW DRMKIT | {self.drumkits[str(last_patch)]}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | NEW DRMKIT | SET DIRECT | {self.drumkits[str(last_patch)].directs[str(patch)]}'
                                )
                                if self.drumkits[str(last_patch)].directs[str(
                                        patch)].output in out:
                                    self.get_smp(self.drumkits[str(
                                        last_patch)].directs[str(patch)],
                                                 direct_head, samp_head, True)
                                    self.log.debug(
                                        f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | GET SAMPLE | {self.drumkits[str(last_patch)].directs[str(patch)]}'
                                    )
                            elif inst_head.channel & 0x40 == 0x40:
                                multi_head = headers.rd_mul_head(1)
                                self.insts.add(str(last_patch))
                                self.insts[str(last_patch)].kmaps.add(
                                    self.file.rd_byte(
                                        gba_ptr_to_addr(multi_head.kmap) + patch
                                    ), str(patch))
                                cdr = self.insts[str(last_patch)].kmaps[str(
                                    patch)].assign_dct
                                inst_head = headers.rd_inst_head(
                                    1,
                                    gba_ptr_to_addr(
                                        multi_head.dct_tbl + cdr * 12))
                                direct_head = headers.rd_dct_head(1)
                                noise_head = headers.rd_nse_head(
                                    1,
                                    gba_ptr_to_addr(
                                        multi_head.dct_tbl + cdr * 12) + 2)
                                self.insts[str(last_patch)].directs.add(
                                    str(cdr))
                                self.set_direct(self.insts[str(
                                    last_patch)].directs[str(cdr)], inst_head,
                                                direct_head, noise_head)
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW MULTI | MULTI HEAD | {multi_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW MULTI | NEW INST   | {self.insts[str(last_patch)]}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW MULTI | NEW KEYMAP | {self.insts[str(last_patch)].kmaps}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW MULTI | SET ASNDCT | {cdr}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW MULTI | INST HEAD  | {inst_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW MULTI | direct HEAD   | {direct_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW MULTI | NOISE HEAD | {noise_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW MULTI | SET DIRECT | {self.insts[str(last_patch)].directs[str(cdr)]}'
                                )
                                if self.insts[str(last_patch)].directs[str(
                                        cdr)].output in out:
                                    self.get_smp(self.insts[str(
                                        last_patch)].directs[str(cdr)],
                                                 direct_head, samp_head, False)
                                    self.log.debug(
                                        f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | GET SAMPLE | {self.insts[str(last_patch)].directs[str(cdr)]}'
                                    )
                            else:
                                direct_head = headers.rd_dct_head(1)
                                noise_head = headers.rd_nse_head(
                                    1, table_ptr + last_patch * 12 + 2)
                                self.directs.add(str(last_patch))
                                if self.directs[str(last_patch)].output in out:
                                    self.get_mul_smp(
                                        self.directs[str(last_patch)],
                                        direct_head, samp_head, False)
                        else:
                            inst_head = headers.rd_inst_head(
                                1, table_ptr + last_patch * 12)
                            self.log.debug(
                                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | PC EXIST | PREV: {last_patch:<#4x} | PNUM: {patch:<#4x} | HEAD: {inst_head}'
                            )
                            if inst_head.channel & 0x80 == 0x80:
                                drum_head = headers.rd_drmkit_head(1)
                                inst_head = headers.rd_inst_head(
                                    1,
                                    gba_ptr_to_addr(
                                        drum_head.dct_tbl + patch * 12))
                                direct_head = headers.rd_dct_head(1)
                                noise_head = headers.rd_nse_head(
                                    1,
                                    gba_ptr_to_addr(
                                        drum_head.dct_tbl + patch * 12) + 2)
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | DM EXIST | DRM HEAD   | {drum_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | DM EXIST | INST HEAD  | {inst_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | DM EXIST | direct HEAD   | {direct_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | DM EXIST | NOISE HEAD | {noise_head}'
                                )
                                if self.dct_exists(
                                        self.drumkits[str(last_patch)].directs,
                                        patch) is False:
                                    self.drumkits[str(last_patch)].directs.add(
                                        str(patch))
                                    self.set_direct(self.drumkits[str(
                                        last_patch)].directs[str(patch)],
                                                    inst_head, direct_head,
                                                    noise_head)
                                    self.log.debug(
                                        f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | DM EXIST | NEW DIRECT | SET DIRECT | {self.drumkits[str(last_patch)].directs[str(patch)]}'
                                    )
                                    if self.drumkits[str(last_patch)].directs[
                                            str(patch)].output in out:
                                        self.get_mul_smp(
                                            self.drumkits[str(last_patch)]
                                            .directs[str(patch)], direct_head,
                                            samp_head, False)
                                        self.log.debug(
                                            f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | DM EXIST | NEW DIRECT | GET SAMPLE | {self.drumkits[str(last_patch)].directs[str(patch)]}'
                                        )
                            elif inst_head.channel & 0x40 == 0x40:
                                multi_head = headers.rd_mul_head(1)
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | ML EXIST | MULTI HEAD | {multi_head}'
                                )
                                if self.kmap_exists(
                                        self.insts[str(last_patch)].kmaps,
                                        patch) is False:
                                    self.insts[str(last_patch)].kmaps.add(
                                        self.file.rd_byte(
                                            gba_ptr_to_addr(multi_head.kmap) +
                                            patch), str(patch))
                                cdr = self.insts[str(last_patch)].kmaps[str(
                                    patch)].assign_dct
                                inst_head = headers.rd_inst_head(
                                    1,
                                    gba_ptr_to_addr(
                                        multi_head.dct_tbl + cdr * 12))
                                direct_head = headers.rd_dct_head(1)
                                noise_head = headers.rd_nse_head(
                                    1,
                                    gba_ptr_to_addr(
                                        multi_head.dct_tbl + cdr * 12) + 2)
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | {self.insts[str(last_patch)].kmaps[str(patch)]}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | SET CDR    | {cdr}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | INST HEAD  | {inst_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | direct HEAD   | {direct_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | NSE HEAD   | {noise_head}'
                                )
                                if self.dct_exists(
                                        self.insts[str(last_patch)].directs,
                                        cdr) is False:
                                    self.insts[str(last_patch)].directs.add(
                                        str(cdr))
                                    self.set_direct(self.insts[str(
                                        last_patch)].directs[str(cdr)],
                                                    inst_head, direct_head,
                                                    noise_head)
                                    self.log.debug(
                                        f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | ML EXIST | SET DIRECT | {self.insts[str(last_patch)].directs[str(cdr)]}'
                                    )
                                    if self.insts[str(last_patch)].directs[str(
                                            cdr)].output in out:
                                        self.get_mul_smp(
                                            self.insts[str(last_patch)].directs[
                                                str(cdr)], direct_head,
                                            samp_head, False)
                                        self.log.debug(
                                            f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | ML EXIST | GET SAMPLE | {self.insts[str(last_patch)].directs[str(cdr)]}'
                                        )
            elif 0x80 <= cmd <= 0xB0:
                event_queue.add(cticks, cmd)
                self.log.debug(
                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | EVT WAIT | TIME: {cticks:<4} | CTRL: {cmd:<#4x} | ARG1: 0x00 | ARG2: 0x00 | ARG3: 0x00 | TIME: {engine.stlen_to_ticks(cmd - 0x80):<#4x}'
                )
                cticks += engine.stlen_to_ticks(cmd - 0x80)
                program_ctr += 1
            if cmd in (0xB1, 0xB2, 0xB6):
                self.log.debug(
                    f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | END EVT  |')
                #event_queue.add(cticks, c)
                break
            self.log.debug(
                f'| PGM: {program_ctr:#x} | CMD: {cmd:#x} | EVT END  | TIME: {cticks:<4x} | CTRL: {cmd:<#4x} | ARG1: 0x00 | ARG2: 0x00 | ARG3: 0x00'
            )
        event_queue.add(cticks, cmd)

        return channel

    def load_song(self, fpath: str, sng_num: int, sng_list_ptr: int = None):
        """Load a song from ROM into memory.

        Loads all samples within the song's voice table and assigns them to
        instruments. Subsequently loads all events commands the Sappy engine
        uses into an event queue for playback processing. Is repeatable.
        """
        self.file = fileio.open_file(fpath, 1)
        header_ptr = self.file.rd_gba_ptr(sng_list_ptr + sng_num * 8)
        num_tracks = self.file.rd_byte(header_ptr)
        unk = self.file.rd_byte()
        priority = self.file.rd_byte()
        echo = self.file.rd_byte()
        inst_table_ptr = self.file.rd_gba_ptr()
        game_name = self.file.rd_str(12, 0xA0)
        game_code = self.file.rd_str(4, 0xAC)

        meta_data = MetaData(
            rom_code=game_code,
            rom_name=game_name,
            tracks=num_tracks,
            echo=echo,
            priority=priority,
            header_ptr=header_ptr,
            voice_ptr=inst_table_ptr,
            unknown=unk)

        channels = engine.ChannelQueue()
        for track_num in range(num_tracks):
            channel = self.load_channel(header_ptr, inst_table_ptr, track_num)
            channels.append(channel)
        self.file.close()

        return channels, self.drumkits, self.samples, self.insts, self.directs, meta_data
