# -*- coding: utf-8 -*-
"""Provides File IO for Sappy."""
import os
import typing
import array


class SampleHeader(typing.NamedTuple):
    """Data for an AGB sound sample."""

    is_looped: int = 0
    frequency: int = 0
    loop: int = 0
    size: int = 0


class DirectSound(typing.NamedTuple):
    sample_mode: int
    midi_key: int
    unused: int
    panning: int
    sample_ptr: int
    attack: int
    decay: int
    sustain: int
    release: int


class PSGInstrument(typing.NamedTuple):
    psg_channel: int
    midi_key: int
    time_len: int
    sweep: int
    flag: int
    attack: int
    decay: int
    sustain: int
    release: int


class SoundEngine(typing.NamedTuple):
    FREQUENCY_TABLE = {
        1: 5734,
        2: 7884,
        3: 10512,
        4: 13379,
        5: 15768,
        6: 18157,
        7: 21024,
        8: 26758,
        9: 31536,
        10: 36314,
        11: 40137,
        12: 42048
    }
    DAC_TABLE = {
        8: 9,
        9: 8,
        10: 7,
        11: 6
    }

    reverb: int
    reverb_enabled: bool
    polyphony: int
    volume_ind: int
    freq_ind: int
    dac_ind: int

    @property
    def volume(self):
        return self.volume_ind * 17

    @property
    def frequency(self):
        return self.FREQUENCY_TABLE[self.freq_ind]

    @property
    def dac(self):
        return self.DAC_TABLE[self.dac_ind]


