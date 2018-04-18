#-*- coding: utf-8 -*-
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

if ARCH in ('x86_64', 'i386', 'x86') and OS == 'Windows':
    LIB = 'fmod.dll'
elif ARCH == 'x86' and OS == 'Linux':
    LIB = 'libfmod.so.10'
else:
    print(ARCH)
    LIB = None

if LIB is not None:
    fmod = ctypes.windll.LoadLibrary(os.path.join(LIBDIR, LIB))

    systemInit = fmod.FSOUND_Init
    systemInit.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_uint)
    systemInit.restype = ctypes.c_bool

    setOutput = fmod.FSOUND_SetOutput
    setOutput.argtypes = (ctypes.c_int)
    setOutput.restype = ctypes.c_bool

    setMasterVolume = fmod.FSOUND_SetSFXMasterVolume
    setMasterVolume.argtypes = (ctypes.c_int)
    setMasterVolume.restype = ctypes.c_bool

    getError = fmod.FSOUND_GetError
    getError.argtypes = ()
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
                          ctypes.c_char)
    playSound.restype = ctypes.c_int

    stopSound = fmod.FSOUND_StopSound
    stopSound.argtypes = (ctypes.c_int)
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
    systemClose.argtypes = ()
    systemClose.restype = ctypes.c_void_p

    enableFX = fmod.FSOUND_FX_Enable
    enableFX.argtypes = (ctypes.c_int, ctypes.c_uint)
    enableFX.restype = ctypes.c_int

    setEcho = fmod.FSOUND_FX_SetEcho
    setEcho.argtypes = (ctypes.c_int, ctypes.c_float, ctypes.c_float,
                        ctypes.c_float, ctypes.c_float, ctypes.c_int)
    setEcho.restype = ctypes.c_bool

    setPaused = fmod.FSOUND_SetPaused
    setPaused.argtypes = (ctypes.c_int, ctypes.c_bool)
    setPaused.restype = ctypes.c_bool

    disableFX = fmod.FSOUND_FX_Disable
    disableFX.argtypes = (ctypes.c_int)
    disableFX.restype = ctypes.c_bool
else:
    import random
    fmod = None
    maxsize = sys.maxsize

    systemInit = lambda freq, chan, flags: True
    setOutput = lambda output: True
    setMasterVolume = lambda vol: True
    getError = lambda: 0
    sampleLoad = lambda index, file, mode, offset, size: random.randint(32, maxsize - 1)
    setLoopPoints = lambda smp_ptr, start, end: True
    playSound = lambda chan, smp_ptr, dsp_ptr, is_paused: random.randint(32, maxsize - 1)
    stopSound = lambda chan: True
    setFrequency = lambda chan, freq: True
    setPan = lambda chan, pan: True
    setVolume = lambda chan, vol: True
    systemClose = lambda: None
    enableFX = lambda chan, fx_type: random.randint(32, maxsize - 1)
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


class FSoundChannelSampleMode(enum.IntEnum):
    """Misc. flags for the FMOD API."""

    FREE = -1
    UNMANAGED = -2
    ALL = -3
    STEREOPAN = -1
    SYSTEMCHANNEL = -1000
    SYSTEMSAMPLE = -1000


# yapf: enable

e = FModErrors
FMOD_ERR_MESSAGES = {
    e.NONE:
    "No errors",
    e.BUSY:
    "Cannot call this command after FSOUND_Init. Call FSOUND_Close first.",
    e.UNINIT:
    "Cannot call this command before FSOUND_Init.",
    e.PLAY:
    "Cannot play the sound.",
    e.INIT:
    "Error initializing output device.",
    e.ALLOC:
    "The output device is already in use and cannot be reused.",
    e.OUTPUT_FORMAT:
    "Soundcard does not support the features needed for this sound system (16bit stereo).",
    e.COOP_LEVEL:
    "Error setting cooperative level for hardware.",
    e.CREATE_BUFFER:
    'Error creating hardware sound buffer.',
    e.FILE_NOTFOUND:
    "File not found.",
    e.FILE_UNKFORMAT:
    "Unknown file format.",
    e.FILE_BAD:
    "Error loading file.",
    e.MEMORY:
    "Not enough memory.",
    e.VERSION:
    "The version number of this file format is not supported.",
    e.INV_PARAM:
    "An invalid parameter was passed to this function.",
    e.NO_EAX:
    "Tried to use an EAX command on a non-EAX enabled channel or output.",
    e.CHANNEL_ALLOC:
    "Failed to allocate a new channel.",
    e.RECORD:
    "Recording is not supported on this machine.",
    e.MEDIAPLAYER:
    "Required MediaPlayer codec is not installed.",
    e.CD_DEVICE:
    "An error occured trying to open the specified CD device."
}

del os, sys, typing
