# -*- coding: utf-8 -*-
"""API for FMOD (Direct clone from original source)."""
import ctypes
import enum
import os
import platform
import sys
import typing

FMOD_VERSION = 3.75
LIBDIR = os.path.join(sys.path[0], 'lib')
OS = platform.system()
ARCH = platform.machine()

if ARCH in ('AMD64', 'i386', 'i586') and OS == 'Windows':
    LIB = 'fmod.dll'
elif ARCH == 'i386' and OS == 'Linux':
    LIB = 'libfmod.so.10'
else:
    LIB = None

if LIB is not None:
    fmod = ctypes.windll.LoadLibrary(os.path.join(LIBDIR, LIB))

    systemInit = fmod.FSOUND_Init
    systemInit.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_uint)
    systemInit.restype = ctypes.c_bool

    setOutput = fmod.FSOUND_SetOutput
    setOutput.argtypes = (ctypes.c_int,)
    setOutput.restype = ctypes.c_bool

    setMasterVolume = fmod.FSOUND_SetSFXMasterVolume
    setMasterVolume.argtypes = (ctypes.c_int,)
    setMasterVolume.restype = ctypes.c_bool

    getError = fmod.FSOUND_GetError
    getError.restype = ctypes.c_uint

    sampleLoad = fmod.FSOUND_Sample_Load
    sampleLoad.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_uint,
                           ctypes.c_int, ctypes.c_int)
    sampleLoad.restype = ctypes.c_int

    setLoopPoints = fmod.FSOUND_Sample_SetLoopPoints
    setLoopPoints.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int)
    setLoopPoints.restype = ctypes.c_bool

    playSound = fmod.FSOUND_PlaySoundEx
    playSound.argtypes = (ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                          ctypes.c_bool)
    playSound.restype = ctypes.c_int

    stopSound = fmod.FSOUND_StopSound
    stopSound.argtypes = (ctypes.c_int,)
    stopSound.restype = ctypes.c_bool

    setFrequency = fmod.FSOUND_SetFrequency
    setFrequency.argtypes = (ctypes.c_int, ctypes.c_int)
    setFrequency.restype = ctypes.c_bool

    setPan = fmod.FSOUND_SetPan
    setPan.argtypes = (ctypes.c_int, ctypes.c_int)
    setPan.restype = ctypes.c_bool

    setVolume = fmod.FSOUND_SetVolume
    setVolume.argtypes = (ctypes.c_int, ctypes.c_int)
    setVolume.restype = ctypes.c_bool

    systemClose = fmod.FSOUND_Close
    systemClose.restype = ctypes.c_void_p

    setPaused = fmod.FSOUND_SetPaused
    setPaused.argtypes = (ctypes.c_int, ctypes.c_bool)
    setPaused.restype = ctypes.c_bool

    setDefaults = fmod.FSOUND_Sample_SetDefaults
    setDefaults.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int)
    setDefaults.restype = ctypes.c_bool
else:
    import random
    fmod = None
    maxsize = sys.maxsize

    systemInit = lambda freq, chan, flags: True
    setOutput = lambda output: True
    setMasterVolume = lambda vol: True
    getError = lambda: 0
    sampleLoad = lambda index, file, mode, offset, size: random.randint(0, 32)
    setLoopPoints = lambda smp_ptr, start, end: True
    playSound = lambda chan, smp_ptr, dsp_ptr, is_paused: random.randint(0, 32)
    stopSound = lambda chan: True
    setFrequency = lambda chan, freq: True
    setPan = lambda chan, pan: True
    setVolume = lambda chan, vol: True
    systemClose = lambda: None
    enableFX = lambda chan, fx_type: random.randint(0, 32)
    setEcho = lambda fx_id, wd_mix, feedback, l_delay, r_delay, pan_delay: True
    setPaused = lambda chan, pause: True
    disableFX = lambda chan: True


class FModErrors(enum.IntEnum):
    """Error codes in the FMOD API."""

    NONE = 0
    BUSY = 1
    UNINIT = 2
    INIT = 3
    ALLOC = 4
    PLAY = 5
    OUTPUT_FORMAT = 6
    COOP_LEVEL = 7
    CREATE_BUFFER = 8
    FILE_NOTFOUND = 9
    FILE_UNKFORMAT = 10
    FILE_BAD = 11
    MEMORY = 12
    VERSION = 13
    INV_PARAM = 14
    NO_EAX = 15
    CHANNEL_ALLOC = 16
    RECORD = 17
    MEDIAPLAYER = 18
    CD_DEVICE = 19


class FSoundModes(enum.IntEnum):
    """Sound flags for the FMOD API."""

    LOOP_OFF = 0x1
    LOOP_NORMAL = 0x2
    LOOP_BIDI = 0x4
    _8BITS = 0x8
    _16BITS = 0x10
    MONO = 0x20
    STEREO = 0x40
    UNSIGNED = 0x80
    SIGNED = 0x100
    DELTA = 0x200
    IT214 = 0x400
    IT215 = 0x800
    HW3D = 0x1000
    _2D = 0x2000
    STREAMABLE = 0x4000
    LOADMEMORY = 0x8000
    LOADRAW = 0x10000
    MPEGACCURATE = 0x20000
    FORCEMONO = 0x40000
    HW2D = 0x80000
    ENABLEFX = 0x100000
    MPEGHALFRATE = 0x200000
    XADPCM = 0x400000
    VAG = 0x800000
    NONBLOCKING = 0x1000000
    GCADPCM = 0x2000000
    MULTICHANNEL = 0x4000000
    USECORE0 = 0x8000000
    USECORE1 = 0x10000000
    LOADMEMORYIOP = 0x20000000
    STREAM_NET = 0x80000000
    NORMAL = _16BITS | SIGNED | MONO


class FSoundtracksampleMode(enum.IntEnum):
    """Misc. flags for the FMOD API."""

    FREE = -1
    UNMANAGED = -2
    ALL = -3
    STEREOPAN = -1
    SYSTEMCHANNEL = -1000
    SYSTEMSAMPLE = -1000


FMOD_ERR_MESSAGES = {
    FModErrors.NONE:
    "No errors",
    FModErrors.BUSY:
    "Cannot call this command after FSOUND_Init. Call FSOUND_Close first.",
    FModErrors.UNINIT:
    "Cannot call this command before FSOUND_Init.",
    FModErrors.PLAY:
    "Cannot play the sound.",
    FModErrors.INIT:
    "Error initializing output device.",
    FModErrors.ALLOC:
    "The output device is already in use and cannot be reused.",
    FModErrors.OUTPUT_FORMAT:
    "Soundcard does not support the features needed for this sound system (16bit stereo).",
    FModErrors.COOP_LEVEL:
    "Error setting cooperative level for hardware.",
    FModErrors.CREATE_BUFFER:
    'Error creating hardware sound buffer.',
    FModErrors.FILE_NOTFOUND:
    "File not found.",
    FModErrors.FILE_UNKFORMAT:
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
    "Tried to use an EAX command on a non-EAX enabled channel or output.",
    FModErrors.CHANNEL_ALLOC:
    "Failed to allocate a new channel.",
    FModErrors.RECORD:
    "Recording is not supported on this machine.",
    FModErrors.MEDIAPLAYER:
    "Required MediaPlayer codec is not installed.",
    FModErrors.CD_DEVICE:
    "An error occured trying to open the specified CD device."
}
