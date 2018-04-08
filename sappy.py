#!python
#-*- coding: utf-8 -*-
# pylint disable=C0103, C0326, E1120, R0902, R0903, R0904, R0912, R0913, R0914, R0915, R1702
# pylint: disable=W0614
# TODO: Either use the original FMOD dlls or find a sound engine.
"""Main file."""
import math
from os import remove
from random import random
from time import time, sleep
from logging import INFO, basicConfig, getLogger
from typing import List, NamedTuple, Union

from containers import *
from fileio import *
from fmod import *
from player import *

from struct import unpack, pack

from ctypes import byref, pointer

BASE = math.pow(2, 1 / 12)
gba_ptr_to_addr = VirtualFile.gba_ptr_to_addr


class Decoder(object):
    """Decoder/interpreter for Sappy code."""
    DEBUG = False
    GB_SQ_MULTI = 0.5 / 4
    GB_WAV_MULTI = 0.5
    GB_WAV_BASE_FREQ = 880
    GB_NSE_MULTI = 0.5
    SAPPY_PPQN = 24
    WIDTH = 32

    if DEBUG:
        basicConfig(level=DEBUG)
    else:
        basicConfig(level=None)
    log = getLogger(name=__name__)

    def __init__(self):
        # yapf: disable
        self.looped:     bool                        = False
        self.playing:    bool                        = False
        self.gb1_chan:   int                         = 0
        self.gb2_chan:   int                         = 0
        self.gb3_chan:   int                         = 0
        self.gb4_chan:   int                         = 0
        self.incr:       int                         = 0
        self.tempo:      int                         = 0
        self.transpose:  int                         = 0
        self._gbl_vol:   int                         = 256
        self.tick_ctr:   bool                        = False
        self.mdrum_map:  list                        = []
        self.mpatch_map: list                        = []
        self.mpatch_tbl: list                        = []
        self.fpath:      str                         = ''
        self.rip_ears:   Collection                  = Collection()
        self.channels:   ChannelQueue[Channel]       = ChannelQueue()  # pylint:    disable = E1136
        self.directs:    DirectQueue[Direct]         = DirectQueue()  # pylint:     disable = E1136
        self.drmkits:    DrumKitQueue[DrumKit]       = DrumKitQueue()  # pylint:    disable = E1136
        self.insts:      InstrumentQueue[Instrument] = InstrumentQueue()  # pylint: disable = E1136
        self.note_arr:   List                        = Collection([Note(*[0]*6)] * 32)
        self.nse_wavs:   List[List[str]]             = [[[] for i in range(10)] for i in range(2)]
        self.note_q:     NoteQueue[Note]             = NoteQueue()  # pylint:       disable = E1136
        self.smp_pool:   SampleQueue[Sample]         = SampleQueue()  # pylint:     disable = E1136
        self.file:       VirtualFile                 = None
        # yapf: enable
        sz = 2048
        if not sz:
            sz = 2048
        for i in range(10):
            for _ in range(sz):
                self.nse_wavs[0][i].append(chr(int(random() * 153)))
            self.nse_wavs[0][i] = "".join(self.nse_wavs[0][i])
            for _ in range(256):
                self.nse_wavs[1][i].append(chr(int(random() * 153)))
            self.nse_wavs[1][i] = "".join(self.nse_wavs[1][i])
        #self.gbl_vol = 255

    @property
    def gbl_vol(self) -> int:
        """Global volume of the player."""
        return self._gbl_vol

    @gbl_vol.setter
    def gbl_vol(self, vol: int) -> None:
        setMasterVolume(vol)
        self._gbl_vol = vol

    def dct_exists(self, dcts: DirectQueue, dct_id: int) -> bool:
        """Check if a direct exists in a specfied `DirectQueue`."""
        for dct in dcts:
            dct: Direct
            if dct.key == str(dct_id):
                return True
        return False

    def set_direct(self, direct: Direct, inst_head: InstrumentHeader,
                   dct_head: DirectHeader, gb_head: NoiseHeader) -> None:
        # yapf: disable
        direct.drum_key  = inst_head.drum_pitch
        direct.output    = DirectTypes(inst_head.channel & 7)
        direct.env_attn  = dct_head.attack
        direct.env_dcy   = dct_head.hold
        direct.env_sus   = dct_head.sustain
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

    def drm_exists(self, patch: int) -> bool:
        """Check if a drumkit on the specified MIDI patch exists."""
        for drm in self.drmkits:
            if drm.key == str(patch):
                return True
        return False

    def free_note(self) -> int:
        """Get a free note number.

        Notes
        ----
        On an actual AGB, only up to 32 notes may be played in tandem.

        Returns
        -------
        int
            On success, a number between 0 and 32. -1 otherwise.
        """
        for i in range(31, -1, -1):
            item = self.note_arr[i]
            if item.enable is False:
                name = note_to_name(item.note_num)
                if name in self.channels[item.parent].playing:
                    self.channels[item.parent].playing.remove(
                        note_to_name(item.note_num))
                return i
        return 255

    def get_smp(self, smp: Sample, dct_head: DirectHeader,
                smp_head: SampleHeader, use_readstr: bool) -> None:
        """Load a sample from ROM into memory."""
        smp.smp_id = dct_head.smp_head
        sid = smp.smp_id
        if self.smp_exists(sid):
            return
        self.smp_pool.add(str(sid))
        w_smp = self.smp_pool[str(sid)]
        smp_head = rd_smp_head(1, VirtualFile.gba_ptr_to_addr(sid))
        if smp.output == DirectTypes.DIRECT:
            w_smp.size = smp_head.size
            w_smp.freq = smp_head.freq * 64
            w_smp.loop_start = smp_head.loop
            w_smp.loop = smp_head.flags > 0
            w_smp.gb_wave = False
            if not use_readstr:
                w_smp.smp_data = self.file.rd_str(smp_head.size)
            else:
                w_smp.smp_data = self.file.rd_addr
        else:
            w_smp.size = 32
            w_smp.freq = self.GB_WAV_BASE_FREQ
            w_smp.loop_start = 0
            w_smp.loop = True
            w_smp.gb_wave = True
            tsi = self.file.rd_str(16, VirtualFile.gba_ptr_to_addr(sid))
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

    def inst_exists(self, patch: int) -> bool:
        """Check if an instrument on the specified MIDI patch is defined."""
        for inst in self.insts:
            if inst.key == str(patch):
                return True
        return False

    def kmap_exists(self, kmaps: KeyMapQueue, kmap_id: int) -> bool:
        """Check if a keymap is defined."""
        for kmap in kmaps:
            if kmap.key == str(kmap_id):
                return True
        return False

    def patch_exists(self, last_patch: int) -> bool:
        """Check if an instrument is defined."""
        for dct in self.directs:
            if self.val(dct.key) == last_patch:
                return True
        for inst in self.insts:
            if self.val(inst.key) == last_patch:
                return True
        for dk in self.drmkits:
            if self.val(dk.key) == last_patch:
                return True
        return False

    def reset_player(self) -> None:
        self.channels.clear()
        self.drmkits.clear()
        self.smp_pool.clear()
        self.insts.clear()
        self.directs.clear()
        self.note_q.clear()

        for i in range(31, -1, -1):
            self.note_arr[i].enable = False

        self.gb1_chan = 255
        self.gb2_chan = 255
        self.gb3_chan = 255
        self.gb4_chan = 255

        self.tempo = 120
        self.incr = 0

    def get_loop_offset(self, pgm_ctr: int):
        """Determine the looping address of a track/channel."""
        loop_offset = -1
        while True:
            self.file.rd_addr = pgm_ctr
            cmd = self.file.rd_byte()
            if 0 <= cmd <= 0xB0 or cmd == 0xCE or cmd == 0xCF or cmd == 0xB4:
                pgm_ctr += 1
            elif cmd == 0xB9:
                self.log.debug(
                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | COND JMP |')
                pgm_ctr += 4
            elif 0xB5 <= cmd <= 0xCD:
                self.log.debug(
                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | CMD  ARG |')
                pgm_ctr += 2
            elif cmd == 0xB2:
                loop_offset = self.file.rd_gba_ptr()
                self.log.debug(
                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | JMP ADDR | {loop_offset:<#x}'
                )
                pgm_ctr += 5
                break
            elif cmd == 0xB3:
                self.log.debug(
                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | SUB ADDR |')
                pgm_ctr += 5
            elif 0xD0 <= cmd <= 0xFF:
                self.log.debug(
                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | BGN NOTE |')
                pgm_ctr += 1
                while self.file.rd_byte() < 0x80:
                    pgm_ctr += 1
                self.log.debug(
                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | END NOTE |')

            if cmd == 0xb1:
                break

        return loop_offset

    def load_events(self, channel: Channel, header_ptr: int, table_ptr: int,
                    track_num: int) -> None:
        pgm_ctr = self.file.rd_gba_ptr(header_ptr + 4 + (track_num + 1) * 4)
        loop_addr = self.get_loop_offset(pgm_ctr)

        inst_head = InstrumentHeader()
        drum_head = DrumKitHeader()
        direct_head = DirectHeader()
        samp_head = SampleHeader()
        multi_head = MultiHeader()
        noise_head = NoiseHeader()

        cticks = 0
        last_cmd = 0xBE
        lln = [0] * 66
        llv = [0] * 66
        lla = [0] * 66
        last_patch = 0
        insub = 0
        transpose = 0
        channel.loop_ptr = -1
        evt_queue = channel.evt_queue

        out = (DirectTypes.DIRECT, DirectTypes.WAVE)

        while True:
            self.file.rd_addr = pgm_ctr
            if pgm_ctr >= loop_addr and channel.loop_ptr == -1 and loop_addr != -1:
                channel.loop_ptr = evt_queue.count

            cmd = self.file.rd_byte()
            if (cmd != 0xB9 and 0xB5 <= cmd < 0xC5) or cmd == 0xCD:
                arg1 = self.file.rd_byte()
                if cmd == 0xBC:
                    transpose = sbyte_to_int(arg1)
                    self.log.debug(
                        f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | SET TRPS | {transpose:<#x}'
                    )
                elif cmd == 0xBD:
                    last_patch = arg1
                    self.log.debug(
                        f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | SET INST | {last_patch:<#x}'
                    )
                elif cmd in (0xBE, 0xBF, 0xC0, 0xC4, 0xCD):
                    last_cmd = cmd
                    self.log.debug(
                        f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | GET ATTR | {last_cmd:<#x}'
                    )
                evt_queue.add(cticks, cmd, arg1)
                self.log.debug(
                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | EVT PLAY | TIME: {cticks:<4} | CTRL: {cmd:<#4x} | ARG1: {arg1:<#4x} | ARG2: 0x00 | ARG3: 0x00'
                )
                pgm_ctr += 2
            elif 0xC4 < cmd < 0xCF:
                evt_queue.add(cticks, cmd)
                self.log.debug(
                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | EVT UNKN | TIME: {cticks:<4} | CTRL: {cmd:<#4x} | ARG1: 0x00 | ARG2: 0x00 | ARG3: 0x00'
                )
                pgm_ctr += 1
            elif cmd == 0xb9:
                arg1 = self.file.rd_byte()
                arg2 = self.file.rd_byte()
                arg3 = self.file.rd_byte()
                evt_queue.add(cticks, cmd, arg1, arg2, arg3)
                self.log.debug(
                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | EVT JUMP | TIME: {cticks:<4} | CTRL: {cmd:<#4x} | ARG1: {arg1:<#4x} | ARG2: {arg2:<#4x} | ARG3: {arg3:<#4x}'
                )
                pgm_ctr += 4
            elif cmd == 0xb4:
                if insub == 1:
                    self.log.debug(
                        f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | END SUB  |')
                    pgm_ctr = rpc  # pylint: disable=E0601
                    insub = 0
                else:
                    self.log.debug(
                        f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | RTN EXEC |')
                    pgm_ctr += 1
            elif cmd == 0xb3:
                self.log.debug(
                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | BGN SUB  |')
                rpc = pgm_ctr + 5
                insub = 1
                pgm_ctr = self.file.rd_gba_ptr()
            elif 0xCF <= cmd <= 0xFF:
                pgm_ctr += 1
                last_cmd = cmd

                g = False
                cmd_num = 0
                while not g:
                    self.file.rd_addr = pgm_ctr
                    arg1 = self.file.rd_byte()
                    if arg1 >= 0x80:
                        if cmd_num == 0:
                            patch = lln[cmd_num] + transpose
                            evt_queue.add(cticks, cmd, patch, llv[cmd_num],
                                          lla[cmd_num])
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | EVT NOTE | TIME: {cticks:<4} | CTRL: {cmd:<#4x} | ARG1: {patch:<#4x} | ARG2: {llv[cmd_num]:<#4x} | ARG3: {lla[cmd_num]:<#4x} | D:    {arg1:<#4x}'
                            )
                        g = True
                    else:
                        lln[cmd_num] = arg1
                        pgm_ctr += 1
                        arg2 = self.file.rd_byte()
                        if arg2 < 0x80:
                            llv[cmd_num] = arg2
                            pgm_ctr += 1
                            arg3 = self.file.rd_byte()
                            if arg3 >= 0x80:
                                arg3 = lla[cmd_num]
                                g = True
                            else:
                                lla[cmd_num] = arg3
                                pgm_ctr += 1
                                cmd_num += 1
                        else:
                            arg2 = llv[cmd_num]
                            arg3 = lla[cmd_num]
                            g = True
                        patch = arg1 + transpose
                        evt_queue.add(cticks, cmd, patch, arg2, arg3)
                        self.log.debug(
                            f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | EVT NOTE | TIME: {cticks:<4} | CTRL: {cmd:<#4x} | ARG1: {patch:<#4x} | ARG2: {arg2:<#4x} | ARG3: {arg3:<#4x} | D:    {arg1:<#4x}'
                        )
                    if self.patch_exists(last_patch) is False:
                        inst_head = rd_inst_head(1, table_ptr + last_patch * 12)
                        self.log.debug(
                            f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW PATCH | PREV: {last_patch:<#4x} | PNUM: {patch:<#4x} | HEAD: {inst_head}'
                        )

                        if inst_head.channel & 0x80 == 0x80:  # Drumkit
                            dct_table = rd_drmkit_head(1).dct_tbl
                            patch_addr = gba_ptr_to_addr(dct_table + patch * 12)
                            inst_head = rd_inst_head(1, patch_addr)
                            direct_head = rd_dct_head(1)
                            noise_head = rd_nse_head(1, patch_addr + 2)
                            self.drmkits.add(str(last_patch))
                            directs = self.drmkits[str(last_patch)].directs
                            directs.add(str(patch))
                            self.set_direct(self.drmkits[str(
                                last_patch)].directs[str(patch)], inst_head,
                                            direct_head, noise_head)
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | DCT TABLE  | {dct_table}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | INST HEAD  | {inst_head}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | DCT HEAD   | {direct_head}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | NOISE HEAD | {noise_head}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | NEW DRMKIT | {self.drmkits[str(last_patch)]}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | NEW DRMKIT | SET DIRECT | {directs[str(patch)]}'
                            )
                            if directs[str(patch)].output in out:
                                self.get_smp(directs[str(patch)], direct_head,
                                             samp_head, False)
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | GET SAMPLE | {directs[str(patch)]}'
                                )
                        elif inst_head.channel & 0x40 == 0x40:  # Multi
                            multi_head = rd_mul_head(1)
                            self.insts.add(str(last_patch))
                            kmaps = self.insts[str(last_patch)].kmaps
                            kmaps.add(0, str(patch))
                            kmaps[str(patch)].assign_dct = self.file.rd_byte(
                                VirtualFile.gba_ptr_to_addr(multi_head.kmap) +
                                patch)
                            cdr = kmaps[str(patch)].assign_dct
                            inst_head = rd_inst_head(
                                1,
                                VirtualFile.gba_ptr_to_addr(
                                    multi_head.dct_tbl + cdr * 12))
                            direct_head = rd_dct_head(1)
                            noise_head = rd_nse_head(
                                1,
                                VirtualFile.gba_ptr_to_addr(
                                    multi_head.dct_tbl + cdr * 12) + 2)
                            self.insts[str(last_patch)].directs.add(str(cdr))
                            self.set_direct(
                                self.insts[str(last_patch)].directs[str(cdr)],
                                inst_head, direct_head, noise_head)
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW MULTI | MULTI HEAD | {multi_head}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW MULTI | NEW INST   | {self.insts[str(last_patch)]}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW MULTI | NEW KEYMAP | {self.insts[str(last_patch)].kmaps.data}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW MULTI | SET ASNDCT | {self.insts[str(last_patch)].kmaps[str(patch)].assign_dct}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW MULTI | INST HEAD  | {inst_head}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW MULTI | DCT HEAD   | {direct_head}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW MULTI | NOISE HEAD | {noise_head}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW MULTI | SET DIRECT | {self.insts[str(last_patch)].directs[str(cdr)]}'
                            )
                            if self.insts[str(last_patch)].directs[str(
                                    cdr)].output in out:
                                self.get_smp(self.insts[str(
                                    last_patch)].directs[str(cdr)], direct_head,
                                             samp_head, False)
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW MULTI | GET SAMPLE | {self.insts[str(last_patch)].directs[str(cdr)]}'
                                )
                        else:  # Direct/GB Sample
                            direct_head = rd_dct_head(1)
                            noise_head = rd_nse_head(
                                1, table_ptr + last_patch * 12 + 2)
                            self.directs.add(str(last_patch))
                            self.set_direct(self.directs[str(last_patch)],
                                            inst_head, direct_head, noise_head)
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DCT   | DCT HEAD   | {direct_head}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DCT   | NOISE HEAD | {noise_head}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DCT   | SET DIRECT | {self.directs[str(last_patch)]}'
                            )
                            if self.directs[str(last_patch)].output in out:
                                self.get_smp(self.directs[str(last_patch)],
                                             direct_head, samp_head, True)
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DCT   | GET SAMPLE | {self.directs[str(last_patch)]}'
                                )
                    else:  # Patch exists
                        inst_head = rd_inst_head(1, table_ptr + last_patch * 12)
                        self.log.debug(
                            f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | PC.EXIST | PREV: {last_patch:<#4x} | PNUM: {patch:<#4x} | HEAD: {inst_head}'
                        )
                        if inst_head.channel & 0x80 == 0x80:
                            drum_head = rd_drmkit_head(1)
                            inst_head = rd_inst_head(
                                1,
                                VirtualFile.gba_ptr_to_addr(
                                    drum_head.dct_tbl + patch * 12))
                            direct_head = rd_dct_head(1)
                            noise_head = rd_nse_head(
                                1,
                                VirtualFile.gba_ptr_to_addr(
                                    drum_head.dct_tbl + patch * 12) + 2)
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | DM EXIST | DRM HEAD   | {drum_head}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | DM EXIST | INST HEAD  | {inst_head}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | DM EXIST | DCT HEAD   | {direct_head}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | DM EXIST | NOISE HEAD | {noise_head}'
                            )
                            if self.dct_exists(
                                    self.drmkits[str(last_patch)].directs,
                                    patch) is False:
                                self.drmkits[str(last_patch)].directs.add(
                                    str(patch))
                                self.set_direct(self.drmkits[str(
                                    last_patch)].directs[str(patch)], inst_head,
                                                direct_head, noise_head)
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | DM EXIST | NEW DIRECT | SET DIRECT | {self.drmkits[str(last_patch)].directs[str(patch)]}'
                                )
                                if self.drmkits[str(last_patch)].directs[str(
                                        patch)].output in out:
                                    self.get_mul_smp(self.drmkits[str(
                                        last_patch)].directs[str(patch)],
                                                     direct_head, samp_head,
                                                     False)
                                    self.log.debug(
                                        f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | DM EXIST | NEW DIRECT | GET SAMPLE | {self.drmkits[str(last_patch)].directs[str(patch)]}'
                                    )
                        elif inst_head.channel & 0x40 == 0x40:
                            multi_head = rd_mul_head(1)
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | ML EXIST | MULTI HEAD | {multi_head}'
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
                            inst_head = rd_inst_head(
                                1,
                                VirtualFile.gba_ptr_to_addr(
                                    multi_head.dct_tbl + cdr * 12))
                            direct_head = rd_dct_head(1)
                            noise_head = rd_nse_head(
                                1,
                                VirtualFile.gba_ptr_to_addr(
                                    multi_head.dct_tbl + cdr * 12) + 2)
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | {self.insts[str(last_patch)].kmaps[str(patch)]}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | SET CDR    | {cdr}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | INST HEAD  | {inst_head}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | DCT HEAD   | {direct_head}'
                            )
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | NSE HEAD   | {noise_head}'
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
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | ML EXIST | SET DIRECT | {self.insts[str(last_patch)].directs[str(cdr)]}'
                                )
                                if self.insts[str(last_patch)].directs[str(
                                        cdr)].output in out:
                                    self.get_mul_smp(self.insts[str(
                                        last_patch)].directs[str(cdr)],
                                                     direct_head, samp_head,
                                                     False)
                                    self.log.debug(
                                        f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | ML EXIST | GET SAMPLE | {self.insts[str(last_patch)].directs[str(cdr)]}'
                                    )

            elif 0x00 <= cmd < 0x80:
                if last_cmd < 0xCF:
                    evt_queue.add(cticks, last_cmd, cmd)
                    self.log.debug(
                        f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | PREV CMD | TIME: {cticks:<4} | CTRL: {last_cmd:<#4x} | ARG1: {cmd:<#4x} | ARG2: 0x00 | ARG3: 0x00 '
                    )
                    pgm_ctr += 1
                else:
                    cmd = last_cmd
                    g = False
                    cmd_num = 0
                    while g is False:
                        self.file.rd_addr = pgm_ctr
                        arg1 = self.file.rd_byte()
                        if arg1 >= 0x80:
                            if cmd_num == 0:
                                patch = lln[cmd_num] + transpose
                                evt_queue.add(cticks, cmd, patch, llv[cmd_num],
                                              lla[cmd_num])
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | PRV NOTE | TIME: {cticks:<4} | CTRL: {cmd:<#4x} | ARG1: {patch:<#4x} | ARG2: {llv[cmd_num]:<#4x} | ARG3: {lla[cmd_num]:<#4x} | D:    {arg1:<#4x}'
                                )
                            g = True
                        else:
                            lln[cmd_num] = arg1
                            pgm_ctr += 1
                            arg2 = self.file.rd_byte()
                            if arg2 < 0x80:
                                llv[cmd_num] = arg2
                                pgm_ctr += 1
                                arg3 = self.file.rd_byte()
                                if arg3 >= 0x80:
                                    arg3 = lla[cmd_num]
                                    g = True
                                else:
                                    lla[cmd_num] = arg3
                                    pgm_ctr += 1
                                    cmd_num += 1
                            else:
                                arg2 = llv[cmd_num]
                                arg3 = lla[cmd_num]
                                g = True
                            patch = arg1 + transpose
                            evt_queue.add(cticks, cmd, patch, arg2, arg3)
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | PRV NOTE | TIME: {cticks:<4} | CTRL: {cmd:<#4x} | ARG1: {patch:<#4x} | ARG2: {arg2:<#4x} | ARG3: {arg3:<#4x} | D:    {arg1:<#4x}'
                            )
                        if self.patch_exists(last_patch) is False:
                            inst_head = rd_inst_head(
                                1, table_ptr + last_patch * 12)
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | PV PATCH | PREV: {last_patch:<#4x} | PNUM: {patch:<#4x} | CHAN: {inst_head.channel:<#4x}'
                            )
                            if inst_head.channel & 0x80 == 0x80:
                                drum_head = rd_drmkit_head(1)
                                inst_head = rd_inst_head(
                                    1,
                                    VirtualFile.gba_ptr_to_addr(
                                        drum_head.dct_tbl + patch * 12))
                                direct_head = rd_dct_head(1)
                                noise_head = rd_nse_head(
                                    1,
                                    VirtualFile.gba_ptr_to_addr(
                                        drum_head.dct_tbl + patch * 12) + 2)
                                self.drmkits.add(str(last_patch))
                                self.drmkits[str(last_patch)].directs.add(
                                    str(patch))
                                self.set_direct(self.drmkits[str(
                                    last_patch)].directs[str(patch)], inst_head,
                                                direct_head, noise_head)
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | DRM HEAD   | {drum_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | INST HEAD  | {inst_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | DCT HEAD   | {direct_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | NOISE HEAD | {noise_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | NEW DRMKIT | {self.drmkits[str(last_patch)]}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | NEW DRMKIT | SET DIRECT | {self.drmkits[str(last_patch)].directs[str(patch)]}'
                                )
                                if self.drmkits[str(last_patch)].directs[str(
                                        patch)].output in out:
                                    self.get_smp(self.drmkits[str(
                                        last_patch)].directs[str(patch)],
                                                 direct_head, samp_head, True)
                                    self.log.debug(
                                        f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | GET SAMPLE | {self.drmkits[str(last_patch)].directs[str(patch)]}'
                                    )
                            elif inst_head.channel & 0x40 == 0x40:
                                multi_head = rd_mul_head(1)
                                self.insts.add(str(last_patch))
                                self.insts[str(last_patch)].kmaps.add(
                                    self.file.rd_byte(
                                        VirtualFile.gba_ptr_to_addr(
                                            multi_head.kmap) + patch),
                                    str(patch))
                                cdr = self.insts[str(last_patch)].kmaps[str(
                                    patch)].assign_dct
                                inst_head = rd_inst_head(
                                    1,
                                    VirtualFile.gba_ptr_to_addr(
                                        multi_head.dct_tbl + cdr * 12))
                                direct_head = rd_dct_head(1)
                                noise_head = rd_nse_head(
                                    1,
                                    VirtualFile.gba_ptr_to_addr(
                                        multi_head.dct_tbl + cdr * 12) + 2)
                                self.insts[str(last_patch)].directs.add(
                                    str(cdr))
                                self.set_direct(self.insts[str(
                                    last_patch)].directs[str(cdr)], inst_head,
                                                direct_head, noise_head)
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW MULTI | MULTI HEAD | {multi_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW MULTI | NEW INST   | {self.insts[str(last_patch)]}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW MULTI | NEW KEYMAP | {self.insts[str(last_patch)].kmaps}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW MULTI | SET ASNDCT | {cdr}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW MULTI | INST HEAD  | {inst_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW MULTI | DCT HEAD   | {direct_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW MULTI | NOISE HEAD | {noise_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW MULTI | SET DIRECT | {self.insts[str(last_patch)].directs[str(cdr)]}'
                                )
                                if self.insts[str(last_patch)].directs[str(
                                        cdr)].output in out:
                                    self.get_smp(self.insts[str(
                                        last_patch)].directs[str(cdr)],
                                                 direct_head, samp_head, False)
                                    self.log.debug(
                                        f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | NW DRUM  | GET SAMPLE | {self.insts[str(last_patch)].directs[str(cdr)]}'
                                    )
                            else:
                                direct_head = rd_dct_head(1)
                                noise_head = rd_nse_head(
                                    1, table_ptr + last_patch * 12 + 2)
                                self.directs.add(str(last_patch))
                                if self.directs[str(last_patch)].output in out:
                                    self.get_mul_smp(
                                        self.directs[str(last_patch)],
                                        direct_head, samp_head, False)
                        else:
                            inst_head = rd_inst_head(
                                1, table_ptr + last_patch * 12)
                            self.log.debug(
                                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | PC EXIST | PREV: {last_patch:<#4x} | PNUM: {patch:<#4x} | HEAD: {inst_head}'
                            )
                            if inst_head.channel & 0x80 == 0x80:
                                drum_head = rd_drmkit_head(1)
                                inst_head = rd_inst_head(
                                    1,
                                    VirtualFile.gba_ptr_to_addr(
                                        drum_head.dct_tbl + patch * 12))
                                direct_head = rd_dct_head(1)
                                noise_head = rd_nse_head(
                                    1,
                                    VirtualFile.gba_ptr_to_addr(
                                        drum_head.dct_tbl + patch * 12) + 2)
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | DM EXIST | DRM HEAD   | {drum_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | DM EXIST | INST HEAD  | {inst_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | DM EXIST | DCT HEAD   | {direct_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | DM EXIST | NOISE HEAD | {noise_head}'
                                )
                                if self.dct_exists(
                                        self.drmkits[str(last_patch)].directs,
                                        patch) is False:
                                    self.drmkits[str(last_patch)].directs.add(
                                        str(patch))
                                    self.set_direct(self.drmkits[str(
                                        last_patch)].directs[str(patch)],
                                                    inst_head, direct_head,
                                                    noise_head)
                                    self.log.debug(
                                        f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | DM EXIST | NEW DIRECT | SET DIRECT | {self.drmkits[str(last_patch)].directs[str(patch)]}'
                                    )
                                    if self.drmkits[str(last_patch)].directs[
                                            str(patch)].output in out:
                                        self.get_mul_smp(
                                            self.drmkits[str(last_patch)]
                                            .directs[str(patch)], direct_head,
                                            samp_head, False)
                                        self.log.debug(
                                            f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | DM EXIST | NEW DIRECT | GET SAMPLE | {self.drmkits[str(last_patch)].directs[str(patch)]}'
                                        )
                            elif inst_head.channel & 0x40 == 0x40:
                                multi_head = rd_mul_head(1)
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | ML EXIST | MULTI HEAD | {multi_head}'
                                )
                                if self.kmap_exists(
                                        self.insts[str(last_patch)].kmaps,
                                        patch) is False:
                                    self.insts[str(last_patch)].kmaps.add(
                                        self.file.rd_byte(
                                            VirtualFile.gba_ptr_to_addr(
                                                multi_head.kmap) + patch),
                                        str(patch))
                                cdr = self.insts[str(last_patch)].kmaps[str(
                                    patch)].assign_dct
                                inst_head = rd_inst_head(
                                    1,
                                    VirtualFile.gba_ptr_to_addr(
                                        multi_head.dct_tbl + cdr * 12))
                                direct_head = rd_dct_head(1)
                                noise_head = rd_nse_head(
                                    1,
                                    VirtualFile.gba_ptr_to_addr(
                                        multi_head.dct_tbl + cdr * 12) + 2)
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | {self.insts[str(last_patch)].kmaps[str(patch)]}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | SET CDR    | {cdr}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | INST HEAD  | {inst_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | DCT HEAD   | {direct_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | ML EXIST | NEW KEYMAP | NSE HEAD   | {noise_head}'
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
                                        f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | ML EXIST | SET DIRECT | {self.insts[str(last_patch)].directs[str(cdr)]}'
                                    )
                                    if self.insts[str(last_patch)].directs[str(
                                            cdr)].output in out:
                                        self.get_mul_smp(
                                            self.insts[str(last_patch)].directs[
                                                str(cdr)], direct_head,
                                            samp_head, False)
                                        self.log.debug(
                                            f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | ML EXIST | GET SAMPLE | {self.insts[str(last_patch)].directs[str(cdr)]}'
                                        )
            elif 0x80 <= cmd <= 0xB0:
                evt_queue.add(cticks, cmd)
                self.log.debug(
                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | EVT WAIT | TIME: {cticks:<4} | CTRL: {cmd:<#4x} | ARG1: 0x00 | ARG2: 0x00 | ARG3: 0x00 | TIME: {stlen_to_ticks(cmd - 0x80):<#4x}'
                )
                cticks += stlen_to_ticks(cmd - 0x80)
                pgm_ctr += 1
            if cmd in (0xB1, 0xB2, 0xB6):
                self.log.debug(
                    f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | END EVT  |')
                #evt_queue.add(cticks, c)
                break
            self.log.debug(
                f'| PGM: {pgm_ctr:#x} | CMD: {cmd:#x} | EVT END  | TIME: {cticks:<4x} | CTRL: {cmd:<#4x} | ARG1: 0x00 | ARG2: 0x00 | ARG3: 0x00'
            )
        evt_queue.add(cticks, cmd)

    def load_directsound(self, fpath: str) -> None:
        for smp in self.smp_pool:
            smp: Sample
            if smp.gb_wave is True:
                if self.val(smp.smp_data) == 0:
                    with open_new_file('temp.raw', 2) as f:
                        f.wr_str(smp.smp_data)
                    smp.fmod_smp = self.load_sample('temp.raw')
                    remove('temp.raw')
                else:
                    smp.fmod_smp = self.load_sample(fpath, smp.smp_data,
                                                    smp.size)
                self.log.debug(
                    f'| FMOD | CODE: {getError():4} | LOAD SMP   | S{smp.fmod_smp} | SIZE: {smp.size} |'
                )
                setLoopPoints(smp.fmod_smp, 0, 31)
                self.log.debug(
                    f'| FMOD | CODE: {getError():4} | SET LOOP   | 0-31')
                continue

            if self.val(smp.smp_data) == 0:
                with open_new_file('temp.raw', 2) as f:
                    f.wr_str(smp.smp_data)
                smp.fmod_smp = self.load_sample(
                    'temp.raw', loop=smp.loop, gb_wave=False)
                remove('temp.raw')
            else:
                smp.fmod_smp = self.load_sample(fpath, smp.smp_data, smp.size,
                                                smp.loop, False)
            self.log.debug(
                f'| FMOD | CODE: {getError():4} | LOAD SMP   | S{smp.fmod_smp} | SIZE: {smp.size} |'
            )
            setLoopPoints(smp.fmod_smp, smp.loop_start, smp.size - 1)
            self.log.debug(
                f'| FMOD | CODE: {getError():4} | SET LOOP   | {smp.loop_start}-{smp.size - 1}'
            )

    def load_square(self) -> None:
        high = chr(int(0x80 + 0x7F * self.GB_SQ_MULTI))
        low = chr(int(0x80 - 0x7F * self.GB_SQ_MULTI))
        for mx2 in range(4):
            sq = f'square{mx2}'
            f_sq = f'{sq}.raw'
            self.smp_pool.add(sq)
            sample = self.smp_pool[sq]
            if mx2 == 3:
                l = [high] * 24
                r = [low] * 8
                sample.smp_data = "".join(l + r)
            else:
                l = [high] * (2**(mx2 + 2))
                r = [low] * (32 - 2**(mx2 + 2))
                sample.smp_data = "".join(l + r)
            sample.freq = 7040
            sample.size = 32
            with open_new_file(f_sq, 2) as f:
                f.wr_str(sample.smp_data)

            sample.fmod_smp = self.load_sample(f_sq, 0, 0)
            self.log.debug(
                f'| FMOD | CODE: {getError():4} | LOAD SQRE{mx2} | S{sample.fmod_smp}'
            )
            setLoopPoints(sample.fmod_smp, 0, 31)
            self.log.debug(
                f'| FMOD | CODE: {getError():4} | SET LOOP   | (00, 31)')
            remove(f_sq)

    def load_noise(self) -> None:
        for i in range(10):
            nse = f'noise0{i}'
            self.smp_pool.add(nse)
            f_nse = f'{nse}.raw'
            with self.smp_pool[nse] as smp:
                smp.smp_data = self.nse_wavs[0][i]
                smp.freq = 7040
                smp.size = 16384
                with open_new_file(f_nse, 2) as f:
                    f.wr_str(smp.smp_data)
                smp.fmod_smp = self.load_sample(f_nse)
                self.log.debug(
                    f'| FMOD | CODE: {getError():4} | LOAD NSE0{i} | S{smp.fmod_smp}'
                )
                setLoopPoints(smp.fmod_smp, 0, 16383)
                self.log.debug(
                    f'| FMOD | CODE: {getError():4} | SET LOOP   | (0, 16383)')
                remove(f_nse)

            nse = f'noise1{i}'
            self.smp_pool.add(nse)
            f_nse = f'{nse}.raw'
            with self.smp_pool[nse] as smp:
                smp.smp_data = self.nse_wavs[1][i]
                smp.freq = 7040
                smp.size = 256
                with open_new_file(f_nse, 2) as f:
                    f.wr_str(smp.smp_data)
                smp.fmod_smp = self.load_sample(f_nse)
                self.log.debug(
                    f'| FMOD | CODE: {getError():4} | LOAD NSE1{i} | S{smp.fmod_smp}'
                )
                setLoopPoints(smp.fmod_smp, 0, 255)
                self.log.debug(
                    f'| FMOD | CODE: {getError():4} | SET LOOP   | (0, 255)')
                remove(f_nse)

    def init_player(self, fpath: str) -> None:
        setOutput(1)
        systemInit(44100, 64, 0)
        self.log.debug(f'| FMOD | CODE: {getError():4} | INIT       |')
        setMasterVolume(self.gbl_vol)
        self.log.debug(
            f'| FMOD | CODE: {getError():4} | SET VOL    | {self.gbl_vol}')

        self.load_directsound(fpath)
        self.load_noise()
        self.load_square()

        self.file.close()
        self.log.debug(f'| FMOD | CODE: {getError():4} | FINISH     |')

    def load_song(self, fpath: str, sng_num: int, sng_list_ptr: int = None):
        """Load a song from ROM into memory.

        Loads all samples within the song's voice table and assigns them to
        instruments. Subsequently loads all events commands the Sappy engine
        uses into an event queue for playback processing. Is repeatable.
        """

        self.reset_player()

        self.file = open_file(fpath, 1)
        header_ptr = self.file.rd_gba_ptr(sng_list_ptr + sng_num * 8)
        num_tracks = self.file.rd_byte(header_ptr)
        unk = self.file.rd_byte()
        priority = self.file.rd_byte()
        echo = self.file.rd_byte()
        #print(echo)
        inst_table_ptr = self.file.rd_gba_ptr()

        self.channels = ChannelQueue([Channel() for i in range(num_tracks)])
        for track_num, channel in enumerate(self.channels):
            self.load_events(channel, header_ptr, inst_table_ptr, track_num)

        self.init_player(fpath)

    def load_sample(self,
                    fpath: str,
                    offset: Union[int, str] = 0,
                    size: int = 0,
                    loop: bool = True,
                    gb_wave: bool = True):
        mode = FSoundModes._8BITS + FSoundModes.LOADRAW + FSoundModes.MONO
        if loop:
            mode += FSoundModes.LOOP_NORMAL
        if gb_wave:
            mode += FSoundModes.UNSIGNED
        else:
            mode += FSoundModes.SIGNED
        fpath = fpath.encode('ascii')
        index = FSoundChannelSampleMode.FREE
        return sampleLoad(index, fpath, mode, offset, size)

    def smp_exists(self, smp_id: int) -> bool:
        """Check if a sample exists in the available sample pool."""
        for smp in self.smp_pool:
            if smp.key == str(smp_id):
                return True
        return False

    def stop_song(self):
        """Stop playing a song."""
        try:
            VirtualFile.from_id(1).close()
        except AttributeError:
            pass
        systemClose()

    def update_notes(self) -> None:
        for item in self.note_arr:
            item: Note
            if item.enable and item.wait_ticks > 0:
                item.wait_ticks -= 1
            if item.wait_ticks <= 0 and item.enable is True and item.note_off is False:
                if self.channels[item.parent].sustain is False:
                    item.reset()
                    if item.note_num in self.channels[item.parent].playing:
                        self.channels[item.parent].playing.remove(item.note_num)

    def update_channels(self) -> None:
        in_for = True
        for plat, chan in enumerate(self.channels):
            if chan.enable is False:
                self.log.debug(f'| CHAN: {plat:>4} | SKIP EXEC  |')
                continue
            if chan.wait_ticks > 0:
                chan.wait_ticks -= 1
            while chan.wait_ticks <= 0:
                evt_queue: Event = chan.evt_queue[chan.pgm_ctr]
                cmd_byte = evt_queue.cmd_byte
                args = evt_queue.arg1, evt_queue.arg2, evt_queue.arg3

                if cmd_byte in (0xB1, 0xB6):
                    chan.enable = False
                    chan.sustain = False
                    in_for = False
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | STOP EXEC  |'
                    )
                    return
                elif cmd_byte == 0xB9:
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | COND JUMP  |'
                    )
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xBA:
                    chan.priority = args[0]
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xBB:
                    self.tempo = args[0] * 2
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET TEMPO  | TEMPO: {self.tempo:3}'
                    )
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xBC:
                    chan.transpose = sbyte_to_int(args[0])
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET TRNPSE | TRNPSE: {chan.transpose:2}'
                    )
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xBD:
                    chan.patch_num = args[0]
                    if self.dct_exists(self.directs, chan.patch_num):
                        chan.output = self.directs[str(chan.patch_num)].output
                    elif self.inst_exists(chan.patch_num):
                        chan.output = ChannelTypes.MUL_SMP
                    elif self.drm_exists(chan.patch_num):
                        chan.output = ChannelTypes.DRUMKIT
                    else:
                        chan.output = ChannelTypes.NULL
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET OUTPUT | PATCH: {chan.patch_num:3} | T: {chan.output.name:>7}'
                    )
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xBE:
                    chan.main_vol = args[0]
                    for nid in chan.notes:
                        note: Note = self.note_arr[nid.note_id]
                        if not note.enable or note.parent != plat:
                            continue
                        iv = note.velocity / 0x7F
                        cv = chan.main_vol / 0x7F
                        ie = note.env_pos / 0xFF
                        dav = iv * cv * ie * 255
                        vol = 0 if chan.mute else int(dav)
                        chan.volume = vol
                        setVolume(note.fmod_channel, vol)
                        self.log.debug(
                            f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | CODE: {getError():4} | SET VOLUME | FMOD: {note.fmod_channel:4} | NOTE: {nid.note_id:>4} | VOL: {chan.main_vol:5} | DAV: {dav:5}'
                        )
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xBF:
                    chan.panning = args[0]
                    pan = chan.panning * 2
                    for nid in chan.notes:
                        note = self.note_arr[nid.note_id]
                        if not note.enable or note.parent != plat:
                            continue
                        setPan(note.fmod_channel, pan)
                        self.log.debug(
                            f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | CODE: {getError():4} | SET PAN    | FMOD: {note.fmod_channel:4} | NOTE: {nid.note_id:>4} | PAN: {chan.panning:5} | DAP: {pan:5}'
                        )
                    chan.pgm_ctr += 1
                elif cmd_byte in (0xC0, 0xC1):
                    if cmd_byte == 0xC0:
                        chan.pitch_bend = args[0]
                    else:
                        chan.pitch_range = sbyte_to_int(args[0])
                    chan.pgm_ctr += 1
                    for nid in chan.notes:
                        note: Note = self.note_arr[nid.note_id]
                        if not note.enable or note.parent != plat:
                            continue
                        pitch = (
                            chan.pitch_bend - 0x40) / 0x40 * chan.pitch_range
                        freq = int(note.freq * math.pow(BASE, pitch))
                        setFrequency(note.fmod_channel, freq)
                        self.log.debug(
                            f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | PBEND      | CODE: {getError():4} | FMOD: {note.fmod_channel:4} | NOTE: {nid.note_id:>4} | BEND: {chan.pitch_bend:4} | DAP: {freq:5}'
                        )
                elif cmd_byte == 0xC2:
                    chan.vib_rate = chan.evt_queue[chan.pgm_ctr].arg1
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET VIBDP  | DEPTH: {chan.vib_rate:3}'
                    )
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xC4:
                    chan.vib_depth = chan.evt_queue[chan.pgm_ctr].arg1
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET VIBRT  | RATE: {chan.vib_depth:4}'
                    )
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xCE:
                    chan.sustain = False
                    for nid in chan.notes:
                        note: Note = self.note_arr[nid.note_id]
                        if not note.enable or note.note_off or note.wait_ticks > -1:
                            continue
                        note.reset()
                        if note.note_num in chan.playing:
                            chan.playing.remove(note.note_num)
                        self.log.debug(
                            f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#6x} | CTRL: {cmd_byte:<#4x} | NOTE OFF   | NOTE: {nid.note_id:>4}'
                        )
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | NOTE OFF   | '
                    )
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xB3:
                    chan.sub_ctr += 1
                    chan.rtn_ptr += 1
                    chan.pgm_ctr = chan.subs[chan.sub_ctr].evt_q_ptr
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | CALL SUB   | RTN: {chan.rtn_ptr:<#5x}'
                    )
                    chan.in_sub = True
                elif cmd_byte == 0xB4:
                    if chan.in_sub:
                        chan.pgm_ctr = chan.rtn_ptr
                        chan.in_sub = False
                        self.log.debug(
                            f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | END SUB    |'
                        )
                    else:
                        chan.pgm_ctr += 1
                elif cmd_byte == 0xB2:
                    self.looped = True
                    chan.in_sub = False
                    chan.pgm_ctr = chan.loop_ptr
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | JUMP ADDR  | PTR: {chan.loop_ptr:<#5x}'
                    )
                elif cmd_byte >= 0xCF:
                    ll = stlen_to_ticks(cmd_byte - 0xCF) + 1
                    if cmd_byte == 0xCF:
                        chan.sustain = True
                        ll = -1
                    nn, vv, uu = args
                    self.note_q.add(nn, vv, plat, uu, ll, chan.patch_num)
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | ADD NOTE   | NOTE: {note_to_name(nn):>4} | VEL: {vv:5} | LEN: {ll:5} | PATCH: {chan.patch_num:3}'
                    )
                    chan.pgm_ctr += 1
                elif cmd_byte <= 0xB0:
                    if self.looped:
                        self.looped = False
                        chan.wait_ticks = 0
                        continue
                    chan.pgm_ctr += 1
                    n_evt_queue = chan.evt_queue[chan.pgm_ctr]
                    if chan.pgm_ctr > 0:
                        chan.wait_ticks = n_evt_queue.ticks - evt_queue.ticks
                    else:
                        chan.wait_ticks = n_evt_queue.ticks
                else:
                    #print(hex(cmd_byte))
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | CONT EXEC  |'
                    )
                    chan.pgm_ctr += 1
            if not in_for:
                self.log.debug(f'| CHAN: {plat:>4} | STOP EXEC  | ')
                break

    def update_vibrato(self) -> None:
        for chan in self.channels:
            if not chan.enable or chan.vib_rate == 0 or chan.vib_depth == 0:
                continue
            for nid in chan.notes:
                item = self.note_arr[nid.note_id]
                if not item.enable or item.note_off:
                    continue
                v_pos = math.sin(math.pi * item.vib_pos) * chan.vib_depth
                pitch = (
                    chan.pitch_bend - 0x40 + v_pos) / 0x40 * chan.pitch_range
                freq = int(item.freq * math.pow(BASE, pitch))
                setFrequency(item.fmod_channel, freq)
                item.vib_pos += 1 / (96 / chan.vib_rate)
                item.vib_pos = math.fmod(item.vib_pos, 2)

    def play_notes(self) -> None:
        cleared_channel = [False for i in range(len(self.channels))]
        for item in self.note_q:
            x = self.free_note()
            self.log.debug(
                f'| FREE NOTE  | NOTE: {x:4} | ID: {note_to_name(item.note_num):>6} |'
            )
            if x == 255:
                continue

            self.note_arr[x] = item
            with self.channels[item.parent] as chan:
                if cleared_channel[item.parent] is False:
                    cleared_channel[item.parent] = True

                    for nid in chan.notes:
                        note = self.note_arr[nid.note_id]
                        if note.enable is True and note.note_off is False:
                            if note.wait_ticks == -1:
                                if not chan.sustain:
                                    note.reset()
                            else:
                                if chan.sustain:
                                    note.reset()
                            self.log.debug(
                                f'| CHAN: {item.parent:>4} | NOTE: {nid.note_id:4} | NOTE OFF   |'
                            )

                chan.notes.add(x, str(x))
                if self.note_arr[x].note_num not in chan.playing:
                    chan.playing.append(self.note_arr[x].note_num)
                pat = item.patch_num
                nn = item.note_num
                std_out = (DirectTypes.DIRECT, DirectTypes.WAVE)
                sqr_out = (DirectTypes.SQUARE1, DirectTypes.SQUARE2)
                if self.dct_exists(self.directs, pat):
                    self.note_arr[x].output = self.directs[str(pat)].output
                    self.note_arr[x].env_attn = self.directs[str(pat)].env_attn
                    self.note_arr[x].env_dcy = self.directs[str(pat)].env_dcy
                    self.note_arr[x].env_sus = self.directs[str(pat)].env_sus
                    self.note_arr[x].env_rel = self.directs[str(pat)].env_rel
                    self.log.debug(
                        f'| CHAN: {item.parent:>4} | DCT EXISTS | NOTE: {x:4} | T: {self.note_arr[x].output:>7} | ATTN: {self.note_arr[x].env_attn:4} | DCY: {self.note_arr[x].env_dcy:5} | SUS: {self.note_arr[x].env_sus:5} | REL: {self.note_arr[x].env_rel:5}'
                    )
                    if DirectTypes(self.directs[str(pat)].output) in std_out:
                        das = str(self.directs[str(pat)].smp_id)
                        #input()
                        daf = note_to_freq(
                            nn + (60 - self.directs[str(pat)].drum_key),
                            self.smp_pool[das].freq)
                        if self.smp_pool[das].gb_wave:
                            daf /= 2
                        self.log.debug(
                            f'| CHAN: {item.parent:>4} | DCT EXISTS | NOTE: {x:4} | STD OUT    | GB: {self.smp_pool[das].gb_wave:6} | DAS: {das:>18} | DAF: {daf:>18}'
                        )
                    elif DirectTypes(self.directs[str(pat)].output) in sqr_out:
                        das = f'square{self.directs[str(pat)].gb1 % 4}'
                        daf = note_to_freq(
                            nn + (60 - self.directs[str(pat)].drum_key))
                    elif DirectTypes(self.directs[str(pat)]
                                     .output) == DirectTypes.NOISE:
                        das = f'noise{self.directs[str(pat)].gb1 % 2}{int(random() * 3)}'
                        daf = note_to_freq(
                            nn + (60 - self.directs[str(pat)].drum_key))
                    else:
                        das = ''
                elif self.inst_exists(pat):
                    dct: Direct = self.insts[str(pat)].directs[str(
                        self.insts[str(pat)].kmaps[str(nn)].assign_dct)]
                    self.note_arr[x].output = dct.output
                    self.note_arr[x].env_attn = dct.env_attn
                    self.note_arr[x].env_dcy = dct.env_dcy
                    self.note_arr[x].env_sus = dct.env_sus
                    self.note_arr[x].env_rel = dct.env_rel
                    self.log.debug(
                        f'| CHAN: {item.parent:>4} | INST EXIST | NOTE: {x:4} | T: {self.note_arr[x].output:>7} | ATTN: {self.note_arr[x].env_attn:4} | DCY: {self.note_arr[x].env_dcy:5} | SUS: {self.note_arr[x].env_sus:5} | REL: {self.note_arr[x].env_rel:5}'
                    )
                    if dct.output in std_out:
                        das = str(dct.smp_id)
                        if dct.fix_pitch:
                            daf = self.smp_pool[das].freq
                        else:
                            daf = note_to_freq(nn, -2
                                               if self.smp_pool[das].gb_wave
                                               else self.smp_pool[das].freq)
                        self.log.debug(
                            f'| CHAN: {item.parent:>4} | INST EXIST | NOTE: {x:4} | STD OUT    | FIX: {dct.fix_pitch:5} | DAS: {das:>18} | DAF: {daf:>18}'
                        )
                    elif dct.output in sqr_out:
                        das = f'square{dct.gb1 % 4}'
                        daf = note_to_freq(nn)
                    else:
                        das = ''
                elif self.drm_exists(pat):
                    dct: Direct = self.drmkits[str(pat)].directs[str(nn)]
                    self.note_arr[x].output = dct.output
                    self.note_arr[x].env_attn = dct.env_attn
                    self.note_arr[x].env_dcy = dct.env_dcy
                    self.note_arr[x].env_sus = dct.env_sus
                    self.note_arr[x].env_rel = dct.env_rel
                    self.log.debug(
                        f'| CHAN: {item.parent:>4} | DRM EXISTS | NOTE: {x:4} | T: {self.note_arr[x].output:>7} | ATTN: {self.note_arr[x].env_attn:4} | DCY: {self.note_arr[x].env_dcy:5} | SUS: {self.note_arr[x].env_sus:5} | REL: {self.note_arr[x].env_rel:5}'
                    )
                    if dct.output in std_out:
                        das = str(dct.smp_id)
                        if dct.fix_pitch and not self.smp_pool[das].gb_wave:
                            daf = self.smp_pool[das].freq
                        else:
                            daf = note_to_freq(dct.drum_key, -2
                                               if self.smp_pool[das].gb_wave
                                               else self.smp_pool[das].freq)
                        self.log.debug(
                            f'| CHAN: {item.parent:>4} | DRM EXISTS | NOTE: {x:4} | STD OUT    | FIX: {dct.fix_pitch:5} | GB: {self.smp_pool[das].gb_wave:6} | DAS: {das:>18} | DAF: {daf:>18}'
                        )
                    elif dct.output in sqr_out:
                        das = f'square{dct.gb1 % 4}'
                        daf = note_to_freq(dct.drum_key)
                    elif dct.output == DirectTypes.NOISE:
                        das = f'noise{dct.gb1 % 2}{int(random() * 10)}'
                        daf = note_to_freq(dct.drum_key)
                    else:
                        das = ''
                else:
                    das = ''

                if not das:
                    return
                daf = daf * math.pow(BASE, self.transpose)
                dav = (item.velocity / 0x7F) * (chan.main_vol / 0x7F) * 255
                out_type = self.note_arr[x].output
                if out_type == NoteTypes.SQUARE1:
                    if self.gb1_chan < 32:
                        with self.note_arr[self.gb1_chan] as gbn:
                            gbn: Note
                            stopSound(gbn.fmod_channel)
                            self.log.debug(
                                f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | STOP SQ1   | F{gbn.fmod_channel:<9}'
                            )
                            gbn.fmod_channel = 0
                            self.channels[gbn.parent].notes.remove(
                                str(self.gb1_chan))
                            gbn.enable = False

                    self.gb1_chan = x
                elif out_type == NoteTypes.SQUARE2:
                    if self.gb2_chan < 32:
                        with self.note_arr[self.gb2_chan] as gbn:
                            stopSound(gbn.fmod_channel)
                            self.log.debug(
                                f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | STOP SQ2   | F{gbn.fmod_channel:<9}'
                            )
                            gbn.fmod_channel = 0
                            self.channels[gbn.parent].notes.remove(
                                str(self.gb2_chan))
                            gbn.enable = False
                    self.gb2_chan = x
                elif out_type == NoteTypes.WAVE:
                    if self.gb3_chan < 32:
                        with self.note_arr[self.gb3_chan] as gbn:
                            stopSound(gbn.fmod_channel)
                            self.log.debug(
                                f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | STOP WAV   | F{gbn.fmod_channel:<9}'
                            )
                            gbn.fmod_channel = 0
                            self.channels[gbn.parent].notes.remove(
                                str(self.gb3_chan))
                            gbn.enable = False
                    self.gb3_chan = x
                elif out_type == NoteTypes.NOISE:
                    if self.gb4_chan < 32:
                        with self.note_arr[self.gb4_chan] as gbn:
                            stopSound(gbn.fmod_channel)
                            self.log.debug(
                                f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | STOP NSE   | F{gbn.fmod_channel:<9}'
                            )
                            gbn.fmod_channel = 0
                            self.channels[gbn.parent].notes.remove(
                                str(self.gb4_chan))
                            gbn.enable = False
                    self.gb4_chan = x

                pitch = (chan.pitch_bend - 0x40) / 0x40 * chan.pitch_range
                freq = int(daf * math.pow(BASE, pitch))
                pan = chan.panning * 2
                vol = 0 if chan.mute else int(dav)
                chan.volume = vol
                self.note_arr[x]: Note
                self.note_arr[x].freq = daf
                self.note_arr[x].phase = NotePhases.INITIAL
                if self.note_arr[x].output == NoteTypes.NOISE:
                    continue

                self.note_arr[x].fmod_channel = playSound(
                    x, self.smp_pool[das].fmod_smp, None, True)

                self.note_arr[x].fmod_fx = enableFX(
                    self.note_arr[x].fmod_channel, 3)
                setEcho(self.note_arr[x].fmod_fx, 0, 0, 333, 333, False)
                setFrequency(self.note_arr[x].fmod_channel, freq)
                setVolume(self.note_arr[x].fmod_channel, vol)
                setPan(self.note_arr[x].fmod_channel, pan)
                setPaused(self.note_arr[x].fmod_channel, False)
                assert getError() == 0
                self.log.debug(
                    f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | PLAY SOUND | F{self.note_arr[x].fmod_channel:<9} | DAS: {das:<5}'
                )
                self.log.debug(
                    f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | SET FREQ   | DAF: {daf:>5}'
                )
                self.log.debug(
                    f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | SET VOLUME | VOL: {vol:>5}'
                )
                self.log.debug(
                    f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | SET PAN    | PAN: {pan:>5}'
                )
        self.note_q.clear()

    def advance_notes(self) -> None:
        for i in range(31, -1, -1):
            item = self.note_arr[i]
            if item.enable is False:
                continue
            if item.output == NoteTypes.DIRECT:
                if item.note_off and item.phase < NotePhases.RELEASE:
                    item.env_step = 0
                    item.phase = NotePhases.RELEASE
                if item.env_step == 0 or (item.env_pos == item.env_dest) or (
                        item.env_step == 0 and
                    (item.env_pos <= item.env_dest)) or (
                        item.env_step >= 0 and item.env_pos >= item.env_dest):
                    phase = item.phase
                    if phase == NotePhases.INITIAL:
                        item.phase = NotePhases.ATTACK
                        item.env_pos = 0
                        item.env_dest = 255
                        item.env_step = item.env_attn
                    elif phase == NotePhases.ATTACK:
                        item.phase = NotePhases.DECAY
                        item.env_dest = item.env_sus
                        item.env_step = (item.env_dcy - 0x100) / 2
                    elif phase == NotePhases.DECAY:
                        item.phase = NotePhases.SUSTAIN
                        item.env_step = 0
                    elif phase == NotePhases.SUSTAIN:
                        item.phase = NotePhases.SUSTAIN
                        item.env_step = 0
                    elif phase == NotePhases.RELEASE:
                        item.phase = NotePhases.NOTEOFF
                        item.env_dest = 0
                        item.env_step = item.env_rel - 0x100
                    elif phase == NotePhases.NOTEOFF:
                        stopSound(item.fmod_channel)
                        disableFX(item.fmod_channel)
                        self.log.debug(
                            f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | STOP DSMP  | F{item.fmod_channel:<9}'
                        )
                        item.fmod_channel = 0
                        self.channels[item.parent].notes.remove(str(i))
                        item.enable = False
                nex = item.env_pos + item.env_step
                if nex > item.env_dest and item.env_step > 0:
                    nex = item.env_dest
                if nex < item.env_dest and item.env_step < 0:
                    nex = item.env_dest
                item.env_pos = nex
                dav = (item.velocity / 0x7F) * (
                    self.channels[item.parent].main_vol / 0x7F) * (
                        item.env_pos / 0xFF) * 255
                vol = int(0 if self.channels[item.parent].mute else dav)
                self.channels[item.parent].volume = vol
                setVolume(item.fmod_channel, vol)
                self.log.debug(
                    f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | SET DVOL   | VOL: {vol:>5}'
                )
            else:
                if item.note_off and item.phase < NotePhases.RELEASE:
                    item.env_step = 0
                    item.phase = NotePhases.RELEASE
                if item.env_step == 0 or (item.env_pos == item.env_dest) or (
                        item.env_step == 0 and
                    (item.env_pos <= item.env_dest)) or (
                        item.env_step >= 0 and item.env_pos >= item.env_dest):
                    phase: NotePhases = item.phase
                    if phase == NotePhases.INITIAL:
                        item.phase = NotePhases.ATTACK
                        item.env_pos = 0
                        item.env_dest = 255
                        item.env_step = 0x100 - (item.env_attn * 8)
                    elif phase == NotePhases.ATTACK:
                        item.phase = NotePhases.DECAY
                        item.env_dest = 255 / item.env_sus * 2
                        item.env_step = (-item.env_dcy) / 2
                    elif phase == NotePhases.DECAY:
                        item.phase = NotePhases.SUSTAIN
                        item.env_step = 0
                    elif phase == NotePhases.SUSTAIN:
                        item.phase = NotePhases.SUSTAIN
                        item.env_step = 0
                    elif phase == NotePhases.RELEASE:
                        item.phase = NotePhases.NOTEOFF
                        item.env_dest = 0
                        item.env_step = (0x8 - item.env_rel) * 2
                    elif phase == NotePhases.NOTEOFF and item.wait_ticks == 0:
                        out_type = item.output
                        if out_type == NoteTypes.SQUARE1:
                            self.gb1_chan = 255
                        elif out_type == NoteTypes.SQUARE2:
                            self.gb2_chan = 255
                        elif out_type == NoteTypes.WAVE:
                            self.gb3_chan = 255
                        elif out_type == NoteTypes.NOISE:
                            self.gb4_chan = 255
                        stopSound(item.fmod_channel)
                        disableFX(item.fmod_channel)
                        self.log.debug(
                            f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | STOP SOUND | F{item.fmod_channel:<9}'
                        )
                        item.fmod_channel = 0
                        self.channels[item.parent].notes.remove(str(i))
                        item.enable = False
                nex = item.env_pos + item.env_step
                if nex > item.env_dest and item.env_step > 0:
                    nex = item.env_dest
                if nex < item.env_dest and item.env_step < 0:
                    nex = item.env_dest
                item.env_pos = nex
                dav = (item.velocity / 0x7F) * (
                    self.channels[item.parent].main_vol / 0x7F) * (
                        item.env_pos / 0xFF) * 255
                vol = int(0 if self.channels[item.parent].mute else dav)
                self.channels[item.parent].volume = vol
                setVolume(item.fmod_channel, vol)
                self.log.debug(
                    f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | SET VOLUME | VOL: {vol:>5}'
                )

    def evt_processor_timer(self) -> None:
        self.update_vibrato()

        if self.tick_ctr:
            self.update_notes()
            self.update_channels()

            self.play_notes()
            self.advance_notes()
            out = self.update_interface()

            print(out, end='\r', flush=True)
            for channel in self.channels:
                if channel.enable:
                    return 1

            self.stop_song()
            return None

        self.tick_ctr = False
        self.incr += 1
        if self.incr >= int(60000 / (self.tempo * self.SAPPY_PPQN)):
            self.tick_ctr = True
            self.incr = 0

        return 0

    def get_player_header(self) -> str:
        top = ('| CHANNEL {:<23}' *
               self.channels.count).format(*range(self.channels.count))
        bottom = '+' + '+'.join(['-' * 32] * self.channels.count)
        return top + '\n' + bottom

    def update_interface(self) -> str:
        template = '|{:32}' * self.channels.count
        bars = [c.volume // (128 // 32 * 2) * '=' for c in self.channels]
        out = []
        for i, c in enumerate(self.channels):
            info = ('{:>3}' * (len(c.playing) + 1)).format(
                *list(map(note_to_name, c.playing)) + [c.wait_ticks])
            out.append(bars[i][:32 - len(bars[i])] + ' ' *
                       (32 - len(info) - len(bars[i])) + info)

        header = template.format(*out)
        return header

    def play_song(self, fpath: str, song_num: int, song_table: int) -> None:
        self.load_song(fpath, song_num, song_table)
        header = self.get_player_header()
        e = self.evt_processor_timer
        print(header)
        while True:
            st = time()
            if e() is None:
                break
            t = round(60000.0 / (self.tempo * 24.0) / 1000.0, 3)
            sleep(math.fabs(round(t - (time() - st), 3)))

    def val(self, expr: str) -> Union[float, int]:
        if expr is None:
            return None
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
                elif char == 'b':
                    if is_bin:
                        break
                    if char not in out and len(out) == 1 and out[0] == '0':
                        is_bin = True
                        out.append(char)
                    else:
                        return 0
                elif char in 'ABCDEFabcdef':
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
