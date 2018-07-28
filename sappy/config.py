# -*- coding: utf-8 -*-
"""Configuration file for the player.

Attributes
----------
GBA_BASE_FRAME_RATE : int
    GBA hardware frame-rate.
TICKS_PER_SECOND : int
    Default M4A engine tempo.
BASE_FREQUENCY : int
    Center frequency for all samples.
SEMITONE_RATIO : float
    Distance of one tone in 12-tone equal temperament.
PSG_WAVEFORM_FREQUENCY : int
    Center frequency for PSG Waveform samples.
PSG_WAVEFORM_VOLUME : float
    Control over PSG Waveform amplitude during sample parsing.
PSG_WAVEFORM_SIZE : int
    Number of 4-bit samples per PSG Waveform
PSG_SQUARE_FREQUENCY : int
    Center frequency for PSG Square1/Square2 samples.
PSG_SQUARE_VOLUME : float
    Control over PSG Square1/Square2 amplitude during sample parsing.
PSG_SQUARE_SIZE : int
    Number of 8-bit samples per square wave.
PSG_NOISE_VOLUME : float
    Control over PSG Noise period amplitude during sample parsing.
PSG_NOISE_NORMAL_SIZE : int
    Number of PSG Noise samples for period 0.
PSG_NOISE_TONE_SIZE : int
    Number of PSG Noise samples for period 1.
PLAYBACK_FRAME_RATE : int
    Emulator frame-rate (default is `GBA_BASE_FRAME_RATE`)
PLAYBACK_SPEED : int
    Scalable ratio of `GBA_BASE_FRAME_RATE` to `PLAYBACK_FRAME_RATE` (default
    is 1).
MAX_FMOD_TRACKS : int
    Set maximum FMOD software channels.
IGNORE_GOTO : bool
    Prevent GOTO commands from executing.
CULL_FRAME_DELAY : int
    Frame delay of `cull_notes`

"""
GBA_BASE_FRAME_RATE = 59.97
TICKS_PER_SECOND = 75

BASE_FREQUENCY = 7040
SEMITONE_RATIO = 2 ** (1 / 12)

PSG_WAVEFORM_FREQUENCY = 8372 * 2
PSG_WAVEFORM_VOLUME = .5  # 0 <= x <= 1
PSG_WAVEFORM_SIZE = 32

PSG_SQUARE_FREQUENCY = 7040
PSG_SQUARE_VOLUME = .2  # 0 <= x <= 1
PSG_SQUARE_SIZE = 8

PSG_NOISE_VOLUME = 0.25  # 0 <= x <= 1
PSG_NOISE_NORMAL_SIZE = 32767 // 2
PSG_NOISE_TONE_SIZE = 127

SHOW_PROCESSOR_EXECUTION = True
SHOW_FMOD_EXECUTION = True

PLAYBACK_FRAME_RATE = GBA_BASE_FRAME_RATE
PLAYBACK_SPEED = GBA_BASE_FRAME_RATE / PLAYBACK_FRAME_RATE * 1
MAX_FMOD_TRACKS = 256

IGNORE_GOTO = False
CULL_FRAME_DELAY = 240
