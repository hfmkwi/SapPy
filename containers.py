#!/usr/bin/python3
#-*- coding: utf-8 -*-
# pylint: disable=C0103,C0123,C0326,E1120,R0901,R0903,R0913,R0914,W0221,W0622
"""Data-storage containers for internal use."""
from collections import deque, UserDict
from enum import Enum
from typing import (Any, ItemsView, KeysView, MutableSequence, NamedTuple,
                    ValuesView)

from fileio import File

__all__ = ('ChannelTypes', 'DirectTypes', 'NoteTypes', 'NotePhases',
           'Collection', 'ChannelQueue', 'DirectQueue', 'DrumKitQueue',
           'EventQueue', 'InstrumentQueue', 'KeyMapQueue', 'NoteQueue',
           'NoteIDQueue', 'SampleQueue', 'SubroutineQueue', 'Channel',
           'Direct', 'DrumKit', 'Event', 'Instrument', 'KeyMap', 'Note',
           'NoteID', 'Sample', 'Subroutine')


class ChannelTypes(Enum):
    """Possible output types for each sound channel"""
    # yapf: disable
    DIRECT  = 0
    SQUARE1 = 1
    SQUARE2 = 2
    WAVE    = 3
    NOISE   = 4
    UNK5    = 5
    UNK6    = 6
    UNK7    = 7
    MUL_SMP = 8
    DRUMKIT = 9
    NULL    = 255
    # yapf: enable


class DirectTypes(Enum):
    """Possible outputs for DirectSound note."""
    # yapf: disable
    DIRECT  = 0
    SQUARE1 = 1
    SQUARE2 = 2
    WAVE    = 3
    NOISE   = 4
    UNK5    = 5
    UNK6    = 6
    UNK7    = 7
    NULL    = 255
    # yapf: enable


class NoteTypes(Enum):
    """Declare possible outputs for the Note object"""
    # yapf: disable
    DIRECT  = 0
    SQUARE1 = 1
    SQUARE2 = 2
    WAVE    = 3
    NOISE   = 4
    UNK5    = 5
    UNK6    = 6
    UNK7    = 7
    NULL    = 255
    # yapf: enable


class NotePhases(Enum):
    """Declare possible phases for the Note object"""
    # yapf: disable
    INITIAL = 0
    ATTACK  = 1
    DECAY   = 2
    SUSTAIN = 3
    RELEASE = 4
    NOTEOFF = 5
    NULL    = 255
    # yapf: enable


class Collection(deque, UserDict):
    """Imitation of the VB6 `Collection` data-container"""

    def __init__(self):
        deque.__init__(self)
        UserDict.__init__(self)

    def __contains__(self, item: Any) -> bool:
        return deque.__contains__(self, item) or item in self.data

    def __delitem__(self, item: int) -> bool:
        out = deque.__getitem__(self, item)
        deque.__delitem__(self, item)
        self.data.pop(out)

    def __eq__(self, other) -> bool:
        return deque.__eq__(self, other) and self.data == other.data

    def __getitem__(self, key: int) -> Any:
        out = deque.__getitem__(self, key)
        if out not in UserDict.keys(self):
            return out
        return self.data[out]

    def __hash__(self):
        return hash((deque.__iter__(self), tuple(self.data)))

    def __ne__(self, other) -> bool:
        return deque.__ne__(self, other) and self.data != other.data

    def add(self, *args):
        """Abstract add method; add some container to a container queue"""
        raise NotImplementedError

    def clear(self):
        """Clear all of storage and the keystore."""
        deque.clear(self)
        UserDict.clear(self)

    def item(self, key: str):
        """Get value from key"""
        return self.data[key]

    def key_append(self, item: Any, key: Any) -> None:
        """Append an item to end of storage.

        Args:
        key: A string reference to the item's index.

        """
        if key in self.data:
            raise KeyError('Key in use.')
        self.data[key] = item
        self.append(key)

    def key_insert(self, item: Any, key: Any, ind: int = None):
        """Insert an item at the specified index within storage."""
        if key in self.data:
            raise KeyError('Key in use.')
        self.data[key] = item
        self.insert(ind, key)

    def remove(self, key: str):
        ind = super().index(key)
        super().__delitem__(ind)
        del self.data[key]

    count = property(fget=deque.__len__)


class ChannelQueue(Collection):
    """LIFO container of sound channels."""

    def add(self, key: str) -> None:
        channel = Channel(key=key)
        self.append(channel)


