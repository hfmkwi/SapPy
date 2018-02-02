#!/usr/bin/python3
#-*- coding: utf-8 -*-
# pylint: disable=C0103, C0326, E1120, R0902, R0903, R0904, R0912, R0913, R0914, R0915, R1702
# pylint: disable=W0401, W0511, W0614
# TODO: Either use the original FMOD dlls or find a sound engine.
"""Main file."""
from enum import Enum
from logging import INFO, basicConfig, getLogger
from struct import unpack
from typing import List, NamedTuple

from containers import *
from fileio import *
from player import *


class SongOutputTypes(Enum):
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

    basicConfig(level=INFO)
    log = getLogger(name=__name__)

    def __init__(self):
        self.playing:      bool                        = bool()
        self.record:       bool                        = bool()
        self.inst_tbl_ptr: int                         = int()
        self.layer:        int                         = int()
        self.sng_lst_ptr:  int                         = int()
        self.sng_num:      int                         = int()
        self.sng_ptr:      int                         = int()
        self.ttl_ticks:    int                         = int()
        self.ttl_msecs:    int                         = int()
        self._gbl_vol:     int                         = 100
        self.prv_tick:     float                       = float()
        self.tick_ctr:     float                       = float()
        self.rip_ears:     list                        = list()
        self.mdrum_map:    list                        = list()
        self.mpatch_map:   list                        = list()
        self.mpatch_tbl:   list                        = list()
        self.fpath:        str                         = str()
        self.mfile:        File                        = None
        self.wfile:        File                        = None
        self.channels:     ChannelQueue[Channel]       = ChannelQueue()  # pylint:    disable = E1136
        self.dct_head:     DirectHeader                = DirectHeader()
        self.directs:      DirectQueue[Direct]         = DirectQueue()  # pylint:     disable = E1136
        self.drm_head:     DrumKitHeader               = DrumKitHeader()
        self.drmkits:      DrumKitQueue[DrumKit]       = DrumKitQueue()  # pylint:    disable = E1136
        self.inst_head:    InstrumentHeader            = InstrumentHeader()
        self.insts:        InstrumentQueue[Instrument] = InstrumentQueue()  # pylint: disable = E1136
        self.note_arr:     List[Note]                  = [Note()] * 32
        self.mul_head:     MultiHeader                 = MultiHeader()
        self.gb_head:      NoiseHeader                 = NoiseHeader()
        self.note_q:       NoteQueue[Note]             = NoteQueue()  # pylint:       disable = E1136
        self.last_evt:     RawMidiEvent                = RawMidiEvent()
        self.smp_head:     SampleHeader                = SampleHeader()
        self.smp_pool:     SampleQueue[Sample]         = SampleQueue()  # pylint:     disable = E1136

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
    def set_direct(queue: DirectQueue, dct_key: str, inst_head: InstrumentHeader,
                   dct_head: DirectHeader, gb_head: NoiseHeader) -> None:
        """UKNOWN"""
        # yapf: disable
        direct = queue.directs[dct_key]
        queue.directs[dct_key] = Direct(
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
            smp_id    = direct.smp_id,
            key       = direct.key
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

    def evt_processor_timer(self, msec: int) -> bool:
        """UKNOWN"""
        self.ttl_msecs += msec
        if self.tick_ctr:
            for i in range(32):
                note = self.note_arr[i]
                note: Note
                if note.enable and note.wait_ticks > 0:
                    w_ticks = note.wait_ticks - (self.tick_ctr - self.prv_tick)
                    self.note_arr[i] = note._replace(wait_ticks=w_ticks)
                if note.wait_ticks <= 0 and note.enable and not note.note_off:
                    if not self.channels[note.parent].sustain:
                        self.note_arr[i] = note._replace(note_off=True)
            for i in range(len(self.channels)):
                if not self.channels[i].enable:
                    continue
                channel = self.channels[i]
                for ep in self.rip_ears:
                    if ep == channel.patch_num:
                        self.channels[i] = channel._replace(mute=True)

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
        dct_q[dct_key] = dct_q[dct_key]._replace(
            smp_id=dct_head.smp_head)
        s_id = dct_q[dct_key].smp_id
        if not self.smp_exists(s_id):
            self.smp_pool.add(str(s_id))
            if dct_q[dct_key].output == DirectTypes.DIRECT:
                self.smp_head = rd_smp_head(
                    File.gba_ptr_to_addr(s_id))
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
                    smp_data=smp_data
                )
            else:
                tsi = self.wfile.rd_str(
                    16, File.gba_ptr_to_addr(s_id))
                smp_data = []
                for ai in range(32):
                    bi = ai % 2
                    newvariable73 = tsi[ai // 2:ai // 2 + 1]
                    if not newvariable73:
                        smp_pt = 0
                    else:
                        smp_pt = ord(newvariable73)
                    smp_pt = chr(smp_pt // 16 ** bi % 16 * self.GB_WAV_BASE_FREQ*16)
                    smp_data.append(smp_pt)
                smp_data = "".join(smp_data)
                self.smp_pool[str(s_id)] = self.smp_pool[str(s_id)].replace(
                    size=32,
                    freq=self.GB_WAV_BASE_FREQ,
                    loop_start=0,
                    loop=True,
                    gb_wave=True,
                    smp_data=smp_data
                )

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
        ptr = self.wfile.rd_gba_ptr(self.sng_lst_ptr + sng_num * 8)
        self.sng_ptr = ptr
        self.layer = self.wfile.rd_ltendian(4)
        pbyte = self.wfile.rd_byte(ptr)
        self.inst_tbl_ptr = self.wfile.rd_gba_ptr(ptr + 4)

        # TODO: raise LOADING_0

        xta = SubroutineQueue()
        for i in range(0, pbyte + 1):
            loop_addr = -1
            pgm_ctr = self.wfile.rd_gba_ptr(ptr + 4 + i * 4)
            self.channels.add()
            xta.clear()
            while True:
                ctl_byte = self.wfile.rd_byte(pgm_ctr)
                if ctl_byte >= 0x00 and ctl_byte <= 0xB0 or ctl_byte in (
                        0xCE, 0xCF, 0xB4):
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
            c_ei = 0
            ctrl = 0xbe
            lln: List = [None] * 66
            llv: List = [None] * 66
            lla: List = [None] * 66
            lp = 0
            src2 = 1
            insub = 0
            trnps = 0
            channels = self.channels
            cur_ch = channels[i]._replace(track_ptr=-1)
            input()
            while True:
                self.wfile.rd_addr = pgm_ctr
                print(pgm_ctr)
                chk_loop_addr = pgm_ctr >= loop_addr and loop_addr != -1
                if chk_loop_addr and cur_ch.loop_ptr == -1:
                    loop_ptr = cur_ch.evt_queue.count + 1
                    channels[i] = cur_ch._replace(loop_ptr=loop_ptr)
                ctl_byte = self.wfile.rd_byte()
                chk_byte_rg = 0xb5 <= ctl_byte < 0xc5
                if (chk_byte_rg and ctl_byte != 0xb9) or ctl_byte == 0xcd:
                    cmd_arg = self.wfile.rd_byte()
                    if ctl_byte == 0xbc:
                        trnps = sbyte_to_int(cmd_arg)
                    elif ctl_byte == 0xbd:
                        lp = cmd_arg
                    elif ctl_byte in (0xbe, 0xbf, 0xc0, 0xc4, 0xcd):
                        ctrl = ctl_byte
                    e_args = (cticks, ctl_byte, cmd_arg, 0, 0)
                    channels[i].evt_queue.add(*e_args)
                elif 0xc4 < ctl_byte < 0xcf:
                    channels[i].evt_queue.add(cticks, ctl_byte, 0, 0, 0)
                elif ctl_byte == 0xb9:
                    cmd_arg = self.wfile.rd_byte()
                    e = self.wfile.rd_byte()
                    f = self.wfile.rd_byte()
                    e_args = cticks, ctl_byte, cmd_arg, e, f
                    channels[i].evt_queue.add(*e_args)
                    pgm_ctr += 4
                elif ctl_byte == 0xb4:
                    if insub == 1:
                        pgm_ctr = rpc  # pylint: disable=E0601
                        in_sub = 0
                    else:
                        pgm_ctr += 1
                elif ctl_byte == 0xb3:
                    rpc = pgm_ctr + 5
                    in_sub = 1
                    pgm_ctr = self.wfile.rd_gba_ptr()
                elif 0xcf <= ctl_byte <= 0xff:
                    pgm_ctr += 1
                    ctrl = ctl_byte
                    g = False
                    n_ctr = 0
                    while not g:
                        cmd_arg = self.wfile.rd_byte()
                        if cmd_arg >= 0x80:
                            if not n_ctr:
                                pn = lln[n_ctr] + trnps
                            l_args = llv[n_ctr], lla[n_ctr]
                            e_args = cticks, ctl_byte, pn, *l_args
                            channels[i].evt_queue.add(*e_args)
                            g = True
                        else:
                            lln[n_ctr] = cmd_arg
                            pgm_ctr += 1
                            e = self.wfile.rd_byte()
                            if e < 0x80:
                                llv[n_ctr] = e
                                pgm_ctr += 1
                                f = self.wfile.rd_byte()
                                if f >= 0x80:
                                    f = lla[n_ctr]
                                    g = True
                                else:
                                    lla[n_ctr] = f
                                    pgm_ctr += 1
                                    n_ctr += 1
                            else:
                                e = llv[n_ctr]
                                f = lla[n_ctr]
                                g = True
                            pn = cmd_arg + trnps
                            e_args = cticks, ctl_byte, pn, e, f
                            channels[i].evt_queue.add(*e_args)
                        if not self.patch_exists(lp):
                            inst_ptr = self.inst_tbl_ptr + lp * 12
                            self.inst_head = rd_inst_head(1, inst_ptr)
                            s_lp = str(lp)
                            s_pn = str(pn)
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
                            elif self.inst_head.channel & 0x40 == 0x40: # Multi
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
                                dct_head = rd_dct_head(1)
                                nse_ptr = inst_ptr + 2
                                nse_addr = File.gba_ptr_to_addr(nse_ptr)
                                self.gb_head = rd_nse_head(1, nse_addr)
                                dcts = self.insts[s_lp].directs
                                dcts.add(s_cdr)
                                h = self.inst_head, self.dct_head, self.gb_head
                                dct_args = dcts, s_cdr, *h
                                self.set_direct(*dct_args)
                                if dcts[s_cdr].output in smp_out:
                                    h = self.dct_head, self.smp_head
                                    self.get_smp(dcts[s_cdr], *h, False)
                            else: # Direct/GB Sample
                                self.dct_head = rd_dct_head(1)
                                nse_addr = self.inst_tbl_ptr + lp * 12 + 2
                                self.gb_head = rd_nse_head(1, nse_addr)
                                self.directs.add(s_lp)
                                h = self.inst_head, self.dct_head, self.gb_head
                                dct_args = self.directs, s_lp, *h
                                self.set_direct(*dct_args)
                        else: # Patch exists
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
                                    h = (
                                        self.inst_head,
                                        self.dct_head,
                                        self.gb_head
                                    )
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
                                        h = (
                                            self.inst_head,
                                            self.dct_head,
                                            self.gb_head
                                        )
                                        dct_args = dcts, s_cdr, *h
                                        self.set_direct(*dct_args)
                                        if dcts[s_cdr].output in smp_out:
                                            h = self.dct_head, self.smp_head
                                            m_args = dcts, s_cdr, *h, False
                                            self.get_mul_smp(*m_args)
                elif 0x00 <= ctl_byte < 0x80:
                    if ctrl < 0xCF:
                        evt_q = self.channels[i].evt_q
                        evt_q.add(cticks, ctrl, c, 0, 0)
                        pgm_ctr += 1
                    else:
                        c = ctrl
                        self.wfile.read_offset = pgm_ctr
                        g = False
                        n_ctr = 0
                        while not g:
                            d = self.wfile.rd_byte()
                            if d >= 0x80:
                                if not n_ctr:
                                    pn = lln[n_ctr] + trnps
                                    evt_q.add(cticks, c, pn, llv[n_ctr], lla[n_ctr])
                            else:
                                lln[n_ctr] = d
                                pgm_ctr += 1
                                e = self.wfile.rd_byte()
                                if e < 0x80:
                                    llv[n_ctr] = e
                                    pgm_ctr += 1
                                    f = self.wfile.rd_byte()
                                    if f >= 0x80:
                                        f = lla[n_ctr]
                                        g = True
                                    else:
                                        lla[n_ctr] = f
                                        pgm_ctr += 1
                                        n_ctr += 1
                                else:
                                    e = llv[n_ctr]
                                    f = lla[n_ctr]
                                    g = True
                                pn = d + trnps
                                evt_q.add(cticks, c, pn, e, f)
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
                                    h = (
                                        self.inst_head,
                                        self.dct_head,
                                        self.gb_head
                                    )
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
                                    h = (
                                        self.inst_head,
                                        self.dct_head,
                                        self.gb_head
                                    )
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
                                        h = (
                                            self.inst_head,
                                            self.dct_head,
                                            self.gb_head
                                        )
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
                                            h = (
                                                self.inst_head,
                                                self.dct_head
                                                self.gb_head
                                            )
                                            dct_args = dcts, s_cdr, *h
                                            self.set_direct(*dct_args)

    def smp_exists(self, smp_id: int) -> bool:
        """Check if a sample exists in the available sample pool."""
        return str(smp_id) in self.smp_pool

    def set_mpatch_map(self, ind: int, inst: int, transpose: int) -> None:
        """Bind a MIDI instrument to a specified MIDI key."""
        self.mpatch_map[ind] = inst
        self.mpatch_tbl[ind] = transpose

    def set_mdrum_map(self, ind: int, new_drum: int) -> None:
        """Bind a MIDI drum to a specified MIDI key."""
        self.mdrum_map[ind] = new_drum

    def stop_song(self):
        """Stop playing a song."""
        File.from_id(1).close()
        File.from_id(2).close()
        # TODO: disable event processor
        # TODO: close sound channel
        # TODO: close MIDI channel
        if self.record:
            self.log.debug('test')
            self.record = False
            self.mfile = File.from_id(42)
            self.mfile.write_little_endian(0x0AFF2F00)
            trk_len = self.mfile.size - 22
            dbg_vars = trk_len, self.ttl_ticks
            self.log.debug('StopSong(): Length: %s, total ticks: %s', *dbg_vars)
            self.mfile.write_little_endian(unpack(self.flip_lng(trk_len), 0x13))
        # TODO: raise SONG_FINISH



def main():
    """Main test method."""
    d = Decoder()
    d.play_song('H:\\Merci\\Downloads\\Sappy\\MZM.gba', 1, 0x0008F2C8)


if __name__ == '__main__':
    main()
