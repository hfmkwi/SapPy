#!/usr/bin/python3
#-*- coding: utf-8 -*-
# pylint: disable=C0103, C0326, R0902, R0903, R0913, W0511
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
        self.playing:     bool                        = bool()
        self.record:      bool                        = bool()
        self.ist_tbl_ptr: int                         = int()
        self.layer:       int                         = int()
        self.sng_lst_ptr: int                         = int()
        self.sng_num:     int                         = int()
        self.sng_ptr:     int                         = int()
        self.ttl_ticks:   int                         = int()
        self.ttl_msecs:   int                         = int()
        self._gbl_vol:    int                         = 100
        self.prv_tick:    float                       = float()
        self.tick_ctr:    float                       = float()
        self.rip_ears:    list                        = list()
        self.mdrum_map:   list                        = list()
        self.mpatch_map:  list                        = list()
        self.mpatch_tbl:  list                        = list()
        self.fpath:       str                         = str()
        self.mfile:       File                        = None
        self.wfile:       File                        = None
        self.channels:    ChannelQueue[Channel]       = ChannelQueue()
        self.dct_head:    DirectHeader                = DirectHeader()
        self.directs:     DirectQueue[Direct]         = DirectQueue()
        self.drm_head:    DrumKitHeader               = DrumKitHeader()
        self.drmkits:     DrumKitQueue[DrumKit]       = DrumKitQueue()
        self.ins_head:    InstrumentHeader            = InstrumentHeader()
        self.insts:       InstrumentQueue[Instrument] = InstrumentQueue()
        self.note_arr:    List[Note]                  = [Note()] * 32
        self.mul_head:    MultiHeader                 = MultiHeader()
        self.gb_head:     NoiseHeader                 = NoiseHeader()
        self.note_q:      NoteQueue[Note]             = NoteQueue()
        self.last_evt:    RawMidiEvent                = RawMidiEvent()
        self.smp_head:    SampleHeader                = SampleHeader()
        self.smp_pool:    SampleQueue[Sample]         = SampleQueue()

    @property
    def global_volume(self) -> int:
        return self._gbl_vol

    @global_volume.setter
    def global_volume(self, vol: int) -> None:
        self._gbl_vol = vol

    @staticmethod
    def dct_exists(dcts: DirectQueue, dct_id: int) -> bool:
        return str(dct_id) in dcts

    @staticmethod
    def flip_lng(val: int) -> int:
        return int.from_bytes(val.to_bytes(4, 'big'), 'little')

    @staticmethod
    def flip_int(val: int) -> int:
        return int.from_bytes(val.to_bytes(2, 'big'), 'little')

    @staticmethod
    def set_direct(queue: Collection, dct_key: str, inst_head: InstrumentHeader,
                   dct_head: DirectHeader, gb_head: NoiseHeader) -> None:
        # yapf: disable
        queue.directs[dct_key] = queue.directs[dct_key].replace(
            drum_key   = inst_head.drum_pitch,
            t_output     = DirectTypes(inst_head.channel & 7),
            env_attn = dct_head.attack,
            env_decay       = dct_head.hold,
            env_sustain     = dct_head.sustain,
            env_release     = dct_head.release,
            raw0            = dct_head.b0,
            raw1            = dct_head.b1,
            gb1             = gb_head.b2,
            gb2             = gb_head.b3,
            gb3             = gb_head.b4,
            gb4             = gb_head.b5,
            fixed_pitch     = (inst_head.channel & 0x08) == 0x08,
            reverse         = (inst_head.channel & 0x10) == 0x10,
            sample_id       = queue.directs[dct_key].sample_id,
            key             = queue.directs[dct_key].key
        )
        # yapf: enable

    @staticmethod
    def write_var_len(ch: int, val: int) -> None:
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
        self.rip_ears.append(inst_id)
        # self.rip_ears[self.rip_ear_cnt] = inst_id
        # self.rip_ear_cnt += 1

    def buffer_evt(self, evt_code: str, ticks: int) -> None:
        self.mfile: File
        if not self.record or self.mfile.file_id != 42:
            return
        d_raw=ticks - self.last_evt.ticks
        evt_code=int(evt_code)
        evt = RawMidiEvent(
            ticks=ticks,
            d_raw=d_raw,
            evt_code=evt_code)
        self.write_var_len(self.mfile.file_id, evt.d_raw)
        self.mfile.write_string(evt.evt_code)
        self.last_evt = evt

    def clear_mpatch_map(self):
        self.mpatch_map.clear()
        self.mdrum_map.clear()
        self.rip_ears.clear()

    def drm_exists(self, patch: int) -> bool:
        return str(patch) in self.drmkits

    def evt_processor_timer(self, msec: int) -> bool:
        self.ttl_msecs += msec
        if self.tick_ctr:
            for i in range(32):
                note = self.note_arr[i]
                if note.enable and note.wait_ticks > 0:
                    w_ticks = note.wait_ticks - (self.tick_ctr - self.prv_tick)
                    self.note_arr[i] = note._replace()
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
        for i in range(32):
            if not self.note_arr[i].enable:
                note = i
        return note

    def get_smp(self, q: Collection, dct_key: str, dct_head: DirectHeader,
                smp_head: SampleHeader, use_readstr: bool) -> None:
        dct_q = q.directs
        dct_q[dct_key] = dct_q[dct_key]._replace(
            sample_id=dct_head.smp_head)
        s_id = dct_q[dct_key].sample_id
        if not self.smp_exists(s_id):
            self.smp_pool.add(str(s_id))
            if dct_q[dct_key].t_output == DirectTypes.DIRECT:
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
                    loop_enable=smp_head.flags > 0,
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
                    loop_enable=True,
                    gb_wave=True,
                    smp_data=smp_data
                )

    get_multi_smp = get_smp

    def inst_exists(self, patch: int) -> bool:
        return str(patch) in self.insts

    @staticmethod
    def kmap_exists(kmaps: KeyMapQueue, kmap_id: int) -> bool:
        return str(kmap_id) in kmaps

    def note_belongs_to_channel(self, note_id: bytes, chnl_id: int) -> bool:
        return self.note_arr[note_id].parent == chnl_id

    def patch_exists(self, lp: int) -> bool:
        lp = str(lp)
        return lp in self.directs or self.inst_exists(lp) or self.drm_exists(lp)

    # yapf: disable
    def play_song(self, fpath: str, sng_num: int, sng_list_ptr: int = None,
                  record: bool = False, record_to: str = "midiout.mid"):
        # yapf: enable
        self.fpath = fpath
        self.sng_lst_ptr = sng_list_ptr
        self.sng_num = sng_num

        if self.playing:
            # TODO: raise SONG_STOP
            pass

        self.ins_head = InstrumentHeader
        self.drm_head = DrumKitHeader
        self.dct_head = DirectHeader
        self.smp_head = SampleHeader
        self.mul_head = MultiHeader
        self.gb_head = NoiseHeader

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
        self.ist_tbl_ptr = self.wfile.rd_gba_ptr(ptr + 4)

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
            transpose = 0
            self.channels[i] = self.channels[i]._replace(track_ptr=-1)
            channel = self.channels[i]
            input()
            while True:
                self.wfile.rd_addr = pgm_ctr
                print(pgm_ctr)
                if pgm_ctr >= loop_addr and channel.loop_ptr == -1 and loop_addr != -1:
                    self.channels[i] = channel._replace(loop_ptr=channel.evt_queue.count + 1)
                ctl_byte = self.wfile.rd_byte()
                if (ctl_byte != 0xb9 and ctl_byte >= 0xb5 and
                        ctl_byte < 0xc5) or ctl_byte == 0xcd:
                    cmd_arg = self.wfile.rd_byte()
                    if ctl_byte == 0xbc:
                        transpose = sbyte_to_int(cmd_arg)
                    elif ctl_byte == 0xbd:
                        lp = cmd_arg
                    elif ctl_byte in (0xbe, 0xbf, 0xc0, 0xc4, 0xcd):
                        ctrl = ctl_byte
                    self.channels[i].evt_queue.add(cticks, ctl_byte, cmd_arg,
                                                     0, 0)
                elif ctl_byte > 0xc4 and ctl_byte < 0xcf:
                    self.channels[i].evt_queue.add(cticks, ctl_byte, 0, 0, 0)
                elif ctl_byte == 0xb9:
                    cmd_arg = self.wfile.rd_byte()
                    e = self.wfile.rd_byte()
                    f = self.wfile.rd_byte()
                    self.channels[i].evt_queue.add(cticks, ctl_byte, cmd_arg,
                                                     e, f)
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
                elif ctl_byte >= 0xcf and ctl_byte <= 0xff:
                    pgm_ctr += 1
                    ctrl = ctl_byte
                    g = False
                    nc = 0
                    while not g:
                        cmd_arg = self.wfile.rd_byte()
                        if cmd_arg >= 0x80:
                            if not nc:
                                pn = lln[nc] + transpose
                            self.channels[i].evt_queue.add(
                                cticks, ctl_byte, pn, llv[nc], lla[nc])
                            g = True
                        else:
                            lln[nc] = cmd_arg
                            pgm_ctr += 1
                            e = self.wfile.rd_byte()
                            if e < 0x80:
                                llv[nc] = e
                                pgm_ctr += 1
                                f = self.wfile.rd_byte()
                                if f >= 0x80:
                                    f = lla[nc]
                                    g = True
                                else:
                                    lla[nc] = f
                                    pgm_ctr += 1
                                    nc += 1
                            else:
                                e = llv[nc]
                                f = lla[nc]
                                g = True
                            pn = cmd_arg + transpose
                            self.channels[i].evt_queue.add(
                                cticks, ctl_byte, pn, e, f)
                        if not self.patch_exists(lp):
                            ins_head = rd_inst_head(
                                1, self.ist_tbl_ptr + lp * 12)
                            if ins_head.channel & 0x80 == 0x80:
                                drm_head = rd_drmkit_head(1)
                                ins_head = rd_inst_head(
                                    1,
                                    self.wfile.gba_ptr_to_addr(
                                        drm_head.dct_tbl + pn * 12))
                                dct_head = rd_dct_head(1)
                                gb_head = rd_nse_head(
                                    1,
                                    self.wfile.gba_ptr_to_addr(
                                        drm_head.dct_tbl + pn * 12 + 2))
                                self.drmkits.add(str(lp))
                                self.drmkits[str(lp)].add(str(pn))
                                self.set_direct(self.drmkits[str(lp)], str(pn),
                                               self.ins_head, self.dct_head,
                                               self.gb_head)
                                if self.insts[str(lp)].directs[str(
                                        cdr)].t_output in (
                                            DirectTypes.DIRECT,
                                            DirectTypes.WAVE):
                                    self.get_smp(self.drmkits[str(lp)],
                                                    str(pn), self.dct_head,
                                                    self.smp_head, False)

    def smp_exists(self, smp_id: int) -> bool:
        return str(smp_id) in self.smp_pool

    def set_mpatch_map(self, ind: int, inst: int, transpose: int) -> None:
        self.mpatch_map[ind] = inst
        self.mpatch_tbl[ind] = transpose

    def set_mdrum_map(self, ind: int, new_drum: int) -> None:
        self.mdrum_map[ind] = new_drum


    def stop_song(self):
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
            self.log.debug('StopSong(): Track length: %s, total ticks: %s',
                            trk_len, self.ttl_ticks)
            self.mfile.write_little_endian(unpack(self.flip_lng(trk_len), 0x13))
        # TODO: raise SONG_FINISH



def main():
    """Main method."""
    d = Decoder()
    d.play_song('H:\\Merci\\Downloads\\Sappy\\MZM.gba', 1, 0x0008F2C8)


if __name__ == '__main__':
    main()
