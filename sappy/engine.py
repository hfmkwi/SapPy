#-*- coding: utf-8 -*-
"""Data-storage containers for internal use."""
import collections
import enum
import typing

import sappy.fileio as fileio

NOTES = {
    0: 'C',
    1: '#C',
    2: 'D',
    3: '#D',
    4: 'E',
    5: 'F',
    6: '#F',
    7: 'G',
    8: '#G',
    9: 'A',
    10: '#A',
    11: 'B'
}

STLEN = {
    0x0: 0x0,
    0x1: 0x1,
    0x2: 0x2,
    0x3: 0x3,
    0x4: 0x4,
    0x5: 0x5,
    0x6: 0x6,
    0x7: 0x7,
    0x8: 0x8,
    0x9: 0x9,
    0xA: 0xA,
    0xB: 0xB,
    0xC: 0xC,
    0xD: 0xD,
    0xE: 0xE,
    0xF: 0xF,
    0x10: 0x10,
    0x11: 0x11,
    0x12: 0x12,
    0x13: 0x13,
    0x14: 0x14,
    0x15: 0x15,
    0x16: 0x16,
    0x17: 0x17,
    0x18: 0x18,
    0x19: 0x1C,
    0x1A: 0x1E,
    0x1B: 0x20,
    0x1C: 0x24,
    0x1D: 0x28,
    0x1E: 0x2A,
    0x1F: 0x2C,
    0x20: 0x30,
    0x21: 0x34,
    0x22: 0x36,
    0x23: 0x38,
    0x24: 0x3C,
    0x25: 0x40,
    0x26: 0x42,
    0x27: 0x44,
    0x28: 0x48,
    0x29: 0x4C,
    0x2A: 0x4E,
    0x2B: 0x50,
    0x2C: 0x54,
    0x2D: 0x58,
    0x2E: 0x5A,
    0x2F: 0x5C,
    0x30: 0x60
}


class ChannelTypes(enum.IntEnum):
    """Possible output types for each sound channel."""

    # yapf: disable
    DIRECT  = 0
    SQUARE1 = 1
    SQUARE2 = 2
    WAVE    = 3
    NOISE   = 4
    UNK5    = 5
    UNK6    = 6
    UNK7    = 7
    MULTI   = 8
    DRUMKIT = 9
    NULL    = 255
    # yapf: enable


class DirectTypes(enum.IntEnum):
    """Possible outputs for DirectSound note."""
    # yapf: disable

    DIRECT   = 0
    SQUARE1  = 1
    SQUARE2  = 2
    WAVEFORM = 3
    NOISE    = 4
    UNK5     = 5
    UNK6     = 6
    UNK7     = 7
    # yapf: enable


class NoteTypes(enum.IntEnum):
    """Declare possible outputs for the Note object."""
    # yapf: disable

    DIRECT   = 0
    SQUARE1  = 1
    SQUARE2  = 2
    WAVEFORM = 3
    NOISE    = 4
    UNK5     = 5
    UNK6     = 6
    UNK7     = 7
    # yapf: enable


class NotePhases(enum.IntEnum):
    """Declare possible phases for the Note object."""
    # yapf: disable

    INITIAL = 0
    ATTACK  = 1
    DECAY   = 2
    SUSTAIN = 3
    RELEASE = 4
    NOTEOFF = 5
    # yapf: enable