class GBARom(object):
    """Base file object."""

    def __init__(self, path: str = None) -> None:
        """Init a GBA ROM file wrapper with basic IO functions.

        Parameters
        ----------
        path : int
            absolute file path to ROM

        Attributes
        ----------
        _file : io.IOWrapper
            base file object used for read/write operations.
        _path : str
            absolute file path to ROM
        _address : int
            address of read head

        """
        self._path = path
        self._file = open(self.path, 'rb', 8192)
        self._address = 0

    @property
    def path(self) -> str:
        """Return the file path."""
        return self._path

    @property
    def address(self) -> int:
        """Return the address of the read head."""
        return self._address

    @address.setter
    def address(self, address: int) -> None:
        if address is not None and 0 <= address < self.size:
            self._address = address
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

    def read(self, addr: int = None) -> int:
        """Read a byte from file.

        Args:
            addr: a valid address in the file at which to move the read head
                if None, defaults to the read head's current position

        Returns:
            an integer [0-255]

        """
        self.address = addr
        return int.from_bytes(self._file.read(1), 'little')


    def read_dword(self, addr: int = None) -> int:
        """Read a stream of int in little-endian format.

        Args:
            width: number of consective int to read
            addr: a valid address in the file at which to move the read head.
                if None, defaults to the read head's current positoin.

        Returns:
            An integer

        """
        self.address = addr
        return int.from_bytes(self._file.read(4), 'little')

    def read_string(self, length: int, addr: int = None) -> str:
        """Read a stream of int as a string from file.

        Args:
            len: number of consecutive int to read
            addr: a valid address in the file at which to move the read head.
                if None, defaults to the read ehad's current position.

        Returns:
            A string of the specified length

        """
        self.address = addr
        out = ''.join(map(chr, memoryview(self._file.read(length))))
        return out

    def read_gba_pointer(self, addr: int = None) -> int:
        """Read a stream of int as an AGB rom pointer.

        Args:
            addr: a valid address in the file at which to move the read head.
                If None, defaults to the read head's current position.

        Returns:
            An AGB rom pointer as an integer on success, otherwise -1

        """
        self.address = addr
        ptr = self.read_dword()
        return to_address(ptr)

    def read_sample(self, addr: int = None) -> SampleHeader:
        """Extract sample attributes."""
        UNUSED_BYTES = 3
        self.address = addr
        self.address += UNUSED_BYTES
        header = SampleHeader(
            is_looped=self.read(),
            frequency=self.read_dword(),
            loop=self.read_dword(),
            size=self.read_dword())

        return header

    def read_psg_instrument(self, address: int = None, is_wave: bool=True):
        """Extract a PSG instrument."""
        self.address = address
        if is_wave:
            data = [self.read() if i != 4 else self.read_dword() for i in range(9)]
        else:
            data = [self.read() for i in range(12)]
            data = data[:5] + data[8:]
        return PSGInstrument(*data)

    def read_directsound(self, address: int = None):
        """Extract a DirectSound instrument."""
        self.address = address
        data = [self.read() if i != 4 else self.read_dword() for i in range(9)]
        return DirectSound(*data)

    def get_song_table(self, track: int) -> None:
        """Extract the track table pointer."""
        DEFAULT_CODE_TABLE = array.array(
            'I',
            (0x1840_0B40, 0x0059_8883, 0x0089_18C9, 0x680A_1889, 0x1C10_6801))
        MT_CODE_TABLE = array.array(
            'I',
            (0x1840_0B40, 0x0051_8882, 0x0089_1889, 0x680A_18C9, 0x1C10_6801))
        ZM_CODE_TABLE = array.array(
            'I',
            (0x4008_2002, 0xD002_2800, 0x4282_6918, 0x1C20_D003, 0xF001_2100))
        GENERIC_CODE_TABLE = (DEFAULT_CODE_TABLE, ZM_CODE_TABLE, MT_CODE_TABLE)
        END_CODE = 0x4700_BC01
        SONG_PTR_OFFSET = 8
        END_CODE_OFFSET = 6
        CODE_TABLE_OFFSET = 5
        thumb_codes = array.array('I')
        self._file.seek(0)
        thumb_codes.fromfile(self._file, self.size // thumb_codes.itemsize)
        for code_ind in range(len(thumb_codes) - END_CODE_OFFSET):
            l_part = thumb_codes[code_ind:code_ind + CODE_TABLE_OFFSET]
            l_match = any(l_part == table for table in GENERIC_CODE_TABLE)
            r_match = thumb_codes[code_ind + END_CODE_OFFSET] == END_CODE
            if l_match and r_match:
                ptr = to_address(thumb_codes[code_ind + SONG_PTR_OFFSET])
                if self.read_gba_pointer(ptr + track * 8) > self.size:
                    code_ind -= 7
                    continue
                return ptr
        return -1

    def get_engine_offset(self):
        """Retrive the offset of the SoundDriverMode call."""
        OLD_SELECT = array.array('B',
            (0x00, 0xB5, 0x00, 0x04, 0x07, 0x4A, 0x08, 0x49,
             0x40, 0x0B, 0x40, 0x18, 0x83, 0x88, 0x59, 0x00,
             0xC9, 0x18, 0x89, 0x00, 0x89, 0x18, 0x0A, 0x68,
             0x01, 0x68, 0x10, 0x1C, 0x00, 0xF0,))
        NEW_SELECT = array.array('B',
            (0x00, 0xB5, 0x00, 0x04, 0x07, 0x4B, 0x08, 0x49,
             0x40, 0x0B, 0x40, 0x18, 0x82, 0x88, 0x51, 0x00,
             0x89, 0x18, 0x89, 0x00, 0xC9, 0x18, 0x0A, 0x68,
             0x01, 0x68, 0x10, 0x1C, 0x00, 0xF0,))
        MF_SELECT = array.array('B',
            (0x00, 0xB5, 0x00, 0x04, 0x07, 0x4B, 0x08, 0x49,
             0x40, 0x0B, 0x40, 0x18, 0x82, 0x88, 0x51, 0x00,
             0x89, 0x18, 0x89, 0x00, 0xC9, 0x18, 0x0A, 0x68,
             0x01, 0x68, 0x10, 0x1C, 0x01, 0xF0,))
        ZM_SELECT = array.array('B',
            (0x10, 0xB5, 0x00, 0x04, 0x00, 0x0C, 0x04, 0x1C,
             0x0C, 0x4B, 0x0D, 0x48, 0xE2, 0x00, 0x12, 0x18,
             0x91, 0x88, 0x48, 0x00, 0x40, 0x18, 0x80, 0x00,
             0xC0, 0x18, 0x03, 0x68, 0x12, 0x68))
        file = array.array('B')
        SEARCH_LEN = 30 // file.itemsize
        self._file.seek(0)
        file.fromfile(self._file, self.size // file.itemsize)
        for byte_ind in range(len(file) - SEARCH_LEN):
            match = any([t == file[byte_ind:byte_ind+SEARCH_LEN] for t in (OLD_SELECT, NEW_SELECT, MF_SELECT, ZM_SELECT)])
            if match:
                return byte_ind
        return -1


    def validate_engine(self, base_address, *offsets):
        """Check if the retrieved engine has valid parameters."""
        dwords = array.array('I')
        self._file.seek(0)
        dwords.fromfile(self._file, self.size // dwords.itemsize)
        for offset in offsets:
            address = (base_address + offset) // 4 + 1
            engine, p_table = dwords[address], dwords[address + 30] & 0x3FFFFFF
            props = parse_mixer(engine)
            if not check_mixer(props) or p_table > self.size:
                continue
            return props

    def get_sound_engine(self) -> SoundEngine:
        offset = self.get_engine_offset()
        if offset == -1:
            return
        out = self.validate_engine(offset, -32, -16, -81)
        return out



def open_file(path: str) -> GBARom:
    """Open an existing file with read/write access in binary mode."""
    return GBARom(path)


def to_address(pointer: int) -> int:
    """Convert an AGB rom pointer to an address."""
    if pointer < 0x8000000 or pointer > 0x9FFFFFF:
        return -1
    return pointer - 0x8000000


def parse_mixer(mixer_data: int) -> SoundEngine:
    return SoundEngine(
        reverb=mixer_data & 0x0000_007F,
        reverb_enabled=mixer_data & 0b1000_0000 == 0x80,
        polyphony=(mixer_data & 0x0000_0F00) >> 8,
        volume_ind=(mixer_data & 0x0000_F000) >> 12,
        freq_ind=(mixer_data & 0x000F_0000) >> 16,
        dac_ind=(mixer_data & 0x00F0_0000) >> 20,
    )


def check_mixer(mixer: SoundEngine):
    reverb_check = 0 <= mixer.reverb <= 127
    polyphony_check = 1 <= mixer.polyphony <= 12
    volume_check = 1 <= mixer.volume_ind <= 15
    frequency_check = 1 <= mixer.freq_ind <= 12
    dac_check = 8 <= mixer.dac_ind <= 11
    return reverb_check == polyphony_check == volume_check == frequency_check == dac_check
