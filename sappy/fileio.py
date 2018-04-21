#-*- coding: utf-8 -*-
"""Provides File IO for Sappy."""
import os
import struct
import typing
import array


class DirectHeader(typing.NamedTuple):
    """Data for a DirectSound instrument."""

    b0: int = 0
    b1: int = 0
    smp_head: int = 0
    attack: int = 0
    hold: int = 0
    is_sustain: int = 0
    release: int = 0


class DrumKitHeader(typing.NamedTuple):
    """Data for a Drumkit instrument."""

    b0: int = 0
    b1: int = 0
    dct_tbl: int = 0
    b6: int = 0
    b7: int = 0
    b8: int = 0
    b9: int = 0


class InstrumentHeader(typing.NamedTuple):
    """Data for a standard instrument."""

    channel: int = 0
    drum_pitch: int = 0


class InvalidHeader(typing.NamedTuple):
    """Data for an invalid data."""

    b0: int = 0
    b1: int = 0
    b2: int = 0
    b3: int = 0
    b4: int = 0
    b5: int = 0
    b6: int = 0
    b7: int = 0
    b8: int = 0
    b9: int = 0


class MasterTableEntry(typing.NamedTuple):
    """Song entry as read from ROM."""

    song: int = 0
    pri1: int = 0
    pri2: int = 0


class MultiHeader(typing.NamedTuple):
    """Data for MultiSample instrument."""

    b0: int = 0
    b1: int = 0
    dct_tbl: int = 0
    kmap: int = 0


class NoiseHeader(typing.NamedTuple):
    """Data for simulated AGB noise."""

    b0: int = 0
    b1: int = 0
    b2: int = 0
    b3: int = 0
    b4: int = 0
    b5: int = 0
    attack: int = 0
    decay: int = 0
    is_sustain: int = 0
    release: int = 0


class SampleHeader(typing.NamedTuple):
    """Data for an AGB sound sample."""

    flags: int = 0
    b4: int = 0
    fine_tune: int = 0
    frequency: int = 0
    loop: int = 0
    size: int = 0


class SongHeader(typing.NamedTuple):
    """Data for an AGB song."""

    tracks: int = 0
    blks: int = 0
    pri: int = 0
    reverb: int = 0
    inst_bank: int = 0


class SquareOneHeader(typing.NamedTuple):
    """Data for a Square1 instrument."""

    raw1: int = 0
    raw2: int = 0
    duty_cycle: int = 0
    b3: int = 0
    b4: int = 0
    b5: int = 0
    attack: int = 0
    decay: int = 0
    is_sustain: int = 0
    release: int = 0


class SquareTwoHeader(typing.NamedTuple):
    """Data for a Square2 instrument."""

    b0: int = 0
    b1: int = 0
    duty_cycle: int = 0
    b3: int = 0
    b4: int = 0
    b5: int = 0
    attack: int = 0
    decay: int = 0
    is_sustain: int = 0
    release: int = 0


class WaveHeader(typing.NamedTuple):
    """Data for a Wave instrument."""

    b0: int = 0
    b1: int = 0
    sample: int = 0
    attack: int = 0
    decay: int = 0
    is_sustain: int = 0
    release: int = 0


