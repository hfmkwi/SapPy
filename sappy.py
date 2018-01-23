# -*- coding: utf-8 -*-
# !/usr/bin/env python3
# pylint: disable=C0326, R0902, R0903,W0511
"""Main file."""
from enum import Enum
from logging import INFO, basicConfig, getLogger
from struct import unpack
from typing import List, NamedTuple

from containers import (Channel, ChannelQueue, Direct, DirectQueue, DrumKit,
                        DrumKitQueue, Instrument, InstrumentQueue, Note,
                        NoteQueue, Sample, SampleQueue, SubroutineQueue)
from fileio import File, open_file
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
        self.playing:                  bool
        self.recording:                bool
        self.ear_piercer_count:        int
        self.instrument_table_pointer: int
        self.layer:                    int
        self.song_list_pointer:        int
        self.song_number:              int
        self.song_pointer:             int
        self.total_ticks:              int
        self.ear_piercers:             list
        self.midi_drum_map:            list
        self.midi_patch_map:           list
        self.midi_patch_table:         list
        self.note_array:               list
        self.file_path:                str
        self.midi_file:                File
        self.previous_event:           RawMidiEvent
        self._global_volume:           int                         = 100
        self.sappy_channels:           ChannelQueue[Channel]       = ChannelQueue()
        self.directs:                  DirectQueue[Direct]         = DirectQueue()
        self.drumkits:                 DrumKitQueue[DrumKit]       = DrumKitQueue()
        self.instruments:              InstrumentQueue[Instrument] = InstrumentQueue()
        self.note_queue:               NoteQueue[Note]             = NoteQueue()
        self.sample_pool:              SampleQueue[Sample]         = SampleQueue()
        # yapf: enable

    def buffer_event(self, event_code: str, ticks: int) -> None:
        if not self.recording or self.midi_file != 42:
            return
        event = RawMidiEvent(
            ticks=ticks,
            raw_delta=ticks - self.previous_event.ticks,
            event_code=int(event_code))
        self.write_var_len(self.midi_file, event.raw_delta)
        self.midi_file.write_string(event.event_code)
        self.previous_event = event

    @property
    def global_volume(self) -> int:
        return self._global_volume

    @global_volume.setter
    def global_volume(self, volume: int) -> None:
        self._global_volume = volume

    @staticmethod
    def flip_long(value: int) -> int:
        pass

    def set_midi_patch_map(self, index: int, instrument: int,
                           transpose: int) -> None:
        self.midi_patch_map[index] = instrument
        self.midi_patch_table[index] = transpose

    def set_midi_drum_map(self, index: int, new_drum: int) -> None:
        self.midi_drum_map[index] = new_drum

    def add_ear_piercer(self, instrument_id: int):
        self.ear_piercers[self.ear_piercer_count] = instrument_id
        self.ear_piercer_count += 1

    def clear_midi_patch_map(self):
        self.midi_patch_map.clear()
        self.midi_drum_map.clear()
        self.ear_piercers.clear()
        self.ear_piercer_count = 0

    def note_belongs_to_channel(self, note_id: bytes, channel_id: int) -> bool:
        return self.note_array[note_id].parent_channel == channel_id

    def patch_exists(self, lp: int) -> bool:
        pass

    # yapf: disable
    def play_song(self, file_path: str, song_number: int,
                  song_list_pointer: str, want_to_record: bool = False,
                  record_to: str = "midiout.mid"):
        # yapf: enable
        self.file_path = file_path
        self.song_list_pointer = song_list_pointer
        self.song_number = song_number

        if self.playing:
            # TODO: raise SONG_STOP
            pass

        ins_head = InstrumentHeader
        drm_head = DrumKitHeader
        dir_head = DirectHeader
        smp_head = SampleHeader
        mul_head = MultiHeader
        agb_head = NoiseHeader

        self.sappy_channels.clear()
        self.drumkits.clear()
        self.sample_pool.clear()
        self.instruments.clear()
        self.directs.clear()
        self.note_queue.clear()
        for i in range(32):
            self.note_array[i].enabled = False

        wfile = open_file(self.file_path, 1)
        pointer = wfile.read_gba_rom_pointer(
            self.song_list_pointer + song_number * 8)
        self.song_pointer = pointer
        self.layer = wfile.read_little_endian(4)
        pbyte = wfile.read_byte(pointer)
        self.instrument_table_pointer = wfile.read_gba_rom_pointer(pointer + 4)

        # TODO: raise LOADING_0

        xta = SubroutineQueue()
        for i in range(1, pbyte + 1):
            loop_offset = -1
            self.sappy_channels.add()
            pc = wfile.read_gba_rom_pointer(pointer + 4 + i * 4)
            self.sappy_channels[i]: Channel.track_pointer = pc
            xta.clear()
            while True:
                wfile.read_offset = pc
                c = wfile.read_byte()
                if c >= b'00' and c <= b'B0' or c in (b'CE', b'CF', b'B4'):
                    pc += 1
                elif c == b'B9':
                    pc += 4
                elif c >= b'B5' and c <= b'CD':
                    pc += 2
                elif c == b'B2':
                    loop_offset = wfile.read_gba_rom_pointer()
                    pc += 5
                    break
                elif c == b'B3':
                    xta.add(wfile.read_gba_rom_pointer())
                    pc += 5
                elif c >= b'D0' and c <= b'FF':
                    pc += 1
                    while wfile.read_byte(1) < b'80':
                        pc += 1

                if c == b'b1':
                    break

            cticks = 0
            c_ei = 0
            lc = b'be'
            lln: List = [None] * 66
            llv: List = [None] * 66
            lla: List = [None] * 66
            lp = 0
            src2 = 1
            insub = 0
            t_r = 0
            self.sappy_channels[i].track_pointer = -1
            while True:
                wfile.read_offset = pc
                if pc >= loop_offset and self.sappy_channels[i].loop_pointer == -1 and loop_offset != -1:
                    self.sappy_channels[
                        i].loop_pointer = self.sappy_channels[i].event_queue.count + 1
                c = wfile.read_byte()
                if (c != b'b9' and c >= b'b5' and c < b'c5') or c == b'cd':
                    d = wfile.read_byte()
                    if c == b'bc': t_r = signed_byte_to_integer(d)
                    if c == b'bd': lp = d
                    if c in (b'be', b'bf', b'c0', b'c4', b'cd'): lc = c
                    self.sappy_channels[i].event_queue.add(cticks, c, d, 0, 0)
                elif c > b'c4' and c < b'cf':
                    self.sappy_channels[i].event_queue.add(cticks, c, 0, 0, 0)
                elif c == b'b9':
                    d = wfile.read_byte()
                    e = wfile.read_byte()
                    f = wfile.read_byte()
                    self.sappy_channels[i].event_queue.add(cticks, c, d, e, f)
                    pc += 4
                elif c == b'b4':
                    if insub == 1:
                        pc = rpc
                        in_sub = 0
                    else:
                        pc += 1
                elif c == b'b3':
                    rpc = pc + 5
                    in_sub = 1
                    pc = wfile.read_gba_rom_pointer()
                elif c >= b'cf' and c <= b'ff':
                    pc += 1
                    lc = c
                    g = False
                    nc = 0
                    while not g:
                        d = wfile.read_byte()
                        if d >= b'80':
                            if not nc:
                                pn = lln[nc] + t_r
                            self.sappy_channels[i].event_queue.add(
                                cticks, c, pn, llv[nc], lla[nc])
                            g = True
                        else:
                            lln[nc] = d
                            pc += 1
                            e = wfile.read_byte()
                            if e < b'80':
                                llv[nc] = e
                                pc += 1
                                f = wfile.read_byte()
                                if f >= b'80':
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
                                cticks, c, pn, e, f)
                        if not self.patch_exists(lp):
                            ins_head = read_instrument_head(
                                1, self.instrument_table_pointer + lp * 12)
                            if ins_head.channel:
                                pass

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
                file.write_byte(b'0A')
                file.write_byte(b'FF')
                file.write_byte(b'2F')
                file.write_byte(b'00')
                track_length = file.size - 22
                self.log.debug('StopSong(): Track length: %s, total ticks: %s',
                               track_length, self.total_ticks)
                file.write_little_endian(
                    unpack(self.flip_long(track_length), 0x13))
        # TODO: raise SONG_FINISH

    def write_var_len(self, midi_file: File, raw_delta: int) -> None:
        pass


def main():
    """Main method."""
    pass
