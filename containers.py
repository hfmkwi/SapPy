#!/usr/bin/python3
#-*- coding: utf-8 -*-
# pylint: disable=C0103,C0123,C0326,E1120,R0901,R0903,R0913,R0914,W0221,W0622
"""Data-storage containers for internal use."""
from collections import deque, UserDict
from enum import IntEnum
from typing import (Any, ItemsView, KeysView, MutableSequence, Union,
                    ValuesView)

from fileio import File

__all__ = ('ChannelTypes', 'DirectTypes', 'NoteTypes', 'NotePhases',
           'Collection', 'ChannelQueue', 'DirectQueue', 'DrumKitQueue',
           'EventQueue', 'InstrumentQueue', 'KeyMapQueue', 'NoteQueue',
           'NoteIDQueue', 'SampleQueue', 'SubroutineQueue', 'Channel', 'Direct',
           'DrumKit', 'Event', 'Instrument', 'KeyMap', 'Note', 'NoteID',
           'Sample', 'Subroutine')


class ChannelTypes(IntEnum):
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


class DirectTypes(IntEnum):
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


class NoteTypes(IntEnum):
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


class NotePhases(IntEnum):
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
    """Imitation of the VB6 `Collection` data-container

    This container behaves similarly to both a list and a dictionary. An item
    may be appended or inserted with or without a key. If an item is added with
    a key, the key is added to the keystore and inserted into the deque in
    place of its associated value.

    An item can be accessed via it's index in the deque. A keyed item can be
    accessed by the passing a valid key to the `item` method or retrieving the
    key from the deque via its index and subsequently passing the key to the
    `item` method.

    Attributes
    ----------
    data : dict
        The keystore; holds all keys and their respective values.
    count : int
        The number of items inside the deque. Wrapper around `deque.__len__`

    Notes
    -----
        To allow keyed elements to be accessed via index, a copy of the key is
        appended to the internal deque. The key is directly accesible via index
        and can be used to lookup its paired value in the keystore.

    Examples
    --------
        >>> c = Collection()
        >>> c.append(1)
        >>> c[0]
        1
        >>> del c[0]
        >>> len(c)
        0
        >>> c.key_append(0xBEEF, 'test')
        >>> c.item('test')
        48879
        >>> c[0]
        'test'
        >>> c.item(c[0])
        48879
        >>> 'test' in c
        True
        >>> 48879 in c
        True
        >>> c.key_insert(0xDEAD, 'bee#f', 0)
        >>> print(c)
        deque(['bee#f', 'test'])
        >>> c[1]
        'test'
        >>> d = Collection()
        >>> c.clear()
        >>> d == c
        True
        >>> d != c
        False

    """

    def __init__(self, *iterables):
        UserDict.__init__(self)
        deque.__init__(self)
        if iterables:
            for iter in iterables:
                if type(iter) == dict:
                    for k in iter:
                        self.key_append(k)
                    continue
                self.extend(iter)

    def __contains__(self, item: Any) -> bool:
        return deque.__contains__(self, item) or item in self.data

    def __delitem__(self, item: int) -> bool:
        out = deque.__getitem__(self, item)
        deque.__delitem__(self, item)
        try:
            self.data.pop(out)
        except:
            pass

    def __getitem__(self, key: Any) -> Any:
        if type(key) == str:
            return self.data[key]
        out = deque.__getitem__(self, key)
        if out in self.data:
            out = self.__getitem__(out)
        return out

    def __iter__(self):
        self._list = tuple(deque.__iter__(self))
        self._ind = 0
        return self

    def __next__(self):
        try:
            self._list = tuple(deque.__iter__(self))
            if self._list[self._ind] in self.data:
                out = self.data[self._list[self._ind]]
            else:
                out = self._list[self._ind]
        except IndexError:
            raise StopIteration
        self._ind += 1
        return out

    def __eq__(self, other: 'Container') -> bool:
        return deque.__eq__(self, other) and self.data == other.data

    def __hash__(self):
        return hash((deque.__iter__(self), tuple(self.data)))

    def __ne__(self, other: 'Container') -> bool:
        return deque.__ne__(self, other) and self.data != other.data

    def __setitem__(self, key: Union[str, int], item: Any) -> None:
        if type(key) == str:
            self.data[key] = item
        elif type(key) == int:
            out = deque.__getitem__(self, key)
            deque.__setitem__(self, key, item)
            if out in self.data:
                self.data[out] = item

    def __repr__(self):
        return [
            i if not self.data.get(i) else self.data[i]
            for i in self.__iter__()
        ]

    def __str__(self):
        return str(tuple(self))

    def add(self, *args):
        """Abstract add method; add some container to a container queue"""
        raise NotImplementedError

    def clear(self):
        """Clear all of storage and the keystore."""
        deque.clear(self)
        self.data.clear()
        assert len(self) == 0
        assert len(self.data) == 0

    def item(self, key: str):
        """Get value from key or index"""
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
        ind = deque.index(self, key)
        deque.__delitem__(self, ind)
        del self.data[key]

    count = property(fget=deque.__len__)


