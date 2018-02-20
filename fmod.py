#!/usr/bin/python3
#-*- coding: utf-8 -*-
"""API for FMOD. (Direct clone from original source)"""
from ctypes import windll
from enum import IntEnum, auto
from typing import NamedTuple, List

__all__ = ('fmod', 'FModErrors', 'FSoundOutputTypes', 'FSoundMixerTypes',
           'FMusicTypes', 'FSoundDSPProperties', 'FSoundCaps', 'FSoundModes',
           'FSoundCDPlayModes', 'FSoundChannelSampleMode',
           'FSoundReverbProperties', 'FSoundReverbPropertyFlags',
           'FSoundReverbChannelProperties', 'FSoundReverbChannelFlags',
           'FSoundFXModes', 'FSoundSpeakerModes', 'FSoundInitModes',
           'FSoundStreamNetStatus', 'FSoundTagFieldType', 'FSoundStatusFlags',
           'FSoundTOCTag', 'fsound_get_error_string', 'fsound_get_error')

FMOD_VERSION = 3.74

fmod = windll.fmod


class FModErrors(IntEnum):
    # yapf: disable
    FMOD_ERR_NONE           = 0
    FMOD_ERR_BUSY           = auto()
    FMOD_ERR_UNINIT         = auto()
    FMOD_ERR_INIT           = auto()
    FMOD_ERR_ALLOC          = auto()
    FMOD_ERR_PLAY           = auto()
    FMOD_ERR_OUTPUT_FORMAT  = auto()
    FMOD_ERR_COOP_LEVEL     = auto()
    FMOD_ERR_CREATE_BUFFER  = auto()
    FMOD_ERR_FILE_NOTFOUND  = auto()
    FMOD_ERR_FILE_UNKFORMAT = auto()
    FMOD_ERR_FILE_BAD       = auto()
    FMOD_ERR_MEMORY         = auto()
    FMOD_ERR_VERSION        = auto()
    FMOD_ERR_INV_PARAM      = auto()
    FMOD_ERR_NO_EAX         = auto()
    FMOD_ERR_CHANNEL_ALLOC  = auto()
    FMOD_ERR_RECORD         = auto()
    FMOD_ERR_MEDIAPLAYER    = auto()
    FMOD_ERR_CD_DEVICE      = auto()
# yapf: enable


class FSoundOutputTypes(IntEnum):
    # yapf: disable
    FSOUND_OUTPUT_NOSOUND = 0
    FSOUND_OUTPUT_WINMM   = auto()
    FSOUND_OUTPUT_DSOUND  = auto()
    FSOUND_OUTPUT_A3D     = auto()
    FSOUND_OUTPUT_OSS     = auto()
    FSOUND_OUTPUT_ESD     = auto()
    FSOUND_OUTPUT_ALSA    = auto()
    FSOUND_OUTPUT_ASIO    = auto()
    FSOUND_OUTPUT_MAC     = auto()
    FSOUND_OUTPUT_NOSOUND_NOREALTIME = auto()
# yapf: enable


class FSoundMixerTypes(IntEnum):
    # yapf: disable
    FSOUND_MIXER_AUTODETECT         = 0
    FSOUND_MIXER_QUALITY_AUTODETECT = auto()
    FSOUND_MIXER_QUALITY_FPU        = auto()
# yapf: enable


class FMusicTypes(IntEnum):
    FMUSIC_TYPE_NON = 0
    FMUSIC_TYPE_MOD = auto()
    FMUSIC_TYPE_S3M = auto()
    FMUSIC_TYPE_XM = auto()
    FMUSIC_TYPE_IT = auto()
    FMUSIC_TYPE_MIDI = auto()
    FMUSIC_TYPE_FSB = auto()


