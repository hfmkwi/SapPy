# -*- coding: utf-8 -*-
"""Provides File IO for Sappy.

Attributes
----------
M4A_MAIN : tuple of int
    THUMB opcodes for M4A_Main call.
AMT_MAIN : tuple of int
    THUMB opcodes for game AMT M4A_Main call.
BMX_MAIN : tuple of int
    THUMB opcodes for game BMX M4A_Main call.
M4A_OLD : tuple of int
    THUMB opcodes preceding SDM call.
LOGGER : logging.Logger
    Module-level logger.

"""
import os
from array import array
from logging import DEBUG, getLogger
from typing import Optional, Union

from .config import PSG_WAVEFORM_VOLUME
from .exceptions import InvalidVoice, InvalidArgument
from .m4a import (M4ADirectSound, M4ADirectSoundSample, M4ANoise, M4ASample,
                  M4ASquare1, M4ASquare2, M4AWaveform, M4AWaveformSample,
                  SoundDriverMode, M4ADrum, M4AVoice, M4ASquareSample,
                  M4ANoiseSample, M4AKeyZone)

M4A_MAIN = (0x1840_0B40, 0x0059_8883, 0x0089_18C9, 0x680A_1889, 0x1C10_6801)
AMT_MAIN = (0x1840_0B40, 0x0051_8882, 0x0089_1889, 0x680A_18C9, 0x1C10_6801)
BMX_MAIN = (0x4008_2002, 0xD002_2800, 0x4282_6918, 0x1C20_D003, 0xF001_2100)
M4A_OLD = (0x00, 0xB5, 0x00, 0x04, 0x07, 0x4A, 0x08, 0x49,
           0x40, 0x0B, 0x40, 0x18, 0x83, 0x88, 0x59, 0x00,
           0xC9, 0x18, 0x89, 0x00, 0x89, 0x18, 0x0A, 0x68,
           0x01, 0x68, 0x10, 0x1C, 0x00, 0xF0)

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)


