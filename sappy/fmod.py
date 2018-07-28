# -*- coding: utf-8 -*-
"""API for FMOD (Direct clone from original source).

Attributes
----------
FMOD_VERSION : float
    FMOD library version.
LIB_DIR : str
    Path to SapPy lib folder.
OS : str
    Machine operating system.
ARCH : str
    Machine bit architecture.
IS_64BIT : str
    Python interpreter architecture.
FMOD_ERR_MESSAGES : Dict[FModErrors, str]
    Lookup table of error strings for FMOD error codes.
LIB : Optional[str]
    Name of FMOD library.
fmod : Union[WinDLL, DummyLibrary]

"""

import sys
from ctypes import *
from enum import IntEnum
from os import path
from platform import system, machine

from .config import MAX_FMOD_TRACKS

FMOD_VERSION = 3.75

LIB_DIR = path.join(path.dirname(path.abspath(__file__)), '..', 'lib')
OS = system()
ARCH = machine()
IS_64BIT = sys.maxsize > 2 ** 32

if ARCH in ('AMD64', 'i386', 'i586') and OS == 'Windows' and not IS_64BIT:
    LIB = 'fmod.dll'
else:
    LIB = None

if LIB is not None:
    fmod = windll.LoadLibrary(path.join(LIB_DIR, LIB))

    fmod.FSOUND_Init.argtypes = (c_int, c_int, c_uint)
    fmod.FSOUND_Init.restype = c_bool

    fmod.FSOUND_SetOutput.argtypes = (c_int,)
    fmod.FSOUND_SetOutput.restype = c_bool

    fmod.FSOUND_SetSFXMasterVolume.argtypes = (c_int,)
    fmod.FSOUND_SetSFXMasterVolume.restype = c_bool

    fmod.FSOUND_GetError.restype = c_uint

    fmod.FSOUND_Sample_Load.argtypes = (c_int, c_char_p, c_uint, c_int, c_int)
    fmod.FSOUND_Sample_Load.restype = c_void_p

    fmod.FSOUND_Sample_SetLoopPoints.argtypes = (c_int, c_int, c_int)
    fmod.FSOUND_Sample_SetLoopPoints.restype = c_bool

    fmod.FSOUND_PlaySoundEx.argtypes = (c_int, c_void_p, c_void_p, c_bool)
    fmod.FSOUND_PlaySoundEx.restype = c_int

    fmod.FSOUND_StopSound.argtypes = (c_int,)
    fmod.FSOUND_StopSound.restype = c_bool

    fmod.FSOUND_SetFrequency.argtypes = (c_int, c_int)
    fmod.FSOUND_SetFrequency.restype = c_bool

    fmod.FSOUND_SetPan.argtypes = (c_int, c_int)
    fmod.FSOUND_SetPan.restype = c_bool

    fmod.FSOUND_SetVolume.argtypes = (c_int, c_int)
    fmod.FSOUND_SetVolume.restype = c_bool

    fmod.FSOUND_Close.restype = c_void_p

    fmod.FSOUND_SetPaused.argtypes = (c_int, c_bool)
    fmod.FSOUND_SetPaused.restype = c_bool

    fmod.FSOUND_SetMute.argtypes = (c_int, c_int)
    fmod.FSOUND_SetMute.restype = c_bool

    fmod.FSOUND_GetMute.argtypes = (c_int,)
    fmod.FSOUND_GetMute.restype = c_bool
else:
    from random import randint


    def _dummy_error(*args):
        """Fake functionality of FSOUND_GetError.

        Returns
        -------
        FModErrors
            Always returns no error.

        """
        del args
        return FModErrors.NONE


    def _dummy_bool(*args):
        """Fake functionality of all FMOD `bool` return functions.

        Returns
        -------
        bool
            Always returns True.

        """
        del args
        return True


    def _dummy_int(*args):
        """Fake functionality of all FMOD `int` return functions.

        Returns
        -------
        int
            Always returns a random integer.

        """
        del args
        return randint(0, MAX_FMOD_TRACKS)


    class DummyLibrary(object):
        """Fake library to simulate FMOD calls without the presence of a
        working FMOD DLL."""

        def __getattr__(self, item):
            if item == 'FSOUND_GetError':
                return _dummy_error
            elif item in 'FSOUND_Sample_Load FSOUND_PlaySoundEx':
                return _dummy_int
            else:
                return _dummy_bool


    fmod = DummyLibrary()