class FSoundDSPProperties(IntEnum):
    # yapf: disable
    FSOUND_DSP_DEFAULTPRI_CLEARUNIT = 0
    FSOUND_DSP_DEFAULTPRI_SFXUNIT   = 100
    FSOUND_DSP_DEFAULTPRI_MUSICUNIT = 200
    FSOUND_DSP_DEFAULTPRI_USER      = 300
    FSOUND_DSP_DEFAULTPRI_FFTUNIT   = 900
    FSOUND_DSP_DEFUALTPRI_CLIPANDCOPYUNIT = 1000
# yapf: enable


class FSoundCaps(IntEnum):
    FSOUND_CAPS_HARDWARE = 0x01
    FSOUND_CAPS_EAX2 = 0x02
    FSOUND_CAPS_EAX3 = 0x10


class FSoundModes(IntEnum):
    # yapf: disable
    FSOUND_LOOP_OFF      = 0x1
    FSOUND_LOOP_NORMAL   = 0x2
    FSOUND_LOOP_BIDI     = 0x4
    FSOUND_8BITS         = 0x8
    FSOUND_16BITS        = 0x10
    FSOUND_MONO          = 0x20
    FSOUND_STEREO        = 0x40
    FSOUND_UNSIGNED      = 0x80
    FSOUND_SIGNED        = 0x100
    FSOUND_DELTA         = 0x200
    FSOUND_IT214         = 0x400
    FSOUND_IT215         = 0x800
    FSOUND_HW3D          = 0x1000
    FSOUND_2D            = 0x2000
    FSOUND_STREAMABLE    = 0x4000
    FSOUND_LOADMEMORY    = 0x8000
    FSOUND_LOADRAW       = 0x10000
    FSOUND_MPEGACCURATE  = 0x20000
    FSOUND_FORCEMONO     = 0x40000
    FSOUND_HW2D          = 0x80000
    FSOUND_ENABLEFX      = 0x100000
    FSOUND_MPEGHALFRATE  = 0x200000
    FSOUND_XADPCM        = 0x400000
    FSOUND_VAG           = 0x800000
    FSOUND_NONBLOCKING   = 0x1000000
    FSOUND_GCADPCM       = 0x2000000
    FSOUND_MULTICHANNEL  = 0x4000000
    FSOUND_USECORE0      = 0x8000000
    FSOUND_USECORE1      = 0x10000000
    FSOUND_LOADMEMORYIOP = 0x20000000
    FSOUND_STREAM_NET    = 0x80000000
    FSOUND_NORMAL        = FSOUND_16BITS | FSOUND_SIGNED | FSOUND_MONO
# yapf: enable


class FSoundCDPlayModes(IntEnum):
    FSOUND_CD_PLAYCONTINUOUS = 0
    FSOUND_CD_PLAYONCE = auto()
    FSOUND_CD_PLAYLOOPED = auto()
    FSOUND_CD_PLAYRANDOM = auto()


class FSoundChannelSampleMode(IntEnum):
    FSOUND_FREE = -1
    FSOUND_UNMANAGED = -2
    FSOUND_ALL = -3
    FSOUND_STEREOPAN = -1
    FSOUND_SYSTEMCHANNEL = -1000
    FSOUND_SYSTEMSAMPLE = -1000


class FSoundReverbProperties(NamedTuple):
    environment: int
    env_size: float
    env_diffusion: float
    room: int
    room_hf: int
    room_lf: int
    decay_time: float
    decay_hf_ratio: float
    decay_lf_ratio: float
    reflections: int
    reflections_delay: float
    reflections_pan: List[float]
    reverb: int
    reverb_delay: float
    reverb_pan: List[float]
    echo_time: float
    echo_depth: float
    modulation_time: float
    modulation_depth: float
    air_absorption_hf: float
    hf_reference: float
    lf_reference: float
    room_roll_off_factor: float
    diffusion: float
    density: float
    flags: int


