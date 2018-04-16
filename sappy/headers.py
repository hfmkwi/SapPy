#-*- coding: utf-8 -*-
"""Player types."""
import typing

import sappy.fileio as fileio


class DirectHeader(typing.NamedTuple):
    """Data for a DirectSound instrument."""

    # yapf: disable
    b0:       int = int()
    b1:       int = int()
    smp_head: int = int()
    attack:   int = int()
    hold:     int = int()
    is_sustain:  int = int()
    release:  int = int()
    # yapf: enable


class DrumKitHeader(typing.NamedTuple):
    """Data for a Drumkit instrument."""

    # yapf: disable
    b0:      int = int()
    b1:      int = int()
    dct_tbl: int = int()
    b6:      int = int()
    b7:      int = int()
    b8:      int = int()
    b9:      int = int()
    # yapf: enable


class InstrumentHeader(typing.NamedTuple):
    """Data for a standard instrument."""

    # yapf: disable
    channel:    int = int()
    drum_pitch: int = int()
    # yapf: enable


class InvalidHeader(typing.NamedTuple):
    """Data for an invalid data."""

    b0: int = int()
    b1: int = int()
    b2: int = int()
    b3: int = int()
    b4: int = int()
    b5: int = int()
    b6: int = int()
    b7: int = int()
    b8: int = int()
    b9: int = int()


class MasterTableEntry(typing.NamedTuple):
    """Song entry as read from ROM."""

    # yapf: disable
    song: int = int()
    pri1: int = int()
    pri2: int = int()
    # yapf: enable


class MultiHeader(typing.NamedTuple):
    """Data for MultiSample instrument."""

    # yapf: disable
    b0:      int = int()
    b1:      int = int()
    dct_tbl: int = int()
    kmap: int = int()
    # yapf: enable


class NoiseHeader(typing.NamedTuple):
    """Data for simulated AGB noise."""

    # yapf: disable
    b0:      int = int()
    b1:      int = int()
    b2:      int = int()
    b3:      int = int()
    b4:      int = int()
    b5:      int = int()
    attack:  int = int()
    decay:   int = int()
    is_sustain: int = int()
    release: int = int()
    # yapf: enable


class SampleHeader(typing.NamedTuple):
    """Data for an AGB sound sample."""

    # yapf: disable
    flags:     int = int()
    b4:        int = int()
    fine_tune: int = int()
    frequency:      int = int()
    loop:      int = int()
    size:      int = int()
    # yapf: enable


class SongHeader(typing.NamedTuple):
    """Data for an AGB song."""

    # yapf: disable
    tracks:    int = int()
    blks:      int = int()
    pri:       int = int()
    reverb:    int = int()
    inst_bank: int = int()
    # yapf: enable


class SquareOneHeader(typing.NamedTuple):
    """Data for a Square1 instrument."""

    # yapf: disable
    raw1:       int = int()
    raw2:       int = int()
    duty_cycle: int = int()
    b3:         int = int()
    b4:         int = int()
    b5:         int = int()
    attack:     int = int()
    decay:      int = int()
    is_sustain:    int = int()
    release:    int = int()
    # yapf: enable


class SquareTwoHeader(typing.NamedTuple):
    """Data for a Square2 instrument."""

    # yapf: disable
    b0:         int = int()
    b1:         int = int()
    duty_cycle: int = int()
    b3:         int = int()
    b4:         int = int()
    b5:         int = int()
    attack:     int = int()
    decay:      int = int()
    is_sustain:    int = int()
    release:    int = int()
    # yapf: enable


class WaveHeader(typing.NamedTuple):
    """Data for a Wave instrument."""

    # yapf: disable
    b0:      int = int()
    b1:      int = int()
    sample:  int = int()
    attack:  int = int()
    decay:   int = int()
    is_sustain: int = int()
    release: int = int()
    # yapf: enable


def rd_dct_head(file_id: int, addr: int = None) -> DirectHeader:
    """Read int from a specified file into a Direct header."""
    w_file = fileio.VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = DirectHeader(
        b0       = w_file.rd_byte(),
        b1       = w_file.rd_byte(),
        smp_head = w_file.rd_ltendian(4),
        attack   = w_file.rd_byte(),
        hold     = w_file.rd_byte(),
        is_sustain  = w_file.rd_byte(),
        release  = w_file.rd_byte()
    )
    # yapf: enable
    return header


def rd_drmkit_head(file_id: int, addr: int = None) -> DrumKitHeader:
    """Read int from a specified file into a DrumKit header."""
    w_file = fileio.VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = DrumKitHeader(
        b0      = w_file.rd_byte(),
        b1      = w_file.rd_byte(),
        dct_tbl = w_file.rd_ltendian(4),
        b6      = w_file.rd_byte(),
        b7      = w_file.rd_byte(),
        b8      = w_file.rd_byte(),
        b9      = w_file.rd_byte()
    )
    # yapf: enable
    return header