class ChannelQueue(Collection):
    """LIFO container of sound channels."""

    def add(self) -> None:
        channel = Channel()
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
    def add(self, ticks: int, cmd_byte: int, arg1: int, arg2: int, arg3: int
           ) -> None:
        event = Event(
            ticks    = ticks,
            cmd_byte = cmd_byte,
            arg1     = arg1,
            arg2     = arg2,
            arg3     = arg3
        )
        self.append(event)
    # yapf: enable


class InstrumentQueue(Collection):
    """LIFO container of AGB instruments."""

    def add(self, key: str) -> None:
        instrument = Instrument(key=key)
        self.key_append(instrument, key)


class KeyMapQueue(Collection):
    """LIFO container of MIDI key maps."""

    def add(self, assign_dct: int, key: str) -> None:
        kmap = KeyMap(key=key, assign_dct=assign_dct)
        self.key_append(kmap, key)


class NoteQueue(Collection):
    """LIFO container of AGB notes."""

    # yapf: disable
    def add(self, enable: bool, fmod_channel: int, note_num: int,
            freq: int, velocity: int, parent: int, unk_val: int,
            output: NoteTypes, env_attn: int, env_dcy: int, env_sus: int,
            env_rel: int, wait_ticks: int, patch_num: int) -> None:
        """Initialize and append a new note."""
        note = Note(
            enable       = enable,
            fmod_channel = fmod_channel,
            note_num     = note_num,
            freq         = freq,
            velocity     = velocity,
            parent       = parent,
            unk_val      = unk_val,
            output       = output,
            env_attn     = env_attn,
            env_dcy      = env_dcy,
            env_sus      = env_sus,
            env_rel      = env_rel,
            wait_ticks   = wait_ticks,
            patch_num    = patch_num
        )
        self.append(note)
        # yapf: enable


class NoteIDQueue(Collection):
    """LIFO container holding internal note IDs."""

    def add(self, note_id: int, key: str) -> None:
        note = NoteID(key=key, note_id=note_id)
        self.key_append(note, key)


class SampleQueue(Collection):
    """LIFO container holding instrument samples."""

    def add(self, key: str) -> None:
        sample = Sample(key=key)
        self.key_append(sample, key)


class SubroutineQueue(Collection):
    """LIFO container holding AGB subs."""

    def add(self, evt_q_ptr: int) -> None:
        subroutine = Subroutine(key="", evt_q_ptr=evt_q_ptr)
        self.append(subroutine)


class Type(object):
    """Custom type object"""

    def __str__(self):
        attr = []
        for name in dir(self):
            if name.startswith('_'):
                continue
            try:
                value = repr(getattr(self, name))
            except:
                value = str(getattr(self, name))
            attr.append(f'{name}={value}, ')
        attr = ''.join(attr)

        template = f'{self.__class__.__name__}({attr})'
        return template

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class Channel(Type):
    """Sound channel"""

    # yapf: disable
    def __init__(self):
        self.in_sub:       bool            = False
        self.enable:       bool            = True
        self.mute:         bool            = False
        self.sustain:      bool            = False
        self.wait_ticks:   float           = -1.0
        self.loop_ptr:     int             = 0
        self.main_vol:     int             = 100
        self.panning:      int             = 0x40
        self.patch_num:    int             = 0x00
        self.pitch_bend:   int             = 0x40
        self.pitch_range:  int             = 2
        self.pgm_ctr:      int             = 0
        self.rtn_ptr:      int             = 0
        self.sub_ctr:      int             = 0
        self.sub_loop_cnt: int             = 1
        self.track_len:    int             = 0
        self.track_ptr:    int             = 0
        self.transpose:    int             = 0
        self.vib_depth:    int             = 0
        self.vib_rate:     int             = 0
        self.key:          str             = ''
        self.output:       ChannelTypes    = ChannelTypes.NULL
        self.evt_queue:    EventQueue      = EventQueue()
        self.notes:        NoteIDQueue     = NoteIDQueue()
        self.subs:         SubroutineQueue = SubroutineQueue()
    # yapf: enable