class Collection(collections.deque, collections.UserDict,
                 typing.MutableSequence):
    """Imitation of the VB6 `Collection` data-container.

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
        """Initialize and populate the keystore and deque."""
        collections.UserDict.__init__(self)
        collections.deque.__init__(self)
        if iterables:
            for iter in iterables:
                if type(iter) == dict:
                    for k, v in enumerate(iter):
                        self.key_append(v, k)
                    continue
                self.extend(iter)

    def __contains__(self, item: typing.Any) -> bool:
        return collections.deque.__contains__(self, item) or item in self.data

    def __delitem__(self, item: int) -> bool:
        out = collections.deque.__getitem__(self, item)
        collections.deque.__delitem__(self, item)
        self.data.pop(out)

    def __getitem__(self, key: typing.Any) -> typing.Any:
        out = self.data.get(key)
        if out is not None:
            return out
        out = collections.deque.__getitem__(self, key)
        out = self.data.get(out, out)
        return out

    def __iter__(self):
        self._list = tuple(collections.deque.__iter__(self))
        self._ind = 0
        return self

    def __next__(self):
        try:
            out = self.data.get(self._list[self._ind], self._list[self._ind])
            self._ind += 1
            return out
        except IndexError:
            raise StopIteration

    def __eq__(self, other: 'Container') -> bool:
        return collections.deque.__eq__(self, other) and self.data == other.data

    def __hash__(self):
        return hash((collections.deque.__iter__(self), tuple(self.data)))

    def __ne__(self, other: 'Container') -> bool:
        return collections.deque.__ne__(self, other) and self.data != other.data

    def __setitem__(self, key: typing.Union[str, int],
                    item: typing.Any) -> None:
        if type(key) == str:
            self.data[key] = item
        elif type(key) == int:
            out = collections.deque.__getitem__(self, key)
            collections.deque.__setitem__(self, key, item)
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
        raise NotImplementedError

    def clear(self):
        collections.deque.clear(self)
        self.data.clear()
        assert len(self) == 0
        assert len(self.data) == 0

    def item(self, key: str):
        """Get value from key or index."""
        return self.data[key]

    def key_append(self, item: typing.Any, key: typing.Any) -> None:
        """Append an keyed item to end of storage.

        Args:
        key: A string reference to the item's index.

        """
        if key in self.data:
            raise KeyError('Key in use.')
        self.data[key] = item
        self.append(key)

    def key_insert(self, item: typing.Any, key: typing.Any, ind: int = None):
        """Insert an item at the specified index within storage."""
        if key in self.data:
            raise KeyError('Key in use.')
        self.data[key] = item
        self.insert(ind, key)

    def remove(self, key: str):
        ind = collections.deque.index(self, key)
        collections.deque.__delitem__(self, ind)
        del self.data[key]

    count = property(fget=collections.deque.__len__)


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
    def add(self, ticks: int, cmd_byte: int, arg1: int = 0, arg2: int = 0, arg3: int = 0) -> None:
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
    def add(self, note_num: int, velocity: int, parent: int, unk_val: int, wait_ticks: float, patch_num: int) -> None:
        """Initialize and append a new note."""
        note = Note(
            note_num     = note_num,
            velocity     = velocity,
            parent       = parent,
            unk_val      = unk_val,
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
    __slots__ = ()

    def __str__(self):
        attr = []
        for name in dir(self):
            if name.startswith('_') or name not in self.__slots__:
                continue
            obj = getattr(self, name)
            try:
                value = repr(obj)
            except:
                value = str(obj)
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
        self.is_enabled:          bool            = True
        self.is_muted:            bool            = False
        self.in_subroutine:       bool            = False
        self.is_sustain:          bool            = False
        self.wait_ticks:          float           = -1.0
        self.loop_ptr:            int             = 0
        self.main_volume:         int             = 100
        self.panning:             int             = 0x40
        self.patch_num:           int             = 0x00
        self.pitch_bend:          int             = 0x40
        self.pitch_range:         int             = 2
        self.program_ctr:         int             = 0
        self.priority:            int             = 0
        self.return_ptr:          int             = 0
        self.subroutine_ctr:      int             = 0
        self.subroutine_loop_cnt: int             = 1
        self.track_len:           int             = 0
        self.track_ptr:           int             = 0
        self.transpose:           int             = 0
        self.vib_depth:           int             = 0
        self.vib_rate:            int             = 0
        self.output_volume:       int             = 0
        self.notes_playing:       list            = []
        self.key:                 str             = ''
        self.output_type:         ChannelTypes    = ChannelTypes.DIRECT
        self.event_queue:         EventQueue      = EventQueue()
        self.notes:               NoteIDQueue     = NoteIDQueue()
        self.subroutines:         SubroutineQueue = SubroutineQueue()
    # yapf: enable


class Direct(Type):
    """DirectSound instrument."""
    __slots__ = ('reverse', 'fix_pitch', 'env_attn', 'env_dcy', 'env_sus',
                 'env_rel', 'raw0', 'raw1', 'gb1', 'gb2', 'gb3', 'gb4',
                 'drum_key', 'key', 'smp_id', 'output')

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
        self.output:    int  = DirectTypes.DIRECT
    # yapf: enable


class DrumKit(Type):
    """Represents a drumkit; contains a queue of DirectSound instruments."""
    __slots__ = ('key', 'directs')

    # yapf: disable
    def __init__(self, key: str):
        self.key:     str         = key
        self.directs: DirectQueue = DirectQueue()
    # yapf: enable


class Event(Type):
    """Internal event."""
    __slots__ = ('cmd_byte', 'arg1', 'arg2', 'arg3', 'ticks')

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
    __slots__ = ('key', 'directs', 'kmaps')

    # yapf: disable
    def __init__(self, key: str):
        self.key:     str         = key
        self.directs: DirectQueue = DirectQueue()
        self.kmaps:   KeyMapQueue = KeyMapQueue()
    # yapf: enable


class KeyMap(Type):
    """Represents a MIDI instrument keybind."""
    __slots__ = ('assign_dct', 'key')

    # yapf: disable
    def __init__(self, key: str, assign_dct: int):
        self.assign_dct: int = assign_dct
        self.key:        str = key
    # yapf: enable


class Note(Type):
    """Container representing a single note in the AGB sound engine."""
    __slots__ = ('enable', 'note_off', 'env_dest', 'env_pos', 'env_step',
                 'vib_pos', 'wait_ticks', 'env_attn', 'env_dcy', 'env_rel',
                 'env_sus', 'fmod_channel', 'frequency', 'note_num', 'parent',
                 'patch_num', 'unk_val', 'velocity', 'key', 'smp_id', 'output',
                 'phase', 'fmod_fx')

    # yapf: disable
    def __init__(self, note_num: int, velocity: int, parent: int, unk_val: int, wait_ticks: float, patch_num: int):
        self.enable:       bool       = True
        self.note_off:     bool       = False
        self.env_dest:     float      = 0.0
        self.env_pos:      float      = 0.0
        self.env_step:     float      = 0.0
        self.vib_pos:      float      = 0.0
        self.wait_ticks:   float      = wait_ticks
        self.env_attn:     int        = 0
        self.env_dcy:      int        = 0
        self.env_rel:      int        = 0
        self.env_sus:      int        = 0
        self.fmod_channel: int        = 0
        self.fmod_fx:      int        = 0
        self.frequency:    int        = 0
        self.note_num:     int        = note_num
        self.parent:       int        = parent
        self.patch_num:    int        = patch_num
        self.unk_val:      int        = unk_val
        self.velocity:     int        = velocity
        self.key:          str        = ''
        self.smp_id:       str        = ''
        self.output:       NoteTypes  = NoteTypes.DIRECT
        self.phase:        NotePhases = NotePhases.INITIAL
    # yapf: enable


class NoteID(Type):
    """Internal note ID."""
    __slots__ = ('note_id', 'key')

    # yapf: disable
    def __init__(self, key: str, note_id: int):
        self.note_id: int = note_id
        self.key:     str = key
    # yapf: enable


class Sample(Type):
    """Sound sample for use during playback."""

    class SampleDataBytes(typing.MutableSequence):
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

        def append(self, value: typing.Any) -> None:
            """Append item to storage."""
            self._storage.append(value)

        def insert(self, index: int, value: typing.Any) -> None:
            """Insert item at specified index."""
            self._storage.insert(index, value)

    # yapf: disable
    def __init__(self, key: str):
        self.gb_wave:    bool      = False
        self.loop:       bool      = False
        self.smp_data_b: bytearray = self.SampleDataBytes()
        self.fmod_smp:   int       = 0
        self.frequency:  int       = 0
        self.loop_start: int       = 0
        self.size:       int       = 0
        self.key:        str       = key
        self.smp_data:   str       = ''
    # yapf: enable

    @property
    def smp_data_len(self):
        """Return the size of the sample data in bytes."""
        return len(self.smp_data_b)

    def rd_smp_data(self, id: int, t_size: int):
        """Read sample data as int from AGB rom."""
        file = fileio.VirtualFile.from_id(id)
        smp_data = bytearray()
        for i in range(t_size):  # pylint: disable=W0612
            smp_data.append(file.read_byte())
        self.smp_data_b = self.SampleDataBytes(smp_data)

    def sav_smp_data(self, id: int):
        """Save bytearray of sample data to AGB rom."""
        file = fileio.VirtualFile.from_id(id)
        for byte in self.smp_data_b:
            file.write_byte(byte)


class Subroutine(Type):
    """Internal AGB subroutine ID."""

    # yapf: disable
    def __init__(self, key: str, evt_q_ptr: int):
        self.evt_q_ptr: int = evt_q_ptr
        self.key:       str = key
    # yapf: enable


def sbyte_to_int(sbyte: int) -> int:
    """Convert a signed byte into a signed 4-byte integer."""
    return sbyte - 0x100 if sbyte >= 0x80 else sbyte


def stlen_to_ticks(short_len: int) -> int:
    """Convert short length to MIDI ticks."""
    return STLEN.get(short_len)


def note_to_name(midi_note: int) -> str:
    """Retrieve the string name of a MIDI note from its byte representation."""
    x = midi_note % 12
    o = midi_note // 12
    return NOTES.get(x) + str(o)


def note_to_freq(midi_note: int, midc_freq: int = -1) -> int:
    """Retrieve the sound frequency in Hz of a MIDI note relative to C3."""
    import math
    magic = math.pow(2, 1.0 / 12.0)
    X = midi_note - 0x3C
    if midc_freq == -1:
        a = 7040
        c = a * math.pow(magic, 3)
    elif midc_freq == -2:
        a = 7040 / 2
        c = a * math.pow(magic, 3)
    else:
        c = midc_freq

    x = c * math.pow(magic, X)
    return int(x)
