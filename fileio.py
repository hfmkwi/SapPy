# -*- coding: utf-8 -*-
# !/usr/bin/env/python -3
# pylint: disable=C0123,W0212
"""Provides File IO for Sappy

Todos:
    TODO(Me) Update all function docstrings
"""
import os
import os.path
import struct

__all__ = ('Error', 'File', 'open_file', 'open_new_file')


class Error(Exception):
    """Module-level base exception"""

    def __init__(self, message: str, code: int) -> None:
        """Initate an exception with a message and err code"""
        super().__init__()
        self.message = message
        self.code = code


class File(object):  # pylint: disable=R0902
    """Base file object """

    _file_table = {}

    def __init__(self, file_path: str = None, file_id: int = None) -> None:
        """Initate a file object with basic IO functions

        Args:
            file_path: refers to an existing file; otherwise refers to a new
                file
            file_id: ID number of the file for internal identification

        Attributes:
            _file_table (dict): A table holding references to all open files
                stored under their respective IDs.
            file_id (int): file number for developer identification.
            file_obj (IOWrapper): root file object used for read/write
                operations.
            file_path (str): file path of the file intended for access.
            read_offset (int): offset of the read head
            write_offset (int): offset of the write head

        """
        self._file_path = file_path  # Set file name for local access

        # Define file ID
        if not self._check_id(file_id):
            self._file_id = self._get_free_file_id()
        else:
            self._file_id = file_id
            self._file_table[file_id] = self

        # Create an IO object for file access
        if self._file_path and self._check_file_exists(self.file_path):
            self._file_obj = open(self.file_path, 'rb+')
        else:
            self._file_obj = None

        self._write_offset = self._read_offset = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def file_path(self) -> str:
        """File path to the file"""
        return self._file_path

    @property
    def file_id(self) -> int:
        """File ID number for internal identification"""
        return self._file_id

    @property
    def read_offset(self) -> int:
        """Current offset of the read head"""
        return self._read_offset

    @read_offset.setter
    def read_offset(self, offset: int = None) -> None:
        if offset is None:
            offset = self._read_offset
        elif offset < 0:
            offset = 0
        self._read_offset = offset

    @property
    def size(self):
        """Number of int in file"""
        return os.path.getsize(self.file_path) + 1

    @property
    def write_offset(self) -> int:
        """Current offset of the write head"""
        return self._write_offset

    @write_offset.setter
    def write_offset(self, offset: int = None) -> None:
        if offset is None:
            offset = self._write_offset
        elif offset < 0:
            offset = 0
        self._write_offset = offset

    @staticmethod
    def _check_file_exists(file_path: str) -> bool:
        """Check if a file path refers to an existing file and not a directory

        Args:
            path: file path to check

        Returns:
            True if successful, False otherwise.

        """
        cur_file = os.path.curdir + file_path
        return (os.path.isabs(file_path) and os.path.exists(file_path) and
                os.path.isfile(file_path)) or (os.path.isabs(cur_file) and
                                               os.path.exists(cur_file) and
                                               os.path.isfile(cur_file))

    @staticmethod
    def gba_rom_pointer_to_offset(pointer: int) -> int:
        """Convert an AGB rom pointer to an integer

        An AGB rom pointer is a 4 byte stream in little-endian format in the
        following format:

        0x[08-09][00-FF][00-FF][00-FF]

        Args:
            pointer: an AGB rom pointer

        Returns:
            An AGB rom pointer as an integer on success, otherwise -1

        """
        if pointer < 0x8000000 or pointer > 0x9FFFFFF:
            return -1
        return pointer - 0x8000000

    @staticmethod
    def get_file_from_id(file_id: int) -> 'File':
        """Retrieve a file object from it's internal ID."""
        return __class__._file_table.get(file_id)

    def _check_id(self, file_id: int) -> bool:
        """Check if the specified file ID is valid and unused

        Args:
            file_id: file ID to check

        Returns:
            True if successful, False otherwise.

        Raises:
            Error: 'invalid file number'

        """
        if file_id is not None and not 0 <= file_id < 256:
            raise Error('invalid file number', 2)
        return file_id not in self._file_table and type(file_id) == int

    def _close(self) -> None:
        """Close a file by ID
        Deletes the reference in the file table and frees the ID for use

        Args:
            file_id: file ID number

        """
        self._file_obj.close()
        self._file_table.pop(self._file_id)
        del self

    def _get(self, offset: int = None) -> int:
        """Imitation of the VB6 `Get` keyword in binary mode

        Args:
            offset: position to move the read head to
                if None, defaults to the current position of the read head

        Returns:
            A int-like object representing one single byte

        """
        if offset is None:
            offset = self.read_offset
        self.read_offset = offset
        self._file_obj.seek(offset)
        byte = struct.unpack('B', self._file_obj.read(1))[0]
        self.read_offset = self._file_obj.tell()
        return byte

    def _get_free_file_id(self) -> int:
        """Return a free file id (internal use only)

        Returns:
            A number (0<=n<256) representing a free file on success

        Raises:
            Error: 'all files are currently in use'

        """
        for file_id in range(256):
            if file_id not in self._file_table:
                self._file_table[file_id] = 1
                return file_id
        raise Error(message='all files are currently in use', code=1)

    def _put(self, data: int, offset: int = None) -> None:
        """Imitation of the VB6 `Put` keyword in binary mode

        Args:
            data: data to be written to file
            offset: the offset in the file at which to relocate the write head
                and write to
                if None, defaults to the write head's current position

        """
        if offset is None:
            offset = self.write_offset
        self.write_offset = offset
        self._file_obj.seek(offset)
        data = struct.pack('B', data)
        self._file_obj.write(data)
        self.write_offset = self._file_obj.tell()
        assert self.write_offset > offset or offset is not None

    def close(self, file_id: int = None) -> None:
        """Close the current file

        Args:
            file_id: a valid file ID

        """
        if not self._check_id(file_id):
            file_id = self.file_id
        if self.file_id != file_id:
            file = self._file_table.get(file_id)
            file.close(file.file_id)
        else:
            self._close()

    def write_byte(self, data: int, offset: int = None) -> None:
        """Write a single byte to file

        Args:
            data: data to write to file
            offset: position to move the write head to.
                if None, defaults to the write head's current position.

        """
        self.write_offset = offset
        self._put(data, offset)

    def write_big_endian(self, width: int, data: int,
                         offset: int = None) -> None:
        """Write an integer as int in big-endian format to file

        Args:
            width: maximum size of data in int form
            data: data to write to file
            offset: position to move the write head to
                if None, defaults to the write head's current position.

        """
        self.write_offset = offset
        for i in range(width):
            byte = data // 16**(i * 2) % 256
            self.write_byte(byte)

    def write_little_endian(self, width: int, data: int,
                            offset: int = None) -> None:
        """Write an integer as int in little-endian format to file

        Args:
            width: maximum byte width of the data
            data: data to write to file
            offset: position to move the write head to
                if None, defaults to the write head's current position.

        """
        self.write_offset = offset
        for i in range(width - 1, -1, -1):
            byte = data // 16**(i * 2) % 256
            self.write_byte(byte)

    def write_string(self, data: str, offset: int = None) -> None:
        """Write a string as int to file

        Args:
            data: data to write to file
            offset: position to move the write head to
                if None, defaults to the write head's current position
        """
        self.write_offset = offset
        for char in data:
            self.write_byte(int([ord(char)]))

    def read_byte(self, offset: int = None) -> int:
        """Read a byte from file

        Args:
            offset: a valid address in the file at which to move the read head
                if None, defaults to the read head's current position

        Returns:
            a int-like object length 1

        """
        self.read_offset = offset
        return self._get(offset)

    def read_vlq(self, offset: int = None) -> int:
        """Read a stream of int in VLQ format

        Args:
            offset: a valid address in the file at which to move the read head
                if None, defaults to the read head's current position

        Returns:
            an integer
        """
        self.read_offset = offset
        vlq = 0
        ret_len = 0
        while True:
            byte = self.read_byte()
            vlq = vlq * 2**7 + (byte % 0x80)
            ret_len += 1
            if ret_len == 4 or byte < 0x80:
                break
        return vlq

    def read_big_endian(self, width: int, offset: int = None) -> int:
        """Read a stream of int in big-endian format

        Args:
            width: number of consecutive int to read
            offset: a valid address in the file at which to move the read head.
                if None, defaults to the read head's current position.

        Returns:
            An integer
        """
        self.read_offset = offset
        out = 0
        for i in range(width - 1, -1, -1):
            out += self.read_byte() * 256**i
        return out

    def read_little_endian(self, width: int, offset: int = None) -> int:
        """Read a stream of int in little-endian format

        Args:
            width: number of consective int to read
            offset: a valid address in the file at which to move the read head.
                if None, defaults to the read head's current positoin.

        Returns:
            An integer
        """
        self.read_offset = offset
        out = 0
        for i in range(width):
            out += self.read_byte() * 256**i
        return out

    def read_string(self, length: int, offset: int = None) -> str:
        """Read a stream of int as a string from file

        Args:
            length: number of consecutive int to read
            offset: a valid address in the file at which to move the read head.
                if None, defaults to the read ehad's current position.

        Returns:
            A string of the specified length
        """
        self.read_offset = offset
        out = []
        for i in range(length):  # pylint: disable=unused-variable
            out.append(chr(self.read_byte()))
        return ''.join(out)

    def read_gba_rom_pointer(self, offset: int = -1) -> int:
        """Read a stream of int as an AGB rom pointer.

        Args:
            offset: a valid address in the file at which to move the read head.
                If None, defaults to the read head's current position.

        Returns:
            An AGB rom pointer as an integer on success, otherwise -1

        """
        pointer = self.read_little_endian(4, offset)
        return self.gba_rom_pointer_to_offset(pointer)


def open_file(file_path: str, file_id: int = None) -> File:
    """Open an existing file with read/write access in byte mode"""
    return File(file_path, file_id)


def open_new_file(file_path: str, file_id: int = None) -> File:
    """Create a new file and open with read/write access in byte mode"""
    with open(file_path, 'wb+') as file:
        file.write(bytes([0]))
    return open_file(file_path, file_id)