class DirectQueue(Collection):
    """LIFO container of DirectSound notes."""

    def add(self, key: str) -> None:
        direct = Direct(key=key)
        self.key_append(direct, key)


class DrumKitQueue(Collection):
    """LIFO container of DrumKit notes."""

    def add(self, key: str) -> None:
        drumkit = DrumKit(key=key)
        self.key_append(drumkit, key)


class EventQueue(Collection):
    """LIFO container of internal events."""

    # yapf: disable
    def add(self, ticks: int, cmd_byte: int, arg1: int, arg2: int, arg3: int,
            key: str) -> None:
        event = Event(
            key          = key,
            ticks        = ticks,
            cmd_byte = cmd_byte,
            arg1       = arg1,
            arg2       = arg2,
            arg3       = arg3
        )
        self.append(event)
    # yapf: enable


class InstrumentQueue(Collection):
    """LIFO container of AGB instruments."""

    def add(self, key: str) -> None:
        instrument = Instrument(key=key)
        super().key_append(instrument, key)


class KeyMapQueue(Collection):
    """LIFO container of MIDI key maps."""

    def add(self, assign_dct: int, key: str) -> None:
        kmap = KeyMap(key=key, assign_dct=assign_dct)
        super().key_append(kmap, key)


class NoteQueue(Collection):
    """LIFO container of AGB notes."""

    # yapf: disable
    def add(self, enable: bool, fmod_channel: int, note_num: int,
            freq: int, velocity: int, parent: int, unk_val: int,
            out_type: NoteTypes, env_attn: int, env_dcy: int, env_sus: int,
            env_rel: int, wait_ticks: int, patch_num: int,
            key: str) -> None:
        """Initialize and append a new note."""
        note = Note(
            key          = key,
            enable       = enable,
            fmod_channel = fmod_channel,
            note_num     = note_num,
            freq         = freq,
            velocity     = velocity,
            patch_num    = patch_num,
            parent       = parent,
            smp_id       = env_rel,
            unk_val      = unk_val,
            out_type     = out_type,
            env_attn     = env_attn,
            env_dcy      = env_dcy,
            env_sus      = env_sus,
            env_rel      = env_rel,
            wait_ticks   = wait_ticks)
        super().key_append(note, key)
        # yapf: enable


class NoteIDQueue(Collection):
    """LIFO container holding internal note IDs."""

    def add(self, note_id: int, key: str) -> None:
        note = NoteID(key=key, note_id=note_id)
        super().key_append(note, key)


class SampleQueue(Collection):
    """LIFO container holding instrument samples."""

    def add(self, key: str) -> None:
        sample = Sample(key=key)
        super().key_append(sample, key)


class SubroutineQueue(Collection):
    """LIFO container holding AGB subs."""

    def add(self, evt_q_ptr: int, key: str) -> None:
        subroutine = Subroutine(key=key, evt_q_ptr=evt_q_ptr)
        super().key_append(subroutine, key)


class Channel(NamedTuple):
    """Sound channel"""
    # yapf: disable
    in_sub:       bool            = bool()
    enable:       bool            = True
    mute:         bool            = False
    sustain:      bool            = False
    wait_ticks:   float           = -1.0
    loop_ptr:     int             = 0
    main_vol:     int             = 100
    panning:      int             = 0x40
    patch_num:    int             = 0x00
    pitch:        int             = 0x40
    pitch_range:  int             = 2
    pgm_ctr:      int             = 1
    rtn_ptr:      int             = int()
    sub_ctr:      int             = 1
    sub_loop_cnt: int             = 1
    track_len:    int             = int()
    track_ptr:    int             = int()
    transpose:    int             = 0
    vib_depth:    int             = int()
    vib_rate:     int             = int()
    key:          str             = str()
    out_type:     ChannelTypes    = ChannelTypes.NULL
    evt_queue:    EventQueue      = EventQueue()
    notes:        NoteQueue       = NoteQueue()
    subs:         SubroutineQueue = SubroutineQueue()
    # yapf: enable


class Direct(NamedTuple):
    """DirectSound instrument."""
    # yapf: disable
    reverse:   bool        = bool()
    fix_pitch: bool        = bool()
    env_attn:  int         = 0x00
    env_dcy:   int         = 0x00
    env_sus:   int         = 0x00
    env_rel:   int         = 0x00
    raw0:      int         = 0x00
    raw1:      int         = 0x00
    gb1:       int         = 0x00
    gb2:       int         = 0x00
    gb3:       int         = 0x00
    gb4:       int         = 0x00
    drum_key:  int         = 0x3C
    key:       str         = str()
    smp_id:    str         = str()
    out_type:  DirectTypes = DirectTypes.NULL
    # yapf: enable