def fmod_init(sample_rate, max_channels, flags):
    """Open FMOD player for playback.

    Parameters
    ----------
    sample_rate : int
        Engine sampling rate.
    max_channels : int
        Maximum software channels.
    flags : int
        Miscellaneous init flags.

    Returns
    -------
    bool
        True on success, False on failure.

    """
    return fmod.FSOUND_Init(sample_rate, max_channels, flags)


def set_output(output_type):
    """Change FMOD playback mode.

    Parameters
    ----------
    output_type : int
        Playback mode.

    Returns
    -------
    bool
        True on success, False on failure.

    """
    return fmod.FSOUND_SetOutput(output_type)


def set_master_volume(volume):
    """Change FMOD global player volume.

    Parameters
    ----------
    volume : int
        New player volume.

    Returns
    -------
    bool
        True on success, False on failure.

    """
    return fmod.FSOUND_SetSFXMasterVolume(volume)


def get_error():
    """Get FMOD error code.

    Returns
    -------
    FModErrors
        Error code and name.

    """
    return FModErrors(fmod.FSOUND_GetError())


def load_sample(index, file, mode, offset=0, size=0):
    """Add sample entry to the FMOD player.

    Parameters
    ----------
    index : int
        Sample pool index.
    file : str
        File path to sample.
    mode : int
        Description of data format.
    offset : int, optional
        Start off set of sample data (default is 0).
    size : int, optional
        Number of samples in sample data (default is 0).

    Returns
    -------
    Union[int, None]
        A FMOD sample handle on success, None on failure.

    """
    file = file.encode('ascii')
    return fmod.FSOUND_Sample_Load(index, file, mode, offset, size)


def set_loop_points(sample_handle, start, end) -> bool:
    """Set FMOD sample entry looping points.

    Parameters
    ----------
    sample_handle : int
        FMOD sample handle.
    start : int
        Starting sample address.
    end : int
        End sample address.

    Returns
    -------
    bool
        True on success, False on failure.

    """
    return fmod.FSOUND_Sample_SetLoopPoints(sample_handle, start, end)


def play_sound(channel, sample_handle, paused, dsp_ptr=None):
    """Open FMOD channel for active playback.

    Parameters
    ----------
    channel : int
        Absolute channel number in channel pool.
    sample_handle : int
        FMOD sample handle.
    paused : bool
        Controls if channel starts paused or not.
    dsp_ptr : int, optional
        Pointer to custom DSP unit, otherwise system default is used.

    Returns
    -------
    int
        A FMOD channel handle on success, -1 on failure.

    """
    return fmod.FSOUND_PlaySoundEx(channel, sample_handle, dsp_ptr, paused)


def stop_sound(channel):
    """Stop a FMOD channel.

    Parameters
    ----------
    channel : int
        FMOD channel handle.

    Returns
    -------
    bool
        True on success, False on failure.

    """
    return fmod.FSOUND_StopSound(channel)


def set_frequency(channel, frequency):
    """Set FMOD channel playback frequency.

    Parameters
    ----------
    channel : int
        FMOD channel handle.
    frequency : int
        New frequency in Hz.

    Returns
    -------
    bool
        True on success, False on failure.

    """
    return fmod.FSOUND_SetFrequency(channel, frequency)


def set_panning(channel, panning):
    """Set FMOD channel panning.

    Parameters
    ----------
    channel : int
        FMOD channel handle.
    panning : int
        New panning.

    Returns
    -------
    bool
        True on success, False on failure.

    """
    return fmod.FSOUND_SetPan(channel, panning)


def set_volume(channel, volume):
    """Set FMOD channel volume.

    Parameters
    ----------
    channel : int
        FMOD channel handle.
    volume : int
        New volume.

    Returns
    -------
    bool
        True on success, False on failure.

    """
    return fmod.FSOUND_SetVolume(channel, volume)


def fmod_close():
    """Close FMOD player."""
    fmod.FSOUND_Close()


def set_paused(channel, paused):
    """Pause or un-pause a FMOD channel.

    Parameters
    ----------
    channel : int
        FMOD channel handle.
    paused : bool
        Pause state.

    Returns
    -------
    bool
        True on success, False on failure.

    """
    return fmod.FSOUND_SetPaused(channel, paused)


def set_mute(channel, mute):
    """Mute or un-mute a FMOD channel.

    Parameters
    ----------
    channel : int
        FMOD channel handle.
    mute : bool
        Mute state.

    Returns
    -------
    bool
        True on success, False on failure.

    """
    return fmod.FSOUND_SetMute(channel, mute)


