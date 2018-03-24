#!/usr/bin/python3
#-*- coding: utf-8 -*-
# pylint: disable=C0103,C0123,W0212,W0622
"""Provides File IO for Sappy"""
import struct
from os.path import (exists, getsize, isabs, isfile)

__all__ = ('Error', 'File', 'open_file', 'open_new_file')


class Error(Exception):
    """Module-level base exception"""

    def __init__(self, msg: str, code: int) -> None:
        """Initate an exception with a message and err code"""
        super().__init__()
        self.msg = msg
        self.code = code


class File(object):  # pylint: disable=R0902
    """Base file object """

    _ftable = {}

    def __init__(self, path: str = None, id: int = None) -> None:
        """Initate a file object with basic IO functions

        Args:
            path: refers to an existing file; otherwise refers to a new
                file
            id: ID number of the file for internal identification

        Attributes:
            _ftable (dict): A table holding references to all open files
                stored under their respective IDs.
            id (int): file number for developer identification.
            file (IOWrapper): root file object used for read/write
                operations.
            path (str): file path of the file intended for access.
            rd_addr (int): offset of the read head
            wr_addr (int): offset of the write head

        """
        self._path = path  # Set file name for local access

        # Define file ID
        if not self._chk_id(id):
            self._id = self._get_free_id()
        else:
            self._id = id
            self._ftable[id] = self

        # Create an IO object for file access
        if self._path and self._chk_path():
            self._file = open(self.path, 'rb+')
        else:
            self._file = None

        self._wr_addr = self._rd_addr = 0

    def __enter__(self):
        self.wr_addr = 0
        self.rd_addr = 0
        self._file = open(self.path, 'rb+')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def path(self) -> str:
        """File path to the file"""
        return self._path

    @property
    def id(self) -> int:
        """File ID number for internal identification"""
        return self._id

    @property
    def rd_addr(self) -> int:
        """Current offset of the read head"""
        return self._rd_addr

    @rd_addr.setter
    def rd_addr(self, addr: int = None) -> None:
        if addr is not None and addr >= 0:
            self._rd_addr = addr
        else:
            self._rd_addr = self._rd_addr

    @property
    def size(self):
        """Number of int in file"""
        return getsize(self.path)

    @property
    def wr_addr(self) -> int:
        """Current offset of the write head"""
        return self._wr_addr

    @wr_addr.setter
    def wr_addr(self, addr: int = None) -> None:
        if addr is not None and addr >= 0:
            self._wr_addr = addr

    @staticmethod
    def gba_ptr_to_addr(ptr: int) -> int:
        """Convert an AGB rom pointer to an integer

        An AGB rom pointer is a 4 byte stream in little-endian format in the
        following format:

        0x[08-09][00-FF][00-FF][00-FF]

        Args:
            pointer: an AGB rom pointer

        Returns:
            An AGB rom pointer as an integer on success, otherwise -1

        """
        if ptr < 0x8000000 or ptr > 0x9FFFFFF:
            return -1
        return ptr - 0x8000000

    @staticmethod
    def from_id(id: int) -> 'File':
        """Retrieve a file object from it's internal ID."""
        return __class__._ftable.get(id)

    def _chk_id(self, id: int) -> bool:
        """Check if the specified file ID is valid and unused

        Args:
            file_id: file ID to check

        Returns:
            True if successful, False otherwise.

        Raises:
            Error: 'invalid file number'

        """
        return id not in self._ftable and type(id) == int

    def _chk_path(self) -> bool:
        """Check if a file path refers to an existing file and not a directory

        Returns:
            True if successful, False otherwise.

        """
        path = self._path
        return exists(path) and isfile(path) and isabs(path)

    def _close(self) -> None:
        """Close a file by ID
        Deletes the reference in the file table and frees the ID for use

        Args:
            file_id: file ID number

        """
        self._file.close()
        self._ftable.pop(self._id)
        del self

    def _get(self, addr: int = None) -> int:
        """Imitation of the VB6 `Get` keyword in binary mode

        Args:
            offset: position to move the read head to
                if None, defaults to the current position of the read head

        Returns:
            A int-like object representing one single byte

        """
        self.rd_addr = addr
        self._file.seek(self.rd_addr)
        byte = ord(self._file.read(1))
        self.rd_addr += 1
        return byte

    def _get_free_id(self) -> int:
        """Return a free file id (internal use only)

        Returns:
            A number (0<=n<256) representing a free file on success

        Raises:
            Error: 'all files are currently in use'

        """
        for file_id in range(256):
            if file_id not in self._ftable:
                self._ftable[file_id] = 1
                return file_id
        raise Error(msg='all files are currently in use', code=1)

    def _put(self, data: int, addr: int = None) -> None:
        """Imitation of the VB6 `Put` keyword in binary mode

        Args:
            data: data to be written to file
            addr: the offset in the file at which to relocate the write head
                and write to
                if None, defaults to the write head's current position

        """
        self.wr_addr = addr
        self._file.seek(self.wr_addr)
        data = struct.pack('B', data)
        self._file.write(data)
        self.wr_addr = self._file.tell()

    def close(self, id: int = None) -> None:  # pylint: disable=W0622
        """Close the current file

        Args:
            id: a valid file ID

        """
        if not self._chk_id(id):
            id = self.id
        if self.id != id:
            file = self._ftable.get(id)
            file.close(file.file_id)
        else:
            self._close()

    wr_byte = _put

    def wr_bgendian(self, width: int, data: int, addr: int = None) -> None:
        """Write an integer as int in big-endian format to file

        Args:
            width: maximum size of data in int form
            data: data to write to file
            addr: address to move the write head to
                if None, defaults to the write head's current position.

        """
        self.wr_addr = addr
        for i in range(width):
            byte = data // 16**(i * 2) % 256
            self.wr_byte(byte)

    def wr_ltendian(self, width: int, data: int, addr: int = None) -> None:
        """Write an integer as int in little-endian format to file

        Args:
            width: maximum byte width of the data
            data: data to write to file
            addr: address to move the write head to
                if None, defaults to the write head's current position.

        """
        self.wr_addr = addr
        for i in range(width - 1, -1, -1):
            byte = data // 16**(i * 2) % 256
            self.wr_byte(byte)

    def wr_str(self, data: str, addr: int = None) -> None:
        """Write a string as int to file

        Args:
            data: data to write to file
            addr: address to move the write head to
                if None, defaults to the write head's current position
        """
        self.wr_addr = addr
        data = map(ord, data)
        for char in data:
            self.wr_byte(char)

    def rd_byte(self, addr: int = None) -> int:
        """Read a byte from file

        Args:
            addr: a valid address in the file at which to move the read head
                if None, defaults to the read head's current position

        Returns:
            an integer [0-255]

        """
        return self._get(addr)

    def rd_vlq(self, addr: int = None) -> int:
        """Read a stream of int in VLQ format

        Args:
            addr: a valid address in the file at which to move the read head
                if None, defaults to the read head's current position

        Returns:
            an integer
        """
        self.rd_addr = addr
        vlq = 0
        ret_len = 0
        while True:
            byte = self.rd_byte()
            vlq = vlq * 2**7 + (byte % 0x80)
            ret_len += 1
            if ret_len == 4 or byte < 0x80:
                break
        return vlq

    def rd_bgendian(self, width: int, addr: int = None) -> int:
        """Read a stream of int in big-endian format

        Args:
            width: number of consecutive int to read
            addr: a valid address in the file at which to move the read head.
                if None, defaults to the read head's current position.

        Returns:
            An integer
        """
        self.rd_addr = addr
        out = 0
        for i in range(width - 1, -1, -1):
            out += self.rd_byte() * 256**i
        return out

    def rd_ltendian(self, width: int, addr: int = None) -> int:
        """Read a stream of int in little-endian format

        Args:
            width: number of consective int to read
            addr: a valid address in the file at which to move the read head.
                if None, defaults to the read head's current positoin.

        Returns:
            An integer
        """
        self.rd_addr = addr
        out = 0
        for i in range(width):
            out += self.rd_byte() * 256**i
        return out

    def rd_str(self, length: int, addr: int = None) -> str:
        """Read a stream of int as a string from file

        Args:
            len: number of consecutive int to read
            addr: a valid address in the file at which to move the read head.
                if None, defaults to the read ehad's current position.

        Returns:
            A string of the specified length
        """
        self.rd_addr = addr
        out = []
        for __ in range(length):
            b = self.rd_byte()
            out.append(b)
        #out = [i if i != 0 else 32 for i in out]
        out = map(chr, out)
        return ''.join(out)

    def rd_gba_ptr(self, addr: int = None) -> int:
        """Read a stream of int as an AGB rom pointer.

        Args:
            addr: a valid address in the file at which to move the read head.
                If None, defaults to the read head's current position.

        Returns:
            An AGB rom pointer as an integer on success, otherwise -1

        """
        self.rd_addr = addr
        ptr = self.rd_ltendian(4)
        return self.gba_ptr_to_addr(ptr)


def open_file(file_path: str, file_id: int = None) -> File:
    """Open an existing file with read/write access in byte mode"""
    return File(file_path, file_id)


def open_new_file(file_path: str, file_id: int = None) -> File:
    """Create a new file and open with read/write access in byte mode"""
    with open(file_path, 'wb+') as file:
        file.write(bytes(1))
    return open_file(file_path, file_id)
