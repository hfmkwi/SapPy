#!/usr/bin/python3
#-*- coding: utf-8 -*-
# pylint disable=C0103, C0326, E1120, R0902, R0903, R0904, R0912, R0913, R0914, R0915, R1702
# pylint: disable=W0614
# TODO: Either use the original FMOD dlls or find a sound engine.
"""Main file."""
import ctypes
import os
import random
from enum import IntEnum
from logging import INFO, basicConfig, getLogger
from struct import unpack
from typing import List, NamedTuple

from containers import *
from fileio import *
from fmod import *
from player import *

#kernal32 = ctypes.windll.kernel32
fmod = ctypes.windll.fmod


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
    DEBUG = False
    GB_SQ_MULTI = 0.5
    GB_WAV_MULTI = 0.5
    GB_WAV_BASE_FREQ = 880
    GB_NSE_MULTI = 0.5
    SAPPY_PPQN = 24

    if DEBUG:
        basicConfig(level=INFO)
    else:
        basicConfig(level=None)
    log = getLogger(name=__name__)

    def __init__(self):
        # yapf: disable
        self.playing:      bool                        = bool()
        self.record:       bool                        = bool()
        self.beats:        int                         = int()
        self.gb1_chan:     int                         = 255
        self.gb2_chan:     int                         = 255
        self.gb3_chan:     int                         = 255
        self.gb4_chan:     int                         = 255
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
        self.output:       SongTypes             = SongTypes.NULL
        self.channels:     ChannelQueue[Channel]       = ChannelQueue()  # pylint:    disable = E1136
        self.dct_head:     DirectHeader                = DirectHeader()
        self.directs:      DirectQueue[Direct]         = DirectQueue()  # pylint:     disable = E1136
        self.drm_head:     DrumKitHeader               = DrumKitHeader()
        self.drmkits:      DrumKitQueue[DrumKit]       = DrumKitQueue()  # pylint:    disable = E1136
        self.inst_head:    InstrumentHeader            = InstrumentHeader()
        self.insts:        InstrumentQueue[Instrument] = InstrumentQueue()  # pylint: disable = E1136
        self.note_arr:     List[Note]                  = [Note()] * 32
        self.nse_wavs:     List[List[str]]             = [[[] for i in range(10)] for i in range(2)]
        self.mul_head:     MultiHeader                 = MultiHeader()
        self.gb_head:      NoiseHeader                 = NoiseHeader()
        self.note_q:       NoteQueue[Note]             = NoteQueue()  # pylint:       disable = E1136
        self.last_evt:     RawMidiEvent                = RawMidiEvent()
        self.smp_head:     SampleHeader                = SampleHeader()
        self.smp_pool:     SampleQueue[Sample]         = SampleQueue()  # pylint:     disable = E1136
        # yapf: enable
        self.ts = self.te = self.sz = int()
        random.seed()
        if not self.sz:
            self.sz = 2048
        self.ts = ctypes.windll.kernel32.GetTickCount()
        for i in range(10):
            for _ in range(self.sz):
                self.nse_wavs[0][i].append(chr(int(random.random() * 153)))
            self.nse_wavs[0][i] = "".join(self.nse_wavs[0][i])
            for _ in range(256):
                self.nse_wavs[1][i].append(chr(int(random.random() * 153)))
            self.nse_wavs[1][i] = "".join(self.nse_wavs[1][i])
            print(self.nse_wavs[1][i])
        self.te = ctypes.windll.kernel32.GetTickCount()
        self.gbl_vol = 255

    @property
    def gbl_vol(self) -> int:
        """Global volume of the player."""
        #TODO: Actually change the volume of whatever sound API I'm using
        return self._gbl_vol

    @gbl_vol.setter
    def gbl_vol(self, vol: int) -> None:
        self._gbl_vol = vol

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
        buf = ch & 0x7F
        while val // 128 > 0:
            val //= 128
            buf |= 0x80
            buf = (buf * 256) | (val & 0x7F)
        file = File.from_id(ch)
        while True:
            file.write_byte(buf & 255)
            if not buf & 0x80:
                break
            buf //= 256

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
        note = -1
        for i in range(32):
            if not self.note_arr[i].enable:
                note = i
        return note

    def get_smp(self, q: Collection, dct_key: str, dct_head: DirectHeader,
                smp_head: SampleHeader, use_readstr: bool) -> None:
        """UNKNOWN"""
        dct_q = q.directs
        dct_q[dct_key] = dct_q[dct_key]._replace(note_id=dct_head.smp_head)
        s_id = dct_q[dct_key].note_id
        if not self.smp_exists(s_id):
            self.smp_pool.add(str(s_id))
            print(self.smp_pool)
            if dct_q[dct_key].output == DirectTypes.DIRECT:
                self.smp_head = rd_smp_head(File.gba_ptr_to_addr(s_id))
                if use_readstr:
                    smp_data = self.wfile.rd_str(smp_head.size)
                else:
                    smp_data = self.wfile.rd_addr
                self.smp_pool[str(s_id)] = self.smp_pool[str(s_id)]._replace(
                    size=smp_head.size,
                    freq=smp_head.freq,
                    loop_start=smp_head.loop,
                    loop=smp_head.flags > 0,
                    gb_wave=False,
                    smp_data=smp_data)
            else:
                tsi = self.wfile.rd_str(16, File.gba_ptr_to_addr(s_id))
                smp_data = []
                for ai in range(32):
                    bi = ai % 2
                    newvariable73 = tsi[ai // 2:ai // 2 + 1]
                    if not newvariable73:
                        smp_pt = 0
                    else:
                        smp_pt = ord(newvariable73)
                    smp_pt = chr(
                        smp_pt // 16**bi % 16 * self.GB_WAV_BASE_FREQ * 16)
                    smp_data.append(smp_pt)
                smp_data = "".join(smp_data)
                self.smp_pool[str(s_id)] = self.smp_pool[str(s_id)].replace(
                    size=32,
                    freq=self.GB_WAV_BASE_FREQ,
                    loop_start=0,
                    loop=True,
                    gb_wave=True,
                    smp_data=smp_data)

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
            self.note_arr[i] = Note(enable=False)

        self.wfile = open_file(self.fpath, 1)
        assert self.wfile is not None
        ptr = self.wfile.rd_gba_ptr(self.sng_lst_ptr + sng_num * 8)
        self.sng_ptr = ptr
        self.layer = self.wfile.rd_ltendian(4)
        pbyte = self.wfile.rd_byte(ptr)
        self.inst_tbl_ptr = self.wfile.rd_gba_ptr(ptr + 4)

        # TODO: raise LOADING_0

        xta = SubroutineQueue()
        for i in range(pbyte):
            loop_addr = -1
            pgm_ctr = self.wfile.rd_gba_ptr(ptr + 4 + i * 4)
            self.channels.add()
            xta.clear()
            while True:
                self.wfile.rd_addr = pgm_ctr
                ctl_byte = self.wfile.rd_byte(pgm_ctr)
                if 0x00 <= ctl_byte <= 0xB0 or ctl_byte in (0xCE, 0xCF, 0xB4):
                    pgm_ctr += 1
                elif ctl_byte == 0xB9:
                    pgm_ctr += 4
                elif ctl_byte >= 0xB5 and ctl_byte <= 0xCD:
                    pgm_ctr += 2
                elif ctl_byte == 0xB2:
                    loop_addr = self.wfile.rd_gba_ptr()
                    pgm_ctr += 5
                    break
                elif ctl_byte == 0xB3:
                    xta.add(self.wfile.rd_gba_ptr())
                    pgm_ctr += 5
                elif ctl_byte >= 0xD0 and ctl_byte <= 0xFF:
                    pgm_ctr += 1
                    while self.wfile.rd_byte() < 0x80:
                        pgm_ctr += 1
                print(hex(pgm_ctr), hex(ctl_byte))
                if ctl_byte == 0xb1:
                    break

            cticks = 0
            lc = 0xbe
            lln: List = [None] * 66
            llv: List = [None] * 66
            lla: List = [None] * 66
            lp = 0
            insub = 0
            trnps = 0
            channels = self.channels
            cur_ch = channels[i]._replace(track_ptr=-1)
            cdr = 0
            print(f"-- READING CHANNEL {i} --")
            evt_queue = channels[i].evt_queue
            while True:
                self.wfile.rd_addr = pgm_ctr
                if pgm_ctr >= loop_addr and loop_addr != -1 and cur_ch.loop_ptr == -1:
                    channels[i] = cur_ch._replace(
                        loop_ptr=cur_ch.evt_queue.count)
                ctl_byte = self.wfile.rd_byte()
                print(hex(pgm_ctr), hex(ctl_byte))
                if (0xb5 <= ctl_byte < 0xc5 and
                        ctl_byte != 0xb9) or ctl_byte == 0xcd:
                    cmd_arg = self.wfile.rd_byte()
                    if ctl_byte == 0xbc:
                        trnps = sbyte_to_int(cmd_arg)
                elif 0xcf <= ctl_byte <= 0xff:
                    pgm_ctr += 1
                    lc = ctl_byte
                    g = False
                    n_ctr = 0
                    while not g:
                        cmd_arg = self.wfile.rd_byte()
                        print(hex(cmd_arg))
                        if cmd_arg >= 0x80:
                            if not n_ctr:
                                pn = lln[n_ctr] + trnps
                            l_args = llv[n_ctr], lla[n_ctr]
                            e_args = cticks, ctl_byte, pn, *l_args
                            evt_queue.add(*e_args)
                            g = True
                        else:
                            assert n_ctr < 66
                            lln[n_ctr] = cmd_arg
                            pgm_ctr += 1
                            e = self.wfile.rd_byte()
                            if e < 0x80:
                                llv[n_ctr] = e
                                pgm_ctr += 1
                                sm = self.wfile.rd_byte()
                                if sm >= 0x80:
                                    sm = lla[n_ctr]
                                    g = True
                                else:
                                    lla[n_ctr] = sm
                                    pgm_ctr += 1
                                    n_ctr += 1
                            else:
                                e = llv[n_ctr]
                                sm = lla[n_ctr]
                                g = True
                            pn = cmd_arg + trnps
                            e_args = cticks, ctl_byte, pn, e, sm
                            evt_queue.add(*e_args)
                        if not self.patch_exists(lp):
                            inst_ptr = self.inst_tbl_ptr + lp * 12
                            self.inst_head = rd_inst_head(1, inst_ptr)
                            s_lp = str(lp)
                            s_pn = str(pn)
                            s_cdr = str(cdr)
                            smp_out = (DirectTypes.DIRECT, DirectTypes.WAVE)
                            if self.inst_head.channel & 0x80 == 0x80:
                                self.drm_head = rd_drmkit_head(1)
                                drm_ptr = self.drm_head.dct_tbl + pn * 12
                                inst_ptr = File.gba_ptr_to_addr(drm_ptr)
                                self.inst_head = rd_inst_head(1, inst_ptr)
                                self.dct_head = rd_dct_head(1)
                                nse_ptr = File.gba_ptr_to_addr(drm_ptr + 2)
                                self.gb_head = rd_nse_head(1, nse_ptr)
                                self.drmkits.add(s_lp)
                                drmkits = self.drmkits
                                drmkits[s_lp].add(s_pn)
                                drmkit = drmkits[s_lp]
                                h = self.inst_head, self.dct_head, self.gb_head
                                dct_args = drmkit, s_pn, *h
                                self.set_direct(*dct_args)
                                dcts = self.insts[s_lp].directs
                                dct_out = dcts[s_cdr].output
                                if dct_out in smp_out:
                                    hd = self.dct_head, self.smp_head
                                    smp_args = drmkit, s_pn, *hd, False
                                    self.get_smp(*smp_args)
                            elif self.inst_head.channel & 0x40 == 0x40:  # Multi
                                self.mul_head = rd_mul_head(1)
                                self.insts.add(s_lp)
                                kmaps = self.insts[s_lp].kmaps
                                kmaps.add(0, s_pn)
                                dct = kmaps[s_pn]
                                mul_ptr = File.gba_ptr_to_addr(self.mul_head)
                                kmap_ptr = mul_ptr + pn
                                dct_byte = self.wfile.rd_byte(kmap_ptr)
                                kmaps[s_pn] = dct._replace(assign_dct=dct_byte)
                                cdr = kmaps[s_pn].assign_dct
                                s_cdr = str(cdr)
                                inst_ptr = self.mul_head.dct_tbl + cdr * 12
                                inst_addr = File.gba_ptr_to_addr(inst_ptr)
                                self.inst_head = rd_inst_head(1, inst_addr)
                                self.dct_head = rd_dct_head(1)
                                nse_ptr = inst_ptr + 2
                                nse_addr = File.gba_ptr_to_addr(nse_ptr)
                                self.gb_head = rd_nse_head(1, nse_addr)
                                dcts = self.insts[s_lp].directs
                                dcts.add(s_cdr)
                                h = self.inst_head, self.dct_head, self.gb_head
                                dct_args = dcts, s_cdr, *h
                                self.set_direct(*dct_args)
                                print(dcts[s_cdr].output)
                                if dcts[s_cdr].output in smp_out:
                                    h = self.dct_head, self.smp_head
                                    self.get_smp(dcts, s_cdr, *h, False)
                            else:  # Direct/GB Sample
                                self.dct_head = rd_dct_head(1)
                                nse_addr = self.inst_tbl_ptr + lp * 12 + 2
                                self.gb_head = rd_nse_head(1, nse_addr)
                                self.directs.add(s_lp)
                                h = self.inst_head, self.dct_head, self.gb_head
                                dct_args = self.directs, s_lp, *h
                                self.set_direct(*dct_args)
                        else:  # Patch exists
                            inst_addr = self.inst_tbl_ptr + lp * 12
                            self.inst_head = rd_inst_head(1, inst_addr)
                            if self.inst_head.channel & 0x80 == 0x80:
                                self.drm_head = rd_drmkit_head(1)
                                inst_ptr = self.drm_head.dct_tbl + pn * 12
                                inst_addr = File.gba_ptr_to_addr(inst_ptr)
                                self.inst_head = rd_inst_head(1, inst_addr)
                                self.dct_head = rd_dct_head(1)
                                gb_ptr = inst_ptr + 2
                                gb_addr = File.gba_ptr_to_addr(gb_ptr)
                                self.gb_head = rd_nse_head(1, gb_addr)
                                dcts = self.drmkits[s_lp].directs
                                if not self.dct_exists(dcts, pn):
                                    dcts.add(s_pn)
                                    h = (self.inst_head, self.dct_head,
                                         self.gb_head)
                                    dct_args = dcts, s_pn, *h
                                    self.set_direct(*dct_args)
                                    if dcts[s_pn].output in smp_out:
                                        h = self.dct_head, self.smp_head
                                        mul_args = dcts, s_pn, *h, False
                                        self.get_mul_smp(*mul_args)
                            elif self.inst_head.channel * 0x40 == 0x40:
                                self.mul_head = rd_mul_head(1)
                                kmaps = self.insts[s_lp].kmaps
                                if not self.kmap_exists(kmaps, pn):
                                    k_ptr = self.mul_head.kmap
                                    k_addr = self.wfile.gba_ptr_to_addr(k_ptr)
                                    k_addr = k_addr + pn
                                    kmaps.add(self.wfile.rd_byte(k_addr), s_pn)
                                    cdr = kmaps[s_pn].assign_dct
                                    s_cdr = str(cdr)
                                    inst_ptr = self.mul_head.dct_tbl + cdr * 12
                                    inst_addr = File.gba_ptr_to_addr(inst_ptr)
                                    self.inst_head = rd_inst_head(1, inst_addr)
                                    self.dct_head = rd_dct_head(1)
                                    nse_ptr = inst_addr + 2
                                    self.gb_head = rd_nse_head(1, nse_ptr)
                                    dcts = self.insts[s_lp].directs
                                    if not self.dct_exists(dcts, cdr):
                                        dcts.add(s_cdr)
                                        h = (self.inst_head, self.dct_head,
                                             self.gb_head)
                                        dct_args = dcts, s_cdr, *h
                                        self.set_direct(*dct_args)
                                        if dcts[s_cdr].output in smp_out:
                                            h = self.dct_head, self.smp_head
                                            m_args = dcts, s_cdr, *h, False
                                            self.get_mul_smp(*m_args)
                elif 0x00 <= ctl_byte < 0x80:
                    if lc < 0xCF:
                        evt_q = self.channels[i].evt_queue
                        evt_q.add(cticks, lc, ctl_byte, 0, 0)
                        pgm_ctr += 1
                    else:
                        ctl_byte = lc
                        self.wfile.read_offset = pgm_ctr
                        g = False
                        n_ctr = 0
                        while not g:
                            d = self.wfile.rd_byte()
                            if d >= 0x80:
                                if not n_ctr:
                                    pn = lln[n_ctr] + trnps
                                    s_pn = str(pn)
                                    l = llv[n_ctr], lla[n_ctr]
                                    e_args = cticks, ctl_byte, pn, *l
                                    evt_q.add(*e_args)
                            else:
                                lln[n_ctr] = d
                                pgm_ctr += 1
                                e = self.wfile.rd_byte()
                                if e < 0x80:
                                    llv[n_ctr] = e
                                    pgm_ctr += 1
                                    sm = self.wfile.rd_byte()
                                    if sm >= 0x80:
                                        sm = lla[n_ctr]
                                        g = True
                                    else:
                                        lla[n_ctr] = sm
                                        pgm_ctr += 1
                                        n_ctr += 1
                                else:
                                    e = llv[n_ctr]
                                    sm = lla[n_ctr]
                                    g = True
                                pn = d + trnps
                                s_pn = str(pn)
                                evt_q.add(cticks, ctl_byte, pn, e, sm)
                            if not self.patch_exists(lp):
                                inst_addr = self.inst_tbl_ptr + lp * 12
                                self.inst_head = rd_inst_head(1, inst_addr)
                                if self.inst_head.channel & 0x80 == 0x80:
                                    self.drm_head = rd_drmkit_head(1)
                                    inst_ptr = self.drm_head.dct_tbl + pn * 12
                                    inst_addr = File.gba_ptr_to_addr(inst_ptr)
                                    self.inst_head = rd_inst_head(1, inst_addr)
                                    self.dct_head = rd_dct_head(1)
                                    nse_addr = inst_addr + 2
                                    self.gb_head = rd_nse_head(1, nse_addr)
                                    self.drmkits.add(s_lp)
                                    dcts = self.drmkits[s_lp].directs
                                    dcts.add(s_pn)
                                    h = (self.inst_head, self.dct_head,
                                         self.gb_head)
                                    dct_args = dcts, s_pn, *h
                                    self.set_direct(*dct_args)
                                    if dcts[s_pn].output in smp_out:
                                        h = self.dct_head, self.gb_head
                                        smp_args = dcts, s_pn, *h, True
                                        self.get_smp(*smp_args)
                                elif self.inst_head.channel & 0x40 == 0x40:
                                    self.mul_head = rd_mul_head(1)
                                    self.insts.add(s_lp)
                                    kmaps = self.insts[s_lp].kmaps
                                    k_addr = self.wfile.rd_byte()
                                    kmaps.add(k_addr)
                                    cdr = kmaps[s_pn].assign_dct
                                    s_cdr = str(cdr)
                                    inst_ptr = self.mul_head.dct_tbl + cdr * 12
                                    inst_addr = File.gba_ptr_to_addr(inst_ptr)
                                    self.inst_head = rd_inst_head(1, inst_addr)
                                    self.dct_head = rd_dct_head(1)
                                    nse_addr = inst_addr + 2
                                    self.gb_head = rd_nse_head(1, nse_addr)
                                    dcts = self.insts[s_lp].directs
                                    dcts.add(s_cdr)
                                    h = (self.inst_head, self.dct_head,
                                         self.gb_head)
                                    dct_args = dcts, s_cdr, *h
                                    self.set_direct(*dct_args)
                                    if dcts[s_cdr].output in smp_out:
                                        h = self.dct_head, self.smp_head
                                        smp_args = dcts, s_cdr, *h, False
                                        self.get_smp(*smp_args)
                            else:
                                inst_addr = self.inst_tbl_ptr + lp * 12
                                self.inst_head = rd_inst_head(1, inst_addr)
                                if self.inst_head.channel & 0x80 == 0x80:
                                    self.drm_head = rd_drmkit_head(1)
                                    inst_ptr = self.drm_head.dct_tbl + pn * 12
                                    inst_addr = File.gba_ptr_to_addr(inst_ptr)
                                    self.inst_head = rd_inst_head(1, inst_addr)
                                    self.dct_head = rd_dct_head(1)
                                    nse_addr = inst_addr = 2
                                    self.gb_head = rd_nse_head(1, nse_addr)
                                    dcts = self.drmkits[s_lp].directs
                                    if not self.dct_exists(dcts, pn):
                                        dcts.add(s_pn)
                                        h = (self.inst_head, self.dct_head,
                                             self.gb_head)
                                        dct_args = dcts, s_pn, *h
                                        self.set_direct(*dct_args)
                                        if dcts[s_pn].output in smp_out:
                                            h = self.dct_head, self.smp_head
                                            smp_args = dcts, s_pn, *h, False
                                            self.get_smp(*smp_args)
                                elif self.inst_head.channel & 0x40 == 0x40:
                                    self.mul_head = rd_mul_head(1)
                                    kmaps = self.insts[s_lp].kmaps
                                    if not self.kmap_exists(kmaps, pn):
                                        kmap_addr = self.mul_head.kmap
                                        r_ptr = File.gba_ptr_to_addr(kmap_addr)
                                        r_addr = r_ptr + pn
                                        args = self.wfile.rd_byte(r_addr), s_pn
                                        kmaps.add(*args)
                                        cdr = kmaps[s_pn].assign_dct
                                        s_cdr = str(cdr)
                                        ptr = self.mul_head.dct_tbl + cdr * 12
                                        i_addr = File.gba_ptr_to_addr(ptr)
                                        args = 1, i_addr
                                        self.inst_head = rd_inst_head(*args)
                                        self.dct_head = rd_dct_head(1)
                                        nse_addr = i_addr + 2
                                        self.gb_head = rd_nse_head(1, nse_addr)
                                        dcts = self.insts[s_lp].dcts
                                        if not self.dct_exists(dcts, cdr):
                                            dcts.add(s_cdr)
                                            h = (self.inst_head, self.dct_head,
                                                 self.gb_head)
                                            dct_args = dcts, s_cdr, *h
                                            self.set_direct(*dct_args)
                                            if dcts[s_cdr].output in smp_out:
                                                h = self.dct_head, self.smp_head
                                                args = dcts, s_cdr, *h, False
                                                self.get_mul_smp(*args)
                elif 0x80 <= ctl_byte <= 0xB0:
                    evt_queue.add(cticks, ctl_byte, 0, 0, 0)
                    cticks += stlen_to_ticks(ctl_byte - 0x80)
                    pgm_ctr += 1
                elif ctl_byte == 0xbd:
                    lp = cmd_arg
                elif ctl_byte in (0xbe, 0xbf, 0xc0, 0xc4, 0xcd):
                    lc = ctl_byte
                    e_args = (cticks, ctl_byte, cmd_arg, 0, 0)
                    evt_queue.add(*e_args)
                elif 0xc4 < ctl_byte < 0xcf:
                    evt_queue.add(cticks, ctl_byte, 0, 0, 0)
                elif ctl_byte == 0xb9:
                    cmd_arg = self.wfile.rd_byte()
                    e = self.wfile.rd_byte()
                    sm = self.wfile.rd_byte()
                    e_args = cticks, ctl_byte, cmd_arg, e, sm
                    evt_queue.add(*e_args)
                    pgm_ctr += 4
                elif ctl_byte == 0xb4:
                    if insub == 1:
                        pgm_ctr = rpc
                        insub = 0
                    else:
                        pgm_ctr += 1
                elif ctl_byte == 0xb3:
                    rpc = pgm_ctr + 5
                    insub = 1
                    pgm_ctr = self.wfile.rd_gba_ptr()
                if ctl_byte in (0xB1, 0xB2):
                    break
            evt_queue.add(cticks, ctl_byte, 0, 0, 0)

        fmod.FSOUND_Init(44100, 64, FSoundInitModes.FSOUND_INIT_GLOBALFOCUS)
        fmod.FSOUND_SetSFXMasterVolume(self.gbl_vol)
        #fmod.FSOUND_SetSFXMasterVolume(100)
        quark = 0
        csm = FSoundChannelSampleMode
        sm = FSoundModes
        print(fsound_get_error_string(fmod.FSOUND_GetError()))
        for i in self.smp_pool:
            smp = self.smp_pool[i]
            quark += 1
            smp: Sample
            if smp.gb_wave:
                if not int(smp.smp_data):
                    with open_new_file('temp.raw', 2) as f:
                        f.wr_str(smp.smp_data)
                    args = (csm.FSOUND_FREE, 'temp.raw', sm.FSOUND_8BITS +
                            sm.FSOUND_LOADRAW + sm.FSOUND_LOOP_NORMAL +
                            sm.FSOUND_MONO + sm.FSOUND_UNSIGNED, 0, 0)
                    fmod_smp = fmod.FSOUND_Sample_Load(*args)
                    print(
                        f'load smp: {fmod_smp} err: {fsound_get_error_string(fmod.FSOUND_GetError())}'
                    )
                    self.smp_pool[i] = smp._replace(fmod_smp=fmod_smp)
                    fmod.FSOUND_Sample_SetLoopPoints(smp.fmod_smp, 0, 31)
                    os.remove('temp.raw')
                else:
                    args = (csm.FSOUND_FREE, fpath, sm.FSOUND_8BITS +
                            sm.FSOUND_LOADRAW + sm.FSOUND_LOOP_NORMAL +
                            sm.FSOUND_MONO + sm.FSOUND_UNSIGNED, smp.smp_data,
                            smp.size)
                    fmod_smp = fmod.FSOUND_Sample_Load(*args)
                    print(
                        f'load smp: {fmod_smp} err: {fsound_get_error_string(fmod.FSOUND_GetError())}'
                    )
                    self.smp_pool[i] = smp._replace(fmod_smp=fmod_smp)
                    fmod.FSOUND_Sample_SetLoopPoints(smp.fmod_smp, 0, 31)
            else:
                if not int(smp.smp_data):
                    with open_new_file('temp.raw', 2) as f:
                        f.wr_str(smp.smp_data)
                    args = (csm.FSOUND_FREE, 'temp.raw',
                            sm.FSOUND_8BITS + sm.FSOUND_LOADRAW +
                            (sm.FSOUND_LOOP_NORMAL if smp.loop else 0) +
                            sm.FSOUND_MONO + sm.FSOUND_SIGNED, 0, 0)
                    fmod_smp = fmod.FSOUND_Sample_Load(*args)
                    print(
                        f'load smp: {fmod_smp} err: {fsound_get_error_string(fmod.FSOUND_GetError())}'
                    )
                    self.smp_pool[i] = smp._replace(fmod_smp=fmod_smp)
                    fmod.FSOUND_Sample_SetLoopPoints(
                        smp.fmod_smp, smp.loop_start, smp.size - 1)
                    os.remove('temp.raw')
                else:
                    args = (csm.FSOUND_FREE, fpath,
                            sm.FSOUND_8BITS + sm.FSOUND_LOADRAW +
                            (sm.FSOUND_LOOP_NORMAL
                             if smp.loop else 0) + sm.FSOUND_MONO +
                            sm.FSOUND_SIGNED, smp.smp_data, smp.size)
                    fmod_smp = fmod.FSOUND_Sample_Load(*args)
                    print(
                        f'load smp: {fmod_smp} err: {fsound_get_error_string(fmod.FSOUND_GetError())}'
                    )
                    self.smp_pool[i] = smp._replace(fmod_smp=fmod_smp)
                    fmod.FSOUND_Sample_SetLoopPoints(
                        smp.fmod_smp, smp.loop_start, smp.size - 1)
        for i in range(10):
            self.smp_pool.add(f'noise0{i}')
            sp = self.smp_pool
            smp = sp[f'noise0{i}']
            smp: Sample
            random.seed()
            with open_new_file(f'noise0{i}.raw', 2) as f:
                f.wr_str(self.nse_wavs[0][i])
            sp[i] = smp._replace(
                freq=7040,
                size=16384,
                smp_data="",
                fmod_smp=fmod.FSOUND_Sample_Load(
                    csm.FSOUND_FREE, f'noise0{i}.raw',
                    sm.FSOUND_8BITS + sm.FSOUND_LOADRAW + sm.FSOUND_LOOP_NORMAL
                    + sm.FSOUND_MONO + sm.FSOUND_UNSIGNED, 0, 0))
            fmod.FSOUND_Sample_SetLoopPoints(smp.fmod_smp, 0, 16383)
            os.remove(f'noise0{i}.raw')
            self.smp_pool.add(f'noise1{i}')
            with open_new_file(f'noise1{i}.raw', 2) as f:
                f.wr_str(self.nse_wavs[1][i])
            sp[i] = smp._replace(
                freq=7040,
                size=256,
                smp_data="",
                fmod_smp=fmod.FSOUND_Sample_Load(
                    csm.FSOUND_FREE, f'noise1{i}.raw',
                    sm.FSOUND_8BITS + sm.FSOUND_LOADRAW + sm.FSOUND_LOOP_NORMAL
                    + sm.FSOUND_MONO + sm.FSOUND_UNSIGNED, 0, 0))
            fmod.FSOUND_Sample_SetLoopPoints(smp.fmod_smp, 0, 255)
            os.remove(f'noise1{i}.raw')

        b1 = chr(int(0x80 + 0x7F * self.GB_SQ_MULTI))
        b2 = chr(int(0x80 - 0x7F * self.GB_SQ_MULTI))
        for mx2 in range(4):
            self.smp_pool.add(f'square{mx2}')
            sp = self.smp_pool
            smp = sp[f'square{mx2}']

            if mx2 == 3:
                sd = "".join([b1] * 24 + [b2] * 8)
            else:
                sd = "".join([b1] * ((mx2 + 2)**2) + [b2] * (32 - (mx2 + 2)**2))
            with open_new_file(f'square{mx2}.raw', 2) as f:
                f.wr_str(sd)
            sp[mx2] = smp._replace(
                smp_data='',
                freq=7040,
                fmod_smp=fmod.FSOUND_Sample_Load(
                    csm.FSOUND_FREE, f'square{mx2}.raw',
                    sm.FSOUND_8BITS + sm.FSOUND_LOADRAW + sm.FSOUND_LOOP_NORMAL
                    + sm.FSOUND_MONO + sm.FSOUND_UNSIGNED, 0, 0))
            os.remove(f'square{mx2}.raw')
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
        print('stop')
        # File.from_id(2).close()
        # TODO: disable event processor
        fmod.FSOUND_Close()
        # TODO: close MIDI channel
        # TODO: raise SONG_FINISH

    def evt_processor_timer(self, msecs: int) -> None:
        ep = 0
        mutethis = False
        self.ttl_msecs += msecs
        if self.tick_ctr > 0:
            n_r = self.note_arr
            for i in range(32):
                n: Note = self.note_arr[i]
                if n.enable and n.wait_ticks > 0:
                    wt = n.wait_ticks - (self.tick_ctr - self.prv_tick)
                    n_r[i] = n._replace(wait_ticks=wt)
                if n.wait_ticks <= 0 and n.enable and not n.note_off:
                    if not self.channels[n.parent].sustain:
                        n_r[i] = n._replace(note_off=True)
            for i in range(self.channels.count):
                if not self.channels[i].enable:
                    continue

                c: Channel = self.channels[i]
                for ep in range(len(self.rip_ears)):
                    if self.rip_ears[ep] == c.patch_num:
                        self.channels[i] = c._replace(mute=True)

                if c.wait_ticks > 0:
                    wt = c.wait_ticks - (self.tick_ctr - self.prv_tick)
                    self.channels[i]._replace(wait_tick=wt)

                o = True

                ch = self.channels

                while True:
                    cb = c.evt_queue[c.pgm_ctr].cmd_byte
                    print(hex(cb))
                    if cb == 0xB1:
                        ch[i] = c._replace(enable=False)
                        o = False
                        break
                    elif cb == 0xB9:
                        ch[i] = c._replace(pgm_ctr=c.pgm_ctr + 1)
                    elif cb == 0xBB:
                        self.tempo = c.evt_queue[c.pgm_ctr].arg1 * 2
                        print(self.tempo)
                        if self.record:
                            ec = chr(0xFF) + chr(0x51)
                            self.buffer_evt(ec, self.ttl_ticks)
                            w = ((60000000 / self.tempo) & 0xFFFFFF) | 0x3000000
                            w = self.flip_lng(w)
                            self.mfile.wr_ltendian(w)
                            ch[i] = c._replace(pgm_ctr=c.pgm_ctr + 1)
                    elif cb == 0xBC:
                        t = sbyte_to_int(c.evt_queue[c.pgm_ctr].arg1)
                        ch[i] = c._replace(transpose=t, pgm_ctr=c.pgm_ctr + 1)
                    elif cb == 0xBD:
                        pn = c.evt_queue[c.pgm_ctr].arg1
                        if self.dct_exists(self.directs, c.patch_num):
                            ot = self.directs[str(c.patch_num)].output
                        elif self.inst_exists(c.patch_num):
                            ot = ChannelTypes.MUL_SMP
                        elif self.drm_exists(c.patch_num):
                            ot = ChannelTypes.DRUMKIT
                        else:
                            ot = ChannelTypes.NULL
                        ch[i] = c._replace(
                            patch_num=pn, output=ot, pgm_ctr=c.pgm_ctr + 1)
                        # TODO: SelectMidiInstrument
                        ec = chr(0xC0 + i) + chr(self.mpatch_map[c.patch_num])
                        self.buffer_evt(ec, self.ttl_ticks)
                    elif cb == 0xBE:
                        v = c.evt_queue[c.pgm_ctr].arg1
                        na = self.note_arr
                        for note in c.notes:
                            n: Note = na[note.note_id]
                            if n.enable and n.parent == i:
                                dav = n.velocity / 0x7F * v / 0x7F * int(
                                    n.env_pos)
                                if mutethis:
                                    dav = 0
                                if self.output == SongTypes.WAVE:
                                    d = dav * 0 if c.mute else 1
                                    fmod.FSOUND_SetVolume(n.fmod_channel, d)
                        ch[i] = c._replace(pgm_ctr=c.pgm_ctr + 1, main_vol=v)
                    elif cb == 0xBF:
                        p = c.evt_queue[c.pgm_ctr].arg1
                        na = self.note_arr
                        for note in c.notes:
                            n: Note = na[note.note_id]
                            if n.enable and n.parent == i:
                                fmod.FSOUND_SetPan(n.fmod_channel,
                                                   c.panning * 2)
                        ch[i] = c._replace(pgm_ctr=c.pgm_ctr + 1, panning=p)
                    elif cb == 0xC0:
                        pb = c.evt_queue[c.pgm_ctr].arg1
                        ch[i] = c._replace(pgm_ctr=c.pgm_ctr + 1, pitch=pb)
                        na = self.note_arr
                        for note in c.notes:
                            n: Note = na[note.note_id]
                            if n.enable and n.parent == i:
                                f = n.freq * 2**(1 / 12)**((
                                    c.pitch - 0x40) / 0x40 * c.pitch_range)
                                fmod.FSOUND_SetFrequency(n.fmod_channel, f)
                    elif cb == 0xC1:
                        pbr = sbyte_to_int(c.evt_queue[c.pgm_ctr].arg1)
                        ch[i] = c._replace(
                            pgm_ctr=c.pgm_ctr + 1, pitch_range=pbr)
                        na = self.note_arr
                        for note in c.notes:
                            n: Note = na[note.note_id]
                            if n.enable and n.parent == i:
                                f = n.freq * 2**(1 / 12)**((
                                    c.pitch - 0x40) / 0x40 * c.pitch_range)
                                fmod.FSOUND_SetFrequency(n.fmod_channel, f)
                    elif cb == 0xC2:
                        vd = c.evt_queue[c.pgm_ctr].arg1
                        ch[i] = c._replace(pgm_ctr=c.pgm_ctr + 1, vib_depth=vd)
                    elif cb == 0xC4:
                        vr = c.evt_queue[c.pgm_ctr].arg1
                        ch[i] = c._replace(pgm_ctr=c.pgm_ctr + 1, vib_rate=vr)
                    elif cb == 0xCE:
                        s = False
                        na = self.note_arr
                        for note in c.notes:
                            n: Note = na[note.note_id]
                            if n.enable and not n.note_off:
                                na[note.note_id] = n._replace(note_off=True)
                        ch[i] = c._replace(pgm_ctr=c.pgm_ctr + 1, sustain=s)
                    elif cb == 0xB3:
                        sc = c.sub_ctr + 1
                        rp = c.pgm_ctr + 1
                        pc = c.subs[c.sub_ctr].evt_q_ptr
                        i = True
                        ch[i] = c._replace(
                            pgm_ctr=pc, sub_ctr=sc, rtn_ptr=rp, in_sub=i)
                    elif cb == 0xB4:
                        if c.in_sub:
                            pc = c.rtn_ptr
                            i = False
                        else:
                            pc = c.pgm_ctr + 1
                            i = c.in_sub
                        ch[i] = c._replace(pgm_ctr=pc, in_sub=i)
                    elif cb == 0xB2:
                        looped = True
                        i = False
                        pc = c.loop_ptr
                        ch[i] = c._replace(pgm_ctr=pc, in_sub=i)
                    elif cb >= 0xCF:
                        input()
                        e = c.evt_queue[c.pgm_ctr]
                        cb = e.cmd_byte
                        ll = stlen_to_ticks(cb - 0xCF) + 1
                        s = c.sustain
                        if cb == 0xCF:
                            s = True
                            ll = 0
                        nn = e.arg1
                        vv = e.arg2
                        uu = e.arg3
                        self.note_q.add(True, 0, nn, 0, vv, i, uu, 0, 0, 0, 0,
                                        0, ll, c.patch_num)
                        print(self.note_q)
                        pc = c.pgm_ctr + 1
                        ch[i] = c._replace(pgm_ctr=pc, sustain=s)
                    elif cb <= 0xB0:
                        e = c.evt_queue[c.pgm_ctr]
                        if looped:
                            looped = False
                            if i == 1:
                                pass
                            wt = 0
                        else:
                            pc = c.pgm_ctr + 1
                            if pc > 1:
                                wt = e.ticks - c.evt_queue[c.pgm_ctr - 1].ticks
                            else:
                                wt = e.ticks
                    else:
                        pc = c.pgm_ctr + 1
                        ch[i] = c._replace(pgm_ctr=pc)
                    if c.wait_ticks > 0:
                        break
                if not o:
                    break
            if self.channels.count > 0:
                clear_channel: List[bool] = [
                    bool() for i in range(self.channels.count)
                ]
                for note in self.note_q:
                    note: Note
                    x = self.free_note()
                    na = self.note_arr
                    if x < 32:
                        na[x] = note
                        chan: Channel = self.channels[note.parent]
                        if not clear_channel[note.parent]:
                            clear_channel[note.parent] = True
                            for note2 in chan.notes:
                                n: Note = na[note2.note_id]
                                if n.enable and not n.note_off:
                                    na[note2.note_id] = n._replace(
                                        note_off=True)
                        chan.notes.add(x, str(x))
                        pat = note.patch_num
                        s_pat = str(pat)
                        nn = note.note_num
                        s_nn = str(nn)
                        n: Note = na[x]
                        out = (DirectTypes.DIRECT, DirectTypes.WAVE)
                        out2 = (DirectTypes.SQUARE1, DirectTypes.SQUARE2)
                        das = 0
                        if self.dct_exists(self.directs, pat):
                            dct: Direct = self.directs[s_pat]
                            ot = dct.output
                            ea = dct.env_attn
                            ed = dct.env_dcy
                            es = dct.env_sus
                            er = dct.env_rel

                            na[x] = n._replace(
                                output=ot,
                                env_attn=ea,
                                env_dcy=ed,
                                env_sus=es,
                                env_rel=er)
                            if ot in out:
                                s = self.smp_pool[das]
                                f = -1 if s.gb_wave else s.freq
                                das = str(dct.smp_id)
                                daf = note_to_freq(nn + (60 - dct.drum_key), f)
                                if s.gb_wave:
                                    daf /= 2
                            elif ot in out2:
                                das = f'square{dct.gb1 % 4}'
                                daf = note_to_freq(nn + (60 - dct.drum_key))
                            elif ot == DirectTypes.NOISE:
                                das = f'noise{dct.gb1 % 2}{int(random.random() * 3)}'
                                daf = note_to_freq(nn + (60 - dct.drum_key))
                            else:
                                das = ''
                        elif self.drm_exists(pat):
                            dct: Direct = self.drmkits[s_pat].directs[s_nn]
                            ot = dct.output
                            ea = dct.env_attn
                            ed = dct.env_dcy
                            es = dct.env_sus
                            er = dct.env_rel

                            na[x] = n._replace(
                                output=ot,
                                env_attn=ea,
                                env_dcy=ed,
                                env_sus=es,
                                env_rel=er)
                            if ot in out:
                                das = str(dct.smp_id)
                                smp: Sample = self.smp_pool[das]
                                if dct.fix_pitch and not smp.gb_wave:
                                    daf = smp.freq
                                else:
                                    daf = note_to_freq(dct.drum_key, -2
                                                       if smp.gb_wave else
                                                       smp.freq)
                            elif ot in out2:
                                das = f'sqaure{dct.gb1 % 4}'
                                daf = note_to_freq(dct.drum_key)
                            elif ot == DirectTypes.NOISE:
                                das = f'noise{dct.gb1 % 2}{int(random.random() * 3)}'
                                daf = note_to_freq(dct.drum_key)
                            else:
                                das = ''
                        else:
                            das = ''

                        if not das:
                            daf *= 2**(1 / 12)**self.transpose
                            dav = int(note.velocity / 0x7F) * int(
                                chan.main_vol / 0x7F) * 255
                            if mutethis:
                                dav = 0
                            ot = na[x].output
                            if ot == NoteTypes.SQUARE1:
                                if self.gb1_chan < 32:
                                    gbn: Note = na[self.gb1_chan]
                                    if self.output == SongTypes.WAVE:
                                        fmod.FSOUND_StopSound(gbn.fmod_channel)
                                na[self.gb1_chan] = gbn._replace(
                                    fmod_channel=0, enable=False)
                                self.channels[gbn.parent].notes.remove(
                                    str(self.gb1_chan))
                                self.gb1_chan = x
                            elif ot == NoteTypes.SQUARE2:
                                if self.gb2_chan < 32:
                                    gbn: Note = na[self.gb2_chan]
                                    if self.output == SongTypes.WAVE:
                                        fmod.FSOUND_StopSound(gbn.fmod_channel)
                                na[self.gb2_chan] = gbn._replace(
                                    fmod_channel=0, enable=False)
                                self.channels[gbn.parent].notes.remove(
                                    str(self.gb2_chan))
                                self.gb2_chan = x
                            elif ot == NoteTypes.WAVE:
                                if self.gb3_chan < 32:
                                    gbn: Note = na[self.gb3_chan]
                                    if self.output == SongTypes.WAVE:
                                        fmod.FSOUND_StopSound(gbn.fmod_channel)
                                na[self.gb3_chan] = gbn._replace(
                                    fmod_channel=0, enable=False)
                                self.channels[gbn.parent].notes.remove(
                                    str(self.gb3_chan))
                                self.gb3_chan = x
                            elif ot == NoteTypes.NOISE:
                                if self.gb4_chan < 32:
                                    gbn: Note = na[self.gb4_chan]
                                    if self.output == SongTypes.WAVE:
                                        fmod.FSOUND_StopSound(gbn.fmod_channel)
                                na[self.gb4_chan] = gbn._replace(
                                    fmod_channel=0, enable=False)
                                self.channels[gbn.parent].notes.remove(
                                    str(self.gb4_chan))
                                self.gb4_chan = x

                            n: Note = na[x]
                            if self.output == SongTypes.WAVE:
                                if not mutethis:
                                    fc = fmod.FSOUND_PlaySound(
                                        x + 1, self.smp_pool[das].fmod_smp)
                                    print(fc)
                                else:
                                    x = x
                            else:
                                fc = note.parent
                            na[x] = n._replace(
                                fmod_channel=fc,
                                freq=daf,
                                phase=NotePhases.INITIAL)
                            n: Note = na[x]
                            if self.output == SongTypes.WAVE:
                                fmod.FSOUND_SetFrequency(
                                    n.fmod_channel, (daf * 2**(1 / 12))
                                    **((chan.pitch - 0x40) / 0x40 *
                                       chan.pitch_range))
                                fmod.FSOUND_SetVolume(n.fmod_channel, dav * 0
                                                      if chan.mute else 1)
                                fmod.FSOUND_SetPan(n.fmod_channel,
                                                   chan.panning * 2)
                            # TODO: RaiseEvent PlayedANote
            self.note_q.clear()
            na = self.note_arr

            if self.note_f_ctr > 0:
                for i in range(32):
                    n: Note = na[i]
                    if na[i].enable:
                        if n.output == NoteTypes.DIRECT:
                            if n.note_off and n.phase < NotePhases.RELEASE:
                                es = 0
                                np = NotePhases.RELEASE
                                na[i] = n._replace(env_step=es, phase=np)
                            n: Note = na[i]
                            if not n.env_step or n.env_pos == n.env_dest or (
                                    not n.env_step and (n.env_pos <= n.env_dest)
                            ) or (n.env_step >= 0 and n.env_pos >= n.env_dest):
                                np = n.phase
                                if np == NotePhases.INITIAL:
                                    np = NotePhases.ATTACK
                                    ep = 0
                                    ed = 255
                                    es = n.env_attn
                                    na[i] = n._replace(
                                        phase=np,
                                        env_pos=ep,
                                        env_dest=ed,
                                        env_sus=es)
                                elif np == NotePhases.ATTACK:
                                    np = NotePhases.DECAY
                                    ed = n.env_sus
                                    es = (n.env_dcy - 0x100) / 2
                                    na[i] = n._replace(
                                        phase=np, env_dest=ed, env_eus=es)
                                elif np == NotePhases.DECAY:
                                    np = NotePhases.SUSTAIN
                                    es = 0
                                    na[i] = n._replace(phase=np, env_sus=0)
                                elif np == NotePhases.RELEASE:
                                    np = NotePhases.NOTEOFF
                                    ed = 0
                                    es = n.env_rel - 0x100
                                    na[i] = n._replace(
                                        phase=np, env_dest=0, env_sus=es)
                                elif np == NotePhases.NOTEOFF:
                                    if self.output == SongTypes.WAVE:
                                        fmod.FSOUND_StopSound(n.fmod_channel)
                                n: Note = na[i]
                        nex = n.env_pos = n.env_step
                        if nex > n.env_dest and n.env_step > 0 or nex < n.env_dest and n.env_step < 0:
                            nex = n.env_dest
                        na[i] = n._replace(env_pos=nex)
                        n: Note = na[i]
                        dav = int(n.velocity / 0x7F) * int(
                            self.channels[n.parent].main_vol / 0x7F) * (
                                int(n.env_pos) / 0xFF * 255)
                        if mutethis:
                            dav = 0
                        if self.output == SongTypes.WAVE:
                            fmod.FSOUND_SetVolume(
                                n.fmod_channel, dav * 0
                                if self.channels[n.parent].mute else 1)
                    else:
                        if n.note_off and n.phase < NotePhases.RELEASE:
                            es = 0
                            np = NotePhases.RELEASE
                            na[i] = n._replace(env_step=es, phase=np)
                            n: Note = na[i]
                        if not n.env_step or n.env_pos == n.env_dest or (
                                not n.env_step and
                            (n.env_pos <= n.env_dest)) or (
                                n.env_step >= 0 and n.env_pos >= n.env_dest):
                            np = n.phase
                            if np == NotePhases.INITIAL:
                                np = NotePhases.ATTACK
                                ep = 0
                                ed = 255
                                es = 0x100 - n.env_attn * 8
                                na[i] = n._replace(
                                    phase=np,
                                    env_pos=ep,
                                    env_dest=ed,
                                    env_step=es)
                            elif np == NotePhases.ATTACK:
                                np = NotePhases.DECAY
                                ed = n.env_sus
                                es = -n.env_dcy * 2
                                na[i] = n._replace(
                                    phase=np, env_dest=ed, env_step=es)
                            elif np == NotePhases.DECAY:
                                np = NotePhases.SUSTAIN
                                es = 0
                                na[i] = n._replace(phase=np, env_step=es)
                            elif np == NotePhases.SUSTAIN:
                                es = 0
                                na[i] = n._replace(env_step=es)
                            elif np == NotePhases.RELEASE:
                                np = NotePhases.NOTEOFF
                                ed = 0
                                es = (0x8 - n.env_rel) * 2
                                na[i] = n._replace(
                                    phase=np, env_dest=ed, env_step=es)
                            elif np == NotePhases.NOTEOFF:
                                ot = n.output
                                if ot == NoteTypes.SQUARE1:
                                    self.gb1_chan = 255
                                elif ot == NoteTypes.SQUARE2:
                                    self.gb2_chan = 255
                                elif ot == NoteTypes.WAVE:
                                    self.gb3_chan = 255
                                elif ot == NoteTypes.NOISE:
                                    self.gb4_chan = 255
                                if self.output == SongTypes.WAVE:
                                    fmod.FSOUND_StopSound(n.fmod_channel)
                                self.channels[n.parent].notes.remove(str(i))
                                na[i] = n._replace(fmod_channel=0, enable=False)
                            n: Note = na[i]

                        nex = n.env_pos + n.env_step
                        if nex > n.env_dest and n.env_step > 0 or nex < n.env_dest and n.env_step > 0:
                            nex = n.env_dest
                        na[i] = n._replace(env_pos=nex)

                        dav = int(n.velocity / 0x7F) * int(
                            self.channels[n.parent].main_vol / 0x7F) * (
                                int(n.env_pos) / 0xFF * 255)
                        if mutethis:
                            dav = 0
                        if self.output == SongTypes.WAVE:
                            fmod.FSOUND_SetVolume(
                                n.fmod_channel, dav * 0
                                if self.channels[n.parent].mute else 1)

            xmmm = False
            for i in range(self.channels.count):
                if self.channels[i].enable:
                    xmmm = True
            if not xmmm or not self.tempo:
                pass
                # self.stop_song()
                # TODO: RaiseEvent SongFinish

        self.prv_tick = 0
        # self.tick_ctr = 0
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
    d = Decoder()
    d.play_song('H:\\Merci\\Downloads\\Sappy\\MZM.gba', 1, 0x8F2C0)
    while True:
        d.tick_ctr = 1
        d.evt_processor_timer(1)
        #fmod.FSOUND_Update()
        print(
            fsound_get_error_string(fmod.FSOUND_GetError()), d.ttl_msecs,
            d.tick_ctr, d.ttl_ticks)


if __name__ == '__main__':
    main()