def get_mute(channel):
    """Get mute state of a FMOD channel.

    Parameters
    ----------
    channel : int
        FMOD channel handle.

    Returns
    -------
    bool
        Mute state.

    """
    return fmod.FSOUND_GetMute(channel)


class FModErrors(IntEnum):
    """Error codes in the FMOD API."""

    NONE = 0
    BUSY = 1
    UNINITIALIZED = 2
    INITIALIZED = 3
    ALLOC = 4
    PLAY = 5
    OUTPUT_FORMAT = 6
    COOP_LEVEL = 7
    CREATE_BUFFER = 8
    FILE_NOT_FOUND = 9
    FILE_UNKNOWN_FORMAT = 10
    FILE_BAD = 11
    MEMORY = 12
    VERSION = 13
    INV_PARAM = 14
    NO_EAX = 15
    CHANNEL_ALLOC = 16
    RECORD = 17
    MEDIA_PLAYER = 18
    CD_DEVICE = 19


class FSoundMode(IntEnum):
    """Sound flags for the FMOD API."""

    LOOP_OFF = 0x1
    LOOP_NORMAL = 0x2
    LOOP_BIDI = 0x4
    PCM8 = 0x8
    PCM16 = 0x10
    MONO = 0x20
    STEREO = 0x40
    UNSIGNED = 0x80
    SIGNED = 0x100
    DELTA = 0x200
    IT214 = 0x400
    IT215 = 0x800
    HW3D = 0x1000
    TWO_DIMENSIONAL = 0x2000
    STREAMABLE = 0x4000
    LOAD_MEMORY = 0x8000
    RAW = 0x10000
    MPEG_ACCURATE = 0x20000
    FORCE_MONO = 0x40000
    HW2D = 0x80000
    ENABLE_FX = 0x100000
    MPEG_HALF_RATE = 0x200000
    XAD_PCM = 0x400000
    VAG = 0x800000
    NON_BLOCKING = 0x1000000
    GCAD_PCM = 0x2000000
    MULTI_CHANNEL = 0x4000000
    USE_CORE0 = 0x8000000
    USE_CORE1 = 0x10000000
    LOAD_MEMORY_IOP = 0x20000000
    STREAM_NET = 0x80000000
    NORMAL = PCM16 | SIGNED | MONO


class FSampleMode(IntEnum):
    """Miscellaneous flags for the FMOD API."""

    FREE = -1
    UNMANAGED = -2
    ALL = -3
    STEREO_PAN = -1
    SYSTEM_CHANNEL = -1000
    SYSTEM_SAMPLE = -1000


FMOD_ERR_MESSAGES = {
    FModErrors.NONE:
        "No errors",
    FModErrors.BUSY:
        "Cannot call this command after FSOUND_Init. Call FSOUND_Close first.",
    FModErrors.UNINITIALIZED:
        "Cannot call this command before FSOUND_Init.",
    FModErrors.PLAY:
        "Cannot play the sound.",
    FModErrors.INITIALIZED:
        "Error initializing vol_output device.",
    FModErrors.ALLOC:
        "The vol_output device is already in use and cannot be reused.",
    FModErrors.OUTPUT_FORMAT:
        "Sound card does not support the features needed for this sound system "
        "(16bit stereo).",
    FModErrors.COOP_LEVEL:
        "Error setting cooperative level for hardware.",
    FModErrors.CREATE_BUFFER:
        'Error creating hardware sound buffer.',
    FModErrors.FILE_NOT_FOUND:
        "File not found.",
    FModErrors.FILE_UNKNOWN_FORMAT:
        "Unknown file format.",
    FModErrors.FILE_BAD:
        "Error loading file.",
    FModErrors.MEMORY:
        "Not enough memory.",
    FModErrors.VERSION:
        "The version number of this file format is not supported.",
    FModErrors.INV_PARAM:
        "An invalid parameter was passed to this function.",
    FModErrors.NO_EAX:
        "Tried to use an EAX command on a non-EAX enabled channel or "
        "vol_output.",
    FModErrors.CHANNEL_ALLOC:
        "Failed to allocate a new channel.",
    FModErrors.RECORD:
        "Recording is not supported on this machine.",
    FModErrors.MEDIA_PLAYER:
        "Required MediaPlayer codec is not installed.",
    FModErrors.CD_DEVICE:
        "An error occurred trying to open the specified CD device."
}
