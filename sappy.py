# -*- coding: utf-8 -*-
# !/usr/bin/env python3
# pylint: disable=C0326, R0902, R0903,W0511
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
    raw_delta:  int
    ticks:      int
    event_code: int
    # yapf: enable


class Decoder(object):
    """Decoder/interpreter for Sappy code."""
    ERROR_CHECKING = False
    GB_SQUARE_MULTI = 0.5
    GB_WAVE_MULTI = 0.5
    GB_WAVE_BASE_FREQUENCY = 880
    GB_NOISE_MULTI = 0.5
    SAPPY_PPQN = 24

    basicConfig(level=INFO)
    log = getLogger(name=__name__)

    def __init__(self):
        # yapf: disable
        self.playing:                  bool                        = bool()
        self.recording:                bool                        = bool()
        self.ear_piercer_count:        int                         = int()
        self.instrument_table_pointer: int                         = int()
        self.layer:                    int                         = int()
        self.song_list_pointer:        int                         = int()
        self.song_number:              int                         = int()
        self.song_pointer:             int                         = int()
        self.total_ticks:              int                         = int()
        self.total_msecs:              int                         = int()
        self._global_volume:           int                         = 100
        self.last_tick:                float                       = float()
        self.tick_counter:             float                       = float()
        self.ear_piercers:             list                        = list()
        self.midi_drum_map:            list                        = list()
        self.midi_patch_map:           list                        = list()
        self.midi_patch_table:         list                        = list()
        self.file_path:                str                         = str()
        self.midi_file:                File                        = None
        self.wfile:                    File                        = None
        self.sappy_channels:           ChannelQueue[Channel]       = ChannelQueue()
        self.dir_head:                 DirectHeader                = DirectHeader()
        self.directs:                  DirectQueue[Direct]         = DirectQueue()
        self.drm_head:                 DrumKitHeader               = DrumKitHeader()
        self.drumkits:                 DrumKitQueue[DrumKit]       = DrumKitQueue()
        self.ins_head:                 InstrumentHeader            = InstrumentHeader()
        self.instruments:              InstrumentQueue[Instrument] = InstrumentQueue()
        self.note_array:               List[Note]                  = [Note(*[None] * 16)] * 32
        self.mul_head:                 MultiHeader                 = MultiHeader()
        self.agb_head:                 NoiseHeader                 = NoiseHeader()
        self.note_queue:               NoteQueue[Note]             = NoteQueue()
        self.previous_event:           RawMidiEvent                = RawMidiEvent(None, None, None)
        self.smp_head:                 SampleHeader                = SampleHeader()
        self.sample_pool:              SampleQueue[Sample]         = SampleQueue()
        # yapf: enable

    @property
    def global_volume(self) -> int:
        return self._global_volume

    @global_volume.setter
    def global_volume(self, volume: int) -> None:
        self._global_volume = volume

    @staticmethod
    def direct_exists(self, directs_collection: DirectQueue,
                      direct_id: int) -> bool:
        return str(direct_id) in directs_collection

    @staticmethod
    def flip_long(value: int) -> int:
        return int.from_bytes(
            value.to_bytes(4, byteorder='big'), byteorder='little')

    @staticmethod
    def flip_int(value: int) -> int:
        return int.from_bytes(
            value.to_bytes(2, byteorder='big'), byteorder='little')

    def add_ear_piercer(self, instrument_id: int):
        self.ear_piercers[self.ear_piercer_count] = instrument_id
        self.ear_piercer_count += 1

    def buffer_event(self, event_code: str, ticks: int) -> None:
        self.midi_file: File
        if not self.recording or self.midi_file.file_id != 42:
            return
        event = RawMidiEvent(
            ticks=ticks,
            raw_delta=ticks - self.previous_event.ticks,
            event_code=int(event_code))
        self.write_var_len(self.midi_file.file_id, event.raw_delta)
        self.midi_file.write_string(event.event_code)
        self.previous_event = event

    def clear_midi_patch_map(self):
        self.midi_patch_map.clear()
        self.midi_drum_map.clear()
        self.ear_piercers.clear()
        self.ear_piercer_count = 0

    def drum_kit_exists(self, patch: int) -> bool:
        return str(patch) in self.drumkits

    def event_processor_timer(self, msec: int) -> bool:
        self.total_msecs += msec
        if self.tick_counter:
            for i in range(32):
                note = self.note_array[i]
                if note.enabled and note.wait_ticks > 0:
                    self.note_array[i] = note._replace(
                        wait_ticks=note.wait_ticks -
                        (self.tick_counter - self.last_tick))
                if note.wait_ticks <= 0 and note.enabled and not note.note_off:
                    if not self.sappy_channels[note.parent_channel].sustain:
                        self.note_array[i] = note._replace(note_off=True)
            for i in range(len(self.sappy_channels)):
                if not self.sappy_channels[i].enabled:
                    continue
                channel = self.sappy_channels[i]
                for ep in self.ear_piercers:
                    if ep == channel.patch_number:
                        self.sappy_channels[i] = channel._replace(mute=True)

    def free_note(self) -> int:
        for i in range(32):
            if not self.note_array[i].enabled:
                return i

    def get_sample(self, queue: Collection, direct_key: str,
                   dir_head: DirectHeader, smp_head: SampleHeader,
                   use_read_string: bool) -> None:
        dq = queue.directs
        dq[direct_key] = dq[direct_key]._replace(
            sample_id=dir_head.sample_header)
        sid = dq[direct_key].sample_id
        if not self.sample_exists(sid):
            self.sample_pool.add(str(sid))
            if dq[direct_key].output_type == DirectOutputTypes.DIRECT:
                self.smp_head = read_sample_head(
                    File.gba_rom_pointer_to_offset(sid))
                if use_read_string:
                    sample_data = self.wfile.read_string(smp_head.size)
                else:
                    sample_data = self.wfile.read_offset
                self.sample_pool[str(sid)] = self.sample_pool[str(
                    sid)]._replace(
                        size=smp_head.size,
                        frequency=smp_head.frequency,
                        loop_start=smp_head.loop,
                        loop_enable=smp_head.flags > 0,
                        gb_wave=False,
                        sample_data=sample_data)
            else:
                tsi = self.wfile.read_string(
                    16, File.gba_rom_pointer_to_offset(sid))
                sample_data = []
                for ai in range(32):
                    bi = ai % 2
                    sample_data.append(
                        chr(
                            int((((
                                0 if tsi[ai // 2:ai // 2 + 1] ==
                                "" else ord(tsi[ai // 2:ai // 2 + 1])) // 16**bi
                                 ) % 16) * self.GB_WAVE_BASE_FREQUENCY * 16)))
                sample_data = "".join(sample_data)
                self.sample_pool[str(sid)] = self.sample_pool[str(sid)].replace(
                    size=32,
                    frequency=self.GB_WAVE_BASE_FREQUENCY,
                    loop_start=0,
                    loop_enable=True,
                    gb_wave=True,
                    sample_data=sample_data)

    def get_sample_with_multi(self, queue: Collection, direct_key: str,
                              dir_head: DirectHeader, smp_head: SampleHeader,
                              use_read_string: bool) -> None:
        self.get_sample(queue, direct_key, dir_head, smp_head, use_read_string)

    def instrument_exists(self, patch: int) -> bool:
        return str(patch) in self.instruments

    def key_map_exists(self, key_map_collection: KeyMapQueue,
                       key_map_id: int) -> bool:
        return str(key_map_id) in key_map_collection

    def note_belongs_to_channel(self, note_id: bytes, channel_id: int) -> bool:
        return self.note_array[note_id].parent_channel == channel_id

    def patch_exists(self, lp: int) -> bool:
        return str(lp) in self.directs or self.instrument_exists(
            lp) or self.drum_kit_exists(lp)

    # yapf: disable
    def play_song(self, file_path: str, song_number: int,
                  song_list_pointer: int = None, want_to_record: bool = False,
                  record_to: str = "midiout.mid"):
        # yapf: enable
        self.file_path = file_path
        self.song_list_pointer = song_list_pointer
        self.song_number = song_number

        if self.playing:
            # TODO: raise SONG_STOP
            pass

        self.ins_head = InstrumentHeader
        self.drm_head = DrumKitHeader
        self.dir_head = DirectHeader
        self.smp_head = SampleHeader
        self.mul_head = MultiHeader
        self.agb_head = NoiseHeader

        self.sappy_channels.clear()
        self.drumkits.clear()
        self.sample_pool.clear()
        self.instruments.clear()
        self.directs.clear()
        self.note_queue.clear()
        for i in range(32):
            self.note_array[i] = self.note_array[i]._replace(enabled=False)

        self.wfile = open_file(self.file_path, 1)
        pointer = self.wfile.read_gba_rom_pointer(
            self.song_list_pointer + song_number * 8)
        self.song_pointer = pointer
        self.layer = self.wfile.read_little_endian(4)
        pbyte = self.wfile.read_byte(pointer)
        self.instrument_table_pointer = self.wfile.read_gba_rom_pointer(
            pointer + 4)

        # TODO: raise LOADING_0

        xta = SubroutineQueue()
        for i in range(0, pbyte + 1):
            loop_offset = -1
            self.sappy_channels.add()
            pc = self.wfile.read_gba_rom_pointer(pointer + 4 + i * 4)
            self.sappy_channels[i] = self.sappy_channels[i]._replace(
                track_pointer=pc)
            xta.clear()
            while True:
                control = self.wfile.read_byte(pc)
                if control >= 0x00 and control <= 0xB0 or control in (0xCE,
                                                                      0xCF,
                                                                      0xB4):
                    pc += 1
                elif control == 0xB9:
                    pc += 4
                elif control >= 0xB5 and control <= 0xCD:
                    pc += 2
                elif control == 0xB2:
                    loop_offset = self.wfile.read_gba_rom_pointer()
                    pc += 5
                    break
                elif control == 0xB3:
                    xta.add(self.wfile.read_gba_rom_pointer())
                    pc += 5
                elif control >= 0xD0 and control <= 0xFF:
                    pc += 1
                    while self.wfile.read_byte() < 0x80:
                        pc += 1
                print(hex(pc), hex(control))
                if control == 0xb1:
                    break

            cticks = 0
            c_ei = 0
            lc = 0xbe
            lln: List = [None] * 66
            llv: List = [None] * 66
            lla: List = [None] * 66
            lp = 0
            src2 = 1
            insub = 0
            t_r = 0
            self.sappy_channels[i] = self.sappy_channels[i]._replace(
                track_pointer=-1)
            while True:
                self.wfile.read_offset = pc
                print(pc)
                if pc >= loop_offset and self.sappy_channels[i].loop_pointer == -1 and loop_offset != -1:
                    self.sappy_channels[i] = self.sappy_channels[i]._replace(
                        loop_pointer=self.sappy_channels[i].event_queue.count +
                        1)
                control = self.wfile.read_byte()
                if (control != 0xb9 and control >= 0xb5 and
                        control < 0xc5) or control == 0xcd:
                    d = self.wfile.read_byte()
                    if control == 0xbc: t_r = signed_byte_to_integer(d)
                    if control == 0xbd: lp = d
                    if control in (0xbe, 0xbf, 0xc0, 0xc4, 0xcd): lc = control
                    self.sappy_channels[i].event_queue.add(
                        cticks, control, d, 0, 0)
                elif control > 0xc4 and control < 0xcf:
                    self.sappy_channels[i].event_queue.add(
                        cticks, control, 0, 0, 0)
                elif control == 0xb9:
                    d = self.wfile.read_byte()
                    e = self.wfile.read_byte()
                    f = self.wfile.read_byte()
                    self.sappy_channels[i].event_queue.add(
                        cticks, control, d, e, f)
                    pc += 4
                elif control == 0xb4:
                    if insub == 1:
                        pc = rpc  # pylint: disable=E0601
                        in_sub = 0
                    else:
                        pc += 1
                elif control == 0xb3:
                    rpc = pc + 5
                    in_sub = 1
                    pc = self.wfile.read_gba_rom_pointer()
                elif control >= 0xcf and control <= 0xff:
                    pc += 1
                    lc = control
                    g = False
                    nc = 0
                    while not g:
                        d = self.wfile.read_byte()
                        if d >= 0x80:
                            if not nc:
                                pn = lln[nc] + t_r
                            self.sappy_channels[i].event_queue.add(
                                cticks, control, pn, llv[nc], lla[nc])
                            g = True
                        else:
                            lln[nc] = d
                            pc += 1
                            e = self.wfile.read_byte()
                            if e < 0x80:
                                llv[nc] = e
                                pc += 1
                                f = self.wfile.read_byte()
                                if f >= 0x80:
                                    f = lla[nc]
                                    g = True
                                else:
                                    lla[nc] = f
                                    pc += 1
                                    nc += 1
                            else:
                                e = llv[nc]
                                f = lla[nc]
                                g = True
                            pn = d + t_r
                            self.sappy_channels[i].event_queue.add(
                                cticks, control, pn, e, f)
                        if not self.patch_exists(lp):
                            ins_head = read_instrument_head(
                                1, self.instrument_table_pointer + lp * 12)
                            if ins_head.channel & 0x80 == 0x80:
                                drm_head = read_drumkit_head(1)
                                ins_head = read_instrument_head(
                                    1,
                                    self.wfile.gba_rom_pointer_to_offset(
                                        drm_head.direct_table + pn * 12))
                                dir_head = read_direct_head(1)
                                agb_head = read_noise_head(
                                    1,
                                    self.wfile.gba_rom_pointer_to_offset(
                                        drm_head.direct_table + pn * 12 + 2))
                                self.drumkits.add(str(lp))
                                self.drumkits[str(lp)].add(str(pn))
                                self.set_stuff(self.drumkits[str(lp)], str(pn),
                                               self.ins_head, self.dir_head,
                                               self.agb_head)
                                if self.instruments[str(lp)].directs[str(
                                        cdr)].output_type in (
                                            DirectOutputTypes.DIRECT,
                                            DirectOutputTypes.WAVE):
                                    self.get_sample(self.drumkits[str(lp)],
                                                    str(pn), self.dir_head,
                                                    self.smp_head, False)

    def sample_exists(self, sample_id: int) -> bool:
        return str(sample_id) in self.sample_pool

    def set_midi_patch_map(self, index: int, instrument: int,
                           transpose: int) -> None:
        self.midi_patch_map[index] = instrument
        self.midi_patch_table[index] = transpose

    def set_midi_drum_map(self, index: int, new_drum: int) -> None:
        self.midi_drum_map[index] = new_drum

    def set_stuff(self, queue: Collection, direct_key: str,
                  ins_head: InstrumentHeader, dir_head: DirectHeader,
                  agb_head: NoiseHeader) -> None:
        # yapf: disable
        queue.directs[direct_key] = queue.directs[direct_key].replace(
            drum_tune_key   = ins_head.drum_pitch,
            output_type     = DirectOutputTypes(ins_head.channel & 7),
            env_attenuation = dir_head.attack,
            env_decay       = dir_head.hold,
            env_sustain     = dir_head.sustain,
            env_release     = dir_head.release,
            raw0            = dir_head.b0,
            raw1            = dir_head.b1,
            gb1             = agb_head.b2,
            gb2             = agb_head.b3,
            gb3             = agb_head.b4,
            gb4             = agb_head.b5,
            fixed_pitch     = (ins_head.channel & 0x08) == 0x08,
            reverse         = (ins_head.channel & 0x10) == 0x10,
            sample_id       = queue.directs[direct_key].sample_id,
            key             = queue.directs[direct_key].key
        )
        # yapf: enable

    def stop_song(self):
        File.get_file_from_id(1).close()
        File.get_file_from_id(2).close()
        # TODO: disable event processor
        # TODO: close sound channel
        # TODO: close MIDI channel
        if self.recording:
            self.log.debug('test')
            self.recording = False
            self.midi_file = 42
            with File.get_file_from_id(self.midi_file) as file:
                file.write_byte(0x0A)
                file.write_byte(0xFF)
                file.write_byte(0x2F)
                file.write_byte(0x00)
                track_length = file.size - 22
                self.log.debug('StopSong(): Track length: %s, total ticks: %s',
                               track_length, self.total_ticks)
                file.write_little_endian(
                    unpack(self.flip_long(track_length), 0x13))
        # TODO: raise SONG_FINISH

    def write_var_len(self, ch: int, value: int) -> None:
        buffer = ch & 0x7F
        while value // 128 > 0:
            value //= 128
            buffer |= 0x80
            buffer = (buffer * 256) | (value & 0x7F)
        file = File.get_file_from_id(ch)
        while True:
            file.write_byte(buffer & 255)
            if not buffer & 0x80:
                break
            buffer //= 256


def main():
    """Main method."""
    d = Decoder()
    d.play_song('H:\\Merci\\Downloads\\Sappy\\MZM.gba', 1, 0x0008F2C8)


if __name__ == '__main__':
    main()
