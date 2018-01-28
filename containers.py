#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=C0123,C0326,R0901,R0903,R0913,R0914,W0221
"""Data-storage containers for internal use."""
from collections import deque
from enum import Enum
from typing import (Any, ItemsView, KeysView, MutableMapping, MutableSequence,
                    NamedTuple, Union, ValuesView)

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


class Collection(MutableMapping):
    """Imitation of the VB6 `Collection` data-container"""
    __slots__ = ('_storage', '_key_store', '_list', 'log')

    def __init__(self, *iterables):
        super().__init__()
        self._storage = deque()
        self._key_store = {}
        self._list = None
        self._initiate_storage(iterables)

    def __contains__(self, item: Any) -> bool:
        if type(item) is int:
            return item in self._storage
        return item in self._key_store

    def __delitem__(self, key: Union[int, str]) -> None:
        if key in self._key_store:
            del self._key_store[key]
            self._storage.remove(key)
        else:
            if type(key) == str:
                raise KeyError('Invalid Key.')
            del self._storage[key]

    def __eq__(self, other) -> bool:
        return repr(self) == repr(other) and \
            self.items() == other.items()

    def __getitem__(self, key: Union[int, str]) -> Any:
        if type(key) == str and key not in self._key_store:
            return None
        elif type(key) == int:
            if self._storage[int(key)] not in self._key_store:
                return self._storage[key]
            return self._key_store.get(self._storage[key])
        else:
            return self._key_store.get(key)

    def __hash__(self):
        return hash((tuple(self._storage), tuple(self._key_store.items())))

    def __iter__(self) -> 'File':
        self._list = self._storage.copy()
        return self

    def __len__(self) -> int:
        return len(self._storage)

    def __ne__(self, other) -> bool:
        return repr(self) != repr(other) and \
            self.items() != other.items()

    def __next__(self) -> Any:
        if not self._list:
            raise StopIteration
        return self._list.popleft()

    def __repr__(self) -> str:
        return self.__repr__()

    def __setitem__(self, key: int, value: Any) -> None:
        self._storage[key] = value

    def __str__(self) -> str:
        return str(list(self._storage))

    def _initiate_storage(self, iterables) -> None:
        for iterable in iterables:
            if type(iterable) == dict:
                for item in iterable.items():
                    key, value = item
                    self.add(value, key)
            else:
                self._storage.extend(iterable)

    def keys(self) -> KeysView:
        """Keys in keystore"""
        return self._key_store.keys()

    def values(self) -> ValuesView:
        """Values in keystore"""
        return self._key_store.values()

    def items(self) -> ItemsView:
        """Key/Value pairs in keystore"""
        return self._key_store.items()

    # yapf: disable
    def add(self, item: Any, key: str = None, bef: int = None,
            aft: int = None) -> None:
        # yapf: enable
        """Add an item to storage.

        Note:
            Neither `before` nor `after` can be used in conjunction.

        Args:
            key: A string reference to the item's index.
            bef: index to insert the item before.
            aft: index to insert the item after.

        """
        if key and key not in self._key_store:
            self._key_store[key] = item
            item = key
        elif key is not None:
            raise KeyError('Key in use.')
        if not bef and not aft:
            self._storage += [item]
        else:
            if bef == aft and bef is not None:
                raise ValueError('Simultaneous usage of "before" and "after"')
            elif bef:
                self._storage.insert(bef - 1, item)
            else:
                self._storage.insert(aft + 1, item)

    def clear(self):
        """Clear all of storage and the keystore."""
        self._storage.clear()
        self._key_store.clear()

    get = __getitem__
    item = __getitem__
    remove = __delitem__
    count = property(fget=__len__)


class ChannelQueue(Collection):
    """LIFO container of sound channels."""

    def add(self, key: str = None) -> None:
        channel = Channel(key=key)
        super().add(channel)


class DirectQueue(Collection):
    """LIFO container of DirectSound notes."""

    def add(self, key: str = None) -> None:
        direct = Direct(key=key)
        super().add(direct, key)


class DrumKitQueue(Collection):
    """LIFO container of DrumKit notes."""

    def add(self, key: str = None) -> None:
        drumkit = DrumKit(key=key)
        super().add(drumkit, key)


class EventQueue(Collection):
    """LIFO container of internal events."""

    # yapf: disable
    def add(self, ticks: int, command_byte: int, param1: int,
            param2: int, param3: int, key: str = None) -> None:
        event = Event(
            key          = key,
            ticks        = ticks,
            command_byte = command_byte,
            param1       = param1,
            param2       = param2,
            param3       = param3
        )
        super().add(event)
    # yapf: enable


class InstrumentQueue(Collection):
    """LIFO container of AGB instruments."""

    def add(self, key: str = None) -> None:
        instrument = Instrument(key=key)
        super().add(instrument, key)