class FSoundReverbPropertyFlags(IntEnum):
    FSOUND_REVERBFLAGS_DECAYTIMESCALE = 0x01
    FSOUND_REVERBFLAGS_REFLECTIONSSCALE = 0x02
    FSOUND_REVERBFLAGS_REFLECTIONDELAYSCALE = 0x04
    FSOUND_REVERBFLAGS_REVERBSCALE = 0x08
    FSOUND_REVERBFLAGS_REVERBDELAYSCALE = 0x10
    FSOUND_REVERBFLAGS_DECAYHFLIMIT = 0x20
    FSOUND_REVERBFLAGS_ECHOTIMESCALE = 0x40
    FSOUND_REVERBFLAGS_MODULATIONTIMESCALE = 0x80
    FSOUND_REVERB_FLAGS_CORE0 = 0x100
    FSOUND_REVERB_FLAGS_CORE1 = 0x200
    FSOUND_REVERBFLAGS_DEFAULT = FSOUND_REVERBFLAGS_DECAYTIMESCALE | FSOUND_REVERBFLAGS_REFLECTIONSSCALE | FSOUND_REVERBFLAGS_REVERBSCALE | FSOUND_REVERBFLAGS_REVERBDELAYSCALE | FSOUND_REVERBFLAGS_DECAYHFLIMIT | FSOUND_REVERB_FLAGS_CORE0 | FSOUND_REVERB_FLAGS_CORE1


class FSoundReverbChannelProperties(NamedTuple):
    direct: int
    direct_hf: int
    room: int
    room_hf: int
    obstruction: int
    obstruction_lf_ratio: float
    occlusion: int
    occlusion_lf_ratio: float
    occlusion_room_ratio: float
    occlusion_direct_ratio: float
    exclusion: int
    exclusion_lf_ratio: float
    outside_volume_hf: int
    doppler_factor: float
    rolloff_factor: float
    room_rolloff_factor: float
    air_absorption_factor: float
    flags: int


class FSoundReverbChannelFlags(IntEnum):
    FSOUND_REVERB_CHANNELFLAGS_DIRECTHFAUTO = 0x1
    FSOUND_REVERB_CHANNELFLAGS_ROOMAUTO = 0x2
    FSOUND_REVERB_CHANNELFLAGS_ROOMHFAUTO = 0x4
    FSOUND_REVERB_CHANNELFLAGS_DEFAULT = FSOUND_REVERB_CHANNELFLAGS_DIRECTHFAUTO | FSOUND_REVERB_CHANNELFLAGS_ROOMAUTO | FSOUND_REVERB_CHANNELFLAGS_ROOMHFAUTO


class FSoundFXModes(IntEnum):
    FSOUND_FX_CHORUS = 0
    FSOUND_FX_COMPRESSOR = auto()
    FSOUND_FX_DISTORTION = auto()
    FSOUND_FX_ECHO = auto()
    FSOUND_FX_FLANGER = auto()
    FSOUND_FX_GARGLE = auto()
    FSOUND_FX_I3DL2REVERB = auto()
    FSOUND_FX_PARAMEQ = auto()
    FSOUND_FX_WAVES_REVERB = auto()


class FSoundSpeakerModes(IntEnum):
    FSOUND_SPEAKERMODE_DOLBYDIGITAL = 0
    FSOUND_SPEAKERMODE_HEADPHONE = auto()
    FSOUND_SPEAKERMODE_MONO = auto()
    FSOUND_SPEAKERMODE_QUAD = auto()
    FSOUND_SPEAKERMODE_STEREO = auto()
    FSOUND_SPEAKERMODE_SURROUND = auto()
    FSOUND_SPEAKERMODE_DTS = auto()
    FSOUND_SPEAKERMODE_PROLOGIC2 = auto()


class FSoundInitModes(IntEnum):
    FSOUND_INIT_USEDEFAULTMIDISYNTH = 0x1
    FSOUND_INIT_GLOBALFOCUS = 0x2
    FSOUND_INIT_ENABLESYSTEMCHANNELFX = 0x4
    FSOUND_INIT_ACCURATEVULEVELS = 0x8
    FSOUND_INIT_PS2_DISABLECORE0REVERB = 0x10
    FSOUND_INIT_PS2_DISABLECORE1REVERB = 0x20
    FSOUND_INIT_PS2_SWAPDMACORES = 0x40
    FSOUND_INIT_DONTLATENCYADJUST = 0x80
    FSOUND_INIT_GX_INITLIBS = 0x100
    FSOUND_INIT_STREAM_FROM_MAIN_THREAD = 0x200