class VirtualFile(object):
    """Base file object."""

    def __init__(self, path: str = None) -> None:
        """Init a file object with basic IO functions.

        Parameters
        ----------
        path
            absolute file path to an existing file

        Attributes
        ----------
        file
            root file object used for read/write operations.
        path
            file path of the file intended for access.
        address
            offset of the read head
        wr_addr
            offset of the write head

        """
        self._path = path
        self._file = open(self.path, 'rb+', 8192)
        self._wr_addr = self._address = 0

    def __enter__(self):
        """Create a temporary VirtualFile."""
        self.address = 0
        self._file = open(self.path, 'rb+', 8192)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Destroy the temporary VirtualFile."""
        self.close()

    @property
    def path(self) -> str:
        """Return the file path."""
        return self._path

    @property
    def address(self) -> int:
        """Return the address of the read head."""
        return self._address

    @address.setter
    def address(self, addr: int) -> None:
        if addr is not None:
            self._address = addr
            self._file.seek(self._address)

    @property
    def size(self):
        """Return size of the file in bytes."""
        return os.path.getsize(self.path)

    def close(self) -> None:
        """Close the current file.

        Args:
            id: a valid file ID

        """
        self._file.close()
        del self

    def wr_str(self, data: str, addr: int = None) -> None:
        """Write a string as int to file.

        Args:
            data: data to write to file
            addr: address to move the write head to
                if None, defaults to the write head's current position
        """
        self.wr_addr = addr
        data = map(ord, data)
        for char in data:
            self._file.write(bytes([char]))

    def rd_byte(self, addr: int = None) -> int:
        """Read a byte from file.

        Args:
            addr: a valid address in the file at which to move the read head
                if None, defaults to the read head's current position

        Returns:
            an integer [0-255]

        """
        self.address = addr
        return int.from_bytes(self._file.read(1), 'little')

    def rd_bgendian(self, width: int, addr: int = None) -> int:
        """Read a stream of int in big-endian format.

        Args:
            width: number of consecutive int to read
            addr: a valid address in the file at which to move the read head.
                if None, defaults to the read head's current position.

        Returns:
            An integer

        """
        self.address = addr
        return int.from_bytes(self._file.read(width), 'big')


    def rd_ltendian(self, width: int, addr: int = None) -> int:
        """Read a stream of int in little-endian format.

        Args:
            width: number of consective int to read
            addr: a valid address in the file at which to move the read head.
                if None, defaults to the read head's current positoin.

        Returns:
            An integer

        """
        self.address = addr
        return int.from_bytes(self._file.read(width), 'little')

    def rd_str(self, length: int, addr: int = None) -> str:
        """Read a stream of int as a string from file.

        Args:
            len: number of consecutive int to read
            addr: a valid address in the file at which to move the read head.
                if None, defaults to the read ehad's current position.

        Returns:
            A string of the specified length

        """
        self.address = addr
        return self._file.read(length).decode()

    def rd_gba_ptr(self, addr: int = None) -> int:
        """Read a stream of int as an AGB rom pointer.

        Args:
            addr: a valid address in the file at which to move the read head.
                If None, defaults to the read head's current position.

        Returns:
            An AGB rom pointer as an integer on success, otherwise -1

        """
        self.address = addr
        ptr = self.rd_ltendian(4)
        return gba_ptr_to_addr(ptr)

    def rd_dct_head(self, addr: int = None) -> DirectHeader:
        """Read bytes from a specified file into a Direct header."""
        self.address = addr
        header = DirectHeader(
            b0=self.rd_byte(),
            b1=self.rd_byte(),
            smp_head=self.rd_ltendian(4),
            attack=self.rd_byte(),
            hold=self.rd_byte(),
            is_sustain=self.rd_byte(),
            release=self.rd_byte())

        return header

    def rd_drmkit_head(self, addr: int = None) -> DrumKitHeader:
        """Read bytes from a specified file into a DrumKit header."""
        self.address = addr
        header = DrumKitHeader(
            b0=self.rd_byte(),
            b1=self.rd_byte(),
            dct_tbl=self.rd_ltendian(4),
            b6=self.rd_byte(),
            b7=self.rd_byte(),
            b8=self.rd_byte(),
            b9=self.rd_byte())

        return header

    def rd_inst_head(self, addr: int = None) -> InstrumentHeader:
        """Read bytes from a specified file into a Instrument header."""
        self.address = addr
        header = InstrumentHeader(
            channel=self.rd_byte(), drum_pitch=self.rd_byte())

        return header

    def rd_inv_head(self, addr: int = None) -> InvalidHeader:
        """Read bytes from a specified file into a Invalid header."""
        self.address = addr
        header = InvalidHeader(
            b0=self.rd_byte(),
            b1=self.rd_byte(),
            b2=self.rd_byte(),
            b3=self.rd_byte(),
            b4=self.rd_byte(),
            b5=self.rd_byte(),
            b6=self.rd_byte(),
            b7=self.rd_byte(),
            b8=self.rd_byte(),
            b9=self.rd_byte())

        return header

    def rd_nse_head(self, addr: int = None) -> NoiseHeader:
        """Read bytes from a specified file into a Noise instrument header."""
        self.address = addr
        header = NoiseHeader(
            b0=self.rd_byte(),
            b1=self.rd_byte(),
            b2=self.rd_byte(),
            b3=self.rd_byte(),
            b4=self.rd_byte(),
            b5=self.rd_byte(),
            attack=self.rd_byte(),
            decay=self.rd_byte(),
            is_sustain=self.rd_byte(),
            release=self.rd_byte())

        return header

    def rd_mul_head(self, addr: int = None) -> MultiHeader:
        """Read bytes from a specified file into a Multi-sample instrument header."""
        self.address = addr
        header = MultiHeader(
            b0=self.rd_byte(),
            b1=self.rd_byte(),
            dct_tbl=self.rd_ltendian(4),
            kmap=self.rd_ltendian(4))

        return header

    def rd_smp_head(self, addr: int = None) -> SampleHeader:
        """Read bytes from a specified file into a Sample header."""
        self.address = addr
        header = SampleHeader(
            flags=self.rd_ltendian(4),
            b4=self.rd_byte(),
            fine_tune=self.rd_byte(),
            frequency=self.rd_ltendian(2),
            loop=self.rd_ltendian(4),
            size=self.rd_ltendian(4))

        return header

    def rd_sng_head(self, addr: int = None) -> SongHeader:
        """Read bytes from a specified file into a Song header."""
        self.address = addr
        header = SongHeader(
            tracks=self.rd_byte(),
            blks=self.rd_byte(),
            pri=self.rd_byte(),
            reverb=self.rd_byte(),
            inst_bank=self.rd_ltendian(4))

        return header

    def rd_sq1_head(self, addr: int = None) -> SquareOneHeader:
        """Read bytes from a specified file into a Square1 instrument header."""

        self.address = addr
        header = SquareOneHeader(
            raw1=self.rd_byte(),
            raw2=self.rd_byte(),
            duty_cycle=self.rd_byte(),
            b3=self.rd_byte(),
            b4=self.rd_byte(),
            b5=self.rd_byte(),
            attack=self.rd_byte(),
            decay=self.rd_byte(),
            is_sustain=self.rd_byte(),
            release=self.rd_byte())
        return header

    def rd_sq2_head(self, addr: int = None) -> SquareTwoHeader:
        """Read bytes from a specified file into a Square2 instrument header."""
        self.address = addr
        header = SquareTwoHeader(
            b0=self.rd_byte(),
            b1=self.rd_byte(),
            duty_cycle=self.rd_byte(),
            b3=self.rd_byte(),
            b4=self.rd_byte(),
            b5=self.rd_byte(),
            attack=self.rd_byte(),
            decay=self.rd_byte(),
            is_sustain=self.rd_byte(),
            release=self.rd_byte())

        return header

    def rd_wav_head(self, addr: int = None) -> WaveHeader:
        """Read bytes from a specified file into a Wave instrument header."""
        self.address = addr
        header = WaveHeader(
            b0=self.rd_byte(),
            b1=self.rd_byte(),
            sample=self.rd_ltendian(4),
            attack=self.rd_byte(),
            decay=self.rd_byte(),
            is_sustain=self.rd_byte(),
            release=self.rd_byte())

        return header

    def get_song_table_ptr(self) -> None:
        search_bytes = (0x1840_0B40, 0x0059_8883, 0x0089_18C9, 0x680A_1889, 0x1C10_6801, None, 0x4700_BC01)
        match = 0
        header = array.array('I')
        while True:
            try:
                header.fromfile(self._file, 7)
            except EOFError:
                return None
            while len(header) > 0:
                instruction = header.pop(0)
                if instruction == search_bytes[match] or search_bytes[match] == None:
                    match += 1
                else:
                    match = 0
            if match < 7:
                continue
            self._file.seek(self._file.tell() + 4)
            ptr = int.from_bytes(self._file.read(4), 'little')
            return gba_ptr_to_addr(ptr)


def open_file(file_path: str) -> VirtualFile:
    """Open an existing file with read/write access in binary mode."""
    return VirtualFile(file_path)


def open_new_file(file_path: str) -> VirtualFile:
    """Create a new file and open with read/write access in binary mode."""
    with open(file_path, 'wb+') as file:
        file.write(bytes(1))
    return open_file(file_path)


def gba_ptr_to_addr(ptr: int) -> int:
    """Convert an AGB rom pointer to an address."""
    if ptr < 0x8000000 or ptr > 0x9FFFFFF:
        return -1
    return ptr - 0x8000000