class DrumKit(NamedTuple):
    """Represents a drumkit; contains a queue of DirectSound instruments."""
    # yapf: disable
    key:     str         = str()
    directs: DirectQueue = DirectQueue()
    # yapf: enable


class Event(NamedTuple):
    """Internal event"""
    # yapf: disable
    cmd_byte: int = int()
    arg1:     int = int()
    arg2:     int = int()
    arg3:     int = int()
    ticks:    int = int()
    # yapf: enable


class Instrument(NamedTuple):
    """Represents an instrument; uses a DirectSound queue to hold sound samples.
    """
    # yapf: disable
    key:     str         = str()
    directs: DirectQueue = DirectQueue()
    kmaps:   KeyMapQueue = KeyMapQueue()
    # yapf: enable


class KeyMap(NamedTuple):
    """Represents a MIDI instrument keybind."""
    # yapf: disable
    assign_dct: int = int()
    key:        str = str()
    # yapf: enable


class Note(NamedTuple):
    """Container representing a single note in the AGB sound engine."""
    # yapf: disable
    enable:       bool       = bool()
    note_off:     bool       = False
    env_dest:     float      = 0.0
    env_pos:      float      = 0.0
    env_step:     float      = 0.0
    wait_ticks:   float      = float()
    env_attn:     int        = int()
    env_dcy:      int        = int()
    env_rel:      int        = int()
    env_sus:      int        = int()
    fmod_channel: int        = int()
    freq:         int        = int()
    note_num:     int        = int()
    parent:       int        = int()
    patch_num:    int        = int()
    unk_val:      int        = int()
    velocity:     int        = int()
    key:          str        = str()
    smp_id:       str        = str()
    out_type:     NoteTypes  = NoteTypes.NULL
    phase:        NotePhases = NotePhases.INITIAL
    # yapf: enable


class NoteID(NamedTuple):
    """Internal note ID."""
    # yapf: disable
    note_id: int = int()
    key:     str = str()
    # yapf: enable


class Sample(NamedTuple):
    """Sound sample for use during playback."""

    class SampleDataBytes(MutableSequence):
        """Holds sample data as extracted from ROM."""

        def __init__(self, data: bytearray = None) -> None:
            super().__init__()
            if not data:
                data = bytearray()
            self._storage = data
            self._iterable = None

        def __delitem__(self, index: int):
            del self._storage[index]

        def __getitem__(self, index: int):
            return self._storage[index]

        def __iter__(self):
            self._iterable = self._storage.copy()
            return self

        def __next__(self):
            return self._iterable.pop()

        def __len__(self):
            return len(self._storage)

        def __setitem__(self, index: int, value: int) -> None:
            if index > len(self._storage):
                self._storage.extend([0] * index - len(self._storage))
            if not self._storage:
                self._storage.extend([0])
            self._storage[index] = value

        def append(self, value: Any) -> None:
            """Append item to storage."""
            self._storage.append(value)

        def insert(self, index: int, value: Any) -> None:
            """Insert item at specified index."""
            self._storage.insert(index, value)

    # yapf: disable
    gb_wave:    bool      = bool()
    loop:       bool      = bool()
    smp_data:   bytearray = SampleDataBytes()
    fmod_smp:   int       = int()
    freq:       int       = int()
    loop_start: int       = int()
    size:       int       = int()
    key:        str       = str()
    smp_data:   str       = str()
    # yapf: enable

    @property
    def smp_data_len(self):
        """Number of int in sample"""
        return len(self.smp_data)

    def rd_smp_data(self, id: int, t_size: int):
        """Read sample data as int from AGB rom."""
        file = File.from_id(id)
        smp_data = bytearray()
        for i in range(t_size):  # pylint: disable=W0612
            smp_data.append(file.read_byte())
        self.smp_data = self.SampleDataBytes(smp_data)

    def sav_smp_data(self, id: int):
        """Save bytearray of sample data to AGB rom."""
        file = File.from_id(id)
        for byte in self.smp_data:
            file.write_byte(byte)


class Subroutine(NamedTuple):
    """Internal AGB subroutine ID."""
    # yapf: disable
    evt_q_ptr: int = int()
    key:       str = str()
    # yapf: enable
