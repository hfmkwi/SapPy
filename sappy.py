#!/usr/bin/python3
#-*- coding: utf-8 -*-
# pylint disable=C0103, C0326, E1120, R0902, R0903, R0904, R0912, R0913, R0914, R0915, R1702
# pylint: disable=W0614
# TODO: Either use the original FMOD dlls or find a sound engine.
"""Main file."""
import math
import os
import random
import time
from ctypes import *
from enum import IntEnum
from logging import INFO, basicConfig, getLogger
from struct import unpack
from typing import List, NamedTuple

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
    d_raw:    int = int()
    ticks:    int = int()
    evt_code: int = int()
    # yapf: enable


class Decoder(object):
    """Decoder/interpreter for Sappy code."""
    DEBUG = True
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
        self.playing:      bool                        = bool()
        self.record:       bool                        = bool()
        self.beats:        int                         = int()
        self.gb1_chan:     int                         = 0
        self.gb2_chan:     int                         = 0
        self.gb3_chan:     int                         = 0
        self.gb4_chan:     int                         = 0
        self.incr:         int                         = int()
        self.inst_tbl_ptr: int                         = int()
        self.last_tempo:   int                         = int()
        self.layer:        int                         = int()
        self.sng_lst_ptr:  int                         = int()
        self.sng_num:      int                         = int()
        self.sng_ptr:      int                         = int()
        self.tempo:        int                         = int()
        self.ttl_ticks:    int                         = int()
        self.ttl_msecs:    int                         = int()
        self.transpose:    int                         = int()
        self._gbl_vol:     int                         = 100
        self.note_f_ctr:   float                       = float()
        self.prv_tick:     float                       = float()
        self.tick_ctr:     float                       = float()
        self.rip_ears:     list                        = list()
        self.mdrum_map:    list                        = list()
        self.mpatch_map:   list                        = list()
        self.mpatch_tbl:   list                        = list()
        self.fpath:        str                         = str()
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
        self.note_arr:     Collection                  = Collection([Note()] * 32)
        self.nse_wavs:     List[List[str]]             = [[[] for i in range(10)] for i in range(2)]
        self.mul_head:     MultiHeader                 = MultiHeader()
        self.gb_head:      NoiseHeader                 = NoiseHeader()
        self.note_q:       NoteQueue[Note]             = NoteQueue()  # pylint:       disable = E1136
        self.last_evt:     RawMidiEvent                = RawMidiEvent()
        self.smp_head:     SampleHeader                = SampleHeader()
        self.smp_pool:     SampleQueue[Sample]         = SampleQueue()  # pylint:     disable = E1136
        # yapf: enable
        random.seed()
        sz = 0
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
        self._gbl_vol = vol
        fmod.FSOUND_SetSFXMasterVolume(self._gbl_vol)

    @staticmethod
    def dct_exists(dcts: DirectQueue, dct_id: int) -> bool:
        """Check if a direct exists in a specfied `DirectQueue`."""
        return str(dct_id) in dcts

    @staticmethod
    def flip_lng(val: int) -> int:
        """Truncate and flip the byteorder of a 4 byte integer."""
        return int.from_bytes(val.to_bytes(4, 'big'), 'little')

    @staticmethod
    def flip_int(val: int) -> int:
        """Truncate and flip the byteorder of a 2 byte integer."""
        return int.from_bytes(val.to_bytes(2, 'big'), 'little')

    @staticmethod
    def set_direct(queue: DirectQueue, dct_key: str,
                   inst_head: InstrumentHeader, dct_head: DirectHeader,
                   gb_head: NoiseHeader) -> None:
        # """UKNOWN"""
        # yapf: disable
        direct = queue[dct_key]
        queue[dct_key] = direct._replace(
            drum_key  = inst_head.drum_pitch,
            output    = DirectTypes(inst_head.channel & 7),
            env_attn  = dct_head.attack,
            env_dcy   = dct_head.hold,
            env_sus   = dct_head.sustain,
            env_rel   = dct_head.release,
            raw0      = dct_head.b0,
            raw1      = dct_head.b1,
            gb1       = gb_head.b2,
            gb2       = gb_head.b3,
            gb3       = gb_head.b4,
            gb4       = gb_head.b5,
            fix_pitch = (inst_head.channel & 0x08) == 0x08,
            reverse   = (inst_head.channel & 0x10) == 0x10,
        )
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
        return str(patch) in self.drmkits

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
        note = 255
        for i in range(32):
            if not self.note_arr[i].enable:
                note = i
        return note

    def get_smp(self, q: Collection, dct_key: str, dct_head: DirectHeader,
                smp_head: SampleHeader, use_readstr: bool) -> None:
        """UNKNOWN"""
        D: Direct = q[dct_key]
        q[dct_key] = D._replace(smp_id=dct_head.smp_head)
        D: Direct = q[dct_key]
        sid = q[dct_key].smp_id
        s_sid = str(sid)
        if not self.smp_exists(sid):
            self.smp_pool.add(s_sid)
            if D.output == DirectTypes.DIRECT:
                self.smp_head = rd_smp_head(1, File.gba_ptr_to_addr(sid))
                smp: Sample = self.smp_pool[s_sid]
                if use_readstr:
                    smp_data = self.wfile.rd_str(smp_head.size,
                                                 self.wfile.rd_addr)
                else:
                    smp_data = self.wfile._file.tell()
                self.smp_pool[s_sid] = smp._replace(
                    size=smp_head.size,
                    freq=smp_head.freq * 64,
                    loop_start=smp_head.loop,
                    loop=smp_head.flags > 0,
                    gb_wave=False,
                    smp_data=smp_data)
            else:
                raise Exception

    get_mul_smp = get_smp

    def inst_exists(self, patch: int) -> bool:
        """Check if an instrument on the specified MIDI patch is defined."""
        return str(patch) in self.insts

    @staticmethod
    def kmap_exists(kmaps: KeyMapQueue, kmap_id: int) -> bool:
        """Check if a keymap is defined."""
        return str(kmap_id) in kmaps

    def note_in_channel(self, note_id: bytes, chnl_id: int) -> bool:
        """Check if a note belongs to a channel."""
        return self.note_arr[note_id].parent == chnl_id

    def patch_exists(self, lp: int) -> bool:
        """UKNOWN"""
        lp = str(lp)
        return lp in self.directs or self.inst_exists(lp) or self.drm_exists(lp)

    # yapf: disable
    def play_song(self, fpath: str, sng_num: int, sng_list_ptr: int = None,
                  record: bool = False, record_to: str = "midiout.mid"):
        """Play a song from an AGB rom that uses the Sappy Sound Engine."""
        # yapf: enable
        self.fpath = fpath
        self.sng_lst_ptr = sng_list_ptr
        self.sng_num = sng_num

        if self.playing:
            # TODO: raise SONG_STOP
            pass

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
            self.note_arr[i] = self.note_arr[i]._replace(enable=False)

        self.wfile = open_file(self.fpath, 1)
        assert self.wfile is not None
        a = self.wfile.rd_gba_ptr(self.sng_lst_ptr + sng_num * 8)
        self.sng_ptr = a
        self.layer = self.wfile.rd_ltendian(4)
        b = self.wfile.rd_byte(a)
        self.inst_tbl_ptr = self.wfile.rd_gba_ptr(a + 4)

        # TODO: raise LOADING_0

        xta = SubroutineQueue()
        for i in range(b):
            loop_offset = -1
            self.channels.add()
            pc = self.wfile.rd_gba_ptr(a + 4 + (i + 1) * 4)
            self.channels[i] = self.channels[i]._replace(track_ptr=pc)
            xta.clear()
            self.log.debug('HEADER STUFF')
            while True:
                self.wfile.rd_addr = pc
                c = self.wfile.rd_byte()
                if 0x00 <= c <= 0xB0 or c == 0xCE or c == 0xCF or c == 0xB4:
                    pc += 1
                elif c == 0xB9:
                    pc += 4
                elif c >= 0xB5 and c <= 0xCD:
                    pc += 2
                elif c == 0xB2:
                    loop_offset = self.wfile.rd_gba_ptr(self.wfile.rd_addr)
                    pc += 5
                    break
                elif c == 0xB3:
                    sub = self.wfile.rd_gba_ptr()
                    self.log.debug('SubRoutine: %s', sub)
                    xta.add(sub)
                    pc += 5
                elif c >= 0xD0 and c <= 0xFF:
                    pc += 1
                    while self.wfile.rd_byte() < 0x80:
                        pc += 1
                self.log.debug('PGM: %s, CTL: %s', hex(pc), hex(c))
                if c == 0xb1:
                    break
            self.channels[i] = self.channels[i]._replace(
                track_len=pc - self.channels[i].track_ptr)
            pc = self.wfile.rd_gba_ptr(a + 4 + (i + 1) * 4)
            cticks = 0
            lc = 0xbe
            lln: List = [None] * 66
            llv: List = [None] * 66
            lla: List = [None] * 66
            lp = 0
            insub = 0
            t_r = 0
            self.channels[i] = self.channels[i]._replace(loop_ptr=-1)
            chan: Channel = self.channels[i]
            cdr = 0
            s_cdr = str(cdr)
            self.log.info("READING CHANNEL %s", i + 1)
            while True:
                self.wfile.rd_addr = pc
                chan: Channel = self.channels[i]
                if pc >= loop_offset and chan.loop_ptr == -1 and loop_offset != -1:
                    self.channels[i] = chan._replace(
                        loop_ptr=chan.evt_queue.count + 1)
                    chan: Channel = self.channels[i]
                c = self.wfile.rd_byte()
                self.log.debug('PGM: %s, CTL: %s', hex(pc), hex(c))
                # time.sleep(0.1)
                if (0xb5 <= c < 0xc5 and c != 0xb9) or c == 0xcd:
                    D = self.wfile.rd_byte()
                    if c == 0xbc:
                        t_r = sbyte_to_int(D)
                    elif c == 0xbd:
                        lp = D
                    elif c == 0xbe or c == 0xbf or c == 0xc0 or c == 0xc4 or c == 0xcd:
                        lc = c
                    self.channels[i].evt_queue.add(cticks, c, D, 0, 0)
                    self.log.debug('Event(%s, %s, %s, 0, 0)', cticks, c, D)
                    pc += 2
                elif 0xc4 < c < 0xcf:
                    self.channels[i].evt_queue.add(cticks, c, 0, 0, 0)
                    self.log.debug('Event(%s, %s, 0, 0, 0)', cticks, c)
                    pc += 1
                elif c == 0xb9:
                    D = self.wfile.rd_byte()
                    e = self.wfile.rd_byte()
                    F = self.wfile.rd_byte()
                    self.channels[i].evt_queue.add(cticks, c, D, e, F)
                    self.log.debug('Event(%s, %s, %s, %s, %s)', cticks, c, D, e,
                                   F)
                    pc += 4
                elif c == 0xb4:
                    if insub == 1:
                        pc = rpc
                        insub = 0
                    else:
                        pc += 1
                elif c == 0xb3:
                    rpc = pc + 5
                    insub = 1
                    # self.wfile.rd_addr -= 4
                    pc = self.wfile.rd_gba_ptr(self.wfile.rd_addr)
                elif 0xcf <= c <= 0xff:
                    pc += 1
                    lc = c
                    g = False
                    nc = 0
                    while not g:
                        D = self.wfile.rd_byte()
                        if D >= 0x80:
                            if nc == 0:
                                pn = lln[nc] + t_r
                                self.channels[i].evt_queue.add(
                                    cticks, c, pn, llv[nc], lla[nc])
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
                            pn = D + t_r
                            self.channels[i].evt_queue.add(cticks, c, pn, e, F)
                        if not self.patch_exists(lp):
                            self.inst_head = rd_inst_head(
                                1, self.inst_tbl_ptr + (lp + 1) * 12)
                            s_lp = str(lp)
                            s_pn = str(pn)
                            s_cdr = str(cdr)
                            out = (DirectTypes.DIRECT, DirectTypes.WAVE)
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
                                        self.drm_head.dct_tbl + pn * 12 + 2))
                                self.drmkits.add(s_lp)
                                self.drmkits[s_lp].add(s_pn)
                                self.set_direct(self.drmkits[s_lp].directs,
                                                s_pn, self.inst_head,
                                                self.dct_head, self.gb_head)
                                if self.insts[s_lp].directs[
                                        s_cdr].output in out:
                                    self.get_smp(self.drmkits[s_lp].directs,
                                                 s_pn, self.dct_head,
                                                 self.smp_head, False)
                            elif self.inst_head.channel & 0x40 == 0x40:  # Multi
                                self.mul_head = rd_mul_head(1)
                                self.insts.add(s_lp)
                                self.insts[s_lp].kmaps.add(0, s_pn)
                                dct: Direct = self.insts[s_lp].kmaps[s_pn]
                                self.insts[s_lp].kmaps[s_pn] = dct._replace(
                                    assign_dct=self.wfile.rd_byte(
                                        File.gba_ptr_to_addr(
                                            self.mul_head.kmap) + pn))
                                cdr = self.insts[s_lp].kmaps[s_pn].assign_dct
                                s_cdr = str(cdr)
                                self.inst_head = rd_inst_head(
                                    1,
                                    File.gba_ptr_to_addr(
                                        self.mul_head.dct_tbl + cdr * 12))
                                self.dct_head = rd_dct_head(1)
                                self.gb_head = rd_nse_head(
                                    1,
                                    File.gba_ptr_to_addr(
                                        self.mul_head.dct_tbl + cdr * 12) + 2)
                                self.insts[s_lp].directs.add(s_cdr)
                                self.set_direct(self.insts[s_lp].directs, s_cdr,
                                                self.inst_head, self.dct_head,
                                                self.gb_head)
                                if self.insts[s_lp].directs[
                                        s_cdr].output in out:
                                    self.get_smp(self.insts[s_lp].directs,
                                                 s_cdr, self.dct_head,
                                                 self.smp_head, False)
                            else:  # Direct/GB Sample
                                self.dct_head = rd_dct_head(1)
                                self.gb_head = rd_nse_head(
                                    1, self.inst_tbl_ptr + lp * 12 + 2)
                                self.directs.add(s_lp)
                                self.set_direct(self.directs, s_lp,
                                                self.inst_head, self.dct_head,
                                                self.gb_head)
                                if self.directs[s_lp].output in out:
                                    self.get_smp(self.directs, s_lp,
                                                 self.dct_head, self.smp_head,
                                                 True)
                        else:  # Patch exists
                            self.inst_head = rd_inst_head(
                                1, self.inst_tbl_ptr + lp * 12)
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
                                        self.drm_head.dct_tbl + pn * 12) + 2)
                                if not self.dct_exists(
                                        self.drmkits[s_lp].directs, pn):
                                    self.drmkits[s_lp].directs.add(s_pn)
                                    self.set_direct(self.drmkits[s_lp].directs,
                                                    s_pn, self.inst_head,
                                                    self.dct_head, self.gb_head)
                                    if self.drmkits[s_lp].directs[
                                            s_pn].output in out:
                                        self.get_mul_smp(
                                            self.drmkits[s_lp].directs, s_pn,
                                            self.dct_head, self.smp_head, False)
                            elif self.inst_head.channel * 0x40 == 0x40:
                                self.mul_head = rd_mul_head(1)
                                if not self.kmap_exists(self.insts[s_lp].kmaps,
                                                        pn):
                                    self.insts[s_lp].kmaps.add(
                                        self.wfile.rd_byte(
                                            self.wfile.gba_ptr_to_addr(
                                                self.mul_head.kmap) + pn), s_pn)
                                    cdr = self.insts[s_lp].kmaps[
                                        s_pn].assign_dct
                                    s_cdr = str(cdr)
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
                                    if not self.dct_exists(
                                            self.insts[s_lp].directs, cdr):
                                        self.insts[s_lp].directs.add(s_cdr)
                                        self.set_direct(
                                            self.insts[s_lp].directs, s_cdr,
                                            self.inst_head, self.dct_head,
                                            self.gb_head)
                                        if self.insts[s_lp].directs[
                                                s_cdr].output in out:
                                            self.get_mul_smp(
                                                self.insts[s_lp].directs, s_cdr,
                                                self.dct_head, self.smp_head,
                                                False)
                elif 0x00 <= c < 0x80:
                    if lc < 0xCF:
                        self.channels[i].evt_queue.add(cticks, lc, c, 0, 0)
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
                                    pn = lln[nc] + t_r
                                    s_pn = str(pn)
                                    self.channels[i].evt_queue.add(
                                        cticks, c, pn, llv[nc], lla[nc])
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
                                pn = D + t_r
                                s_pn = str(pn)
                                self.channels[i].evt_queue.add(
                                    cticks, c, pn, e, F)
                            if not self.patch_exists(lp):
                                self.inst_head = rd_inst_head(
                                    1, self.inst_tbl_ptr + lp * 12)
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
                                    self.drmkits.add(s_lp)
                                    self.drmkits[s_lp].directs.add(s_pn)
                                    self.set_direct(self.drmkits[s_lp].directs,
                                                    s_pn, self.inst_head,
                                                    self.dct_head, self.gb_head)
                                    if self.drmkits[s_lp].directs[
                                            s_pn].output in out:
                                        self.get_smp(self.drmkits[s_lp].directs,
                                                     s_pn, self.dct_head,
                                                     self.smp_head, True)
                                elif self.inst_head.channel & 0x40 == 0x40:
                                    self.mul_head = rd_mul_head(1)
                                    self.insts.add(s_lp)
                                    self.insts[s_lp].kmaps.add(
                                        File.gba_ptr_to_addr(
                                            self.mul_head.kmap) + pn, s_pn)
                                    cdr = self.insts[s_lp].kmaps[
                                        s_pn].assign_dct
                                    s_cdr = str(cdr)
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
                                    self.insts[s_lp].directs.add(s_cdr)
                                    self.set_direct(self.insts[s_lp].directs,
                                                    s_cdr, self.inst_head,
                                                    self.dct_head, self.gb_head)
                                    if self.insts[s_lp].directs[
                                            s_cdr].output in out:
                                        self.get_smp(self.insts[s_lp].directs,
                                                     s_cdr, self.dct_head,
                                                     self.smp_head, False)
                            else:
                                self.inst_head = rd_inst_head(
                                    1, self.inst_tbl_ptr + (lp + 1) * 12)
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
                                    if not self.dct_exists(
                                            self.drmkits[s_lp].directs, pn):
                                        self.drmkits[s_lp].directs.add(s_pn)
                                        self.set_direct(
                                            self.drmkits[s_lp].directs, s_pn,
                                            self.inst_head, self.dct_head,
                                            self.gb_head)
                                        if self.drmkits[s_lp].directs[
                                                s_pn].output in out:
                                            self.get_smp(
                                                self.drmkits[s_lp].directs,
                                                s_pn, self.dct_head,
                                                self.smp_head, False)
                                elif self.inst_head.channel & 0x40 == 0x40:
                                    self.mul_head = rd_mul_head(1)
                                    if not self.kmap_exists(
                                            self.insts[s_lp].kmaps, pn):
                                        self.insts[s_lp].kmaps.add(
                                            self.wfile.rd_byte(
                                                File.gba_ptr_to_addr(
                                                    self.mul_head.kmap) + pn),
                                            s_pn)
                                        cdr = self.insts[s_lp].kmaps[
                                            s_pn].assign_dct
                                        s_cdr = str(cdr)
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
                                        if not self.dct_exists(
                                                self.insts[s_lp].dcts, cdr):
                                            self.insts[s_lp].dcts.add(s_cdr)
                                            self.set_direct(
                                                self.insts[s_lp].dcts, s_cdr,
                                                self.inst_head, self.dct_head,
                                                self.gb_head)
                                            if self.insts[s_lp].dcts[
                                                    s_cdr].output in out:
                                                self.get_mul_smp(
                                                    self.insts[s_lp].dcts,
                                                    s_cdr, self.dct_head,
                                                    self.smp_head, False)
                elif 0x80 <= c <= 0xB0:
                    self.channels[i].evt_queue.add(cticks, c, 0, 0, 0)
                    cticks += stlen_to_ticks(c - 0x80)
                    pc += 1
                if c in (0xB1, 0xB2):
                    break
            self.channels[i].evt_queue.add(cticks, c, 0, 0, 0)
        fmod.FSOUND_Init(44100, 64, 0)
        self.log.info('init FMOD err: %s', fsound_get_error())
        fmod.FSOUND_SetSFXMasterVolume(self.gbl_vol)
        self.log.info('set volume to: %s err: %s', self.gbl_vol,
                      fsound_get_error())
        quark = 0
        csm = FSoundChannelSampleMode
        sm = FSoundModes
        for i in range(len(self.smp_pool) - 1):
            quark += 1
            smp: Sample = self.smp_pool[i + 1]
            self.log.info('#%s - %s - %s', quark, smp.gb_wave, smp.smp_data)
            if smp.gb_wave:
                try:
                    val = int(smp.smp_data)
                except:
                    val = 0
                if val == 0:
                    with open_new_file('temp.raw', 2) as f:
                        f.wr_str(smp.smp_data)
                    fmod_smp = fmod.FSOUND_Sample_Load(
                        csm.FSOUND_FREE, b'temp.raw', sm.FSOUND_8BITS +
                        sm.FSOUND_LOADRAW + sm.FSOUND_LOOP_NORMAL +
                        sm.FSOUND_MONO + sm.FSOUND_UNSIGNED, 0, 0)
                    #print(
                    #    f'load smp: {fmod_smp} err: {fsound_get_error_string(fmod.FSOUND_GetError())}'
                    #)
                    self.smp_pool[i] = smp._replace(fmod_smp=fmod_smp)
                    smp: Sample = self.smp_pool[i]
                    fmod.FSOUND_Sample_SetLoopPoints(smp.fmod_smp, 0, 31)
                    os.remove('temp.raw')
                else:
                    fmod_smp = fmod.FSOUND_Sample_Load(
                        csm.FSOUND_FREE,
                        fpath.encode(encoding='ascii'),
                        sm.FSOUND_8BITS + sm.FSOUND_LOADRAW +
                        sm.FSOUND_LOOP_NORMAL + sm.FSOUND_MONO +
                        sm.FSOUND_UNSIGNED,
                        ord(smp.smp_data[0]),
                        smp.size)
                    #print(
                    #    f'load smp: {fmod_smp} err: {fsound_get_error_string(fmod.FSOUND_GetError())}'
                    #)
                    self.smp_pool[i] = smp._replace(fmod_smp=fmod_smp)
                    smp: Sample = self.smp_pool[i]
                    fmod.FSOUND_Sample_SetLoopPoints(smp.fmod_smp, 0, 31)
            else:
                try:
                    val = int(smp.smp_data)
                except:
                    val = 0
                if val == 0:
                    with open_new_file('temp.raw', 2) as f:
                        self.log.debug('writing str %s', smp.smp_data)
                        f.wr_str(smp.smp_data)
                    fmod_smp = fmod.FSOUND_Sample_Load(
                        csm.FSOUND_FREE,
                        'temp.raw'.encode(encoding='ascii'),
                        sm.FSOUND_8BITS + sm.FSOUND_LOADRAW +
                        sm.FSOUND_LOOP_NORMAL
                        if smp.loop else 0 + sm.FSOUND_MONO + sm.FSOUND_SIGNED,
                        0,
                        0)
                    #print(
                    #    f'no gbwav temp.raw load smp: {fmod_smp} err: {fsound_get_error_string(fmod.FSOUND_GetError())}'
                    #)
                    self.smp_pool[i] = smp._replace(fmod_smp=fmod_smp)
                    self.log.debug('smp %s fmod_smp %s', i,
                                   self.smp_pool[i].fmod_smp)
                    smp: Sample = self.smp_pool[i]
                    fmod.FSOUND_Sample_SetLoopPoints(
                        smp.fmod_smp, smp.loop_start, smp.size - 1)
                    os.remove('temp.raw')
                else:
                    print(smp.size)
                    fmod_smp = fmod.FSOUND_Sample_Load(
                        csm.FSOUND_FREE,
                        fpath.encode(encoding='ascii'),
                        sm.FSOUND_8BITS + sm.FSOUND_LOADRAW +
                        (sm.FSOUND_LOOP_NORMAL if smp.loop else 0) +
                        sm.FSOUND_MONO + sm.FSOUND_SIGNED,
                        smp.smp_data,
                        smp.size)
                    #print(
                    #    f'no gbwav fpath load smp: {fmod_smp} err: {fsound_get_error_string(fmod.FSOUND_GetError())}'
                    #)
                    self.smp_pool[i] = smp._replace(fmod_smp=fmod_smp)
                    smp: Sample = self.smp_pool[i]
                    fmod.FSOUND_Sample_SetLoopPoints(
                        smp.fmod_smp, smp.loop_start, smp.size - 1)
        for i in range(10):
            self.smp_pool.add(f'noise0{i}')
            smp: Sample = self.smp_pool[f'noise0{i}']
            random.seed()
            f_nse = f'noise0{i}.raw'.encode(encoding='ascii')
            with open_new_file(f_nse, 2) as f:
                f.wr_str(self.nse_wavs[0][i])
            self.smp_pool[f'noise0{i}'] = smp._replace(
                freq=7040,
                size=16384,
                smp_data='',
                fmod_smp=fmod.FSOUND_Sample_Load(
                    csm.FSOUND_FREE, f_nse,
                    sm.FSOUND_8BITS + sm.FSOUND_LOADRAW + sm.FSOUND_LOOP_NORMAL
                    + sm.FSOUND_MONO + sm.FSOUND_UNSIGNED, 0, 0))
            smp: Sample = self.smp_pool[f'noise0{i}']
            self.log.info('loaded noise0%s fmod_smp: %s err: %s', i,
                          smp.fmod_smp, fsound_get_error())
            fmod.FSOUND_Sample_SetLoopPoints(smp.fmod_smp, 0, 16383)
            self.log.info('set noise0%s loop points err: %s', i,
                          fsound_get_error())
            os.remove(f_nse)
            self.smp_pool.add(f'noise1{i}')
            f_nse = f'noise1{i}.raw'.encode(encoding='ascii')
            with open_new_file(f_nse, 2) as f:
                f.wr_str(self.nse_wavs[1][i])
            self.smp_pool[f'noise1{i}'] = smp._replace(
                freq=7040,
                size=256,
                smp_data='',
                fmod_smp=fmod.FSOUND_Sample_Load(
                    csm.FSOUND_FREE, f_nse,
                    sm.FSOUND_8BITS + sm.FSOUND_LOADRAW + sm.FSOUND_LOOP_NORMAL
                    + sm.FSOUND_MONO + sm.FSOUND_UNSIGNED, 0, 0))
            smp: Sample = self.smp_pool[f'noise1{i}']
            self.log.info('loaded noise1%s fmod_smp: %s err: %s', i,
                          smp.fmod_smp, fsound_get_error())
            fmod.FSOUND_Sample_SetLoopPoints(smp.fmod_smp, 0, 255)
            self.log.info('set noise1%s loop points err: %s', i,
                          fsound_get_error())
            os.remove(f_nse)

        b1 = chr(int(0x80 + 0x7F * self.GB_SQ_MULTI))
        b2 = chr(int(0x80 - 0x7F * self.GB_SQ_MULTI))
        for mx2 in range(4):
            sq = f'square{mx2}'
            self.smp_pool.add(sq)
            smp: Sample = self.smp_pool[sq]
            if mx2 == 3:
                smp_dat = "".join([b1] * 24 + [b2] * 8)
            else:
                smp_dat = "".join([b1] * (
                    (mx2 + 2)**2) + [b2] * (32 - (mx2 + 2)**2))
            self.log.debug('smp dat: %s', smp_dat)
            f_sq = (sq + '.raw').encode('ascii')
            with open_new_file(f_sq, 2) as f:
                f.wr_str(smp_dat)
            self.smp_pool[sq] = smp._replace(
                smp_data='',
                freq=7040,
                size=32,
                fmod_smp=fmod.FSOUND_Sample_Load(
                    csm.FSOUND_FREE, f_sq, sm.FSOUND_8BITS + sm.FSOUND_LOADRAW +
                    sm.FSOUND_LOOP_NORMAL + sm.FSOUND_MONO + sm.FSOUND_UNSIGNED,
                    0, 0))
            self.log.info('load %s err: %s', sq, fsound_get_error())
            smp: Sample = self.smp_pool[sq]
            fmod.FSOUND_Sample_SetLoopPoints(smp.fmod_smp, 0, 31)
            self.log.info('set %s loop points err: %s', sq, fsound_get_error())
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
        print('Done')

    def smp_exists(self, note_id: int) -> bool:
        """Check if a sample exists in the available sample pool."""
        return str(note_id) in self.smp_pool

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
        if self.tick_ctr > 0:
            for i in range(32):
                note: Note = self.note_arr[i]
                if note.enable and note.wait_ticks > 0:
                    self.note_arr[i] = note._replace(
                        wait_ticks=note.wait_ticks -
                        (self.tick_ctr - self.prv_tick))
                    note: Note = self.note_arr[i]
                if note.wait_ticks <= 0 and note.enable and not note.note_off:
                    if not self.channels[note.parent].sustain:
                        self.note_arr[i] = note._replace(note_off=True)
                    note: Note = self.note_arr[i]
            for i in range(len(self.channels)):
                if not self.channels[i].enable:
                    continue
                chan: Channel = self.channels[i]
                for ep in range(len(self.rip_ears)):
                    if self.rip_ears[ep] == chan.patch_num:
                        self.channels[i] = chan._replace(mute=True)
                        chan: Channel = self.channels[i]

                if chan.wait_ticks > 0:
                    self.channels[i] = chan._replace(
                        wait_ticks=chan.wait_ticks -
                        (self.tick_ctr - self.prv_tick))
                    chan: Channel = self.channels[i]
                chan: Channel = self.channels[i]
                in_for = True
                looped = False
                self.log.debug('Channel wait_ticks: %s', chan.wait_ticks)
                while chan.wait_ticks <= 0:
                    chan: Channel = self.channels[i]
                    cmd = chan.evt_queue[chan.pgm_ctr].cmd_byte
                    self.log.debug('PGM: %s, CMD: %s', hex(chan.pgm_ctr),
                                   hex(cmd))
                    if cmd == 0xB1:
                        self.channels[i] = chan._replace(enable=False)
                        self.log.debug('Disabled channel %s', i)
                        chan: Channel = self.channels[i]
                        in_for = False
                        break
                    elif cmd == 0xB9:
                        self.channels[i] = chan._replace(
                            pgm_ctr=chan.pgm_ctr + 1)
                        chan: Channel = self.channels[i]
                    elif cmd == 0xBB:
                        self.tempo = chan.evt_queue[chan.pgm_ctr].arg1 * 2
                        self.channels[i] = chan._replace(
                            pgm_ctr=chan.pgm_ctr + 1)
                        chan: Channel = self.channels[i]
                    elif cmd == 0xBC:
                        self.channels[i] = chan._replace(
                            transpose=sbyte_to_int(
                                chan.evt_queue[chan.pgm_ctr].arg1),
                            pgm_ctr=chan.pgm_ctr + 1)
                        chan: Channel = self.channels[i]
                    elif cmd == 0xBD:
                        pn = chan.evt_queue[chan.pgm_ctr].arg1
                        if self.dct_exists(self.directs, chan.patch_num):
                            out_type = self.directs[str(chan.patch_num)].output
                        elif self.inst_exists(chan.patch_num):
                            out_type = ChannelTypes.MUL_SMP
                        elif self.drm_exists(chan.patch_num):
                            out_type = ChannelTypes.DRUMKIT
                        else:
                            out_type = ChannelTypes.NULL
                        self.channels[i] = chan._replace(
                            patch_num=pn,
                            output=out_type,
                            pgm_ctr=chan.pgm_ctr + 1)
                        chan: Channel = self.channels[i]
                    elif cmd == 0xBE:
                        self.channels[i] = chan._replace(
                            main_vol=chan.evt_queue[chan.pgm_ctr].arg1)
                        chan: Channel = self.channels[i]
                        for note in chan.notes:
                            note: Note = self.note_arr[note.note_id]
                            if note.enable and note.parent == i:
                                dav = (note.velocity / 0x7F) * (
                                    chan.main_vol / 0x7F) * (
                                        int(note.env_pos) / 0xFF * 255)
                                if mutethis:
                                    dav = 0
                                fmod.FSOUND_SetVolume(
                                    note.fmod_channel,
                                    c_float(dav * 0 if chan.mute else dav * 1))
                                self.log.debug(
                                    'CMD 0xBE set vol chan %s err: %s',
                                    note.fmod_channel, fsound_get_error())
                        self.channels[i] = chan._replace(
                            pgm_ctr=chan.pgm_ctr + 1)
                        chan: Channel = self.channels[i]
                    elif cmd == 0xBF:
                        self.channels[i] = chan._replace(
                            panning=chan.evt_queue[chan.pgm_ctr].arg1)
                        chan: Channel = self.channels[i]
                        for note in chan.notes:
                            note: Note = self.note_arr[note.note_id]
                            if note.enable and note.parent == i:
                                fmod.FSOUND_SetPan(note.fmod_channel,
                                                   chan.panning * 2)
                                self.log.debug(
                                    'CMD 0xBF set pan chan %s err; %s',
                                    note.fmod_channel, fsound_get_error())
                        self.channels[i] = chan._replace(
                            pgm_ctr=chan.pgm_ctr + 1)
                        chan: Channel = self.channels[i]
                    elif cmd == 0xC0:
                        self.channels[i] = chan._replace(
                            pgm_ctr=chan.pgm_ctr + 1,
                            pitch=chan.evt_queue[chan.pgm_ctr].arg1)
                        chan: Channel = self.channels[i]
                        for note in chan.notes:
                            note: Note = self.note_arr[note.note_id]
                            if note.enable and note.parent == i:
                                freq = c_float(27.5 * 2**
                                               ((chan.pitch - 21) / 12))
                                fmod.FSOUND_SetFrequency(
                                    note.fmod_channel, freq)
                                self.log.debug(
                                    'CMD 0xC0 set freq chan %s note %s err: %s',
                                    note.fmod_channel, note.note_id,
                                    fsound_get_error())
                    elif cmd == 0xC1:
                        self.channels[i] = chan._replace(
                            pgm_ctr=chan.pgm_ctr + 1,
                            pitch_range=sbyte_to_int(
                                chan.evt_queue[chan.pgm_ctr].arg1))
                        chan: Channel = self.channels[i]
                        for note in chan.notes:
                            note: Note = self.note_arr[note.note_id]
                            if note.enable and note.parent == i:
                                freq = c_float(27.5 * 2**
                                               ((chan.pitch - 21) / 12))
                                fmod.FSOUND_SetFrequency(
                                    note.fmod_channel, freq)
                                self.log.debug(
                                    'CMD 0xC0 set freq chan %s note %s err: %s',
                                    note.fmod_channel, note.note_id,
                                    fsound_get_error())
                    elif cmd == 0xC2:
                        self.channels[i] = chan._replace(
                            pgm_ctr=chan.pgm_ctr + 1,
                            vib_depth=chan.evt_queue[chan.pgm_ctr].arg1)
                        chan: Channel = self.channels[i]
                    elif cmd == 0xC4:
                        self.channels[i] = chan._replace(
                            pgm_ctr=chan.pgm_ctr + 1,
                            vib_rate=chan.evt_queue[chan.pgm_ctr].arg1)
                        chan: Channel = self.channels[i]
                    elif cmd == 0xCE:
                        for item in chan.notes:
                            temp: Note = self.note_arr[item.note_id]
                            if temp.enable and not temp.note_off:
                                self.note_arr[item.note_id] = temp._replace(
                                    note_off=True)
                        self.channels[i] = chan._replace(
                            pgm_ctr=chan.pgm_ctr + 1, sustain=False)
                        chan: Channel = self.channels[i]
                    elif cmd == 0xB3:
                        self.channels[i] = chan._replace(
                            pgm_ctr=chan.subs[chan.sub_ctr].evt_q_ptr,
                            sub_ctr=chan.sub_ctr + 1,
                            rtn_ptr=chan.pgm_ctr + 1,
                            in_sub=True)
                        chan: Channel = self.channels[i]
                    elif cmd == 0xB4:
                        if chan.in_sub:
                            self.channels[i] = chan._replace(
                                pgm_ctr=chan.rtn_ptr, in_sub=False)
                        else:
                            self.channels[i] = chan._replace(
                                pgm_ctr=chan.pgm_ctr + 1)
                        chan: Channel = self.channels[i]
                    elif cmd == 0xB2:
                        looped = True
                        self.channels[i] = chan._replace(
                            pgm_ctr=chan.loop_ptr, in_sub=False)
                        chan: Channel = self.channels[i]
                    elif cmd >= 0xCF:
                        ll = stlen_to_ticks(
                            chan.evt_queue[chan.pgm_ctr].cmd_byte - 0xCF) + 1
                        if chan.evt_queue[chan.pgm_ctr].cmd_byte == 0xCF:
                            self.channels[i] = chan._replace(sustain=True)
                            chan: Channel = self.channels[i]
                            ll = 0
                        nn = chan.evt_queue[chan.pgm_ctr].arg1
                        vv = chan.evt_queue[chan.pgm_ctr].arg2
                        uu = chan.evt_queue[chan.pgm_ctr].arg3
                        self.log.debug('nn %s vv %s uu %s', nn, vv, uu)
                        self.note_q.add(True, 0, nn, 0, vv, i, uu, 0, 0, 0, 0,
                                        0, ll, chan.patch_num)
                        self.channels[i] = chan._replace(
                            pgm_ctr=chan.pgm_ctr + 1)
                    elif cmd <= 0xB0:
                        if looped:
                            looped = False
                            self.channels[i] = chan._replace(wait_ticks=0)
                            chan: Channel = self.channels[i]
                        else:
                            pc = chan.pgm_ctr + 1
                            if pc > 1:
                                wt = chan.evt_queue[chan.
                                                    pgm_ctr].ticks - chan.evt_queue[chan.
                                                                                    pgm_ctr
                                                                                    -
                                                                                    1].ticks
                            else:
                                wt = chan.evt_queue[chan.pgm_ctr].ticks
                            self.channels[i] = chan._replace(
                                pgm_ctr=pc, wait_ticks=wt)
                            chan: Channel = self.channels[i]
                    else:
                        self.channels[i] = chan._replace(
                            pgm_ctr=chan.pgm_ctr + 1)
                        chan: Channel = self.channels[i]
                if not in_for:
                    break
            if self.channels.count > 0:
                clear_channel: List[bool] = [
                    bool() for i in range(len(self.channels))
                ]
                for i in range(len(self.note_q)):
                    note: Note = self.note_q[i]
                    x = self.free_note()
                    if x < 32:
                        self.note_arr[x] = note
                        chan: Channel = self.channels[note.parent]
                        if not clear_channel[note.parent]:
                            clear_channel[note.parent] = True
                            for note2 in self.channels[note.parent].notes:
                                note3: Note = self.note_arr[note2.note_id]
                                if note3.enable and not note3.note_off:
                                    self.note_arr[
                                        note2.note_id] = note3._replace(
                                            note_off=True)
                                    note3: Note = self.note_arr[note2.note_id]
                        self.channels[note.parent].notes.add(x, str(x))
                        chan: Channel = self.channels[note.parent]
                        pat = note.patch_num
                        nn = note.note_num
                        s_pat = str(pat)
                        s_nn = str(nn)
                        # n: Note = self.note_arr[x]

                        std_out = (DirectTypes.DIRECT, DirectTypes.WAVE)
                        sqr_out = (DirectTypes.SQUARE1, DirectTypes.SQUARE2)
                        das = 0
                        if self.dct_exists(self.directs, pat):
                            dct: Direct = self.directs[s_pat]
                            note: Note = self.note_arr[x]
                            self.note_arr[x] = note._replace(
                                output=NoteTypes(dct.output),
                                env_attn=dct.env_attn,
                                env_dcy=dct.env_dcy,
                                env_sus=dct.env_sus,
                                env_rel=dct.env_rel)
                            note: Note = self.note_arr[x]
                            if dct.output in std_out:
                                das = str(dct.smp_id)
                                daf = note_to_freq(nn + (60 - dct.drum_key), -1
                                                   if self.smp_pool[das].gb_wave
                                                   else self.smp_pool[das].freq)
                                if self.smp_pool[das].gb_wave:
                                    daf /= 2
                            elif dct.output in sqr_out:
                                das = f'square{dct.gb1 % 4}'
                                daf = note_to_freq(nn + (60 - dct.drum_key))
                            elif dct.output == DirectTypes.NOISE:
                                das = f'noise{dct.gb1 % 2}{int(random.random() * 3)}'
                                daf = note_to_freq(nn + (60 - dct.drum_key))
                            else:
                                das = ''
                        elif self.inst_exists(pat):
                            dct: Direct = self.insts[s_pat].directs[str(
                                self.insts[s_pat].kmaps[s_nn].assign_dct)]
                            note: Note = self.note_arr[x]
                            self.note_arr[x] = note._replace(
                                output=NoteTypes(dct.output),
                                env_attn=dct.env_attn,
                                env_dcy=dct.env_dcy,
                                env_sus=dct.env_sus,
                                env_rel=dct.env_rel)
                            if dct.output in std_out:
                                das = str(dct.smp_id)
                                if dct.fix_pitch:
                                    daf = self.smp_pool[das].freq
                                else:
                                    daf = note_to_freq(
                                        nn, -2 if self.smp_pool[das].gb_wave
                                        else self.smp_pool[das].freq)
                            elif dct.output in sqr_out:
                                das = f'square{dct.gb1 % 4}'
                                daf = note_to_freq(nn)
                            else:
                                das = ''
                        elif self.drm_exists(pat):
                            dct: Direct = self.drmkits[s_pat].directs[s_nn]
                            note: Note = self.note_arr[x]
                            self.note_arr[x] = note._replace(
                                output=NoteTypes(dct.output),
                                env_attn=dct.env_attn,
                                env_dcy=dct.env_dcy,
                                env_sus=dct.env_sus,
                                env_rel=dct.env_rel)
                            if dct.output in std_out:
                                das = str(
                                    self.drmkits[s_pat].directs[s_nn].smp_id)
                                if dct.fix_pitch and not self.smp_pool[das].gb_wave:
                                    daf = self.smp_pool[das].freq
                                else:
                                    daf = note_to_freq(
                                        dct.drum_key, -2
                                        if self.smp_pool[das].gb_wave else
                                        self.smp_pool[das].freq)
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
                            daf *= (2**(1 / 12))**self.transpose
                            dav = (note.velocity / 0x7F) * ((
                                chan.main_vol / 0x7F) * 255)
                            if mutethis:
                                dav = 0
                            out_type = self.note_arr[x].output
                            if out_type == NoteTypes.SQUARE1:
                                gbn: Note = self.note_arr[self.gb1_chan]
                                if self.gb1_chan < 32:
                                    fmod.FSOUND_StopSound(gbn.fmod_channel)
                                    self.log.debug(
                                        'GB1 chan %s stop sound err: %s',
                                        gbn.fmod_channel, fsound_get_error())
                                    self.note_arr[self.gb1_chan] = gbn._replace(
                                        fmod_channel=0, enable=False)
                                    gbn: Note = self.note_arr[self.gb1_chan]
                                    self.channels[gbn.parent].notes.remove(
                                        str(self.gb1_chan))
                                self.gb1_chan = x
                            elif out_type == NoteTypes.SQUARE2:
                                gbn: Note = self.note_arr[self.gb2_chan]
                                if self.gb2_chan < 32:
                                    fmod.FSOUND_StopSound(gbn.fmod_channel)
                                    self.log.debug(
                                        'GB2 chan %s stop sound err: %s',
                                        gbn.fmod_channel, fsound_get_error())
                                    self.note_arr[self.gb2_chan] = gbn._replace(
                                        fmod_channel=0, enable=False)
                                    gbn: Note = self.note_arr[self.gb2_chan]
                                    self.channels[gbn.parent].notes.remove(
                                        str(self.gb2_chan))
                                self.gb2_chan = x
                            elif out_type == NoteTypes.WAVE:
                                gbn: Note = self.note_arr[self.gb3_chan]
                                if self.gb3_chan < 32:
                                    fmod.FSOUND_StopSound(gbn.fmod_channel)
                                    self.log.debug(
                                        'GB3 chan %s stop sound err: %s',
                                        gbn.fmod_channel, fsound_get_error())
                                    self.note_arr[self.gb3_chan] = gbn._replace(
                                        fmod_channel=0, enable=False)
                                    gbn: Note = self.note_arr[self.gb3_chan]
                                    self.channels[gbn.parent].notes.remove(
                                        str(self.gb3_chan))
                                self.gb3_chan = x
                            elif out_type == NoteTypes.NOISE:
                                gbn: Note = self.note_arr[self.gb4_chan]
                                if self.gb4_chan < 32:
                                    fmod.FSOUND_StopSound(gbn.fmod_channel)
                                    self.log.debug(
                                        'GB4 chan %s stop sound err: %s',
                                        gbn.fmod_channel, fsound_get_error())
                                    self.note_arr[self.gb4_chan] = gbn._replace(
                                        fmod_channel=0, enable=False)
                                    gbn: Note = self.note_arr[self.gb4_chan]
                                    self.channels[gbn.parent].notes.remove(
                                        str(self.gb4_chan))
                                self.gb4_chan = x

                            note: Note = self.note_arr[x]
                            if self.output == SongTypes.WAVE:
                                if not mutethis:
                                    out = x + 1
                                    p = fmod.FSOUND_PlaySound(
                                        x + 1, self.smp_pool[das].fmod_smp)
                                    self.note_arr[x] = self.note_arr[
                                        x]._replace(fmod_channel=out)
                                else:
                                    x = x
                                self.log.debug(
                                    'Play sound das %s chan %s smp %s err: %s',
                                    hex(int(das)), x + 1,
                                    self.smp_pool[das].key, fsound_get_error())
                            else:
                                self.note_arr[x] = self.note_arr[x]._replace(
                                    fmod_channel=note.parent)
                            self.note_arr[x] = self.note_arr[x]._replace(
                                freq=daf, phase=NotePhases.INITIAL)
                            note: Note = self.note_arr[x]
                            chan: Channel = self.channels[note.parent]
                            if self.output == SongTypes.WAVE:
                                freq = c_float(27.5 * 2**
                                               ((chan.pitch - 21) / 12))
                                fmod.FSOUND_SetFrequency(
                                    note.fmod_channel,
                                    c_float(daf * (2**(1 / 12))**
                                            ((chan.pitch - 0x40
                                             ) / 0x40 * chan.pitch_range)))
                                self.log.debug(
                                    'Set frequency chan: %s freq: %s err: %s',
                                    note.fmod_channel, freq, fsound_get_error())
                                vol = c_float(dav * 0 if chan.mute else dav * 1)
                                fmod.FSOUND_SetVolume(note.fmod_channel, vol)
                                self.log.debug(
                                    'Set volume: %s chan: %s err: %s', vol,
                                    note.fmod_channel, fsound_get_error())
                                fmod.FSOUND_SetPan(note.fmod_channel,
                                                   chan.panning * 2)
                            # TODO: RaiseEvent PlayedANote
            self.note_q.clear()

            if self.note_f_ctr > 0:
                for i in range(32):
                    if self.note_arr[i].enable:
                        note: Note = self.note_arr[i]
                        if note.output == NoteTypes.DIRECT:
                            if note.note_off and note.phase < NotePhases.RELEASE:
                                self.note_arr[i] = note._replace(
                                    env_step=0, phase=NotePhases.RELEASE)
                            note: Note = self.note_arr[i]
                            if not note.env_step or (
                                    note.env_pos == note.env_dest) or (
                                        not note.env_step and
                                        (note.env_pos <= note.env_dest)) or (
                                            note.env_step >= 0 and
                                            note.env_pos >= note.env_dest):
                                phase = note.phase
                                if phase == NotePhases.INITIAL:
                                    self.note_arr[i] = note._replace(
                                        phase=NotePhases.ATTACK,
                                        env_pos=0,
                                        env_dest=255,
                                        env_step=note.env_attn)
                                    note: Note = self.note_arr[i]
                                elif phase == NotePhases.ATTACK:
                                    self.note_arr[i] = note._replace(
                                        phase=NotePhases.DECAY,
                                        env_dest=note.env_sus,
                                        env_step=(note.env_dcy - 0x100) / 2)
                                    note: Note = self.note_arr[i]
                                elif phase == NotePhases.DECAY:
                                    self.note_arr[i] = note._replace(
                                        phase=NotePhases.SUSTAIN, env_step=0)
                                    note: Note = self.note_arr[i]
                                elif phase == NotePhases.SUSTAIN:
                                    self.note_arr[i] = note._replace(
                                        phase=NotePhases.SUSTAIN, env_step=0)
                                    note: Note = self.note_arr[i]
                                elif phase == NotePhases.RELEASE:
                                    self.note_arr[i] = note._replace(
                                        phase=NotePhases.NOTEOFF,
                                        env_dest=0,
                                        env_step=note.env_rel - 0x100)
                                    note: Note = self.note_arr[i]
                                elif phase == NotePhases.NOTEOFF:
                                    fmod.FSOUND_StopSound(note.fmod_channel)
                                    self.log.debug('Stop sound chan %r err: %s',
                                                   note.fmod_channel + 1,
                                                   fsound_get_error())
                                    self.note_arr[i] = note._replace(
                                        fmod_channel=0, enable=False)
                                    note: Note = self.note_arr[i]
                                    self.channels[note.parent].notes.remove(
                                        str(i))
                                note: Note = self.note_arr[i]
                        note: Note = self.note_arr[i]
                        nex = note.env_pos + note.env_step
                        if nex > note.env_dest and note.env_step > 0:
                            nex = note.env_dest
                        if nex < note.env_dest and note.env_step < 0:
                            nex = note.env_dest
                        self.note_arr[i] = note._replace(env_pos=nex)
                        note: Note = self.note_arr[i]
                        dav = (note.velocity / 0x7F) * (
                            self.channels[note.parent].main_vol / 0x7F) * (
                                int(note.env_pos) / 0xFF) * 255
                        if mutethis:
                            dav = 0
                        fmod.FSOUND_SetVolume(
                            note.fmod_channel,
                            c_float(dav * 0 if self.channels[note.parent].mute
                                    else dav * 1))
                        self.log.debug('Set chan %s vol err: %s',
                                       note.fmod_channel, fsound_get_error())
                    else:
                        if note.note_off and note.phase < NotePhases.RELEASE:
                            self.note_arr[i] = note._replace(
                                env_step=0, phase=NotePhases.RELEASE)
                        note: Note = self.note_arr[i]
                        if not note.env_step or note.env_pos == note.env_dest or (
                                not note.env_step and
                                note.env_pos <= note.env_dest) or (
                                    note.env_step >= 0 and
                                    note.env_pos >= note.env_dest):
                            phase: NotePhases = note.phase
                            if phase == NotePhases.INITIAL:
                                self.note_arr[i] = note._replace(
                                    phase=NotePhases.ATTACK,
                                    env_pos=0,
                                    env_dest=255,
                                    env_step=0x100 - note.env_attn * 8)
                                note: Note = self.note_arr[i]
                            elif phase == NotePhases.ATTACK:
                                self.note_arr[i] = note._replace(
                                    phase=NotePhases.DECAY,
                                    env_dest=note.env_sus,
                                    env_step=-(note.env_dcy) * 2)
                                note: Note = self.note_arr[i]
                            elif phase == NotePhases.DECAY:
                                self.note_arr[i] = note._replace(
                                    phase=NotePhases.SUSTAIN, env_step=0)
                                note: Note = self.note_arr[i]
                            elif phase == NotePhases.SUSTAIN:
                                self.note_arr[i] = note._replace(
                                    phase=NotePhases.SUSTAIN, env_step=0)
                                note: Note = self.note_arr[i]
                            elif phase == NotePhases.RELEASE:
                                self.note_arr[i] = note._replace(
                                    phase=NotePhases.NOTEOFF,
                                    env_dest=0,
                                    env_step=(0x08 - note.env_rel))
                                note: Note = self.note_arr[i]
                            elif phase == NotePhases.NOTEOFF:
                                out_type = note.output
                                if out_type == NoteTypes.SQUARE1:
                                    self.gb1_chan = 255
                                elif out_type == NoteTypes.SQUARE2:
                                    self.gb2_chan = 255
                                elif out_type == NoteTypes.WAVE:
                                    self.gb3_chan = 255
                                elif out_type == NoteTypes.NOISE:
                                    self.gb4_chan = 255
                                fmod.FSOUND_StopSound(note.fmod_channel)
                                self.log.debug(
                                    'Stop sound from NOTEOFF %s err: %s',
                                    note.fmod_channel, fsound_get_error())
                                self.note_arr[i] = note._replace(
                                    fmod_channel=0, enable=False)
                                note: Note = self.note_arr[i]
                                try:
                                    self.channels[note.parent].notes.remove(
                                        str(i))
                                except:
                                    pass
                            note: Note = self.note_arr[i]
                        note: Note = self.note_arr[i]
                        nex = note.env_pos + note.env_step
                        if nex > note.env_dest and note.env_step > 0:
                            nex = note.env_dest
                        if nex < note.env_dest and note.env_step > 0:
                            nex = note.env_dest
                        self.note_arr[i] = note._replace(env_pos=nex)
                        note: Note = self.note_arr[i]
                        dav = (note.velocity / 0x7F) * (
                            self.channels[note.parent].main_vol / 0x7F) * (
                                int(note.env_pos) / 0xFF) * 255
                        if mutethis:
                            dav = 0
                        vol = c_float(dav * 0 if self.channels[note.parent].mute
                                      else dav * 1)
                        fmod.FSOUND_SetVolume(note.fmod_channel, vol)
                        self.log.debug('Set volume chan %s vol %s err: %s',
                                       note.fmod_channel, vol,
                                       fsound_get_error())

            xmmm = False
            for i in range(len(self.channels)):
                #self.channels[i] = self.channels[i]._replace(enable=True)
                if self.channels[i].enable:
                    xmmm = True
            if not xmmm or not self.tempo:
                self.stop_song()
                raise Exception
                return None
                # TODO: RaiseEvent SongFinish

        self.prv_tick = 0
        self.tick_ctr = 0
        self.incr += 1
        if self.incr >= int(60000 / (self.tempo * self.SAPPY_PPQN)):
            self.tick_ctr = 1
            self.ttl_ticks += 1
            if not self.ttl_ticks % 48:
                self.beats += 1
                # TODO: RaiseEvent Beat(self.beats)
            self.incr = 0

        self.note_f_ctr = 1

        if self.tempo != self.last_tempo:
            self.last_tempo = self.tempo
            # TODO: EvtProcessor Stuff


def main():
    """Main test method."""
    import time
    d = Decoder()

    d.play_song(
        'C:\\Users\\chenc\\Downloads\\Metroid - Zero Mission (U) [!]\\Metroid - Zero Mission (U) [!].gba',
        1, 0x8F2C0)
    while True:
        d.evt_processor_timer(1)
        fmod.FSOUND_Update()
        print(fsound_get_error(), d.note_f_ctr, d.ttl_msecs, d.tick_ctr,
              d.ttl_ticks)
        time.sleep(0.001)
    fmod.FSOUND_Close()


if __name__ == '__main__':
    main()