class GBARom(object):
    """ROM I/O helper.

    Parameters
    ----------
    path : int
        Absolute file path to ROM

    Attributes
    ----------
    _file : io.IOWrapper
        Base file object used for read/write operations.
    _code : str
        Internal GBA ROM production code.
    _name : str
        Internal GBA ROM production name.
    _path : str
        Absolute file path to ROM.
    address : int
        Address of read head.

    """

    def __init__(self, path: str = None):
        self._path = path
        self._file = open(self.path, 'rb', 8192)
        self._size = os.path.getsize(self.path)
        self._code = self.read_string(4, 0xAC)
        self._name = self.read_string(12, 0xA0)
        self.address = 0

    # region PROPERTIES

    @property
    def path(self):
        """ROM file path.

        Returns
        -------
        str
            Absolute file path to GBA ROM.

        """
        return self._path

    @property
    def address(self):
        """Read head address.

        Returns
        -------
        int
            Underlying file wrapper address.

        """
        return self._file.tell()

    @address.setter
    def address(self, address):
        """Move read head address.

        Parameters
        ----------
        address : int or None
            New address for read head.

        """
        if address is None:
            return
        self._file.seek(address)

    @property
    def code(self) -> str:
        """AGB production code."""
        return self._code

    @property
    def name(self) -> str:
        """Internal ROM name."""
        return self._name

    @property
    def size(self):
        """Return size of the file in bytes."""
        return self._size

    # endregion

    # region GENERIC FUNCTIONALITY

    def reset(self):
        """Set file to initial state."""
        self.address = 0

    def close(self) -> None:
        """Close the ROM."""
        self._file.close()
        del self

    def read(self, address=None, size=1):
        """Read a stream of byte(s) as an integer.

        Parameters
        ----------
        address : int, optional
            Address to read from (default is None for no change).
        size : int
            Data size in bytes.

        Returns
        -------
            int

        """
        self.address = address
        return int.from_bytes(self._file.read(size), 'little')

    def read_signed(self, address=None):
        """Read a signed byte.

        Parameters
        ----------
        address : int, optional
            Address to read from (default is None for no change).

        Returns
        -------
        int
            Signed integer.

        """
        mask = 2 ** 7
        data = self.read(address)
        out = -(data & mask) + (data & ~mask)
        return out

    def read_dword(self, address=None):
        """Read a DWORD (4 byte little-endian) from ROM.

        Parameters
        ----------
        address : int, optional
            Address to read from (default is None for no change).

        Returns
        -------
        int
            DWORD.

        """
        return self.read(address, 4)

    def read_string(self, length: int, address=None) -> str:
        """Read an ASCII string from ROM.

        Parameters
        ----------
        length : int
            String size in bytes.
        address : int, optional
            Address to read from (default is None for no change).

        Returns
        -------
            str

        """
        self.address = address
        out = str(self._file.read(length), 'utf7')
        return out

    def read_gba_ptr(self, address=None):
        """Read an GBA rom pointer.

        Parameters
        ----------
        address : int
            address in ROM; -1 is no change.

        Returns
        -------
        int
            ROM address

        """
        rom_ptr = self.read_dword(address)
        return to_address(rom_ptr)

    def peek(self, address=None):
        """Peek at 1 byte.

        Parameters
        ----------
        address : int
            address in ROM; -1 is no change.

        Returns
        -------
        int
            1 byte

        """
        prev = self.address
        data = self.read(address)
        self.address = prev
        return data

    # endregion

    # region SAMPLE PARSING

    def read_directsound_sample(self, address=None):
        """Parse a DirectSound sample into a sample construct.

        Parameters
        ----------
        address : int
            Address of DirectSound sample entry (default is -1 for current
            address).

        Returns
        -------
        sample : M4ADirectSoundSample
            A DirectSound sample construct.

        """
        self.address = address

        buffer_size = 3
        buffer = [self.read() for _ in range(buffer_size)]
        if buffer != [0, 0, 0]:
            return None
        looped = self.read()
        frequency = self.read_dword()
        loop_start = self.read_dword()
        size = self.read_dword()
        sample_data = self.read(size=size).to_bytes(size, 'little')
        sample = M4ADirectSoundSample(looped, frequency, loop_start,
                                      sample_data)
        if not sample.is_valid():
            return None
        return sample

    def read_waveform_sample(self, address=None):
        """Parse a PSG Waveform sample into a sample construct.

        Parameters
        ----------
        address : int
            Address of PSG Waveform sample entry (default is -1 for current
            address).

        Returns
        -------
        sample : M4AWaveformSample
            A PSG Waveform sample construct.

        """
        self.address = address

        wave_data = self.read_string(32)
        data = []
        for byte_ind in range(32):
            wave_ind, power = divmod(byte_ind, 2)
            byte = ord(wave_data[wave_ind]) / (16 ** power) % 16
            byte *= int(16 * PSG_WAVEFORM_VOLUME)
            data.append(int(byte))
        sample = M4AWaveformSample(bytes(data))
        return sample

    def load_sample(self, voice: M4AVoice) -> Optional[M4ASample]:
        """Create sample construct of ROM sample entry."""
        sample = None
        if voice.mode in (0x0, 0x8):
            voice: M4ADirectSound
            voice_address = voice.sample_ptr
            voice_ptr = to_address(voice_address)
            if voice_ptr == -1:
                LOGGER.warning(InvalidVoice(voice_address, voice.mode))
            else:
                sample = self.read_directsound_sample(voice_ptr)
        elif voice.mode in (0x1, 0x9, 0x2, 0xA):
            voice: Union[M4ASquare1, M4ASquare2]
            try:
                sample = M4ASquareSample(voice.duty_cycle)
            except IndexError:
                LOGGER.warning(
                    f'Invalid Square{1 if voice.mode in (0x1, 0x9) else 2}')
        elif voice.mode in (0x3, 0xB):
            voice: M4AWaveform
            voice_address = voice.sample_ptr
            voice_ptr = to_address(voice_address)
            if voice_ptr == -1:
                LOGGER.warning(InvalidVoice(voice_address, voice.mode))
            else:
                sample = self.read_waveform_sample(voice_ptr)
        elif voice.mode in (0x4, 0xC):
            voice: M4ANoise
            try:
                sample = M4ANoiseSample(voice.period)
            except InvalidArgument as e:
                LOGGER.warning(e)
        return sample

    # endregion

    # region VOICE PARSING

    def read_square1(self, address=None):
        """Construct a PSG Square1 voice construct from ROM data.

        Parameters
        ----------
        address : int
            Address of PSG Square1 voice entry (default is -1 for current
            address).

        Returns
        -------
        M4ASquare1
            PSG Square1 voice construct.
        """
        self.address = address
        data = [self.read() for _ in range(12)]
        data = data[1:5] + data[8:]
        return M4ASquare1(*data)

    def read_square2(self, address=None):
        """Construct a PSG Square2 voice construct from ROM data.

        Parameters
        ----------
        address : int
            Address of PSG Square2 voice entry (default is -1 for current
            address).

        Returns
        -------
        M4ASquare2
            PSG Square2 voice construct
        """
        self.address = address
        data = [self.read() for _ in range(12)]
        data = data[1:3] + data[4:5] + data[8:]
        return M4ASquare2(*data)

    def read_waveform(self, address=None):
        """Construct a PSG Waveform voice construct from ROM data.

        Parameters
        ----------
        address : int
            Address of PSG Waveform voice entry (default is -1 for current
            address).

        Returns
        -------
        M4AWaveform
            PSG Waveform voice construct
        """
        self.address = address
        data = [self.read() if i != 4 else self.read_dword() for i in range(9)]
        data = data[1:3] + data[4:]
        return M4AWaveform(*data)

    def read_noise(self, address=None):
        """Construct a Noise voice construct from ROM data.

        Parameters
        ----------
        address : int
            Address of Noise voice entry (default is -1 for current address).

        Returns
        -------
        M4ANoise
            Noise voice construct
        """
        self.address = address
        data = [self.read() for _ in range(12)]
        data = data[1:3] + data[4:5] + data[8:]
        return M4ANoise(*data)

    def read_directsound(self, address=None):
        """Construct a DirectSound voice construct from ROM data.

        Parameters
        ----------
        address : int
            Address of DirectSound voice entry (default is -1 for current
            address).

        Returns
        -------
        M4ADirectSound
            DirectSound voice construct
        """
        self.address = address
        data = [self.read() if i != 4 else self.read_dword() for i in range(9)]
        data = data[:2] + data[3:]
        return M4ADirectSound(*data)

    def read_voice(self, voice_ptr: int) -> Optional[M4AVoice]:
        """Load voice entry from ROM."""
        mode = self.read(voice_ptr)
        self.address = voice_ptr
        if mode in (0x0, 0x8):
            return self.read_directsound()
        elif mode in (0x1, 0x9):
            return self.read_square1()
        elif mode in (0x2, 0xA):
            return self.read_square2()
        elif mode in (0x3, 0xB):
            return self.read_waveform()
        elif mode in (0x4, 0xC):
            return self.read_noise()
        else:
            return None

    def load_voice(self, table_ptr: int, voice_id: int) -> Optional[M4AVoice]:
        """Load a M4A _voice."""
        voice_ptr = table_ptr + voice_id * 12
        voice_type = self.read(voice_ptr)
        if voice_type == 0x80:  # Percussion
            voice = M4ADrum({})
            voice_table_ptr = self.read_dword(voice_ptr + 4)
            for midi_key in range(128):
                midi_voice_ptr = to_address(voice_table_ptr + midi_key * 12)
                sub_voice = self.read_voice(midi_voice_ptr)
                if sub_voice is None:
                    continue
                voice.voice_table[midi_key] = sub_voice
                self.load_sample(sub_voice)
        elif voice_type == 0x40:  # Multi
            voice_table_ptr = self.read_dword(voice_ptr + 4)
            keymap_ptr = to_address(self.read_dword())
            voice_keys = [self.read(keymap_ptr + midi_key)
                          for midi_key in range(128)]
            voice = M4AKeyZone({}, {})
            for midi_key, voice_key in enumerate(voice_keys):
                midi_voice_ptr = to_address(voice_table_ptr + voice_key * 12)
                sub_voice = self.read_voice(midi_voice_ptr)
                if sub_voice is None:
                    continue
                voice.voice_table[voice_key] = sub_voice
                voice.keymap[midi_key] = voice_key
                self.load_sample(sub_voice)
        else:  # Everything else
            voice = self.read_voice(voice_ptr)
            if voice is None:
                return
            self.load_sample(voice)
        return voice

    # endregion

    def get_song_table(self):
        """Extract the track table address."""
        end_cmd = 0x4700_BC01
        song_table_offset = 8
        end_cmd_offset = 6
        table_offset = 5
        code = self.code[:3]
        if code == 'AMT':
            table = AMT_MAIN
        elif code == 'BMX':
            table = BMX_MAIN
        else:
            table = M4A_MAIN

        thumb_codes = array('I')
        self._file.seek(0)
        thumb_codes.fromfile(self._file, self.size // thumb_codes.itemsize)
        thumb_codes = tuple(thumb_codes)
        index = 0
        while True:
            try:
                index = thumb_codes.index(table[0], index)
            except ValueError:
                return -1
            r_match = thumb_codes[index + end_cmd_offset] == end_cmd
            if not r_match:
                index += 1
                continue
            l_part = thumb_codes[index:index + table_offset]
            l_match = l_part == table
            if not l_match:
                index += 1
                continue
            ptr = to_address(thumb_codes[index + song_table_offset])
            if ptr == -1:
                LOGGER.warning(f'Invalid song table: 0x{ptr:<8X}')
            else:
                if ptr <= self.size:
                    return ptr
            index += 1

    # region SDM PARSING

    def get_m4a_address(self):
        """Retrieve the offset of the M4A_Main call."""
        thumbs = array('B')
        table = M4A_OLD
        self._file.seek(0)
        thumbs.fromfile(self._file, self.size // thumbs.itemsize)
        thumbs = tuple(thumbs)
        index = 0
        while True:
            try:
                index = thumbs.index(table[1], index)
            except ValueError:
                return -1
            data = thumbs[index - 1:index - 1 + len(table)]
            # print(tuple(map(hex, table)), tuple(map(hex, data)))
            if table == data:
                return index
            index += 1

    def get_valid_sdm(self, m4a_main_address: int,
                      bounds: range) -> SoundDriverMode:
        """Check for a valid SoundDriverMode call."""
        thumbs = array('I')
        self._file.seek(0)
        thumbs.fromfile(self._file, self.size // thumbs.itemsize)
        thumbs = tuple(thumbs)
        start = (m4a_main_address + bounds.start) // 4 + 1
        max_len = (bounds.stop - bounds.start)
        engines = [parse_sdm(e) for e in thumbs[start:start + max_len]]
        tables = [t & 0x3FFFFFF for t in
                  thumbs[start + 30:start + 30 + max_len]]
        for engine, table in zip(engines, tables):
            if not check_sdm(engine) or table > self.size:
                continue
            return engine
        return SoundDriverMode()

    def get_sdm(self) -> SoundDriverMode:
        """Get SoundDriverMode call parameters from the offset of the Main call.

        Returns
        -------
            SoundDriverMode

        """
        game_code = self.read_string(4, 0xAC)
        if game_code[:3] == 'AMT':
            out = self.get_valid_sdm(0x45A8, range(-32, 32))  # 0x45A8
        elif game_code[:3] == 'A88':
            out = SoundDriverMode()
        elif game_code[:3] == 'AXV':
            out = SoundDriverMode()
        else:
            offset = self.get_m4a_address()
            if offset == -1:
                return SoundDriverMode()
            out = self.get_valid_sdm(offset, range(-32, 32))
        return out

    # endregion


def to_address(ptr: int):
    """Convert a ROM pointer to an address."""
    if ptr < 0x8000000 or ptr > 0x9FFFFFF:
        return -1
    return ptr - 0x8000000


def parse_sdm(driver_data: int) -> SoundDriverMode:
    """Construct a SoundDriverMode object."""
    return SoundDriverMode(
        reverb=driver_data & 0x0000_007F,
        reverb_enabled=driver_data & 0x0000_0080 == 0x80,
        polyphony=(driver_data & 0x0000_0F00) >> 8,
        volume_ind=(driver_data & 0x0000_F000) >> 12,
        freq_ind=(driver_data & 0x000F_0000) >> 16,
        dac_ind=(driver_data & 0x00F0_0000) >> 20,
    )


def check_sdm(driver: SoundDriverMode):
    """Check if the SoundDriverMode parameters are in valid range."""
    reverb = 0 <= driver.reverb <= 127
    polyphony = 1 <= driver.polyphony <= 12
    volume = 1 <= driver.volume_ind <= 15
    frequency = 1 <= driver.freq_ind <= 12
    dac = 8 <= driver.dac_ind <= 11
    return reverb == polyphony == volume == frequency == dac
