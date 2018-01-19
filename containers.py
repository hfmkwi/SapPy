# -*- coding: utf-8 -*-
<<<<<<< HEAD
# !/usr/bin/env python -3
"""Data-storage containers for internal use."""
import logging
import itertools
=======
# !/usr/bin/env python3
# TODO(Me): Add the rest of the docstrings.
"""Data-storage containers for internal use."""
>>>>>>> 825e82705536130e0b50125b88a06c55e9f3979f
from collections import deque
from collections.abc import MutableMapping
from enum import Enum
from typing import Any, NamedTuple, Union

<<<<<<< HEAD
# logging.basicConfig(level=logging.INFO)

logging.basicConfig(level=None)
=======
>>>>>>> 825e82705536130e0b50125b88a06c55e9f3979f

# pylint: disable=C0326
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
    # yapf: disable


# pylint: disable=C0326
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


# pylint: disable=C0326
class NoteOutputTypes(Enum):
    """Declare possible outputs for the Note object"""
<<<<<<< HEAD
    DIRECT = 0
=======
    # yapf: disable
    DIRECT  = 0
>>>>>>> 825e82705536130e0b50125b88a06c55e9f3979f
    SQUARE1 = 1
    SQUARE2 = 2
    WAVE    = 3
    NOISE   = 4
    UNK5    = 5
    UNK6    = 6
    UNK7    = 7
    # yapf: enable


# pylint: disable=C0326
class NotePhases(Enum):
    """Declare possible phases for the Note object"""
<<<<<<< HEAD
=======
    # yapf: disable
>>>>>>> 825e82705536130e0b50125b88a06c55e9f3979f
    INITIAL = 0
    ATTACK  = 1
    DECAY   = 2
    SUSTAIN = 3
    RELEASE = 4
    NOTEOFF = 5
    # yapf: enable


<<<<<<< HEAD
class Note(NamedTuple):  # pylint: disable=R0903
    """Container representing a single note in the AGB sound engine"""
    enabled: bool
    fmod_channel: int
    note_number: bytes
    frequency: int
    velocity: bytes
    patch_number: bytes
    parent_channel: int
    sample_id: str
    unknown_value: bytes
    note_off: bool
    note_phase: NotePhases
    output_type: NoteOutputTypes
    env_step: float
    env_destination: float
    env_positon: float
    env_attenuation: bytes
    env_decay: bytes
    env_sustain: bytes
    env_release: bytes
    wait_ticks: float
    key: str


class Collection(object):
=======
# pylint: disable=C0123
class Collection(MutableMapping):
>>>>>>> 825e82705536130e0b50125b88a06c55e9f3979f
    """Imitation of the VB6 `Collection` data-container"""
    __slots__ = ('_storage', '_key_store', '_list', 'log')

    def __init__(self, *iterables):
<<<<<<< HEAD
        self.log = logging.getLogger(name='{m_name}.{c_name}'.format(
            m_name=__name__, c_name=self.__class__.__name__))
        # self.log.info('Instantiated new Collection')
        # self.log.debug('*iterables: %s', iterables)
=======
>>>>>>> 825e82705536130e0b50125b88a06c55e9f3979f
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

    def __eq__(self, other):
        return repr(self) == repr(other) and \
            self.items() == other.items()

    def __ne__(self, other):
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

    def __iter__(self) -> object:
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
        if not iterables:
            return None
        for iterable in iterables:
<<<<<<< HEAD
            for item in iterable:
                if isinstance(iterable, dict):
                    self.add(iterable[item], item)
                else:
                    self.add(item)

    @property
    def count(self):
        """Return the number of items in the collection."""
        return len(self._storage)

    # yapf: disable
    def add(self, item: Any, key: str = None, before: int = 0,
            after: int = 0) -> None: # yapf: enable
=======
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

    count = property(fget=__len__)

    # yapf: disable
    def add(self, item: Any, key: str = None, before: int = None,
            after: int = None) -> None:
        # yapf: enable
