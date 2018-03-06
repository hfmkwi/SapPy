#!python
#-*- coding: utf-8 -*-
# pylint disable=C0103, C0326, E1120, R0902, R0903, R0904, R0912, R0913, R0914, R0915, R1702
# pylint: disable=W0614
# TODO: Either use the original FMOD dlls or find a sound engine.
"""Main file."""
import math
import os
import random
import string
import time
from contextlib import suppress
from ctypes import *
from enum import IntEnum
from logging import INFO, basicConfig, getLogger
from struct import unpack
from typing import List, NamedTuple, Union

from containers import *
from fileio import *
from fmod import *
from player import *

#fmod = system.System()

DEBUG = True


class SongTypes(IntEnum):
    """Possible outputs for each song."""
    NULL = 0
    WAVE = 1
    MIDI = 2


class RawMidiEvent(NamedTuple):
    """MIDI event container."""
    # yapf: disable
    d_raw:    int = 0
    ticks:    int = 0
    evt_code: int = 0
    # yapf: enable


class Decoder(object):
    """Decoder/interpreter for Sappy code."""
    DEBUG = False
    GB_SQ_MULTI = 0.5
    GB_WAV_MULTI = 0.5
    GB_WAV_BASE_FREQ = 880
    GB_NSE_MULTI = 0.5
    SAPPY_PPQN = 24

    if DEBUG:
        basicConfig(level=DEBUG)
    else:
        basicConfig(level=INFO)
    log = getLogger(name=__name__)

    def __init__(self):
        # yapf: disable
        self.playing:      bool                        = False
        self.record:       bool                        = False
        self.beats:        int                         = 0
        self.gb1_chan:     int                         = 0
        self.gb2_chan:     int                         = 0
        self.gb3_chan:     int                         = 0
        self.gb4_chan:     int                         = 0
        self.incr:         int                         = 0
        self.inst_tbl_ptr: int                         = 0
        self.last_tempo:   int                         = 0
        self.layer:        int                         = 0
        self.sng_lst_ptr:  int                         = 0
        self.sng_num:      int                         = 0
        self.sng_ptr:      int                         = 0
        self.tempo:        int                         = 0
        self.ttl_ticks:    int                         = 0
        self.ttl_msecs:    int                         = 0
        self.transpose:    int                         = 0
        self._gbl_vol:     int                         = 100
        self.note_f_ctr:   float                       = 0.0
        self.last_tick:    float                       = 0.0
        self.tick_ctr:     float                       = 0.0
        self.rip_ears:     Collection                  = Collection()
        self.mdrum_map:    list                        = []
        self.mpatch_map:   list                        = []
        self.mpatch_tbl:   list                        = []
        self.fpath:        str                         = ''
        self.mfile:        File                        = None
        self.wfile:        File                        = None
        self.output:       SongTypes                   = SongTypes.WAVE
        self.channels:     ChannelQueue[Channel]       = ChannelQueue()  # pylint:    disable = E1136
        self.dct_head:     DirectHeader                = DirectHeader()
        self.directs:      DirectQueue[Direct]         = DirectQueue()  # pylint:     disable = E1136
        self.drm_head:     DrumKitHeader               = DrumKitHeader()
        self.drmkits:      DrumKitQueue[DrumKit]       = DrumKitQueue()  # pylint:    disable = E1136
        self.inst_head:    InstrumentHeader            = InstrumentHeader()
        self.insts:        InstrumentQueue[Instrument] = InstrumentQueue()  # pylint: disable = E1136
        self.note_arr:     Collection                  = Collection([Note(*[0]*14)] * 32)
        self.nse_wavs:     List[List[str]]             = [[[] for i in range(10)] for i in range(2)]
        self.mul_head:     MultiHeader                 = MultiHeader()
        self.gb_head:      NoiseHeader                 = NoiseHeader()
        self.note_q:       NoteQueue[Note]             = NoteQueue()  # pylint:       disable = E1136
        self.last_evt:     RawMidiEvent                = RawMidiEvent()
        self.smp_head:     SampleHeader                = SampleHeader()
        self.smp_pool:     SampleQueue[Sample]         = SampleQueue()  # pylint:     disable = E1136
        # yapf: enable
        random.seed()
        sz = 1
        if not sz:
            sz = 2048
        for i in range(10):
            for _ in range(sz):
                self.nse_wavs[0][i].append(chr(int(random.random() * 153)))
            self.nse_wavs[0][i] = "".join(self.nse_wavs[0][i])
            for _ in range(256):
                self.nse_wavs[1][i].append(chr(int(random.random() * 153)))
            self.nse_wavs[1][i] = "".join(self.nse_wavs[1][i])
        self.gbl_vol = 255

    @property
    def gbl_vol(self) -> int:
        """Global volume of the player."""
        return self._gbl_vol

    @gbl_vol.setter
    def gbl_vol(self, vol: int) -> None:
        fmod.FSOUND_SetSFXMasterVolume(vol)
        self._gbl_vol = vol

    def dct_exists(self, dcts: DirectQueue, dct_id: int) -> bool:
        """Check if a direct exists in a specfied `DirectQueue`."""
        for dct in dcts:
            dct: Direct
            if dct.key == str(dct_id):
                return True
        return False

    @staticmethod
    def flip_lng(val: int) -> int:
        """Truncate and flip the byteorder of a 4 byte integer."""
        b = ['' for i in range(4)]
        s1 = (list('00000000') + list(hex(val)[2:]))[-8:]
        b[0] = s1[0:2]
        b[1] = s1[2:4]
        b[2] = s1[4:6]
        b[3] = s1[6:8]
        s2 = ''.join(b)
        return int('0x' + s2, base=16)

    @staticmethod
    def flip_int(val: int) -> int:
        """Truncate and flip the byteorder of a 2 byte integer."""
        b1 = val % 0x100
        val //= 0x100
        b2 = val % 0x100

        val = b1
        val *= 0x100
        val += b2

        return val

    def set_direct(self, direct: Direct, inst_head: InstrumentHeader,
                   dct_head: DirectHeader, gb_head: NoiseHeader) -> None:
        # """UKNOWN"""
        # yapf: disable
        with direct as d:
            d.drum_key  = inst_head.drum_pitch
            d.output    = DirectTypes(inst_head.channel & 7)
            d.env_attn  = dct_head.attack
            d.env_dcy   = dct_head.hold
            d.env_sus   = dct_head.sustain
            d.env_rel   = dct_head.release
            d.raw0      = dct_head.b0
            d.raw1      = dct_head.b1
            d.gb1       = gb_head.b2
            d.gb2       = gb_head.b3
            d.gb3       = gb_head.b4
            d.gb4       = gb_head.b5
            d.fix_pitch = (inst_head.channel & 0x08) == 0x08
            d.reverse   = (inst_head.channel & 0x10) == 0x10
        # yapf: enable

    @staticmethod
    def write_var_len(ch: int, val: int) -> None:
        """UNKNOWN"""
        buffer = val & 0x7F
        while val // 128 > 0:
            val //= 128
            buffer |= 0x80
            buffer = (buffer * 256) | (val & 0x7F)
        file = File.from_id(ch)
        while True:
            file.write_byte(buffer & 255)
            if buffer & 0x80:
                buffer //= 256
            else:
                break

    def add_ear_piercer(self, inst_id: int):
        """UNKNOWN"""
        self.rip_ears.append(inst_id)

    def buffer_evt(self, evt_code: str, ticks: int) -> None:
        """UNKNOWN"""
        self.mfile: File
        if not self.record or self.mfile.file_id != 42:
            return
        d_raw = ticks - self.last_evt.ticks
        evt_code = int(evt_code)
        evt = RawMidiEvent(ticks=ticks, d_raw=d_raw, evt_code=evt_code)
        self.write_var_len(self.mfile.file_id, evt.d_raw)
        self.mfile.write_string(evt.evt_code)
        self.last_evt = evt

    def clear_mpatch_map(self):
        """Clear the MIDI patch map, the MIDI drum map, and the ear piercers."""
        self.mpatch_map.clear()
        self.mdrum_map.clear()
        self.rip_ears.clear()

    def drm_exists(self, patch: int) -> bool:
        """Check if a drumkit on the specified MIDI patch exists."""
        for drm in self.drmkits:
            if self.val(drm.key) == patch:
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
        for i in range(32):
            if self.note_arr[i].enable is False:
                return i
        return 255

    def get_smp(self, smp: Sample, dct_head: DirectHeader,
                smp_head: SampleHeader, use_readstr: bool) -> None:
        """UNKNOWN"""
        with smp as D:
            D.smp_id = dct_head.smp_head
            sid = D.smp_id
            if not self.smp_exists(sid):
                self.smp_pool.add(str(sid))
                if D.output == DirectTypes.DIRECT:
                    smp_head = rd_smp_head(1, File.gba_ptr_to_addr(sid))
                    with self.smp_pool[str(sid)] as smp:

                        smp.size = smp_head.size
                        smp.freq = smp_head.freq * 64
                        smp.loop_start = smp_head.loop
                        smp.loop = smp_head.flags > 0
                        smp.gb_wave = False
                        self.log.debug(
                            f'{smp_head} {sid:#x} {File.gba_ptr_to_addr(sid):#x}'
                        )
                        # raise Exception
                        if use_readstr:
                            smp_data = self.wfile.rd_str(smp_head.size)
                        else:
                            smp_data = self.wfile.rd_addr
                        smp.smp_data = smp_data
                else:
                    with self.smp_pool[str(sid)] as smp:
                        smp.size = 32
                        smp.freq = self.GB_WAV_BASE_FREQ
                        smp.loop_start = 0
                        smp.loop = True
                        smp.gb_wave = True
                        tsi = self.wfile.rd_str(16, File.gba_ptr_to_addr(sid))
                        smp.smp_data = ""

    get_mul_smp = get_smp

    def inst_exists(self, patch: int) -> bool:
        """Check if an instrument on the specified MIDI patch is defined."""
        for inst in self.insts:
            if self.val(inst.key) == patch:
                return True
        return False

    def kmap_exists(self, kmaps: KeyMapQueue, kmap_id: int) -> bool:
        """Check if a keymap is defined."""
        for kmap in kmaps:
            if kmap.key == str(kmap_id):
                return True
        return True

    def note_in_channel(self, note_id: bytes, chnl_id: int) -> bool:
        """Check if a note belongs to a channel."""
        return self.note_arr[note_id].parent == chnl_id

    def patch_exists(self, lp: int) -> bool:
        """UKNOWN"""
        for dct in self.directs:
            if self.val(dct.key) == lp:
                return True
        for inst in self.insts:
            if self.val(inst.key) == lp:
                return True
        for dk in self.drmkits:
            if self.val(dk.key) == lp:
                return True
        return False

    # yapf: disable
    def play_song(self, fpath: str, sng_num: int, sng_list_ptr: int = None,
                  record: bool = False, record_to: str = "midiout.mid"):
        """Play a song from an AGB rom that uses the Sappy Sound Engine."""
        # yapf: enable
        self.fpath = fpath
        self.sng_lst_ptr = sng_list_ptr
        self.sng_num = sng_num

        if self.playing:
            self.stop_song()

        self.inst_head = InstrumentHeader()
        self.drm_head = DrumKitHeader()
        self.dct_head = DirectHeader()
        self.smp_head = SampleHeader()
        self.mul_head = MultiHeader()
        self.gb_head = NoiseHeader()

        self.channels.clear()
        self.drmkits.clear()
        self.smp_pool.clear()
        self.insts.clear()
        self.directs.clear()
        self.note_q.clear()
        for i in range(32):
            self.note_arr[i].enable = False

        self.wfile = open_file(self.fpath, 1)
        a = self.wfile.rd_gba_ptr(self.sng_lst_ptr + sng_num * 8)
        self.sng_ptr = a
        self.layer = self.wfile.rd_ltendian(4)
        b = self.wfile.rd_byte(a)
        self.inst_tbl_ptr = self.wfile.rd_gba_ptr(a + 4)

        # TODO: raise LOADING_0

        xta = SubroutineQueue()
        for i in range(b):
            self.log.debug(f"| CHN: {i:>#8} | BEGIN SUB |")
            loop_offset = -1
            self.channels.add()
            pc = self.wfile.rd_gba_ptr(a + 4 + (i + 1) * 4) + 1
            self.channels[i].track_ptr = pc
            xta.clear()
            while True:
                self.wfile.rd_addr = pc
                c = self.wfile.rd_byte()
                if 0 <= c <= 0xB0 or c == 0xCE or c == 0xCF or c == 0xB4:
                    pc += 1
                elif c == 0xB9:
                    self.log.debug(f'| PGM: {pc:#x} | CMD: {c:#x} | COND JMP |')
                    pc += 4
                elif c >= 0xB5 and c <= 0xCD:
                    self.log.debug(f'| PGM: {pc:#x} | CMD: {c:#x} | CMD  ARG |')
                    pc += 2
                elif c == 0xB2:
                    loop_offset = self.wfile.rd_gba_ptr()
                    self.log.debug(
                        f'| PGM: {pc:#x} | CMD: {c:#x} | JMP ADDR | {loop_offset:<#x}'
                    )
                    pc += 5
                    break
                elif c == 0xB3:
                    sub = self.wfile.rd_gba_ptr()
                    self.log.debug(
                        f'| PGM: {pc:#x} | CMD: {c:#x} | SUB ADDR | {sub:<#x}')
                    xta.add(sub)
                    pc += 5
                elif c >= 0xD0 and c <= 0xFF:
                    pc += 1
                    self.log.debug(f'| PGM: {pc:#x} | CMD: {c:#x} | BGN NOTE |')
                    while self.wfile.rd_byte() < 0x80:
                        pc += 1
                    self.log.debug(f'| PGM: {pc:#x} | CMD: {c:#x} | END NOTE |')

                elif c == 0xb1:
                    break
            self.channels[i].track_len = pc - self.channels[i].track_ptr
            self.log.debug(
                f'| PGM: {pc:#x} | CMD: {c:#x} | SET TLEN | {self.channels[i].track_len}'
            )
            pc = self.wfile.rd_gba_ptr(a + 4 + (i + 1) * 4)

            cticks = 0
            lc = 0xbe
            lln: List = [0] * 66
            llv: List = [0] * 66
            lla: List = [0] * 66
            lp = 0
            insub = 0
            tR = 0
            self.channels[i].loop_ptr = -1
            cdr = 0
            self.log.debug(f'| CHN: {i:>#8} | BEGIN EVT |')
            while True:
                self.wfile.rd_addr = pc
                if pc >= loop_offset and self.channels[i].loop_ptr == -1 and loop_offset != -1:
                    self.channels[i].loop_ptr = self.channels[i].evt_queue.count
                c = self.wfile.rd_byte()
                if (c != 0xB9 and 0xB5 <= c < 0xC5) or c == 0xCD:
                    D = self.wfile.rd_byte()
                    if c == 0xbc:
                        tR = sbyte_to_int(D)
                        self.log.debug(
                            f'| PGM: {pc:#x} | CMD: {c:#x} | SET TRPS | {tR:<#x}'
                        )
                    elif c == 0xbd:
                        lp = D
                        self.log.debug(
                            f'| PGM: {pc:#x} | CMD: {c:#x} | SET INST | {lp:<#x}'
                        )
                    elif c == 0xbe or c == 0xbf or c == 0xc0 or c == 0xc4 or c == 0xcd:
                        lc = c
                        self.log.debug(
                            f'| PGM: {pc:#x} | CMD: {c:#x} | GET ATTR | {lc:<#x}'
                        )
                    self.channels[i].evt_queue.add(cticks, c, D, 0, 0)
                    self.log.debug(
                        f'| PGM: {pc:#x} | CMD: {c:#x} | EVT PLAY | TIME: {cticks:<4} | CTRL: {c:<#4x} | ARG1: {D:<#4x} | ARG2: 0x00 | ARG3: 0x00'
                    )
                    pc += 2
                elif 0xc4 < c < 0xcf:
                    self.channels[i].evt_queue.add(cticks, c, 0, 0, 0)
                    self.log.debug(
                        f'| PGM: {pc:#x} | CMD: {c:#x} | EVT UNKN | TIME: {cticks:<4} | CTRL: {c:<#4x} | ARG1: 0x00 | ARG2: 0x00 | ARG3: 0x00'
                    )
                    pc += 1
                elif c == 0xb9:
                    D = self.wfile.rd_byte()
                    e = self.wfile.rd_byte()
                    F = self.wfile.rd_byte()
                    self.channels[i].evt_queue.add(cticks, c, D, e, F)
                    self.log.debug(
                        f'| PGM: {pc:#x} | CMD: {c:#x} | EVT JUMP | TIME: {cticks:<4} | CTRL: {c:<#4x} | ARG1: {D:<#4x} | ARG2: {e:<#4x} | ARG3: {F:<#4x}'
                    )
                    pc += 4
                elif c == 0xb4:
                    if insub == 1:
                        pc = rpc  # pylint: disable=E0601
                        insub = 0
                        self.log.debug(
                            f'| PGM: {pc:#x} | CMD: {c:#x} | END SUB  |')
                    else:
                        self.log.debug(
                            f'| PGM: {pc:#x} | CMD: {c:#x} | RTN EXEC |')
                        pc += 1
                elif c == 0xb3:
                    rpc = pc + 5
                    insub = 1
                    pc = self.wfile.rd_gba_ptr()
                    self.log.debug(f'| PGM: {pc:#x} | CMD: {c:#x} | BGN SUB  |')
                elif 0xcf <= c <= 0xff:
                    pc += 1
                    lc = c
                    g = False
                    nc = 0
                    while not g:
                        D = self.wfile.rd_byte()
                        if D >= 0x80:
                            if nc == 0:
                                pn = lln[nc] + tR
                                self.channels[i].evt_queue.add(
                                    cticks, c, pn, llv[nc], lla[nc])
                                self.log.debug(
                                    f'| PGM: {pc:#x} | CMD: {c:#x} | EVT NOTE | TIME: {cticks:<4} | CTRL: {c:<#4x} | ARG1: {pn:<#4x} | ARG2: {llv[nc]:<#4x} | ARG3: {lla[nc]:<#4x} | D:    {D:<#4x}'
                                )
                            g = True
                        else:
                            lln[nc] = D
                            pc += 1
                            e = self.wfile.rd_byte()
                            if e < 0x80:
                                llv[nc] = e
                                pc += 1
                                F = self.wfile.rd_byte()
                                if F >= 0x80:
                                    F = lla[nc]
                                    g = True
                                else:
                                    lla[nc] = F
                                    pc += 1
                                    nc += 1
                            else:
                                e = llv[nc]
                                F = lla[nc]
                                g = True
                            pn = D + tR
                            self.channels[i].evt_queue.add(cticks, c, pn, e, F)
                            self.log.debug(
                                f'| PGM: {pc:#x} | CMD: {c:#x} | EVT NOTE | TIME: {cticks:<4} | CTRL: {c:<#4x} | ARG1: {pn:<#4x} | ARG2: {e:<#4x} | ARG3: {F:<#4x} | D:    {D:<#4x}'
                            )
                        with suppress(None):
                            if not self.patch_exists(lp):
                                self.inst_head = rd_inst_head(
                                    1, self.inst_tbl_ptr + lp * 12)
                                self.log.debug(
                                    f'| PGM: {pc:#x} | CMD: {c:#x} | NW PATCH | PREV: {lp:<#4x} | PNUM: {pn:<#4x} | HEAD: {self.inst_head}'
                                )

                                out = (DirectTypes.DIRECT, DirectTypes.WAVE)
                                if self.inst_head.channel & 0x80 == 0x80:  # Drumkit
                                    self.drm_head = rd_drmkit_head(1)
                                    self.inst_head = rd_inst_head(
                                        1,
                                        File.gba_ptr_to_addr(
                                            self.drm_head.dct_tbl + pn * 12))
                                    self.dct_head = rd_dct_head(1)
                                    self.gb_head = rd_nse_head(
                                        1,
                                        File.gba_ptr_to_addr(
                                            self.drm_head.dct_tbl + pn * 12) +
                                        2)
                                    self.drmkits.add(str(lp))
                                    self.drmkits[str(lp)].directs.add(str(pn))
                                    self.set_direct(
                                        self.drmkits[str(lp)].directs[str(pn)],
                                        self.inst_head, self.dct_head,
                                        self.gb_head)
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW DRUM  | DRM HEAD   | {self.drm_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW DRUM  | INST HEAD  | {self.inst_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW DRUM  | DCT HEAD   | {self.dct_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW DRUM  | NOISE HEAD | {self.gb_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW DRUM  | NEW DRMKIT | {self.drmkits[str(lp)]}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW DRUM  | NEW DRMKIT | SET DIRECT | {self.drmkits[str(lp)].directs[str(pn)]}'
                                    )
                                    if self.drmkits[str(lp)].directs[str(
                                            pn)].output in (DirectTypes.DIRECT,
                                                            DirectTypes.WAVE):
                                        self.get_smp(self.drmkits[str(
                                            lp)].directs[str(pn)],
                                                     self.dct_head,
                                                     self.smp_head, False)
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | NW DRUM  | GET SAMPLE | {self.drmkits[str(lp)].directs[str(pn)]}'
                                        )
                                elif self.inst_head.channel & 0x40 == 0x40:  # Multi
                                    self.mul_head = rd_mul_head(1)
                                    self.insts.add(str(lp))
                                    self.insts[str(lp)].kmaps.add(0, str(pn))
                                    self.insts[str(lp)].kmaps[str(
                                        pn)].assign_dct = self.wfile.rd_byte(
                                            File.gba_ptr_to_addr(
                                                self.mul_head.kmap) + pn)
                                    cdr = self.insts[str(lp)].kmaps[str(
                                        pn)].assign_dct
                                    self.inst_head = rd_inst_head(
                                        1,
                                        File.gba_ptr_to_addr(
                                            self.mul_head.dct_tbl + cdr * 12))
                                    self.dct_head = rd_dct_head(1)
                                    self.gb_head = rd_nse_head(
                                        1,
                                        File.gba_ptr_to_addr(
                                            self.mul_head.dct_tbl + cdr * 12) +
                                        2)
                                    self.insts[str(lp)].directs.add(str(cdr))
                                    self.set_direct(
                                        self.insts[str(lp)].directs[str(cdr)],
                                        self.inst_head, self.dct_head,
                                        self.gb_head)
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | MULTI HEAD | {self.mul_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | NEW INST   | {self.insts[str(lp)]}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | NEW KEYMAP | {self.insts[str(lp)].kmaps}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | SET ASNDCT | {self.insts[str(lp)].kmaps[str(pn)].assign_dct}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | INST HEAD  | {self.inst_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | DCT HEAD   | {self.dct_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | NOISE HEAD | {self.gb_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | SET DIRECT | {self.insts[str(lp)].directs[str(cdr)]}'
                                    )
                                    if self.insts[str(lp)].directs[str(
                                            cdr)].output in out:
                                        self.get_smp(self.insts[str(
                                            lp)].directs[str(cdr)],
                                                     self.dct_head,
                                                     self.smp_head, False)
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | GET SAMPLE | {self.insts[str(lp)].directs[str(cdr)]}'
                                        )
                                else:  # Direct/GB Sample
                                    self.dct_head = rd_dct_head(1)
                                    self.gb_head = rd_nse_head(
                                        1, self.inst_tbl_ptr + lp * 12 + 2)
                                    self.directs.add(str(lp))
                                    self.set_direct(self.directs[str(lp)],
                                                    self.inst_head,
                                                    self.dct_head, self.gb_head)
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW DCT   | DCT HEAD   | {self.dct_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW DCT   | NOISE HEAD | {self.gb_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW DCT   | SET DIRECT | {self.directs[str(lp)]}'
                                    )
                                    if self.directs[str(lp)].output in out:
                                        self.get_smp(self.directs[str(lp)],
                                                     self.dct_head,
                                                     self.smp_head, False)
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | NW DCT   | GET SAMPLE | {self.directs[str(lp)]}'
                                        )
                            else:  # Patch exists
                                self.inst_head = rd_inst_head(
                                    1, self.inst_tbl_ptr + lp * 12)
                                self.log.debug(
                                    f'| PGM: {pc:#x} | CMD: {c:#x} | PC EXIST | PREV: {lp:<#4x} | PNUM: {pn:<#4x} | HEAD: {self.inst_head}'
                                )
                                if self.inst_head.channel & 0x80 == 0x80:
                                    self.drm_head = rd_drmkit_head(1)
                                    self.inst_head = rd_inst_head(
                                        1,
                                        File.gba_ptr_to_addr(
                                            self.drm_head.dct_tbl + pn * 12))
                                    self.dct_head = rd_dct_head(1)
                                    self.gb_head = rd_nse_head(
                                        1,
                                        File.gba_ptr_to_addr(
                                            self.drm_head.dct_tbl + pn * 12) +
                                        2)
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | DM EXIST | DRM HEAD   | {self.drm_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | DM EXIST | INST HEAD  | {self.inst_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | DM EXIST | DCT HEAD   | {self.dct_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | DM EXIST | NOISE HEAD | {self.gb_head}'
                                    )
                                    if not self.dct_exists(
                                            self.drmkits[str(lp)].directs, pn):
                                        self.drmkits[str(lp)].directs.add(
                                            str(pn))
                                        self.set_direct(
                                            self.drmkits[str(lp)].directs[str(
                                                pn)], self.inst_head,
                                            self.dct_head, self.gb_head)
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | DM EXIST | NEW DIRECT | SET DIRECT | {self.drmkits[str(lp)].directs[str(pn)]}'
                                        )
                                        if self.drmkits[str(lp)].directs[str(
                                                pn)].output in out:
                                            self.get_mul_smp(
                                                self.drmkits[str(lp)].directs[
                                                    str(pn)], self.dct_head,
                                                self.smp_head, False)
                                            self.log.debug(
                                                f'| PGM: {pc:#x} | CMD: {c:#x} | DM EXIST | NEW DIRECT | GET SAMPLE | {self.drmkits[str(lp)].directs[str(pn)]}'
                                            )
                                elif self.inst_head.channel & 0x40 == 0x40:
                                    self.mul_head = rd_mul_head(1)
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | MULTI HEAD | {self.mul_head}'
                                    )
                                    if self.kmap_exists(
                                            self.insts[str(lp)].kmaps,
                                            pn) is False:
                                        self.insts[str(lp)].kmaps.add(
                                            self.wfile.rd_byte(
                                                self.wfile.gba_ptr_to_addr(
                                                    self.mul_head.kmap) + pn),
                                            str(pn))
                                        cdr = self.insts[str(lp)].kmaps[str(
                                            pn)].assign_dct
                                        self.inst_head = rd_inst_head(
                                            1,
                                            File.gba_ptr_to_addr(
                                                self.mul_head.dct_tbl + cdr * 12
                                            ))
                                        self.dct_head = rd_dct_head(1)
                                        self.gb_head = rd_nse_head(
                                            1,
                                            File.gba_ptr_to_addr(
                                                self.mul_head.dct_tbl + cdr * 12
                                            ) + 2)
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | NEW KEYMAP | {self.insts[str(lp)].kmaps[str(pn)]}'
                                        )
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | NEW KEYMAP | SET CDR    | {cdr}'
                                        )
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | NEW KEYMAP | INST HEAD  | {self.inst_head}'
                                        )
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | NEW KEYMAP | DCT HEAD   | {self.dct_head}'
                                        )
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | NEW KEYMAP | NSE HEAD   | {self.gb_head}'
                                        )
                                        if not self.dct_exists(
                                                self.insts[str(lp)].directs,
                                                cdr):
                                            self.insts[str(lp)].directs.add(
                                                str(cdr))
                                            self.set_direct(
                                                self.insts[str(lp)].directs[str(
                                                    cdr)], self.inst_head,
                                                self.dct_head, self.gb_head)
                                            self.log.debug(
                                                f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | SET DIRECT | {self.insts[str(lp)].directs[str(cdr)]}'
                                            )
                                            if self.insts[str(lp)].directs[str(
                                                    cdr)].output in out:
                                                self.get_mul_smp(
                                                    self.insts[str(lp)].directs[
                                                        str(cdr)],
                                                    self.dct_head,
                                                    self.smp_head, False)
                                                self.log.debug(
                                                    f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | GET SAMPLE | {self.insts[str(lp)].directs[str(cdr)]}'
                                                )
                elif 0x00 <= c < 0x80:
                    if lc < 0xCF:
                        self.channels[i].evt_queue.add(cticks, lc, c, 0, 0)
                        self.log.debug(
                            f'| PGM: {pc:#x} | CMD: {c:#x} | PREV CMD | TIME: {cticks:<4} | CTRL: {lc:<#4x} | ARG1: {c:<#4x} | ARG2: 0x00 | ARG3: 0x00 '
                        )
                        pc += 1
                    else:
                        c = lc
                        self.wfile.rd_addr = pc
                        g = False
                        nc = 0
                        while not g:
                            D = self.wfile.rd_byte()
                            if D >= 0x80:
                                if not nc:
                                    pn = lln[nc] + tR
                                    self.channels[i].evt_queue.add(
                                        cticks, c, pn, llv[nc], lla[nc])
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | PRV NOTE | TIME: {cticks:<4} | CTRL: {c:<#4x} | ARG1: {pn:<#4x} | ARG2: {llv[nc]:<#4x} | ARG3: {lla[nc]:<#4x} | D:    {D:<#4x}'
                                    )
                                g = True
                            else:
                                lln[nc] = D
                                pc += 1
                                e = self.wfile.rd_byte()
                                if e < 0x80:
                                    llv[nc] = e
                                    pc += 1
                                    F = self.wfile.rd_byte()
                                    if F >= 0x80:
                                        F = lla[nc]
                                        g = True
                                    else:
                                        lla[nc] = F
                                        pc += 1
                                        nc += 1
                                else:
                                    e = llv[nc]
                                    F = lla[nc]
                                    g = True
                                pn = D + tR
                                self.channels[i].evt_queue.add(
                                    cticks, c, pn, e, F)
                                self.log.debug(
                                    f'| PGM: {pc:#x} | CMD: {c:#x} | PRV NOTE | TIME: {cticks:<4} | CTRL: {c:<#4x} | ARG1: {pn:<#4x} | ARG2: {e:<#4x} | ARG3: {F:<#4x} | D:    {D:<#4x}'
                                )
                            if not self.patch_exists(lp):
                                self.inst_head = rd_inst_head(
                                    1, self.inst_tbl_ptr + lp * 12)
                                self.log.debug(
                                    f'| PGM: {pc:#x} | CMD: {c:#x} | PV PATCH | PREV: {lp:<#4x} | PNUM: {pn:<#4x} | CHAN: {self.inst_head.channel:<#4x}'
                                )
                                if self.inst_head.channel & 0x80 == 0x80:
                                    self.drm_head = rd_drmkit_head(1)
                                    self.inst_head = rd_inst_head(
                                        1,
                                        File.gba_ptr_to_addr(
                                            self.drm_head.dct_tbl + pn * 12))
                                    self.dct_head = rd_dct_head(1)
                                    self.gb_head = rd_nse_head(
                                        1,
                                        File.gba_ptr_to_addr(
                                            self.drm_head.dct_tbl + pn * 12) +
                                        2)
                                    self.drmkits.add(str(lp))
                                    self.drmkits[str(lp)].directs.add(str(pn))
                                    self.set_direct(
                                        self.drmkits[str(lp)].directs[str(pn)],
                                        self.inst_head, self.dct_head,
                                        self.gb_head)
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW DRUM  | DRM HEAD   | {self.drm_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW DRUM  | INST HEAD  | {self.inst_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW DRUM  | DCT HEAD   | {self.dct_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW DRUM  | NOISE HEAD | {self.gb_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW DRUM  | NEW DRMKIT | {self.drmkits[str(lp)]}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW DRUM  | NEW DRMKIT | SET DIRECT | {self.drmkits[str(lp)].directs[str(pn)]}'
                                    )
                                    if self.drmkits[str(lp)].directs[str(
                                            pn)].output in out:
                                        self.get_smp(self.drmkits[str(
                                            lp)].directs[str(pn)],
                                                     self.dct_head,
                                                     self.smp_head, False)
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | NW DRUM  | GET SAMPLE | {self.drmkits[str(lp)].directs[str(pn)]}'
                                        )
                                elif self.inst_head.channel & 0x40 == 0x40:
                                    self.mul_head = rd_mul_head(1)
                                    self.insts.add(str(lp))
                                    self.insts[str(lp)].kmaps.add(
                                        File.gba_ptr_to_addr(
                                            self.mul_head.kmap) + pn, str(pn))
                                    cdr = self.insts[str(lp)].kmaps[str(
                                        pn)].assign_dct
                                    self.inst_head = rd_inst_head(
                                        1,
                                        File.gba_ptr_to_addr(
                                            self.mul_head.dct_tbl + cdr * 12))
                                    self.dct_head = rd_dct_head(1)
                                    self.gb_head = rd_nse_head(
                                        1,
                                        File.gba_ptr_to_addr(
                                            self.mul_head.dct_tbl + cdr * 12) +
                                        2)
                                    self.insts[str(lp)].directs.add(str(cdr))
                                    self.set_direct(
                                        self.insts[str(lp)].directs[str(cdr)],
                                        self.inst_head, self.dct_head,
                                        self.gb_head)
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | MULTI HEAD | {self.mul_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | NEW INST   | {self.insts[str(lp)]}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | NEW KEYMAP | {self.insts[str(lp)].kmaps}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | SET ASNDCT | {cdr}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | INST HEAD  | {self.inst_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | DCT HEAD   | {self.dct_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | NOISE HEAD | {self.gb_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | SET DIRECT | {self.insts[str(lp)].directs[str(cdr)]}'
                                    )
                                    if self.insts[str(lp)].directs[str(
                                            cdr)].output in out:
                                        self.get_smp(self.insts[str(
                                            lp)].directs[str(cdr)],
                                                     self.dct_head,
                                                     self.smp_head, False)
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | NW DRUM  | GET SAMPLE | {self.insts[str(lp)].directs[str(cdr)]}'
                                        )
                            else:
                                self.inst_head = rd_inst_head(
                                    1, self.inst_tbl_ptr + lp * 12)
                                self.log.debug(
                                    f'| PGM: {pc:#x} | CMD: {c:#x} | PC EXIST | PREV: {lp:<#4x} | PNUM: {pn:<#4x} | HEAD: {self.inst_head}'
                                )
                                if self.inst_head.channel & 0x80 == 0x80:
                                    self.drm_head = rd_drmkit_head(1)
                                    self.inst_head = rd_inst_head(
                                        1,
                                        File.gba_ptr_to_addr(
                                            self.drm_head.dct_tbl + pn * 12))
                                    self.dct_head = rd_dct_head(1)
                                    self.gb_head = rd_nse_head(
                                        1,
                                        File.gba_ptr_to_addr(
                                            self.drm_head.dct_tbl + pn * 12) +
                                        2)
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | DM EXIST | DRM HEAD   | {self.drm_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | DM EXIST | INST HEAD  | {self.inst_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | DM EXIST | DCT HEAD   | {self.dct_head}'
                                    )
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | DM EXIST | NOISE HEAD | {self.gb_head}'
                                    )
                                    if not self.dct_exists(
                                            self.drmkits[str(lp)].directs, pn):
                                        self.drmkits[str(lp)].directs.add(
                                            str(pn))
                                        self.set_direct(
                                            self.drmkits[str(lp)].directs[str(
                                                pn)], self.inst_head,
                                            self.dct_head, self.gb_head)
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | DM EXIST | NEW DIRECT | SET DIRECT | {self.drmkits[str(lp)].directs[str(pn)]}'
                                        )
                                        if self.drmkits[str(lp)].directs[str(
                                                pn)].output in out:
                                            self.get_smp(
                                                self.drmkits[str(lp)].directs[
                                                    str(pn)], self.dct_head,
                                                self.smp_head, False)
                                            self.log.debug(
                                                f'| PGM: {pc:#x} | CMD: {c:#x} | DM EXIST | NEW DIRECT | GET SAMPLE | {self.drmkits[str(lp)].directs[str(pn)]}'
                                            )
                                elif self.inst_head.channel & 0x40 == 0x40:
                                    self.mul_head = rd_mul_head(1)
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | MULTI HEAD | {self.mul_head}'
                                    )
                                    if not self.kmap_exists(
                                            self.insts[str(lp)].kmaps, pn):
                                        self.insts[str(lp)].kmaps.add(
                                            self.wfile.rd_byte(
                                                File.gba_ptr_to_addr(
                                                    self.mul_head.kmap) + pn),
                                            str(pn))
                                        cdr = self.insts[str(lp)].kmaps[str(
                                            pn)].assign_dct
                                        self.inst_head = rd_inst_head(
                                            1,
                                            File.gba_ptr_to_addr(
                                                self.mul_head.dct_tbl + cdr * 12
                                            ))
                                        self.dct_head = rd_dct_head(1)
                                        self.gb_head = rd_nse_head(
                                            1,
                                            File.gba_ptr_to_addr(
                                                self.mul_head.dct_tbl + cdr * 12
                                            ) + 2)
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | NEW KEYMAP | {self.insts[str(lp)].kmaps[str(pn)]}'
                                        )
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | NEW KEYMAP | SET CDR    | {cdr}'
                                        )
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | NEW KEYMAP | INST HEAD  | {self.inst_head}'
                                        )
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | NEW KEYMAP | DCT HEAD   | {self.dct_head}'
                                        )
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | NEW KEYMAP | NSE HEAD   | {self.gb_head}'
                                        )
                                        if not self.dct_exists(
                                                self.insts[str(lp)].dcts, cdr):
                                            self.insts[str(lp)].dcts.add(
                                                str(cdr))
                                            self.set_direct(
                                                self.insts[str(lp)].dcts[str(
                                                    cdr)], self.inst_head,
                                                self.dct_head, self.gb_head)
                                            self.log.debug(
                                                f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | SET DIRECT | {self.insts[str(lp)].directs[str(cdr)]}'
                                            )
                                            if self.insts[str(lp)].dcts[str(
                                                    cdr)].output in out:
                                                self.get_mul_smp(
                                                    self.insts[str(lp)].dcts[
                                                        str(cdr)],
                                                    self.dct_head,
                                                    self.smp_head, False)
                                                self.log.debug(
                                                    f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | GET SAMPLE | {self.insts[str(lp)].directs[str(cdr)]}'
                                                )
                elif 0x80 <= c <= 0xB0:
                    self.channels[i].evt_queue.add(cticks, c, 0, 0, 0)
                    self.log.debug(
                        f'| PGM: {pc:#x} | CMD: {c:#x} | EVT WAIT | TIME: {cticks:<4} | CTRL: {c:<#4x} | ARG1: 0x00 | ARG2: 0x00 | ARG3: 0x00 | TIME: {stlen_to_ticks(c - 0x80):<#4x}'
                    )
                    cticks += stlen_to_ticks(c - 0x80)
                    pc += 1
                if c in (0xB1, 0xB2):
                    self.log.debug(f'| PGM: {pc:#x} | CMD: {c:#x} | END EVT  |')
                    break
            self.channels[i].evt_queue.add(cticks, c, 0, 0, 0)
            self.log.debug(
                f'| PGM: {pc:#x} | CMD: {c:#x} | EVT END  | TIME: {cticks:<4x} | CTRL: {c:<#4x} | ARG1: 0x00 | ARG2: 0x00 | ARG3: 0x00'
            )
        self.log.debug(
            f'+---------------+-----------+----------+------------+------------+------------+------------+------------+------------+'
        )
        self.log.debug(f'+------+------------+------------+')
        fmod.FSOUND_Init(44100, 64, 0)
        self.log.debug(
            f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | INIT       |')
        fmod.FSOUND_SetSFXMasterVolume(self.gbl_vol)
        self.log.debug(
            f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | SET VOL    | {self.gbl_vol}'
        )
        quark = 0
        csm = FSoundChannelSampleMode
        sm = FSoundModes
        for smp in self.smp_pool:
            smp: Sample
            quark += 1
            self.log.debug(
                f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | SMP ID: {quark:2} | S{smp.smp_data} | GB:  {repr(smp.gb_wave):<5} |'
            )
            if smp.gb_wave:
                if self.val(smp.smp_data) == 0:
                    with open_new_file('temp.raw', 2) as f:
                        f.wr_str(smp.smp_data)
                    smp.fmod_smp = fmod.FSOUND_Sample_Load(
                        c_long(csm.FSOUND_FREE),
                        'temp.raw'.encode(encoding='ascii'),
                        int(sm.FSOUND_8BITS + sm.FSOUND_LOADRAW +
                            sm.FSOUND_LOOP_NORMAL + sm.FSOUND_MONO +
                            sm.FSOUND_UNSIGNED),
                        0,
                        0)
                    self.log.debug(
                        f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | LOAD SMP   | S{smp.fmod_smp} | SIZE: {smp.size} |'
                    )
                    fmod.FSOUND_Sample_SetLoopPoints(int(smp.fmod_smp), 0, 31)
                    self.log.debug(
                        f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | SET LOOP   | (0, 31)'
                    )
                    os.remove('temp.raw')
                else:
                    smp.fmod_smp = fmod.FSOUND_Sample_Load(
                        int(csm.FSOUND_FREE),
                        fpath.encode(encoding='ascii'),
                        int(sm.FSOUND_8BITS + sm.FSOUND_LOADRAW +
                            sm.FSOUND_LOOP_NORMAL + sm.FSOUND_MONO +
                            sm.FSOUND_UNSIGNED),
                        int(smp.smp_data),
                        int(smp.size))
                    self.log.debug(
                        f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | LOAD SMP   | S{smp.fmod_smp} | SIZE: {smp.size} |'
                    )
                    fmod.FSOUND_Sample_SetLoopPoints(int(smp.fmod_smp), 0, 31)
                    self.log.debug(
                        f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | SET LOOP   | (0, 31)'
                    )
            else:
                if self.val(smp.smp_data) == 0:
                    with open_new_file('temp.raw', 2) as f:
                        f.wr_str(smp.smp_data)
                    smp.fmod_smp = fmod.FSOUND_Sample_Load(
                        int(csm.FSOUND_FREE),
                        'temp.raw'.encode(encoding='ascii'),
                        int(sm.FSOUND_8BITS + sm.FSOUND_LOADRAW +
                            (sm.FSOUND_LOOP_NORMAL if smp.loop else 0
                            ) + sm.FSOUND_MONO + sm.FSOUND_SIGNED),
                        0,
                        0)
                    self.log.debug(
                        f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | LOAD SMP   | S{smp.fmod_smp} | SIZE: {smp.size} |'
                    )
                    fmod.FSOUND_Sample_SetLoopPoints(
                        int(smp.fmod_smp), int(smp.loop_start),
                        int(smp.size - 1))
                    self.log.debug(
                        f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | SET LOOP   | ({smp.loop_start},  {smp.size - 1})'
                    )
                    os.remove('temp.raw')
                else:
                    smp.fmod_smp = fmod.FSOUND_Sample_Load(
                        int(csm.FSOUND_FREE),
                        fpath.encode(encoding='ascii'),
                        int(sm.FSOUND_8BITS + sm.FSOUND_LOADRAW +
                            (sm.FSOUND_LOOP_NORMAL if smp.loop else 0
                            ) + sm.FSOUND_MONO + sm.FSOUND_SIGNED),
                        int(smp.smp_data),
                        int(smp.size))
                    self.log.debug(
                        f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | LOAD SMP   | S{smp.fmod_smp} | SIZE: {smp.size} |'
                    )
                    fmod.FSOUND_Sample_SetLoopPoints(
                        int(smp.fmod_smp), int(smp.loop_start), int(smp.size))
                    self.log.debug(
                        f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | SET LOOP   | (0, 31)'
                    )
        for i in range(10):
            self.smp_pool.add(f'noise0{i}')
            with self.smp_pool[f'noise0{i}'] as smp:
                random.seed()
                f_nse = f'noise0{i}.raw'.encode(encoding='ascii')
                with open_new_file(f_nse, 2) as f:
                    f.wr_str(self.nse_wavs[0][i])
                smp.freq = 7040
                smp.size = 16384
                smp.smp_data = ''
                smp.fmod_smp = fmod.FSOUND_Sample_Load(
                    csm.FSOUND_FREE, f_nse,
                    sm.FSOUND_8BITS + sm.FSOUND_LOADRAW + sm.FSOUND_LOOP_NORMAL
                    + sm.FSOUND_MONO + sm.FSOUND_UNSIGNED, 0, 0)
                self.log.debug(
                    f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | LOAD NSE0{i} | S{smp.fmod_smp}'
                )
                fmod.FSOUND_Sample_SetLoopPoints(int(smp.fmod_smp), 0, 16383)
                self.log.debug(
                    f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | SET LOOP   | (0, 16383)'
                )
                os.remove(f_nse)

            self.smp_pool.add(f'noise1{i}')
            with self.smp_pool[f'noise1{i}'] as smp:
                f_nse = f'noise1{i}.raw'.encode(encoding='ascii')
                with open_new_file(f_nse, 2) as f:
                    f.wr_str(self.nse_wavs[1][i])
                smp.freq = 7040
                smp.size = 256
                smp.smp_data = ''
                smp.fmod_smp = fmod.FSOUND_Sample_Load(
                    csm.FSOUND_FREE, f_nse,
                    sm.FSOUND_8BITS + sm.FSOUND_LOADRAW + sm.FSOUND_LOOP_NORMAL
                    + sm.FSOUND_MONO + sm.FSOUND_UNSIGNED, 0, 0)
                self.log.debug(
                    f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | LOAD NSE1{i} | S{smp.fmod_smp}'
                )
                fmod.FSOUND_Sample_SetLoopPoints(int(smp.fmod_smp), 0, 255)
                self.log.debug(
                    f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | SET LOOP   | (0, 255)'
                )
                os.remove(f_nse)

        b1 = chr(int(0x80 + 0x7F * self.GB_SQ_MULTI))
        b2 = chr(int(0x80 - 0x7F * self.GB_SQ_MULTI))
        for mx2 in range(4):
            sq = f'square{mx2}'
            self.smp_pool.add(sq)
            with self.smp_pool[f'square{mx2}'] as smp:
                if mx2 == 3:
                    smp_dat = "".join([b1] * 24 + [b2] * 8)
                else:
                    smp_dat = "".join([b1] * (
                        (mx2 + 2)**2) + [b2] * (32 - (mx2 + 2)**2))
                f_sq = f'{sq}.raw'.encode('ascii')
                with open_new_file(f_sq, 2) as f:
                    f.wr_str(smp_dat)
                smp.smp_data = '',
                smp.freq = 7040,
                smp.size = 32,
                smp.fmod_smp = fmod.FSOUND_Sample_Load(
                    csm.FSOUND_FREE, f_sq, sm.FSOUND_8BITS + sm.FSOUND_LOADRAW +
                    sm.FSOUND_LOOP_NORMAL + sm.FSOUND_MONO + sm.FSOUND_UNSIGNED,
                    0, 0)
                self.log.debug(
                    f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | LOAD SQRE{mx2} | S{smp.fmod_smp}'
                )
                fmod.FSOUND_Sample_SetLoopPoints(int(smp.fmod_smp), 0, 31)
                self.log.debug(
                    f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | SET LOOP   | (00, 31)'
                )
                os.remove(f_sq)

        self.gb1_chan = 255
        self.gb2_chan = 255
        self.gb3_chan = 255
        self.gb4_chan = 255

        self.tempo = 120
        self.last_tempo = -1
        self.incr = 0
        self.wfile.close()
        self.ttl_ticks = 0
        self.ttl_msecs = 0
        self.beats = 0
        self.log.debug(
            f'| FMOD | CODE: {fmod.FSOUND_GetError():4} | FINISH     |')
        self.log.debug(f'+------+------------+------------+')
        self.log.debug(f'+------------+------------+------------+')

    def smp_exists(self, smp_id: int) -> bool:
        """Check if a sample exists in the available sample pool."""
        for smp in self.smp_pool:
            if self.val(smp.key) == smp_id:
                return True
        return False

    def set_mpatch_map(self, ind: int, inst: int, transpose: int) -> None:
        """Bind a MIDI instrument to a specified MIDI key."""
        self.mpatch_map[ind] = inst
        self.mpatch_tbl[ind] = transpose

    def set_mdrum_map(self, ind: int, new_drum: int) -> None:
        """Bind a MIDI drum to a specified MIDI key."""
        self.mdrum_map[ind] = new_drum

    def stop_song(self):
        """Stop playing a song."""
        try:
            File.from_id(1).close()
        except AttributeError:
            pass
        fmod.FSOUND_Close()

    def evt_processor_timer(self, msecs: int) -> None:
        ep = 0
        mutethis = False
        self.ttl_msecs += msecs
        self.log.debug(
            f'| WAIT TICK  | MS: {self.ttl_msecs:<6} | TICK: {self.tick_ctr:<5}'
        )

        if self.tick_ctr > 0:
            for i in range(32):
                with self.note_arr[i] as item:
                    if item.enable and item.wait_ticks > 0:
                        item.wait_ticks = item.wait_ticks - (
                            self.tick_ctr - self.last_tick)
                    if item.wait_ticks <= 0 and item.enable is True and item.note_off is False:
                        if self.channels[item.parent].sustain is False:
                            item.note_off = True
            for i in range(self.channels.count):
                if self.channels[i].enable is False:
                    self.log.debug(f'| CHAN: {i:>4} | SKIP EXEC  |')
                    continue
                self.log.debug(f'| CHAN: {i:>4} | BEGIN EXEC |')
                with self.channels[i] as chan:
                    chan: Channel
                    for ep in range(self.rip_ears.count):
                        if self.rip_ears[ep] == chan.patch_num:
                            chan.mute = True
                            self.log.debug(f'| CHAN: {i:>4} | MUTE CHAN  |')
                            break

                    if chan.wait_ticks > 0:
                        chan.wait_ticks = chan.wait_ticks - (
                            self.tick_ctr - self.last_tick)
                        self.log.debug(
                            f'| CHAN: {i:>4} | CMD: NONE  | DELTA WAIT | TIME: {chan.wait_ticks:<5}'
                        )
                    just_looped = False
                    in_for = True
                    while chan.wait_ticks <= 0:
                        cmd_byte = chan.evt_queue[chan.pgm_ctr].cmd_byte
                        if cmd_byte == 0xB1:
                            chan.enable = False
                            in_for = False
                            self.log.debug(
                                f'| CHAN: {i:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | STOP EXEC  |'
                            )
                            break
                        elif cmd_byte == 0xB9:
                            self.log.debug(
                                f'| CHAN: {i:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | COND JUMP  |'
                            )
                            chan.pgm_ctr += 1
                        elif cmd_byte == 0xBB:
                            self.tempo = chan.evt_queue[chan.pgm_ctr].arg1 * 2
                            self.log.debug(
                                f'| CHAN: {i:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET TEMPO  | TEMPO: {self.tempo:3}'
                            )
                            chan.pgm_ctr += 1
                        elif cmd_byte == 0xBC:
                            chan.transpose = sbyte_to_int(
                                chan.evt_queue[chan.pgm_ctr].arg1)
                            self.log.debug(
                                f'| CHAN: {i:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET TRNPSE | SHIFT: {chan.transpose:3}'
                            )
                            chan.pgm_ctr += 1
                        elif cmd_byte == 0xBD:
                            chan.patch_num = chan.evt_queue[chan.pgm_ctr].arg1
                            if self.dct_exists(self.directs, chan.patch_num):
                                chan.output = self.directs[str(
                                    chan.patch_num)].output
                            elif self.inst_exists(chan.patch_num):
                                chan.output = ChannelTypes.MUL_SMP
                            elif self.drm_exists(chan.patch_num):
                                chan.output = ChannelTypes.DRUMKIT
                            else:
                                chan.output = ChannelTypes.NULL
                            self.log.debug(
                                f'| CHAN: {i:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET OUTPUT | PATCH: {chan.patch_num:3} | T: {chan.output.name:>7}'
                            )
                            chan.pgm_ctr += 1
                        elif cmd_byte == 0xBE:
                            chan.main_vol = chan.evt_queue[chan.pgm_ctr].arg1
                            for item in chan.notes:
                                if self.note_arr[item.
                                                 note_id].enable is True and self.note_arr[item.
                                                                                           note_id].parent == i:
                                    dav = (self.note_arr[item.note_id].velocity
                                           / 0x7F) * (chan.main_vol / 0x7F) * (
                                               int(self.note_arr[item.note_id].
                                                   env_pos) / 0xFF) * 255
                                    if mutethis:
                                        dav = 0
                                    fmod.FSOUND_SetVolume(
                                        self.note_arr[item.note_id]
                                        .fmod_channel,
                                        int(dav * 0 if chan.mute else dav * 1))
                                    self.log.debug(
                                        f'| CHAN: {i:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | CODE: {fmod.FSOUND_GetError():4} | SET VOLUME | FMOD: {self.note_arr[item.note_id].fmod_channel:4} | NOTE: {item.note_id:>4} | VOL: {chan.main_vol:5} | DAV: {dav:5}'
                                    )
                            chan.pgm_ctr += 1
                        elif cmd_byte == 0xBF:
                            chan.panning = chan.evt_queue[chan.pgm_ctr].arg1
                            for item in chan.notes:
                                item: Note
                                if self.note_arr[item.
                                                 note_id].enable and self.note_arr[item.
                                                                                   note_id].parent == i:
                                    fmod.FSOUND_SetPan(self.note_arr[
                                        item.note_id].fmod_channel,
                                                       int(chan.panning * 2))
                                    self.log.debug(
                                        f'| CHAN: {i:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET PAN    | CODE: {fmod.FSOUND_GetError():4} | FMOD: {self.note_arr[item.note_id].fmod_channel:4} | NOTE: {item.note_id:>4} | PAN: {chan.panning:5} | DAP: {chan.panning * 2:5}'
                                    )
                            chan.pgm_ctr += 1
                        elif cmd_byte == 0xC0:
                            chan.pitch_bend = chan.evt_queue[chan.pgm_ctr].arg1
                            chan.pgm_ctr += 1
                            for item in chan.notes:
                                item: Note
                                if self.note_arr[item.
                                                 note_id].enable and self.note_arr[item.
                                                                                   note_id].parent == i:
                                    freq = self.note_arr[item.note_id].freq * (
                                        2**
                                        (1 / 12))**((chan.pitch_bend - 0x40
                                                    ) / 0x40 * chan.pitch_range)
                                    #fmod.FSOUND_SetFrequency(
                                    #    self.note_arr[item.note_id]
                                    #    .fmod_channel, c_float(freq))
                                    self.log.debug(
                                        f'| CHAN: {i:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET PBEND  | CODE: {fmod.FSOUND_GetError():4} | FMOD: {self.note_arr[item.note_id].fmod_channel:4} | NOTE: {item.note_id:>4} | BEND: {chan.pitch_bend:4} | DAP: {freq:5}'
                                    )
                        elif cmd_byte == 0xC1:
                            chan.pitch_range = sbyte_to_int(
                                chan.evt_queue[chan.pgm_ctr].arg1)
                            chan.pgm_ctr += 1
                            for item in chan.notes:
                                item: Note
                                if self.note_arr[item.
                                                 note_id].enable and self.note_arr[item.
                                                                                   note_id].parent == i:
                                    freq = c_float(
                                        self.note_arr[item.note_id].freq *
                                        (2**(1 / 12))**
                                        ((chan.pitch_bend - 0x40
                                         ) / 0x40 * chan.pitch_range))
                                    #fmod.FSOUND_SetFrequency(
                                    #    self.note_arr[item.note_id]
                                    #    .fmod_channel, freq)
                                    self.log.debug(
                                        f'| CHAN: {i:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET BENDRG | CODE: {fmod.FSOUND_GetError():4} | FMOD: {self.note_arr[item.note_id].fmod_channel:4} | NOTE: {item.note_id:>4} | BEND: {chan.pitch_bend:4} | DAP: {freq:5}'
                                    )
                        elif cmd_byte == 0xC2:
                            chan.vib_depth = chan.evt_queue[chan.pgm_ctr].arg1
                            self.log.debug(
                                f'| CHAN: {i:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET VIBDP  | DEPTH: {chan.vib_depth:3}'
                            )
                            chan.pgm_ctr += 1
                        elif cmd_byte == 0xC4:
                            chan.vib_rate = chan.evt_queue[chan.pgm_ctr].arg1
                            self.log.debug(
                                f'| CHAN: {i:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET VIBRT  | RATE: {chan.vib_rate:4}'
                            )
                            chan.pgm_ctr += 1
                        elif cmd_byte == 0xCE:
                            chan.sustain = False
                            for item in chan.notes:
                                if self.note_arr[item.
                                                 note_id].enable is True and self.note_arr[item.
                                                                                           note_id].note_off is False:
                                    self.note_arr[item.note_id].note_off = True

                                    self.log.debug(
                                        f'| CHAN: {i:>4} | PGM: {chan.pgm_ctr:<#6x} | CTRL: {cmd_byte:<#4x} | NOTE OFF   | NOTE: {item.note_id:>4}'
                                    )
                            self.log.debug(
                                f'| CHAN: {i:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | NOTE OFF   | '
                            )
                            chan.pgm_ctr += 1
                        elif cmd_byte == 0xB3:
                            chan.sub_ctr = chan.sub_ctr + 1
                            chan.rtn_ptr = chan.pgm_ctr + 1
                            chan.pgm_ctr = chan.subs[chan.sub_ctr].evt_q_ptr
                            self.log.debug(
                                'CMD 0xB3 call sub: %s ptr: %s chan: %s',
                                chan.sub_ctr, chan.rtn_ptr, chan.pgm_ctr)
                            chan.in_sub = True
                        elif cmd_byte == 0xB4:
                            if chan.in_sub:
                                chan.pgm_ctr = chan.rtn_ptr
                                chan.in_sub = False
                                self.log.debug('CMD 0xB4 end sub chan: %s', i)
                            else:
                                chan.pgm_ctr += 1
                        elif cmd_byte == 0xB2:
                            just_looped = True
                            chan.in_sub = False
                            chan.pgm_ctr = chan.loop_ptr
                            self.log.debug('CMD 0xB2 jump to addr: %s',
                                           chan.pgm_ctr)
                        elif cmd_byte >= 0xCF:
                            ll = stlen_to_ticks(chan.evt_queue[chan.pgm_ctr]
                                                .cmd_byte - 0xCF)
                            if chan.evt_queue[chan.pgm_ctr].cmd_byte == 0xCF:
                                chan.sustain = True
                                ll = 0
                            nn = chan.evt_queue[chan.pgm_ctr].arg1
                            vv = chan.evt_queue[chan.pgm_ctr].arg2
                            uu = chan.evt_queue[chan.pgm_ctr].arg3
                            self.note_q.add(True, 0, nn, 0, vv, i, uu, 0, 0, 0,
                                            0, 0, ll, chan.patch_num)
                            self.log.debug(
                                f'| CHAN: {i:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | ADD NOTE   | NOTE: {note_to_name(nn):>4} | VEL: {vv:5} | LEN: {ll:5} | PATCH: {chan.patch_num:3}'
                            )
                            chan.pgm_ctr += 1
                        elif cmd_byte <= 0xB0:
                            if just_looped:
                                just_looped = False
                                chan.wait_ticks = 0
                            else:
                                chan.pgm_ctr += 1
                                if chan.pgm_ctr > 1:
                                    chan.wait_ticks = chan.evt_queue[chan.
                                                                     pgm_ctr].ticks - chan.evt_queue[chan.
                                                                                                     pgm_ctr
                                                                                                     -
                                                                                                     1].ticks
                                else:
                                    chan.wait_ticks = chan.evt_queue[
                                        chan.pgm_ctr].ticks
                        else:
                            self.log.debug(
                                f'| CHAN: {i:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | CONT EXEC  |'
                            )
                            chan.pgm_ctr += 1
                    if not in_for:
                        self.log.debug(f'| CHAN: {i:>4} | STOP EXEC  | ')
                        break

            if self.channels.count > 0:
                cleared_channel = [False for i in range(len(self.channels))]
                for item in self.note_q:
                    x = self.free_note()
                    self.log.debug(
                        f'| CHAN: {i:>4} | PLAY NOTE  | NOTE: {note_to_name(item.note_num):>4} |'
                    )
                    self.log.debug(
                        f'| CHAN: {i:>4} | FREE NOTE  | NOTE: {x:4} |')
                    if x < 32:
                        self.note_arr[x] = item
                        with self.channels[item.parent] as chan:
                            if cleared_channel[item.parent] is False:
                                cleared_channel[item.parent] = True
                                for item2 in chan.notes:
                                    if self.note_arr[item2.
                                                     note_id].enable is True and self.note_arr[item2.
                                                                                               note_id].note_off is False:
                                        self.note_arr[
                                            item2.note_id].note_off = True

                                        self.log.debug(
                                            f'| CHAN: {item.parent:>4} | NOTE: {item2.note_id:4} | NOTE OFF   |'
                                        )

                            chan.notes.add(x, str(x))
                            pat = item.patch_num
                            nn = item.note_num

                            std_out = (DirectTypes.DIRECT, DirectTypes.WAVE)
                            sqr_out = (DirectTypes.SQUARE1, DirectTypes.SQUARE2)
                            if self.dct_exists(self.directs, pat):
                                self.note_arr[x].output = self.directs[str(
                                    pat)].output
                                self.note_arr[x].env_attn = self.directs[str(
                                    pat)].env_attn
                                self.note_arr[x].env_dcy = self.directs[str(
                                    pat)].env_dcy
                                self.note_arr[x].env_sus = self.directs[str(
                                    pat)].env_sus
                                self.note_arr[x].env_rel = self.directs[str(
                                    pat)].env_rel
                                self.log.debug(
                                    f'| CHAN: {i:>4} | DCT EXISTS | NOTE: {x:4} | T: {self.note_arr[x].output:>7} | ATTN: {self.note_arr[x].env_attn:4} | DCY: {self.note_arr[x].env_dcy:5} | SUS: {self.note_arr[x].env_sus:5} | REL: {self.note_arr[x].env_rel:5}'
                                )
                                if DirectTypes(self.directs[str(pat)]
                                               .output) in std_out:
                                    das = str(self.directs[str(pat)].smp_id)
                                    daf = note_to_freq(
                                        nn +
                                        (60 - self.directs[str(pat)].drum_key),
                                        -1 if self.smp_pool[das].gb_wave else
                                        self.smp_pool[das].freq)
                                    if self.smp_pool[das].gb_wave:
                                        daf /= 2
                                    self.log.debug(
                                        f'| CHAN: {i:>4} | DCT EXISTS | NOTE: {x:4} | STD OUT    | GB: {self.smp_pool[das].gb_wave:6} | DAS: {das:>18} | DAF: {daf:>18}'
                                    )
                                elif DirectTypes(self.directs[str(pat)]
                                                 .output) in sqr_out:
                                    das = f'square{self.directs[str(pat)].gb1 % 4}'
                                    daf = note_to_freq(nn + (
                                        60 - self.directs[str(pat)].drum_key))
                                    print('db', daf)
                                elif DirectTypes(self.directs[str(pat)]
                                                 .output) == DirectTypes.NOISE:
                                    das = f'noise{self.directs[str(pat)].gb1 % 2}{int(random.random() * 10)}'
                                    daf = note_to_freq(nn + (
                                        60 - self.directs[str(pat)].drum_key))
                                    print('dc', daf)
                                else:
                                    das = ''
                            elif self.inst_exists(pat):
                                dct: Direct = self.insts[str(pat)].directs[str(
                                    self.insts[str(pat)].kmaps[str(nn)]
                                    .assign_dct)]
                                self.note_arr[x].output = dct.output
                                self.note_arr[x].env_attn = dct.env_attn
                                self.note_arr[x].env_dcy = dct.env_dcy
                                self.note_arr[x].env_sus = dct.env_sus
                                self.note_arr[x].env_rel = dct.env_rel
                                self.log.debug(
                                    f'| CHAN: {i:>4} | INST EXIST | NOTE: {x:4} | T: {self.note_arr[x].output:>7} | ATTN: {self.note_arr[x].env_attn:4} | DCY: {self.note_arr[x].env_dcy:5} | SUS: {self.note_arr[x].env_sus:5} | REL: {self.note_arr[x].env_rel:5}'
                                )
                                if dct.output in std_out:
                                    das = str(dct.smp_id)
                                    if dct.fix_pitch:
                                        daf = self.smp_pool[das].freq
                                    else:
                                        daf = note_to_freq(
                                            nn, -2 if self.smp_pool[das].gb_wave
                                            else self.smp_pool[das].freq)
                                    self.log.debug(
                                        f'| CHAN: {i:>4} | INST EXIST | NOTE: {x:4} | STD OUT    | FIX: {dct.fix_pitch:5} | DAS: {das:>18} | DAF: {daf:>18}'
                                    )
                                elif dct.output in sqr_out:
                                    das = f'square{dct.gb1 % 4}'
                                    daf = note_to_freq(nn)
                                else:
                                    das = ''
                            elif self.drm_exists(pat):
                                dct: Direct = self.drmkits[str(pat)].directs[
                                    str(nn)]
                                self.note_arr[x].output = dct.output
                                self.note_arr[x].env_attn = dct.env_attn
                                self.note_arr[x].env_dcy = dct.env_dcy
                                self.note_arr[x].env_sus = dct.env_sus
                                self.note_arr[x].env_rel = dct.env_rel
                                self.log.debug(
                                    f'| CHAN: {i:>4} | DRM EXISTS | NOTE: {x:4} | T: {self.note_arr[x].output:>7} | ATTN: {self.note_arr[x].env_attn:4} | DCY: {self.note_arr[x].env_dcy:5} | SUS: {self.note_arr[x].env_sus:5} | REL: {self.note_arr[x].env_rel:5}'
                                )
                                if dct.output in std_out:
                                    das = str(dct.smp_id)
                                    if dct.fix_pitch and not self.smp_pool[das].gb_wave:
                                        daf = self.smp_pool[das].freq
                                    else:
                                        daf = note_to_freq(
                                            dct.drum_key, -2
                                            if self.smp_pool[das].gb_wave else
                                            self.smp_pool[das].freq)
                                    self.log.debug(
                                        f'| CHAN: {i:>4} | DRM EXISTS | NOTE: {x:4} | STD OUT    | FIX: {dct.fix_pitch:5} | GB: {self.smp_pool[das].gb_wave:6} | DAS: {das:>18} | DAF: {daf:>18}'
                                    )
                                elif dct.output in sqr_out:
                                    das = f'square{dct.gb1 % 4}'
                                    daf = note_to_freq(dct.drum_key)
                                elif dct.output == DirectTypes.NOISE:
                                    das = f'noise{dct.gb1 % 2}{int(random.random() * 3)}'
                                    daf = note_to_freq(dct.drum_key)
                                else:
                                    das = ''
                            else:
                                das = ''

                            if das != '':
                                daf = daf * ((2**(1 / 12))**self.transpose)
                                dav = (item.velocity / 0x7F) * (
                                    chan.main_vol / 0x7F) * 255
                                if mutethis:
                                    dav = 0
                                out_type = NoteTypes(self.note_arr[x].output)

                                if out_type == NoteTypes.SQUARE1:
                                    if self.gb1_chan < 32:
                                        with self.note_arr[
                                                self.gb1_chan] as gbn:
                                            gbn: Note
                                            fmod.FSOUND_StopSound(
                                                gbn.fmod_channel)
                                            self.log.debug(
                                                'GB1 chan %s stop sound err: %s',
                                                gbn.fmod_channel, get_err_str())
                                            gbn.fmod_channel = 0
                                            self.channels[
                                                gbn.parent].notes.remove(
                                                    str(self.gb1_chan))
                                            gbn.enable = False
                                    self.gb1_chan = x
                                elif out_type == NoteTypes.SQUARE2:
                                    if self.gb2_chan < 32:
                                        with self.note_arr[
                                                self.gb2_chan] as gbn:
                                            fmod.FSOUND_StopSound(
                                                gbn.fmod_channel)
                                            self.log.debug(
                                                'GB2 chan %s stop sound err: %s',
                                                gbn.fmod_channel, get_err_str())
                                            gbn.fmod_channel = 0
                                            self.channels[
                                                gbn.parent].notes.remove(
                                                    str(self.gb2_chan))
                                            gbn.enable = False
                                    self.gb2_chan = x
                                elif out_type == NoteTypes.WAVE:
                                    if self.gb3_chan < 32:
                                        with self.note_arr[
                                                self.gb3_chan] as gbn:
                                            fmod.FSOUND_StopSound(
                                                gbn.fmod_channel)
                                            self.log.debug(
                                                'GB3 chan %s stop sound err: %s',
                                                gbn.fmod_channel, get_err_str())
                                            gbn.fmod_channel = 0
                                            self.channels[
                                                gbn.parent].notes.remove(
                                                    str(self.gb3_chan))
                                            gbn.enable = False
                                    self.gb3_chan = x
                                elif out_type == NoteTypes.NOISE:
                                    if self.gb4_chan < 32:
                                        with self.note_arr[
                                                self.gb4_chan] as gbn:
                                            fmod.FSOUND_StopSound(
                                                gbn.fmod_channel)
                                            self.log.debug(
                                                'GB4 chan %s stop sound err: %s',
                                                gbn.fmod_channel, get_err_str())
                                            gbn.fmod_channel = 0
                                            self.channels[
                                                gbn.parent].notes.remove(
                                                    str(self.gb4_chan))
                                            gbn.enable = False
                                    self.gb4_chan = x

                                if not mutethis:
                                    self.note_arr[
                                        x].fmod_channel = fmod.FSOUND_PlaySound(
                                            x + 1, self.smp_pool[das].fmod_smp)
                                    self.log.debug(
                                        'Play sound das %s chan %s smp %s err: %s',
                                        das, x, self.smp_pool[das].fmod_smp,
                                        get_err_str())

                                #self.note_arr[x].fmod_channel = item.parent
                                self.note_arr[x].freq = daf
                                self.note_arr[x].phase = NotePhases.INITIAL
                                freq = int(daf * (2**(1 / 12))**
                                           ((chan.pitch_bend - 0x40
                                            ) / 0x40 * chan.pitch_range))
                                fmod.FSOUND_SetFrequency(
                                    item.fmod_channel, freq)
                                self.log.debug(
                                    'Set frequency chan: %s freq: %s err: %s',
                                    item.fmod_channel, freq, get_err_str())
                                vol = int(dav * 0 if not chan.mute else dav * 1)
                                fmod.FSOUND_SetVolume(item.fmod_channel, vol)
                                self.log.debug(
                                    'Set volume: %s chan: %s err: %s', vol,
                                    item.fmod_channel, get_err_str())
                                pan = int(chan.panning * 2)
                                fmod.FSOUND_SetPan(item.fmod_channel, pan)
                                self.log.debug(
                                    'Set panning: %s chan: %s err: %s', pan,
                                    item.fmod_channel, get_err_str())
            self.note_q.clear()

            if self.note_f_ctr > 0:
                for i in range(32):
                    if self.note_arr[i].enable:
                        with self.note_arr[i] as item:
                            if item.output == NoteTypes.DIRECT:
                                if item.note_off and item.phase < NotePhases.RELEASE:
                                    item.env_step = 0
                                    item.phase = NotePhases.RELEASE
                                if item.env_step == 0 or (
                                        item.env_pos == item.env_dest
                                ) or (item.env_step == 0 and
                                      (item.env_pos <= item.env_dest)) or (
                                          item.env_step >= 0 and
                                          item.env_pos >= item.env_dest):
                                    if item.phase == NotePhases.INITIAL:
                                        item.phase = NotePhases.ATTACK
                                        item.env_pos = 0
                                        item.env_dest = 255
                                        item.env_step = item.env_attn
                                    elif item.phase == NotePhases.ATTACK:
                                        item.phase = NotePhases.DECAY
                                        item.env_dest = item.env_sus
                                        item.env_step = (
                                            item.env_dcy - 0x100) / 2
                                    elif item.phase == NotePhases.DECAY:
                                        item.phase = NotePhases.SUSTAIN
                                        item.env_step = 0
                                    elif item.phase == NotePhases.SUSTAIN:
                                        item.phase = NotePhases.SUSTAIN
                                        item.env_step = 0
                                    elif item.phase == NotePhases.RELEASE:
                                        item.phase = NotePhases.NOTEOFF
                                        item.env_dest = 0
                                        item.env_step = item.env_rel - 0x100
                                    elif item.phase == NotePhases.NOTEOFF:
                                        fmod.FSOUND_StopSound(
                                            int(item.fmod_channel))
                                        self.log.debug(
                                            'Stop sound chan %r err: %s',
                                            item.fmod_channel, get_err_str())
                                        item.fmod_channel = 0
                                        self.channels[item.parent].notes.remove(
                                            str(i))
                                        item.enable = False
                                nex = item.env_pos + item.env_step
                                if nex > item.env_dest and item.env_step > 0:
                                    nex = item.env_dest
                                if nex < item.env_dest and item.env_step < 0:
                                    nex = item.env_dest
                                item.env_pos = nex
                                dav = (item.velocity / 0x7F) * (
                                    self.channels[item.parent].main_vol / 0x7F
                                ) * (int(item.env_pos) / 0xFF) * 255
                                if mutethis:
                                    dav = 0
                                vol = int(dav * 0 if self.channels[item.parent]
                                          .mute else dav * 1)
                                fmod.FSOUND_SetVolume(item.fmod_channel, vol)
                                self.log.debug(
                                    'Test set volume: %s chan: %s vol err: %s',
                                    vol, item.fmod_channel, get_err_str())
                            else:
                                if item.note_off and item.phase < NotePhases.RELEASE:
                                    item.env_step = 0
                                    item.phase = NotePhases.RELEASE
                                if item.env_step == 0 or (
                                        item.env_pos == item.env_dest
                                ) or (item.env_step == 0 and
                                      (item.env_pos <= item.env_dest)) or (
                                          item.env_step >= 0 and
                                          item.env_pos >= item.env_dest):
                                    phase: NotePhases = NotePhases(item.phase)
                                    if phase == NotePhases.INITIAL:
                                        item.phase = NotePhases.ATTACK
                                        item.env_pos = 0
                                        item.env_dest = 255
                                        item.env_step = 0x100 - (
                                            item.env_attn * 8)
                                    elif phase == NotePhases.ATTACK:
                                        item.phase = NotePhases.DECAY
                                        item.env_dest = item.env_sus
                                        item.env_step = (-(item.env_dcy)) * 2
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
                                    elif phase == NotePhases.NOTEOFF:
                                        out_type = item.output
                                        if out_type == NoteTypes.SQUARE1:
                                            self.gb1_chan = 255
                                        elif out_type == NoteTypes.SQUARE2:
                                            self.gb2_chan = 255
                                        elif out_type == NoteTypes.WAVE:
                                            self.gb3_chan = 255
                                        elif out_type == NoteTypes.NOISE:
                                            self.gb4_chan = 255
                                        fmod.FSOUND_StopSound(
                                            int(item.fmod_channel))
                                        self.log.debug(
                                            'Stop sound from NOTEOFF %s err: %s',
                                            item.fmod_channel, get_err_str())
                                        item.fmod_channel = 0
                                        item.enable = False
                                        self.channels[item.parent].notes.remove(
                                            str(i))
                                        #input()
                                nex = item.env_pos + item.env_step
                                if nex > item.env_dest and item.env_step > 0:
                                    nex = item.env_dest
                                if nex < item.env_dest and item.env_step < 0:
                                    nex = item.env_dest
                                item.env_pos = nex
                                dav = (item.velocity / 0x7F) * (
                                    self.channels[item.parent].main_vol / 0x7F
                                ) * (int(item.env_pos) / 0xFF) * 255
                                if mutethis:
                                    dav = 0
                                vol = int(dav * 0 if self.channels[item.parent]
                                          .mute else dav * 1)
                                fmod.FSOUND_SetVolume(item.fmod_channel, vol)
                                self.log.debug(
                                    'Set volume: %s chan: %s err: %s', vol,
                                    item.fmod_channel, get_err_str())
            xmmm = False
            for i in range(self.channels.count):
                if self.channels[i].enable:
                    xmmm = True
            if not xmmm or not self.tempo:
                self.stop_song()

        self.last_tick = 0
        self.tick_ctr = 0
        self.incr += 1
        if self.incr >= int(60000 / (self.tempo * self.SAPPY_PPQN)):
            self.tick_ctr = 1
            self.ttl_ticks += 1
            if self.ttl_ticks % 48 == 0:
                self.beats += 1
            self.incr = 0

        self.note_f_ctr = 1

        if self.tempo != self.last_tempo:
            self.last_tempo = self.tempo
            # TODO: EvtProcessor Stuff

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
                if char in string.digits:
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


import time, multiprocessing
d = Decoder()
d.play_song(
    "C:\\Program Files\\BizHawk\\Roms\\Metroid - Zero Mission (U) [!].gba", 5,
    0x8F2C0)

wait = 60000 / (d.tempo * d.SAPPY_PPQN)
print(wait)
e = d.evt_processor_timer
s = time.sleep

starttime = time.time()


def main():
    """Main test method."""
    while True:
        e(1)
        time.sleep(wait / 60000)


if __name__ == '__main__':
    main()
