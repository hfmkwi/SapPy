# -*- coding: utf-8 -*-
"""Main self.file."""
from collections import OrderedDict
from logging import getLogger, DEBUG
from typing import Union, Dict, List

from .cmd import (BEND, BENDR, EOT, FINE, GOTO, KEYSH, LFODL,
                  LFOS, MEMACC, MOD, MODT, NOTE, PAN, PATT, PEND, PREV,
                  PRIO, TEMPO, TUNE, VOICE, VOL, WAIT, XCMD)
from .exceptions import (InvalidSongNumber, BlankSong, InvalidROM,
                         UnknownCommand)
from .inst_set import (GateArg, CMD, NoteCMD, WaitCMD, mxv, REPEATABLE)
from .m4a import (M4ASong, MetaData, M4AVoice, M4ASample,
                  M4ADirectSound,
                  M4AWaveform, M4ANoise,
                  M4ASquare2, M4ASquare1, M4AKeyZone, M4ADrum, M4ATrack)
from .rom import GBARom

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)


# TODO: Implement argument parser handler
class SingleArgumentHandler(object):
    pass


class Parser(object):
    """Intermediary for translating M4A data into Python constructs.

    Parameters
    ----------
    path : str
        File path to ROM.

    Attributes
    ----------
    file : GBARom
        Open file instance for read access.
    voices : set
        Global list of all voices used by an M4A song.

    """

    def __init__(self, path):
        self.file = GBARom(path)
        self.voices = set()

    def load_track(self, program_ctr):
        """Parses all M4A commands into Python constructs for later execution.

        Parameters
        ----------
        program_ctr : int
            Starting address of track data.

        Returns
        -------
        M4ATrack
            New track construct with parsed track data.

        """
        last_cmd = CMD.VOL
        last_note = 0
        last_velocity = 0
        last_ext = 0
        track_data: OrderedDict = OrderedDict()

        self.file.address = program_ctr
        done: bool = False
        while not done:

            cmd_pos = self.file.address
            byte = self.file.read()
            command = None

            if byte in REPEATABLE or NoteCMD.TIE <= byte <= NoteCMD.N96:
                last_cmd = byte

            if WaitCMD.W00 <= byte <= WaitCMD.W96:
                command = WAIT(byte)
            elif byte == CMD.FINE:
                command = FINE()
                done = True
            elif byte == CMD.GOTO:
                loop_ptr = self.file.read_gba_ptr()
                command = GOTO(loop_ptr)
            elif byte == CMD.PATT:
                address = self.file.read_gba_ptr()
                command = PATT(address)
            elif byte == CMD.PEND:
                command = PEND()
            elif byte == CMD.PREV:
                command = PREV()
                done = True
            elif byte == CMD.MEMACC:
                op_code = self.file.read()
                address = self.file.read()
                data = self.file.read()
                command = MEMACC(op_code, address, data)
            elif byte == CMD.PRIO:
                command = PRIO(self.file.read())
            elif byte == CMD.TEMPO:
                command = TEMPO(self.file.read())
            elif byte == CMD.KEYSH:
                data = self.file.read_signed()
                command = KEYSH(data)
            elif byte == CMD.VOICE:
                voice_id = self.file.read()
                self.voices.add(voice_id)
                command = VOICE(voice_id)
            elif byte == CMD.VOL:
                command = VOL(self.file.read())
            elif byte == CMD.PAN:
                command = PAN(self.file.read())
            elif byte == CMD.BEND:
                command = BEND(self.file.read())
            elif byte == CMD.BENDR:
                command = BENDR(self.file.read())
            elif byte == CMD.LFOS:
                command = LFOS(self.file.read())
            elif byte == CMD.LFODL:
                command = LFODL(self.file.read())
            elif byte == CMD.MOD:
                command = MOD(self.file.read())
            elif byte == CMD.MODT:
                command = MODT(self.file.read())
            elif byte == CMD.TUNE:
                command = TUNE(self.file.read())
            elif byte == CMD.XCMD:
                last_ext = self.file.read()
                arg = self.file.read()
                command = XCMD(last_ext, arg)
            elif byte == NoteCMD.EOT:
                note = self.file.read()
                if note <= mxv:
                    command = EOT(note)
                else:  # ALL SUSTAINED OFF
                    command = EOT()
                    self.file.address -= 1
            elif NoteCMD.TIE <= byte <= NoteCMD.N96:
                o = self.file.address
                note = self.file.read()
                velocity = self.file.read()
                gate = self.file.read()
                self.file.address = o
                if note <= mxv:
                    last_note = self.file.read()
                    if velocity <= mxv:
                        last_velocity = self.file.read()
                        if GateArg.gtp1 <= gate <= GateArg.gtp3:
                            self.file.address += 1
                if not GateArg.gtp1 <= gate <= GateArg.gtp3:
                    gate = None
                note_cmd = NOTE(byte, last_note, last_velocity, gate)
                command = note_cmd
            elif 0 <= byte <= mxv:
                if last_cmd == CMD.VOICE:
                    voice_id = byte
                    self.voices.add(voice_id)
                    command = VOICE(byte)
                elif last_cmd == CMD.VOL:
                    command = VOL(byte)
                elif last_cmd == CMD.PAN:
                    command = PAN(byte)
                elif last_cmd == CMD.BEND:
                    command = BEND(byte)
                elif last_cmd == CMD.BENDR:
                    command = BENDR(byte)
                elif last_cmd == CMD.LFOS:
                    command = LFOS(byte)
                elif last_cmd == CMD.LFODL:
                    command = LFODL(byte)
                elif last_cmd == CMD.MOD:
                    command = MOD(byte)
                elif last_cmd == CMD.MODT:
                    command = MODT(byte)
                elif last_cmd == CMD.TUNE:
                    command = TUNE(byte)
                elif last_cmd == NoteCMD.EOT:
                    command = EOT(byte)
                elif last_cmd == CMD.XCMD:
                    command = XCMD(last_ext, byte)
                elif NoteCMD.N96 >= last_cmd >= NoteCMD.TIE:
                    o = self.file.address
                    last_note = byte
                    velocity = self.file.read()
                    gate = self.file.read()
                    self.file.address = o
                    if velocity <= mxv:
                        last_velocity = self.file.read()
                        if GateArg.gtp1 <= gate <= GateArg.gtp3:
                            self.file.address += 1
                    if not GateArg.gtp1 <= gate <= GateArg.gtp3:
                        gate = None
                    note_cmd = NOTE(last_cmd, last_note, last_velocity,
                                    gate)
                    command = note_cmd
                else:
                    raise UnknownCommand(byte)
            track_data[cmd_pos] = command
        return M4ATrack(track_data)

    def load_tracks(self, song_ptr, num_tracks):
        """Load an M4A song entry's command data.

        Parameters
        ----------
        song_ptr : int
            Pointer to the M4A song entry.
        num_tracks : int
            Number of tracks in the M4A song entry.

        Returns
        -------
        List[M4ATrack]
            List of track constructs in ascending load order.

        """
        tracks = []

        for track_num in range(num_tracks):
            start_address = self.file.read_gba_ptr(song_ptr + 8 + track_num * 4)
            self.file.reset()
            track = self.load_track(start_address)
            tracks.append(track)
        return tracks

    def load_voices(self, table_ptr):
        """Create `M4AVoice` constructs from the ROM voice table.

        Do **NOT** use unless `load_tracks` has been called first.

        Parameters
        ----------
        table_ptr : int
            Pointer to voice table.

        Returns
        -------
        Dict[int, M4AVoice]
            Dictionary of voice constructs linked by voice ID.

        """
        voices = {}
        self.file.reset()
        for voice_id in self.voices:
            voice = self.file.load_voice(table_ptr, voice_id)
            voices[voice_id] = voice
        return voices

    def load_samples(self, voices):
        """Create `M4ASample` constructs from ROM sample data based on loaded
        voices.

        Notes
        -----
            The sample dictionary uses sample pointers to link only DirectSound
            and PSG Waveform samples. Square1/Square2 and Noise samples are
            linked using strings that denote their duty cycles and periods,
            respectively.

        Parameters
        ----------
        voices : Dict[int, M4AVoice]
            Dictionary of voice constructs linked by voice ID.

        Returns
        -------
        Dict[Union[int, str], M4ASample]
            Dictionary of sample constructs linked by sample pointer.

        """
        samples = {}
        self.file.reset()
        for voice in voices.values():
            if voice.mode in (0x0, 0x8, 0x3, 0xB):
                voice: Union[M4ADirectSound, M4AWaveform]
            elif voice.mode not in (0x40, 0x80):
                voice: Union[M4ASquare1, M4ASquare2, M4ANoise]
            else:
                voice: Union[M4ADrum, M4AKeyZone]
                sub_samples = self.load_samples(voice.voice_table)
                samples.update(sub_samples)
                continue
            key = voice.sample_ptr
            if key in samples:
                continue
            sample = self.file.load_sample(voice)
            if sample is None:
                continue
            samples[key] = sample
        return samples

    def load_song(self, song_id, song_table_ptr=None):
        """Create an `M4ASong` construct from an entry in the ROM song table.

        Parameters
        ----------
        song_id : int
            Song entry number.
        song_table_ptr : int, optional
            Pointer to song table.

        Returns
        -------
        M4ASong
            Song construct with sample, voice, and track command data.

        Raises
        ------
        InvalidROM
            If the `GBARom` search algorithm does not find a valid song table
            pointer.
        InvalidSongNumber
            If the song number refers to a non-existent/out-of-bounds song
            entry.
        BlankSong
            If the song has no tracks.

        """

        if song_table_ptr is None:
            song_table_ptr = self.file.get_song_table()
            if song_table_ptr == -1:
                raise InvalidROM()

        song_ptr = self.file.read_gba_ptr(song_table_ptr + song_id * 8)
        if song_ptr == -1:
            raise InvalidSongNumber(song_id)

        num_tracks = self.file.read(song_ptr)
        if num_tracks == 0:
            raise BlankSong()

        unk = self.file.read()
        priority = self.file.read()
        reverb = self.file.read()
        voice_table_ptr = self.file.read_gba_ptr()

        tracks = self.load_tracks(song_ptr, num_tracks)
        voices = self.load_voices(voice_table_ptr)
        samples = self.load_samples(voices)
        sdm = self.file.get_sdm()
        meta_data = MetaData(
            rom_code=self.file.code,
            rom_name=self.file.name,
            tracks=num_tracks,
            reverb=reverb,
            priority=priority,
            main_ptr=song_ptr,
            voice_ptr=voice_table_ptr,
            song_ptr=song_table_ptr,
            unknown=unk)
        song = M4ASong(tracks, voices, samples, meta_data, sdm)
        return song
