#-*- coding: utf-8 -*-
"""API for FMOD. (Direct clone from original source)"""
import ctypes
from ctypes import POINTER, Structure, c_bool, c_float, c_int, c_uint, windll
from enum import IntEnum, auto
from typing import List, NamedTuple
import sys
import os

__all__ = ('FModErrors', 'FSoundModes', 'FSoundChannelSampleMode', 'get_err',
           'get_err_str', 'systemInit', 'setVolume', 'getError', 'sampleLoad',
           'setLoopPoints', 'playSound', 'stopSound', 'setPan', 'setVolume',
           'setMasterVolume', 'setFrequency', 'systemClose', 'setOutput',
           'enableFX', 'setEcho', 'setPaused', 'disableFX')
# yapf: disable

FMOD_VERSION = 3.75

LIBDIR = os.path.join(sys.path[0], 'lib')
print(LIBDIR)
fmod            = windll.LoadLibrary(LIBDIR + '\\fmod.dll')
systemInit      = fmod.FSOUND_Init
setOutput       = fmod.FSOUND_SetOutput
setMasterVolume = fmod.FSOUND_SetSFXMasterVolume
getError        = fmod.FSOUND_GetError
sampleLoad      = fmod.FSOUND_Sample_Load
setLoopPoints   = fmod.FSOUND_Sample_SetLoopPoints
playSound       = fmod.FSOUND_PlaySoundEx
stopSound       = fmod.FSOUND_StopSound
setFrequency    = fmod.FSOUND_SetFrequency
setPan          = fmod.FSOUND_SetPan
setVolume       = fmod.FSOUND_SetVolume
systemClose     = fmod.FSOUND_Close
enableFX        = fmod.FSOUND_FX_Enable
enableFX.argtypes = (c_int, c_uint)
setEcho         = fmod.FSOUND_FX_SetEcho
setPaused       = fmod.FSOUND_SetPaused
disableFX       = fmod.FSOUND_FX_Disable

class FModErrors(IntEnum):
    NONE           = 0
    BUSY           = 1
    UNINIT         = 2
    INIT           = 3
    ALLOC          = 4
    PLAY           = 5
    OUTPUT_FORMAT  = 6
    COOP_LEVEL     = 7
    CREATE_BUFFER  = 8
    FILE_NOTFOUND  = 9
    FILE_UNKFORMAT = 10
    FILE_BAD       = 11
    MEMORY         = 12
    VERSION        = 13
    INV_PARAM      = 14
    NO_EAX         = 15
    CHANNEL_ALLOC  = 16
    RECORD         = 17
    MEDIAPLAYER    = 18
    CD_DEVICE      = 19


class FSoundModes(IntEnum):
    LOOP_OFF      = 0x1
    LOOP_NORMAL   = 0x2
    LOOP_BIDI     = 0x4
    _8BITS        = 0x8
    _16BITS       = 0x10
    MONO          = 0x20
    STEREO        = 0x40
    UNSIGNED      = 0x80
    SIGNED        = 0x100
    DELTA         = 0x200
    IT214         = 0x400
    IT215         = 0x800
    HW3D          = 0x1000
    _2D           = 0x2000
    STREAMABLE    = 0x4000
    LOADMEMORY    = 0x8000
    LOADRAW       = 0x10000
    MPEGACCURATE  = 0x20000
    FORCEMONO     = 0x40000
    HW2D          = 0x80000
    ENABLEFX      = 0x100000
    MPEGHALFRATE  = 0x200000
    XADPCM        = 0x400000
    VAG           = 0x800000
    NONBLOCKING   = 0x1000000
    GCADPCM       = 0x2000000
    MULTICHANNEL  = 0x4000000
    USECORE0      = 0x8000000
    USECORE1      = 0x10000000
    LOADMEMORYIOP = 0x20000000
    STREAM_NET    = 0x80000000
    NORMAL        = _16BITS | SIGNED | MONO


class FSoundChannelSampleMode(IntEnum):
    FREE          = -1
    UNMANAGED     = -2
    ALL           = -3
    STEREOPAN     = -1
    SYSTEMCHANNEL = -1000
    SYSTEMSAMPLE  = -1000


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


def get_err(errcode: int) -> str:
    msg = FMOD_ERR_MESSAGES.get(FModErrors(errcode))
    if not msg:
        msg = "Unknown error"
    return msg


def get_err_str() -> str:
    return get_err(fmod.FSOUND_GetError())