class FSoundStreamNetStatus(IntEnum):
    FSOUND_STREAM_NET_NOTCONNECTED = 0
    FSOUND_STREAM_NET_CONNECTING = auto()
    FSOUND_STREAM_NET_BUFFERING = auto()
    FSOUND_STREAM_NET_READY = auto()
    FSOUND_STREAM_NET_ERROR = auto()


class FSoundTagFieldType(IntEnum):
    FSOUND_TAGFIELD_VORBISCOMMENT = 0
    FSOUND_TAGFIELD_ID3V1 = auto()
    FSOUND_TAGFIELD_ID3V2 = auto()
    FSOUND_TAGFIELD_SHOUTCAST = auto()
    FSOUND_TAGFIELD_ICECAST = auto()
    FSOUND_TAGFIELD_ASF = auto()


class FSoundStatusFlags(IntEnum):
    FSOUND_PROTOCOL_SHOUTCAST = 0x1
    FSOUND_PROTOCOL_ICECAST = 0x2
    FSOUND_PROTOCOL_HTTP = 0x4
    FSOUND_FORMAT_MPEG = 0x10000
    FSOUND_FORMAT_OGGVORBIS = 0x20000


class FSoundTOCTag(NamedTuple):
    tag_name: List[int]
    num_tracks: int
    min: List[int]
    sec: List[int]
    frame: List[int]


e = FModErrors
FMOD_ERR_MESSAGES = {
    e.FMOD_ERR_NONE:
    "No errors",
    e.FMOD_ERR_BUSY:
    "Cannot call this command after FSOUND_Init. Call FSOUND_Close first.",
    e.FMOD_ERR_UNINIT:
    "Cannot call this command before FSOUND_Init.",
    e.FMOD_ERR_PLAY:
    "Cannot play the sound.",
    e.FMOD_ERR_INIT:
    "Error initializing output device.",
    e.FMOD_ERR_ALLOC:
    "The output device is already in use and cannot be reused.",
    e.FMOD_ERR_OUTPUT_FORMAT:
    "Soundcard does not support the features needed for this sound system (16bit stereo).",
    e.FMOD_ERR_COOP_LEVEL:
    "Error setting cooperative level for hardware.",
    e.FMOD_ERR_CREATE_BUFFER:
    'Error creating hardware sound buffer.',
    e.FMOD_ERR_FILE_NOTFOUND:
    "File not found.",
    e.FMOD_ERR_FILE_UNKFORMAT:
    "Unknown file format.",
    e.FMOD_ERR_FILE_BAD:
    "Error loading file.",
    e.FMOD_ERR_MEMORY:
    "Not enough memory.",
    e.FMOD_ERR_VERSION:
    "The version number of this file format is not supported.",
    e.FMOD_ERR_INV_PARAM:
    "An invalid parameter was passed to this function.",
    e.FMOD_ERR_NO_EAX:
    "Tried to use an EAX command on a non-EAX enabled channel or output.",
    e.FMOD_ERR_CHANNEL_ALLOC:
    "Failed to allocate a new channel.",
    e.FMOD_ERR_RECORD:
    "Recording is not supported on this machine.",
    e.FMOD_ERR_MEDIAPLAYER:
    "Required MediaPlayer codec is not installed.",
    e.FMOD_ERR_CD_DEVICE:
    "An error occured trying to open the specified CD device."
}


def fsound_get_error_string(errcode: int) -> str:
    msg = FMOD_ERR_MESSAGES.get(FModErrors(errcode))
    if not msg:
        msg = "Unknown error"
    return msg


def fsound_get_error() -> str:
    return fsound_get_error_string(fmod.FSOUND_GetError())
