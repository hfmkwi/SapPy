# -*- coding: utf-8 -*-
# !/usr/bin/env python3
# pylint: disable=C0123,C0326,R0901,R0903,R0913,R0914,W0221
"""Data-storage containers for internal use."""
from collections import deque
from enum import Enum
from typing import Any, MutableMapping, MutableSequence, NamedTuple, Union

from fileio import File


class ChannelOutputTypes(Enum):
    """Possible output types for each sound channel"""
    # yapf: disable
    DIRECT       = 0
    SQUARE1      = 1
    SQUARE2      = 2
    WAVE         = 3
    NOISE        = 4
    UNK5         = 5
    UNK6         = 6
    UNK7         = 7
    MULTI_SAMPLE = 8
    DRUMKIT      = 9
    NULL         = 255
    # yapf: enable


class DirectOutputTypes(Enum):
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
    # yapf: enable


class NoteOutputTypes(Enum):
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

    def __ne__(self, other) -> bool:
        return repr(self) != repr(other) and \
            self.items() != other.items()

    def __getitem__(self, key: Union[int, str]) -> Any:
        if type(key) == str and key not in self._key_store:
            return None
        elif type(key) == int:
            if self._storage[int(key)] not in self._key_store:
                return self._storage[key]
            return self._key_store.get(self._storage[key])
        else:
            return self._key_store.get(key)

    def __iter__(self) -> 'File':
        self._list = self._storage.copy()
        return self

    def __len__(self) -> int:
        return len(self._storage)

    def __next__(self) -> Any:
        if not self._list:
            raise StopIteration
        return self._list.popleft()

    def __repr__(self) -> str:
        return self.__repr__()

    def __setitem__(self, key: str, value: Any) -> None:
        self.add(value, str(key))

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

    def keys(self) -> list:
        return self._key_store.keys()

    def values(self) -> list:
        return self._key_store.values()

    def items(self) -> list:
        return self._key_store.items()

    # yapf: disable
    def add(self, item: Any, key: str = None, before: int = None,
            after: int = None) -> None:
        # yapf: enable
        """Add an item to storage.

        Note:
            Neither `before` nor `after` can be used in conjunction.

        Args:
            key: A string reference to the item's index.
            before: index to insert the item before.
            after: index to insert the item after.

        """
        key = str(key)
        if key and key not in self._key_store:
            self._key_store[key] = item
            item = key
        else:
            raise KeyError('Key in use.')
        if not before and not after:
            self._storage += [item]
        else:
            if before == after and before is not None:
                raise ValueError('Simultaneous usage of "before" and "after"')
            elif before:
                self._storage.insert(before - 1, item)
            else:
                self._storage.insert(after + 1, item)

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
    def add(self, ticks: int, command_byte: bytes, param1: bytes,
            param2: bytes, param3: bytes, key: str = None) -> None:
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

    def add(self, assign_direct: int, key: str = None) -> None:
        key_map = KeyMap(key=key, assign_direct=assign_direct)
        super().add(key_map, key)


class NoteQueue(Collection):
    """LIFO container of AGB notes."""

    # yapf: disable
    def add(self, enabled: bool, fmod_channel: int, note_number: bytes,
            frequency: int, velocity: bytes, parent_channel: int,
            unknown_value: bytes, output_type: NoteOutputTypes,
            env_attenuation: bytes, env_decay: bytes, env_sustain: bytes,
            env_release: bytes, wait_ticks: int, patch_number: bytes,
            key: str = None) -> None:
        """Initialize and append a new note."""
        note = Note(
            key             = key,
            enabled         = enabled,
            fmod_channel    = fmod_channel,
            note_number     = note_number,
            frequency       = frequency,
            velocity        = velocity,
            patch_number    = patch_number,
            parent_channel  = parent_channel,
            sample_id       = env_release,
            unknown_value   = unknown_value,
            output_type     = output_type,
            env_attenuation = env_attenuation,
            env_decay       = env_decay,
            env_sustain     = env_sustain,
            env_release     = env_release,
            wait_ticks=wait_ticks)
        super().add(note, key)
        # yapf: enable


class NoteIDQueue(Collection):
    """LIFO container holding internal note IDs."""

    def add(self, note_id: bytes, key: str = None) -> None:
        note = NoteID(key=key, note_id=note_id)
        super().add(note, key)


class SampleQueue(Collection):
    """LIFO container holding instrument samples."""

    def add(self, key: str = None) -> None:
        sample = Sample(key=key)
        super().add(sample, key)


class SubroutineQueue(Collection):
    """LIFO container holding AGB subroutines."""

    def add(self, event_queue_pointer: int, key: str = None) -> None:
        subroutine = Subroutine(
            key=key, event_queue_pointer=event_queue_pointer)
        super().add(subroutine, key)