def rd_inst_head(file_id: int, addr: int = None) -> InstrumentHeader:
    """Read int from a specified file into a Instrument header."""
    w_file = fileio.VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = InstrumentHeader(
        channel    = w_file.rd_byte(),
        drum_pitch = w_file.rd_byte()
    )
    # yapf: enable
    return header


def rd_inv_head(file_id: int, addr: int = None) -> InvalidHeader:
    """Read int from a specified file into a Invalid header."""
    w_file = fileio.VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = InvalidHeader(
        b0 = w_file.rd_byte(),
        b1 = w_file.rd_byte(),
        b2 = w_file.rd_byte(),
        b3 = w_file.rd_byte(),
        b4 = w_file.rd_byte(),
        b5 = w_file.rd_byte(),
        b6 = w_file.rd_byte(),
        b7 = w_file.rd_byte(),
        b8 = w_file.rd_byte(),
        b9 = w_file.rd_byte()
    )
    # yapf: enable
    return header


def rd_nse_head(file_id: int, addr: int = None) -> NoiseHeader:
    """Read int from a specified file into a Noise instrument header."""
    w_file = fileio.VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = NoiseHeader(
        b0      = w_file.rd_byte(),
        b1      = w_file.rd_byte(),
        b2      = w_file.rd_byte(),
        b3      = w_file.rd_byte(),
        b4      = w_file.rd_byte(),
        b5      = w_file.rd_byte(),
        attack  = w_file.rd_byte(),
        decay   = w_file.rd_byte(),
        is_sustain = w_file.rd_byte(),
        release = w_file.rd_byte()
    )
    # yapf: enable
    return header


def rd_mul_head(file_id: int, addr: int = None) -> MultiHeader:
    """Read int from a specified file into a Multi-sample instrument header."""
    w_file = fileio.VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = MultiHeader(
        b0      = w_file.rd_byte(),
        b1      = w_file.rd_byte(),
        dct_tbl = w_file.rd_ltendian(4),
        kmap    = w_file.rd_ltendian(4)
    )
    # yapf: enable
    return header


def rd_smp_head(file_id: int, addr: int = None) -> SampleHeader:
    """Read int from a specified file into a Sample header."""
    w_file = fileio.VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = SampleHeader(
        flags     = w_file.rd_ltendian(4),
        b4        = w_file.rd_byte(),
        fine_tune = w_file.rd_byte(),
        frequency      = w_file.rd_ltendian(2),
        loop      = w_file.rd_ltendian(4),
        size      = w_file.rd_ltendian(4)
    )
    # yapf: enable
    return header


def rd_sng_head(file_id: int, addr: int = None) -> SongHeader:
    """Read int from a specified file into a Song header."""
    w_file = fileio.VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = SongHeader(
        tracks    = w_file.rd_byte(),
        blks      = w_file.rd_byte(),
        pri       = w_file.rd_byte(),
        reverb    = w_file.rd_byte(),
        inst_bank = w_file.rd_ltendian(4)
    )
    # yapf: enable
    return header


def rd_sq1_head(file_id: int, addr: int = None) -> SquareOneHeader:
    """Read int from a specified file into a Square1 instrument header."""
    w_file = fileio.VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = SquareOneHeader(
        raw1       = w_file.rd_byte(),
        raw2       = w_file.rd_byte(),
        duty_cycle = w_file.rd_byte(),
        b3         = w_file.rd_byte(),
        b4         = w_file.rd_byte(),
        b5         = w_file.rd_byte(),
        attack     = w_file.rd_byte(),
        decay      = w_file.rd_byte(),
        is_sustain    = w_file.rd_byte(),
        release    = w_file.rd_byte()
    )
    # yapf: enable
    return header


def rd_sq2_head(file_id: int, addr: int = None) -> SquareTwoHeader:
    """Read bytes from a specified file into a Square2 instrument header."""
    w_file = fileio.VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = SquareTwoHeader(
        b0         = w_file.rd_byte(),
        b1         = w_file.rd_byte(),
        duty_cycle = w_file.rd_byte(),
        b3         = w_file.rd_byte(),
        b4         = w_file.rd_byte(),
        b5         = w_file.rd_byte(),
        attack     = w_file.rd_byte(),
        decay      = w_file.rd_byte(),
        is_sustain    = w_file.rd_byte(),
        release    = w_file.rd_byte()
    )
    # yapf: enable
    return header


def rd_wav_head(file_id: int, addr: int = None) -> WaveHeader:
    """Read bytes from a specified file into a Wave instrument header."""
    w_file = fileio.VirtualFile.from_id(file_id)
    w_file.rd_addr = addr
    # yapf: disable
    header = WaveHeader(
        b0      = w_file.rd_byte(),
        b1      = w_file.rd_byte(),
        sample  = w_file.rd_ltendian(4),
        attack  = w_file.rd_byte(),
        decay   = w_file.rd_byte(),
        is_sustain = w_file.rd_byte(),
        release = w_file.rd_byte()
    )
    # yapf: enable
    return header
