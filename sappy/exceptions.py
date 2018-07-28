# -*- coding: utf-8 -*-
"""M4A Exceptions."""


class M4AException(Exception):
    """Base class exception for this module.

    Parameters
    ----------

    """

    def __init__(self, message):
        super().__init__(message)


class InvalidArgument(M4AException):
    """Raised when an argument is in an invalid range.

    Parameters
    ----------
    arg : int
        Command argument
    arg_type : str
        Description of argument type

    """

    def __init__(self, arg, arg_type):
        super().__init__(f'Invalid argument: {arg:2X} [{arg_type}]')


class UnknownCommand(M4AException):
    """Raised when an unknown command is parsed/executed.

    Parameters
    ----------
    cmd : int
        Command byte

    """

    def __init__(self, cmd: int):
        super().__init__(f'{cmd:2X}')


class InvalidROM(M4AException):
    """Raised when a ROM lacks a song table."""

    def __init__(self):
        super().__init__(f'Invalid/Unsupported ROM.')


class InvalidSongNumber(M4AException):
    """Raised when the users attempts to access a non-existent song.

    Parameters
    ----------
    song_id : int
        Song table entry number.

    """

    def __init__(self, song_id):
        super().__init__(f'Invalid song number: {song_id}')


class InvalidPointer(M4AException):
    """Raised when an invalid pointer is processsed.

    Parameters
    ----------
    pointer : int
        Address that failed to convert.

    """

    def __init__(self, pointer):
        super().__init__(f'Invalid pointer: 0x{pointer:<8X}')


class InvalidVoice(M4AException):
    """Raised when parsing an invalid M4A voice entry.

    Parameters
    ----------
    pointer : int
        Address of voice entry.
    mode : int
        Type of voice entry.

    """

    def __init__(self, pointer, mode):
        super().__init__(f'Invalid voice@0x{pointer:<X} [0x{mode:<X}]')


class BlankSong(M4AException):
    """Raised when a song has no tracks."""

    def __init__(self):
        super().__init__('Blank song.')


class SoundDriverModeNotFound(M4AException):
    """Raised when the SDM search fails to find a valid SDM call."""

    def __init__(self):
        super().__init__('Could not find SDM; using default SDM settings.')