class Channel(NamedTuple):
    """Sound channel"""
    # yapf: disable
    in_subroutine:         bool
    vibrato_depth:         bytes
    vibrato_rate:          bytes
    return_pointer:        int
    track_length_in_bytes: int
    track_pointer:         int
    output_type:           ChannelOutputTypes
    enabled:               bool       = True
    mute:                  bool       = False
    sustain:               bool       = False
    main_volume:           bytes      = b'100'
    patch_number:          bytes      = b'0x00'
    pitch_bend:            bytes      = b'0x40'
    wait_ticks:            float      = -1.0
    loop_pointer:          int        = 0
    panning:               int        = 0x40
    pitch_bend_range:      int        = 2
    program_counter:       int        = 1
    sub_count_at_loop:     int        = 1
    subroutine_counter:    int        = 1
    transpose:             int        = 0
    event_queue:           EventQueue = EventQueue()
    notes:                 NoteQueue  = NoteQueue()
    subroutines:           SubroutineQueue = SubroutineQueue()
    # yapf: enable


class Direct(NamedTuple):
    """DirectSound instrument."""
    # yapf: disable
    key:             str
    output_type:     DirectOutputTypes
    reverse:         bool  = False
    fixed_pitch:     bool  = False
    env_attenuation: bytes = b'0x00'
    env_decay:       bytes = b'0x00'
    env_sustain:     bytes = b'0x00'
    env_release:     bytes = b'0x00'
    raw0:            bytes = b'0x00'
    raw1:            bytes = b'0x00'
    gb1:             bytes = b'0x00'
    gb2:             bytes = b'0x00'
    gb3:             bytes = b'0x00'
    gb4:             bytes = b'0x00'
    drum_tune_key:   bytes = b'0x3C'
    sample_id:       str   = '0'
    # yapf: enable


class DrumKit(NamedTuple):
    """Represents a drumkit; contains a queue of DirectSound instruments."""
    # yapf: disable
    key:     str
    directs: DirectQueue
    # yapf: enable


class Event(NamedTuple):
    """Internal event"""
    # yapf: disable
    command_byte: bytes
    param1:       bytes
    param2:       bytes
    param3:       bytes
    ticks:        int
    # yapf: enable


class Instrument(NamedTuple):
    """Represents an instrument; uses a DirectSound queue to hold sound samples.
    """
    # yapf: disable
    key:      str
    directs:  DirectQueue = DirectQueue()
    key_maps: KeyMapQueue = KeyMapQueue()
    # yapf: enable


class KeyMap(NamedTuple):
    """Represents a MIDI instrument keybind."""
    # yapf: disable
    key:           str
    assign_direct: int
    # yapf: enable


class Note(NamedTuple):
    """Container representing a single note in the AGB sound engine."""
    # yapf: disable
    enabled:         bool
    env_attenuation: bytes
    env_decay:       bytes
    env_sustain:     bytes
    env_release:     bytes
    note_number:     bytes
    patch_number:    bytes
    unknown_value:   bytes
    velocity:        bytes
    wait_ticks:      float
    fmod_channel:    int
    frequency:       int
    parent_channel:  int
    sample_id:       str
    key:             str
    output_type:     NoteOutputTypes
    note_off:        bool  = False
    env_step:        float = 0.0
    env_destination: float = 0.0
    env_positon:     float = 0.0
    note_phase:      NotePhases = NotePhases.INITIAL
    # yapf: enable


class NoteID(NamedTuple):
    """Internal note ID."""
    # yapf: disable
    note_id: bytes
    key:     str
    # yapf: enable


class Sample(NamedTuple):
    """Sound sample for use during playback."""

    class SampleDataBytes(MutableSequence):
        """Holds sample data as extracted from ROM."""

        def __init__(self, data: bytearray = None) -> None:
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
            self._storage.append(value)

        def insert(self, index: int, value: Any) -> None:
            self._storage.insert(index, value)

    # yapf: disable
    gb_wave:           bool      = None
    loop_enable:       bool      = None
    fmod_sample:       int       = None
    frequency:         int       = None
    loop_start:        int       = None
    size:              int       = None
    key:               str       = None
    sample_data:       str       = None
    sample_data_array: bytearray = SampleDataBytes()
    # yapf: enable

    @property
    def sample_data_length(self):
        """Number of bytes in sample"""
        return len(self.sample_data_array)

    def read_sample_data_from_file(self, file_id: int, t_size: int):
        """Read sample data as bytes from AGB rom."""
        file = File.get_file_from_id(file_id)
        sample_data = bytearray()
        for i in range(t_size):  # pylint: disable=W0612
            sample_data.append(file.read_byte())
        self.sample_data_array = self.SampleDataBytes(sample_data)

    def save_sample_data_to_file(self, file_id: int):
        """Save bytearray of sample data to AGB rom."""
        file = File.get_file_from_id(file_id)
        for byte in self.sample_data_array:
            file.write_byte(byte)


class Subroutine(NamedTuple):
    """Internal AGB subroutine ID."""
    # yapf: disable
    event_queue_pointer: int
    key:                 str
    # yapf: enable
