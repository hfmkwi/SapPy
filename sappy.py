#!python
#-*- coding: utf-8 -*-
# pylint disable=C0103, C0326, E1120, R0902, R0903, R0904, R0912, R0913, R0914, R0915, R1702
# pylint: disable=W0614
# TODO: Either use the original FMOD dlls or find a sound engine.
"""Main file."""
import math
from os import remove
from random import random
from logging import INFO, basicConfig, getLogger
from typing import List, NamedTuple, Union

from containers import *
from fileio import *
from fmod import *
from player import *

BASE = math.pow(2, 1 / 12)


class Decoder(object):
    """Decoder/interpreter for Sappy code."""
    DEBUG = False
    GB_SQ_MULTI = 0.5 / 4
    GB_WAV_MULTI = 0.5
    GB_WAV_BASE_FREQ = 880
    GB_NSE_MULTI = 0.5
    SAPPY_PPQN = 24

    if DEBUG:
        basicConfig(level=DEBUG)
    else:
        basicConfig(level=None)
    log = getLogger(name=__name__)

    def __init__(self):
        # yapf: disable
        self.playing:      bool                        = False
        self.gb1_chan:     int                         = 0
        self.gb2_chan:     int                         = 0
        self.gb3_chan:     int                         = 0
        self.gb4_chan:     int                         = 0
        self.incr:         int                         = 0
        self.inst_tbl_ptr: int                         = 0
        self.layer:        int                         = 0
        self.sng_lst_ptr:  int                         = 0
        self.sng_num:      int                         = 0
        self.sng_ptr:      int                         = 0
        self.tempo:        int                         = 0
        self.transpose:    int                         = 0
        self._gbl_vol:     int                         = 256
        self.note_f_ctr:   float                       = 0.0
        self.tick_ctr:     float                       = 0.0
        self.rip_ears:     Collection                  = Collection()
        self.mdrum_map:    list                        = []
        self.mpatch_map:   list                        = []
        self.mpatch_tbl:   list                        = []
        self.fpath:        str                         = ''
        self.mfile:        File                        = None
        self.wfile:        File                        = None
        self.channels:     ChannelQueue[Channel]       = ChannelQueue()  # pylint:    disable = E1136
        self.dct_head:     DirectHeader                = DirectHeader()
        self.directs:      DirectQueue[Direct]         = DirectQueue()  # pylint:     disable = E1136
        self.drm_head:     DrumKitHeader               = DrumKitHeader()
        self.drmkits:      DrumKitQueue[DrumKit]       = DrumKitQueue()  # pylint:    disable = E1136
        self.inst_head:    InstrumentHeader            = InstrumentHeader()
        self.insts:        InstrumentQueue[Instrument] = InstrumentQueue()  # pylint: disable = E1136
        self.note_arr:     List                        = Collection([Note(*[0]*6)] * 32)
        self.nse_wavs:     List[List[str]]             = [[[] for i in range(10)] for i in range(2)]
        self.mul_head:     MultiHeader                 = MultiHeader()
        self.gb_head:      NoiseHeader                 = NoiseHeader()
        self.note_q:       NoteQueue[Note]             = NoteQueue()  # pylint:       disable = E1136
        self.smp_head:     SampleHeader                = SampleHeader()
        self.smp_pool:     SampleQueue[Sample]         = SampleQueue()  # pylint:     disable = E1136
        self.just_looped:  bool                        = False
        # yapf: enable
        sz = 16383
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
        # """UKNOWN"""
        # yapf: disable
        with direct as d:
            d.drum_key  = int(inst_head.drum_pitch)
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
            # for i in range(32):
            if self.note_arr[i].enable is False:
                return i
        return 255

    def get_smp(self, smp: Sample, dct_head: DirectHeader,
                smp_head: SampleHeader, use_readstr: bool) -> None:
        """UNKNOWN"""
        smp.smp_id = dct_head.smp_head
        sid = smp.smp_id
        if self.smp_exists(sid):
            return
        self.smp_pool.add(str(sid))
        w_smp = self.smp_pool[str(sid)]
        smp_head = rd_smp_head(1, File.gba_ptr_to_addr(sid))
        if smp.output == DirectTypes.DIRECT:
            w_smp.size = smp_head.size
            w_smp.freq = smp_head.freq * 64
            w_smp.loop_start = smp_head.loop
            w_smp.loop = smp_head.flags > 0
            w_smp.gb_wave = False
            self.log.debug(
                f'{smp_head} {sid:#x} {File.gba_ptr_to_addr(sid):#x}'
            )
            # raise Exception
            if use_readstr:
                w_smp.smp_data = self.wfile.rd_str(smp_head.size)
            else:
                w_smp.smp_data = self.wfile._file.tell()
        else:
            w_smp.size = 32
            w_smp.freq = self.GB_WAV_BASE_FREQ
            w_smp.loop_start = 0
            w_smp.loop = True
            w_smp.gb_wave = True
            tsi = self.wfile.rd_str(16, File.gba_ptr_to_addr(sid))
            w_smp.smp_data = ""
            for ai in range(32):
                bi = ai % 2
                l = int(ai / 2)
                w_smp.smp_data += chr(
                    int((((0 if tsi[l:l + 1] ==
                            '' else ord(tsi[l:l + 1])) //
                            (16**bi)) % 16) *
                        (self.GB_WAV_MULTI * 16)))

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
    def load_song(self, fpath: str, sng_num: int, sng_list_ptr: int = None,
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
        for i in range(31, -1, -1):
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
            pc = self.wfile.rd_gba_ptr(a + 4 + (i + 1) * 4)
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
                elif 0xB5 <= c <= 0xCD:
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
                    xta.add(sub)
                    self.log.debug(
                        f'| PGM: {pc:#x} | CMD: {c:#x} | SUB ADDR | {sub:<#x}')
                    pc += 5
                elif 0xD0 <= c <= 0xFF:
                    self.log.debug(f'| PGM: {pc:#x} | CMD: {c:#x} | BGN NOTE |')
                    pc += 1
                    while self.wfile.rd_byte() < 0x80:
                        pc += 1
                    self.log.debug(f'| PGM: {pc:#x} | CMD: {c:#x} | END NOTE |')

                if c == 0xb1:
                    break
            self.channels[i].track_len = pc - self.channels[i].track_ptr
            self.log.debug(
                f'| PGM: {pc:#x} | CMD: {c:#x} | SET TLEN | {self.channels[i].track_len}'
            )
            pc = self.wfile.rd_gba_ptr(a + 4 + (i + 1) * 4)

            cticks = 0
            lc = 0xBE
            lln: List = [0] * 66
            llv: List = [0] * 66
            lla: List = [0] * 66
            lp = 0
            insub = 0
            tR = 0
            self.channels[i].loop_ptr = -1
            self.log.debug(f'| CHN: {i:>#8} | BEGIN EVT |')
            while True:
                self.wfile.rd_addr = pc
                if pc >= loop_offset and self.channels[i].loop_ptr == -1 and loop_offset != -1:
                    self.channels[i].loop_ptr = self.channels[i].evt_queue.count
                c = self.wfile.rd_byte()
                if (c != 0xB9 and 0xB5 <= c < 0xC5) or c == 0xCD:
                    D = self.wfile.rd_byte()
                    if c == 0xBC:
                        tR = sbyte_to_int(D)
                        self.log.debug(
                            f'| PGM: {pc:#x} | CMD: {c:#x} | SET TRPS | {tR:<#x}'
                        )
                    if c == 0xBD:
                        lp = D
                        self.log.debug(
                            f'| PGM: {pc:#x} | CMD: {c:#x} | SET INST | {lp:<#x}'
                        )
                    if c == 0xBE or c == 0xBF or c == 0xC0 or c == 0xC4 or c == 0xCD:
                        lc = c
                        self.log.debug(
                            f'| PGM: {pc:#x} | CMD: {c:#x} | GET ATTR | {lc:<#x}'
                        )
                    self.channels[i].evt_queue.add(cticks, c, D, 0, 0)
                    self.log.debug(
                        f'| PGM: {pc:#x} | CMD: {c:#x} | EVT PLAY | TIME: {cticks:<4} | CTRL: {c:<#4x} | ARG1: {D:<#4x} | ARG2: 0x00 | ARG3: 0x00'
                    )
                    pc += 2
                elif 0xC4 < c < 0xCF:
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
                        self.log.debug(
                            f'| PGM: {pc:#x} | CMD: {c:#x} | END SUB  |')
                        pc = rpc  # pylint: disable=E0601
                        insub = 0
                    else:
                        self.log.debug(
                            f'| PGM: {pc:#x} | CMD: {c:#x} | RTN EXEC |')
                        pc += 1
                elif c == 0xb3:
                    self.log.debug(f'| PGM: {pc:#x} | CMD: {c:#x} | BGN SUB  |')
                    rpc = pc + 5
                    insub = 1
                    pc = self.wfile.rd_gba_ptr()
                elif 0xCF <= c <= 0xFF:
                    pc += 1
                    lc = c

                    g = False
                    nc = 0
                    while not g:
                        self.wfile.rd_addr = pc
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
                        if self.patch_exists(lp) is False:
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
                                        self.drm_head.dct_tbl + pn * 12) + 2)
                                self.drmkits.add(str(lp))
                                self.drmkits[str(lp)].directs.add(str(pn))
                                self.set_direct(
                                    self.drmkits[str(lp)].directs[str(pn)],
                                    self.inst_head, self.dct_head, self.gb_head)
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
                                    self.get_smp(
                                        self.drmkits[str(lp)].directs[str(pn)],
                                        self.dct_head, self.smp_head, False)
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
                                        self.mul_head.dct_tbl + cdr * 12) + 2)
                                self.insts[str(lp)].directs.add(str(cdr))
                                self.set_direct(
                                    self.insts[str(lp)].directs[str(cdr)],
                                    self.inst_head, self.dct_head, self.gb_head)
                                self.log.debug(
                                    f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | MULTI HEAD | {self.mul_head}'
                                )
                                self.log.debug(
                                    f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | NEW INST   | {self.insts[str(lp)]}'
                                )
                                self.log.debug(
                                    f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | NEW KEYMAP | {self.insts[str(lp)].kmaps.data}'
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
                                    self.get_smp(
                                        self.insts[str(lp)].directs[str(cdr)],
                                        self.dct_head, self.smp_head, False)
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW MULTI | GET SAMPLE | {self.insts[str(lp)].directs[str(cdr)]}'
                                    )
                            else:  # Direct/GB Sample
                                self.dct_head = rd_dct_head(1)
                                self.gb_head = rd_nse_head(
                                    1, self.inst_tbl_ptr + lp * 12 + 2)
                                self.directs.add(str(lp))
                                self.set_direct(self.directs[str(lp)],
                                                self.inst_head, self.dct_head,
                                                self.gb_head)
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
                                                 self.dct_head, self.smp_head,
                                                 True)
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | NW DCT   | GET SAMPLE | {self.directs[str(lp)]}'
                                    )
                        else:  # Patch exists
                            self.inst_head = rd_inst_head(
                                1, self.inst_tbl_ptr + lp * 12)
                            self.log.debug(
                                f'| PGM: {pc:#x} | CMD: {c:#x} | PC.EXIST | PREV: {lp:<#4x} | PNUM: {pn:<#4x} | HEAD: {self.inst_head}'
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
                                        self.drm_head.dct_tbl + pn * 12) + 2)
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
                                if self.dct_exists(
                                        self.drmkits[str(lp)].directs,
                                        pn) is False:
                                    self.drmkits[str(lp)].directs.add(str(pn))
                                    self.set_direct(
                                        self.drmkits[str(lp)].directs[str(pn)],
                                        self.inst_head, self.dct_head,
                                        self.gb_head)
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | DM EXIST | NEW DIRECT | SET DIRECT | {self.drmkits[str(lp)].directs[str(pn)]}'
                                    )
                                    if self.drmkits[str(lp)].directs[str(
                                            pn)].output in out:
                                        self.get_mul_smp(
                                            self.drmkits[str(lp)].directs[str(
                                                pn)], self.dct_head,
                                            self.smp_head, False)
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | DM EXIST | NEW DIRECT | GET SAMPLE | {self.drmkits[str(lp)].directs[str(pn)]}'
                                        )
                            elif self.inst_head.channel & 0x40 == 0x40:
                                self.mul_head = rd_mul_head(1)
                                self.log.debug(
                                    f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | MULTI HEAD | {self.mul_head}'
                                )
                                if self.kmap_exists(self.insts[str(lp)].kmaps,
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
                                        self.mul_head.dct_tbl + cdr * 12))
                                self.dct_head = rd_dct_head(1)
                                self.gb_head = rd_nse_head(
                                    1,
                                    File.gba_ptr_to_addr(
                                        self.mul_head.dct_tbl + cdr * 12) + 2)
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
                                if self.dct_exists(self.insts[str(lp)].directs,
                                                   cdr) is False:
                                    self.insts[str(lp)].directs.add(str(cdr))
                                    self.set_direct(
                                        self.insts[str(lp)].directs[str(cdr)],
                                        self.inst_head, self.dct_head,
                                        self.gb_head)
                                    self.log.debug(
                                        f'| PGM: {pc:#x} | CMD: {c:#x} | ML EXIST | SET DIRECT | {self.insts[str(lp)].directs[str(cdr)]}'
                                    )
                                    if self.insts[str(lp)].directs[str(
                                            cdr)].output in out:
                                        self.get_mul_smp(
                                            self.insts[str(lp)].directs[str(
                                                cdr)], self.dct_head,
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
                        g = False
                        nc = 0
                        while g is False:
                            self.wfile.rd_addr = pc
                            D = self.wfile.rd_byte()
                            if D >= 0x80:
                                if nc == 0:
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
                            if self.patch_exists(lp) is False:
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
                                                     self.smp_head, True)
                                        self.log.debug(
                                            f'| PGM: {pc:#x} | CMD: {c:#x} | NW DRUM  | GET SAMPLE | {self.drmkits[str(lp)].directs[str(pn)]}'
                                        )
                                elif self.inst_head.channel & 0x40 == 0x40:
                                    self.mul_head = rd_mul_head(1)
                                    self.insts.add(str(lp))
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
                                    self.dct_head = rd_dct_head(1)
                                    self.gb_head = rd_nse_head(
                                        1, self.inst_tbl_ptr + lp * 12 + 2)
                                    self.directs.add(str(lp))
                                    if self.directs[str(lp)].output in out:
                                        self.get_mul_smp(
                                            self.directs[str(lp)],
                                            self.dct_head, self.smp_head, False)
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
                                    if self.dct_exists(
                                            self.drmkits[str(lp)].directs,
                                            pn) is False:
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
                                                File.gba_ptr_to_addr(
                                                    self.mul_head.kmap) + pn),
                                            str(pn))
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
                                    if self.dct_exists(
                                            self.insts[str(lp)].directs,
                                            cdr) is False:
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
                                                self.insts[str(lp)].directs[str(
                                                    cdr)], self.dct_head,
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
                if c == 0xB1 or c == 0xB2:
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
        systemInit(44100, 64, 0)
        self.log.debug(
            f'| FMOD | CODE: {getError():4} | INIT       |')
        setMasterVolume(self._gbl_vol)
        self.log.debug(
            f'| FMOD | CODE: {getError():4} | SET VOL    | {self.gbl_vol}'
        )
        for smp in self.smp_pool:
            smp: Sample
            self.log.debug(
                f'| FMOD | CODE: {getError():4} | S{self.val(smp.smp_data)} | GB:  {repr(smp.gb_wave):<5} |'
            )
            if smp.gb_wave is True:
                if self.val(smp.smp_data) == 0:
                    with open_new_file('temp.raw', 2) as f:
                        f.wr_str(smp.smp_data)
                    smp.fmod_smp = self.load_sample('temp.raw')
                    self.log.debug(
                        f'| FMOD | CODE: {getError():4} | LOAD SMP   | S{smp.fmod_smp} | SIZE: {smp.size} |'
                    )
                    setLoopPoints(smp.fmod_smp, 0, 31)
                    self.log.debug(
                        f'| FMOD | CODE: {getError():4} | SET LOOP   | (0, 31)'
                    )
                    remove('temp.raw')
                else:
                    smp.fmod_smp = self.load_sample(fpath, smp.smp_data, smp.size)
                    self.log.debug(
                        f'| FMOD | CODE: {getError():4} | LOAD SMP   | S{smp.fmod_smp} | SIZE: {smp.size} |'
                    )
                    setLoopPoints(smp.fmod_smp, 0, 31)
                    self.log.debug(
                        f'| FMOD | CODE: {getError():4} | SET LOOP   | (0, 31)'
                    )
            else:
                if self.val(smp.smp_data) == 0:
                    with open_new_file('temp.raw', 2) as f:
                        f.wr_str(smp.smp_data)
                    smp.fmod_smp = self.load_sample('temp.raw', loop=smp.loop, gb_wave=False)
                    self.log.debug(
                        f'| FMOD | CODE: {getError():4} | LOAD SMP   | S{smp.fmod_smp} | SIZE: {smp.size} |'
                    )
                    setLoopPoints(smp.fmod_smp, smp.loop_start, smp.size - 1)
                    self.log.debug(
                        f'| FMOD | CODE: {getError():4} | SET LOOP   | ({smp.loop_start},  {smp.size - 1})'
                    )
                    remove('temp.raw')
                else:
                    smp.fmod_smp = self.load_sample(fpath, smp.smp_data, smp.size, smp.loop, False)
                    self.log.debug(
                        f'| FMOD | CODE: {getError():4} | LOAD SMP   | S{smp.fmod_smp} | SIZE: {smp.size} |'
                    )
                    setLoopPoints(smp.fmod_smp, smp.loop_start, smp.size - 1)
                    self.log.debug(
                        f'| FMOD | CODE: {getError():4} | SET LOOP   | (0, 31)'
                    )
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
                    f'| FMOD | CODE: {getError():4} | SET LOOP   | (0, 16383)'
                )
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
                    f'| FMOD | CODE: {getError():4} | SET LOOP   | (0, 255)'
                )
                remove(f_nse)

        b1 = chr(int(0x80 + 0x7F * self.GB_SQ_MULTI))
        b2 = chr(int(0x80 - 0x7F * self.GB_SQ_MULTI))
        for mx2 in range(4):
            sq = f'square{mx2}'
            f_sq = f'{sq}.raw'
            self.smp_pool.add(sq)
            with self.smp_pool[sq] as smp:
                if mx2 == 3:
                    smp.smp_data = "".join([b1] * 24 + [b2] * 8)
                else:
                    smp.smp_data = "".join([b1] * (2**(mx2 + 2)) + [b2] *
                                           (32 - 2**(mx2 + 2)))
                smp.freq = 7040,
                smp.size = 32,
                with open_new_file(f_sq, 2) as f:
                    f.wr_str(smp.smp_data)
                smp.fmod_smp = self.load_sample(f_sq, 0, 0)
                self.log.debug(
                    f'| FMOD | CODE: {getError():4} | LOAD SQRE{mx2} | S{smp.fmod_smp}'
                )
                setLoopPoints(smp.fmod_smp, 0, 31)
                self.log.debug(
                    f'| FMOD | CODE: {getError():4} | SET LOOP   | (00, 31)'
                )
                remove(f_sq)

        self.gb1_chan = 255
        self.gb2_chan = 255
        self.gb3_chan = 255
        self.gb4_chan = 255

        self.tempo = 120
        self.incr = 0
        self.wfile.close()
        self.log.debug(
            f'| FMOD | CODE: {getError():4} | FINISH     |')
        self.log.debug(f'+------+------------+------------+')
        self.log.debug(f'+------------+------------+------------+')

    def load_sample(self, fpath: str, smp_data: Union[int, str] = 0, size: int = 0, loop: bool = True, gb_wave: bool=True):
        mask = FSoundModes._8BITS + FSoundModes.LOADRAW + FSoundModes.MONO
        if loop:
            mask += FSoundModes.LOOP_NORMAL
        if gb_wave:
            mask += FSoundModes.UNSIGNED
        else:
            mask += FSoundModes.SIGNED
        fpath = fpath.encode('ascii')
        mode = FSoundChannelSampleMode.FSOUND_FREE
        return sampleLoad(mode, fpath, mask, smp_data, size)

    def smp_exists(self, smp_id: int) -> bool:
        """Check if a sample exists in the available sample pool."""
        for smp in self.smp_pool:
            if smp.key == str(smp_id):
                return True
        return False

    def stop_song(self):
        """Stop playing a song."""
        try:
            File.from_id(1).close()
        except AttributeError:
            pass
        systemClose()

    def update_notes(self) -> None:
        for item in self.note_arr:
            item: Note
            if item.enable and item.wait_ticks > 0:
                item.wait_ticks -= 1
            elif item.wait_ticks <= 0 and item.enable is True and item.note_off is False:
                if self.channels[item.parent].sustain is False:
                    item.reset()

    def update_channels(self) -> None:
        in_for = True
        for plat, chan in enumerate(self.channels):
            if chan.enable is False:
                self.log.debug(f'| CHAN: {plat:>4} | SKIP EXEC  |')
                continue
            self.log.debug(f'| CHAN: {plat:>4} | BEGIN EXEC |')
            if chan.wait_ticks > 0:
                chan.wait_ticks -= 1
                self.log.debug(
                    f'| CHAN: {plat:>4} | CMD: NONE  | DELTA WAIT | TIME: {chan.wait_ticks:<5}'
                )
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
                        note = self.note_arr[nid.note_id]
                        print('be', note, note.parent, plat)
                        #if note.enable is True and note.parent == plat:
                        if not note.enable or note.parent != plat:
                            continue
                        iv = note.velocity / 0x7F
                        cv = chan.main_vol / 0x7F
                        ie = note.env_pos / 0xFF
                        dav = iv * cv * ie * 255
                        vol = 0 if chan.mute else int(dav)
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
                        print('bf', note, note.parent, plat)
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
                        print('c0', note, note.parent, plat)
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
                        print('ce', note, note.parent, plat)
                        if not note.enable or note.note_off:
                            continue
                        note.reset()
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
                        self.log.debug(f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | END SUB    |')
                    else:
                        chan.pgm_ctr += 1
                elif cmd_byte == 0xB2:
                    self.just_looped = True
                    chan.in_sub = False
                    chan.pgm_ctr = chan.loop_ptr
                    self.log.debug(f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | JUMP ADDR  | PTR: {chan.loop_ptr:<#5x}')
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
                    if self.just_looped:
                        self.just_looped = False
                        chan.wait_ticks = 0
                        continue
                    chan.pgm_ctr += 1
                    n_evt_queue = chan.evt_queue[chan.pgm_ctr]
                    if chan.pgm_ctr > 0:
                        chan.wait_ticks = n_evt_queue.ticks - evt_queue.ticks
                    else:
                        chan.wait_ticks = n_evt_queue.ticks
                else:
                    print(hex(cmd_byte), evt_queue)
                    #input()
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
                                pass
                            elif note.wait_ticks > -1:
                                note.reset()

                            self.log.debug(
                                f'| CHAN: {item.parent:>4} | NOTE: {nid.note_id:4} | NOTE OFF   |'
                            )

                chan.notes.add(x, str(x))
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

                if das != '':
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
                    self.note_arr[x].freq = daf
                    self.note_arr[x].phase = NotePhases.INITIAL
                    self.note_arr[x].fmod_channel = playSound(
                        x, self.smp_pool[das].fmod_smp)
                    setFrequency(self.note_arr[x].fmod_channel,
                                             freq)
                    setVolume(self.note_arr[x].fmod_channel, vol)
                    setPan(self.note_arr[x].fmod_channel, pan)
                    self.log.debug(f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | PLAY SOUND | F{self.note_arr[x].fmod_channel:<9} | DAS: {das:<5}')
                    self.log.debug(f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | SET FREQ   | DAF: {daf:>5}')
                    self.log.debug(f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | SET VOLUME | VOL: {vol:>5}')
                    self.log.debug(f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | SET PAN    | PAN: {pan:>5}')

    def advance_notes(self) -> None:
        for i in range(31, -1, -1):
            item = self.note_arr[i]
            if item.enable is False:
                continue
            if item.output == NoteTypes.DIRECT:
                if item.note_off and item.phase < NotePhases.RELEASE:
                    item.env_step = 0
                    item.phase = NotePhases.RELEASE
                if item.env_step == 0 or (
                        item.env_pos == item.env_dest) or (
                            item.env_step == 0 and
                            (item.env_pos <= item.env_dest)) or (
                                item.env_step >= 0 and
                                item.env_pos >= item.env_dest):
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
                        self.log.debug(f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | STOP DSMP  | F{item.fmod_channel:<9}')
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
                vol = int(dav * 0 if self.channels[item.parent]
                            .mute else dav * 1)
                setVolume(item.fmod_channel, vol)
                self.log.debug(
                    f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | SET DVOL   | VOL: {vol:>5}'
                )
            else:
                if item.note_off and item.phase < NotePhases.RELEASE:
                    item.env_step = 0
                    item.phase = NotePhases.RELEASE
                if item.env_step == 0 or (
                        item.env_pos == item.env_dest) or (
                            item.env_step == 0 and
                            (item.env_pos <= item.env_dest)) or (
                                item.env_step >= 0 and
                                item.env_pos >= item.env_dest):
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
                        stopSound(int(item.fmod_channel))
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
                vol = int(dav * 0 if self.channels[item.parent]
                            .mute else dav * 1)
                setVolume(item.fmod_channel, vol)
                self.log.debug(f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {getError():4} | SET VOLUME | VOL: {vol:>5}')

    def evt_processor_timer(self) -> None:
        if self.tick_ctr > 0:
            self.update_notes()
            self.update_channels()

            if self.channels.count > 0:
                self.play_notes()
            self.note_q.clear()

            if self.note_f_ctr > 0:
                self.advance_notes()
            xmmm = False
            for i in range(self.channels.count):
                if self.channels[i].enable:
                    xmmm = True
                    break
            if not xmmm or not self.tempo:
                self.stop_song()
                return None
            return 1

        self.tick_ctr = 0
        self.incr += 1
        if self.incr >= int(60000 / (self.tempo * self.SAPPY_PPQN)):
            self.tick_ctr = 1
            self.incr = 0

        self.note_f_ctr = 1

        return 0

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