class KeyMapQueue(Collection):
    """LIFO container of MIDI key maps."""

    def add(self, assign_dct: int, key: str = None) -> None:
        kmap = KeyMap(key=key, assign_dct=assign_dct)
        super().add(kmap, key)


class NoteQueue(Collection):
    """LIFO container of AGB notes."""

    # yapf: disable
    def add(self, enable: bool, fmod_channel: int, note_num: int,
            freq: int, velocity: int, parent: int,
            unk_val: int, t_output: NoteTypes,
            env_attn: int, env_decay: int, env_sustain: int,
            env_release: int, wait_ticks: int, patch_num: int,
            key: str = None) -> None:
        """Initialize and append a new note."""
        note = Note(
            key             = key,
            enable         = enable,
            fmod_channel    = fmod_channel,
            note_num     = note_num,
            freq       = freq,
            velocity        = velocity,
            patch_num    = patch_num,
            parent  = parent,
            sample_id       = env_release,
            unk_val   = unk_val,
            t_output     = t_output,
            env_attn = env_attn,
            env_decay       = env_decay,
            env_sustain     = env_sustain,
            env_release     = env_release,
            wait_ticks=wait_ticks)
        super().add(note, key)
        # yapf: enable


class NoteIDQueue(Collection):
    """LIFO container holding internal note IDs."""

    def add(self, note_id: int, key: str = None) -> None:
        note = NoteID(key=key, note_id=note_id)
        super().add(note, key)


class SampleQueue(Collection):
    """LIFO container holding instrument samples."""

    def add(self, key: str = None) -> None:
        sample = Sample(key=key)
        super().add(sample, key)


class SubroutineQueue(Collection):
    """LIFO container holding AGB subs."""

    def add(self, event_queue_pointer: int, key: str = None) -> None:
        subroutine = Subroutine(
            key=key, event_queue_pointer=event_queue_pointer)
        super().add(subroutine, key)


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
    t_output:     ChannelTypes    = ChannelTypes.NULL
    evt_queue:    EventQueue      = EventQueue()
    notes:        NoteQueue       = NoteQueue()
    subs:         SubroutineQueue = SubroutineQueue()
    # yapf: enable


class Direct(NamedTuple):
    """DirectSound instrument."""
    # yapf: disable
    reverse:     bool        = bool()
    fixed_pitch: bool        = bool()
    env_attn:    int         = 0x00
    env_decay:   int         = 0x00
    env_sustain: int         = 0x00
    env_release: int         = 0x00
    raw0:        int         = 0x00
    raw1:        int         = 0x00
    gb1:         int         = 0x00
    gb2:         int         = 0x00
    gb3:         int         = 0x00
    gb4:         int         = 0x00
    drum_key:    int         = 0x3C
    key:         str         = str()
    sample_id:   str         = str()
    t_output:    DirectTypes = DirectTypes.NULL
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
    command_byte: int = int()
    param1:       int = int()
    param2:       int = int()
    param3:       int = int()
    ticks:        int = int()
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
    env_step:     float      = 0.0
    env_pos:      float      = 0.0
    wait_ticks:   float      = float()
    env_attn:     int        = int()
    env_decay:    int        = int()
    env_release:  int        = int()
    env_sustain:  int        = int()
    fmod_channel: int        = int()
    freq:         int        = int()
    note_num:     int        = int()
    parent:       int        = int()
    patch_num:    int        = int()
    unk_val:      int        = int()
    velocity:     int        = int()
    key:          str        = str()
    sample_id:    str        = str()
    t_output:     NoteTypes  = NoteTypes.NULL
    note_phase:   NotePhases = NotePhases.INITIAL
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
    gb_wave:     bool      = bool()
    loop_enable: bool      = bool()
    smp_data:    bytearray = SampleDataBytes()
    fmod_sample: int       = int()
    freq:        int       = int()
    loop_start:  int       = int()
    size:        int       = int()
    key:         str       = str()
    sample_data: str       = str()
    # yapf: enable

    @property
    def smp_data_len(self):
        """Number of int in sample"""
        return len(self.smp_data)

    def rd_smp_data(self, id: int, t_size: int):
        """Read sample data as int from AGB rom."""
        file = File.from_id(id)
        sample_data = bytearray()
        for i in range(t_size):  # pylint: disable=W0612
            sample_data.append(file.read_byte())
        self.smp_data = self.SampleDataBytes(sample_data)

    def sav_smp_data(self, id: int):
        """Save bytearray of sample data to AGB rom."""
        file = File.from_id(id)
        for byte in self.smp_data:
            file.write_byte(byte)


class Subroutine(NamedTuple):
    """Internal AGB subroutine ID."""
    # yapf: disable
    event_queue_pointer: int = int()
    key:                 str = str()
    # yapf: enable