class Direct(Type):
    """DirectSound instrument."""

    # yapf: disable
    def __init__(self, key: str):
        self.reverse:   bool = False
        self.fix_pitch: bool = False
        self.env_attn:  int  = 0x00
        self.env_dcy:   int  = 0x00
        self.env_sus:   int  = 0x00
        self.env_rel:   int  = 0x00
        self.raw0:      int  = 0x00
        self.raw1:      int  = 0x00
        self.gb1:       int  = 0x00
        self.gb2:       int  = 0x00
        self.gb3:       int  = 0x00
        self.gb4:       int  = 0x00
        self.drum_key:  int  = 0x3C
        self.key:       str  = key
        self.smp_id:    str  = ''
        self.output:    int  = DirectTypes.NULL
    # yapf: enable


class DrumKit(Type):
    """Represents a drumkit; contains a queue of DirectSound instruments."""

    # yapf: disable
    def __init__(self, key: str):
        self.key:     str         = key
        self.directs: DirectQueue = DirectQueue()
    # yapf: enable


class Event(Type):
    """Internal event"""

    # yapf: disable
    def __init__(self, ticks: int, cmd_byte: int, arg1: int, arg2: int, arg3: int, ):
        self.cmd_byte: int = cmd_byte
        self.arg1:     int = arg1
        self.arg2:     int = arg2
        self.arg3:     int = arg3
        self.ticks:    int = ticks
    # yapf: enable


class Instrument(Type):
    """Represents an instrument; uses a DirectSound queue to hold sound samples."""

    # yapf: disable
    def __init__(self, key: str):
        self.key:     str         = key
        self.directs: DirectQueue = DirectQueue()
        self.kmaps:   KeyMapQueue = KeyMapQueue()
    # yapf: enable


class KeyMap(Type):
    """Represents a MIDI instrument keybind."""

    # yapf: disable
    def __init__(self, key: str, assign_dct: int):
        self.assign_dct: int = assign_dct
        self.key:        str = key
    # yapf: enable


class Note(Type):
    """Container representing a single note in the AGB sound engine."""
    __slots__ = ('enable', 'fmod_channel', 'note_num', 'freq', 'velocity',
                 'parent', 'unk_val', 'output', 'env_attn', 'env_dcy',
                 'env_sus', 'env_rel', 'wait_ticks', 'patch_num')

    # yapf: disable
    def __init__(self, enable: bool, fmod_channel: int, note_num: int, freq: int,
                 velocity: int, parent: int, unk_val: int, output: NoteTypes,
                 env_attn: int, env_dcy: int, env_sus: int, env_rel: int,
                 wait_ticks: float, patch_num: int):
        self.enable:       bool       = enable
        self.note_off:     bool       = False
        self.env_dest:     float      = 0.0
        self.env_pos:      float      = 0.0
        self.env_step:     float      = 0.0
        self.wait_ticks:   float      = wait_ticks
        self.env_attn:     int        = env_attn
        self.env_dcy:      int        = env_dcy
        self.env_rel:      int        = env_rel
        self.env_sus:      int        = env_sus
        self.fmod_channel: int        = fmod_channel
        self.freq:         int        = freq
        self.note_num:     int        = note_num
        self.parent:       int        = parent
        self.patch_num:    int        = patch_num
        self.unk_val:      int        = unk_val
        self.velocity:     int        = velocity
        self.key:          str        = ''
        self.smp_id:       str        = ''
        self.output:       NoteTypes  = output
        self.phase:        NotePhases = NotePhases.NULL
    # yapf: enable


class NoteID(Type):
    """Internal note ID."""

    # yapf: disable
    def __init__(self, key: str, note_id: int):
        self.note_id: int = note_id
        self.key:     str = key
    # yapf: enable


class Sample(Type):
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
    def __init__(self, key: str):
        self.gb_wave:    bool      = False
        self.loop:       bool      = False
        self.smp_data_b: bytearray = self.SampleDataBytes()
        self.fmod_smp:   int       = 0
        self.freq:       int       = 0
        self.loop_start: int       = 0
        self.size:       int       = 0
        self.key:        str       = key
        self.smp_data:   str       = ''
    # yapf: enable

    @property
    def smp_data_len(self):
        """Number of int in sample"""
        return len(self.smp_data_b)

    def rd_smp_data(self, id: int, t_size: int):
        """Read sample data as int from AGB rom."""
        file = File.from_id(id)
        smp_data = bytearray()
        for i in range(t_size):  # pylint: disable=W0612
            smp_data.append(file.read_byte())
        self.smp_data_b = self.SampleDataBytes(smp_data)

    def sav_smp_data(self, id: int):
        """Save bytearray of sample data to AGB rom."""
        file = File.from_id(id)
        for byte in self.smp_data_b:
            file.write_byte(byte)


class Subroutine(Type):
    """Internal AGB subroutine ID."""

    # yapf: disable
    def __init__(self, key: str, evt_q_ptr: int):
        self.evt_q_ptr: int = evt_q_ptr
        self.key:       str = key
    # yapf: enable