>>>>>>> 825e82705536130e0b50125b88a06c55e9f3979f
        """Add an item to storage.

        Note:
            Neither `before` nor `after` can be used in conjunction.

        Args:
            key: A string reference to the item's index.
            before: index to insert the item before.
            after: index to insert the item after.

        """
<<<<<<< HEAD
        if before == after and before is not 0:
            raise ValueError('Simultaneous usage of "before" and "after"')
        # self.log.info('Adding "%s" with key reference "%s".', item, key)
        if key and key not in self._key_store:
            self._key_store[key] = item
        if not before and not after:
            # self.log.debug('Appending item.')
            self._storage.append(item)
        else:
            if before:
                self._storage.insert(before-1, item)
            else:
                self._storage.insert(after+1, item)

    def item(self, key: Union[str, int]) -> Any:
        """Get an item from storage via its index or key reference."""
        self.log.info('Getting item via reference "%s".', key)
        out = self._key_store.get(key)
        if out is None:
            out = self._storage[key]
            if out in self._key_store:
                out = self._key_store.get(key)
        return out

    def remove(self, key: Union[str, int]) -> None:
        """Remove an item from storage via its index or key reference."""
        self.log.info('Removing item via reference "%s".', key)
=======
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


# pylint: disable=R0901
class ChannelQueue(Collection):
    """LIFO container of sound channels."""

    # pylint: disable=W0221
    def add(self, key: str = None) -> None:
        channel = Channel(key=key)
        super().add(channel)


# pylint: disable=R0901
class DirectQueue(Collection):
    """LIFO container of DirectSound notes."""

    # pylint: disable=W0221
    def add(self, key: str = None) -> None:
        direct = Direct(key=key)
        super().add(direct, key)


# pylint: disable=R0901
class EventQueue(Collection):
    """LIFO container of internal events."""

    # yapf: disable
    # pylint: disable=C0326,R0913,W0221
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


# pylint: disable=R0901
class NoteQueue(Collection):
    """LIFO container of AGB notes"""

    # pylint: disable=C0326,R0913,R0914,W0221
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
        # yapf: enable
        if not key:
            super().add(note)
        else:
            super().add(note, key)


class SubroutineQueue(Collection):
    """LIFO container holding AGB subroutines."""
    pass


# pylint: disable=C0326,R0903
class Channel(NamedTuple):
    """Sound channel"""
    # yapf: disable
    in_subroutine:         bool
    vibrato_depth:         bytes
    vibrato_rate:          bytes
    return_pointer:        int
    track_length_in_bytes: int
    track_pointer:         int
    enabled:               bool       = True
    mute:                  bool       = False
    sustain:               bool       = False
    main_volume:           bytes      = b'100'
    patch_number:          bytes      = b'0x00'
    pitch_bend:            bytes      = b'0x40'
    loop_pointer:          int        = 0
    panning:               int        = 0x40
    pitch_bend_range:      int        = 2
    program_counter:       int        = 1
    sub_count_at_loop:     int        = 1
    subroutine_counter:    int        = 1
    transpose:             int        = 0
    wait_ticks:            float      = -1.0
    output_type:           ChannelOutputTypes
    event_queue:           EventQueue = EventQueue()
    notes:                 NoteQueue  = NoteQueue()
    subroutines:           SubroutineQueue = SubroutineQueue()
    # yapf: enable


# pylint: disable=C0326,R0903
class Direct(NamedTuple):
    """DirectSound note"""
    # yapf: disable
    key:             str
    output_type:     DirectOutputTypes
    sample_id:       str   = '0'
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
    reverse:         bool  = False
    fixed_pitch:     bool  = False
    drum_tune_key:   bytes = bytes([0x3C])
    # yapf: enable


# pylint: disable=C0326,R0903
class Event(NamedTuple):
    """Internal event"""
    # yapf: disable
    ticks:        int
    command_byte: bytes
    param1:       bytes
    param2:       bytes
    param3:       bytes
    # yapf: enable


# pylint: disable=C0326,R0903
class Note(NamedTuple):
    """Container representing a single note in the AGB sound engine"""
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
>>>>>>> 825e82705536130e0b50125b88a06c55e9f3979f
