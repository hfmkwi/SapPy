# -*- coding: utf-8 -*-
"""M4A engine command constructs."""
from abc import abstractmethod

from .config import IGNORE_GOTO
from .inst_set import (CMD, KeyArg, MemAccArg, ModArg, NoteCMD,
                       VelocityArg, WaitCMD, GateArg)
from .m4a import M4ATrack, FMODNote


class M4ACommand(object):
    """M4A Command base class.

    Parameters
    ----------
    cmd : int
        M4A command byte.
    *args
        M4A command arguments.

    Attributes
    ----------
    cmd : int
        M4A command byte.
    args : tuple of int
        M4A command arguments.

    """

    def __init__(self, cmd, *args):
        """Initialize command using parsed data."""
        self.cmd = cmd
        self.args = args

    @abstractmethod
    def __call__(self, track: M4ATrack):
        """Execute command."""
        raise NotImplementedError()

    def __str__(self):
        """Return command as ASM call."""
        return self.__class__.__name__


class WAIT(M4ACommand):
    """Waits `x` ticks.

    Represents an M4A WAIT command. Tick value is determined by the value
    located in the command definition.

    Parameters
    ----------
    wait_cmd : int
        Valid wait command byte.

    See Also
    --------
    inst_set.WaitCMD

    """

    def __init__(self, wait_cmd):
        super().__init__(wait_cmd)
        self._ticks = int(WaitCMD(wait_cmd).name[1:])

    def __call__(self, track: M4ATrack):
        track.ticks = self._ticks
        track.program_ctr += 1

    def __str__(self):
        return WaitCMD(self.cmd).name


class FINE(M4ACommand):
    """Ends track playback."""

    def __init__(self):
        super().__init__(CMD.FINE)

    def __call__(self, track: M4ATrack):
        track.enabled = False
        track.program_ctr += 1


class GOTO(M4ACommand):
    """Jump unconditionally to address in track data.

    Parameters
    ----------
    pointer : int
        Address to jump to.

    """

    def __init__(self, pointer):
        ptr_chunks = list(memoryview(pointer.to_bytes(4, 'little')))
        super().__init__(CMD.GOTO, *ptr_chunks)
        self._pointer = pointer

    def __call__(self, track: M4ATrack):
        if not IGNORE_GOTO:
            track.program_ctr = tuple(track.track_data.keys()).index(
                self._pointer)
            track.base_ctr = track.program_ctr
        else:
            track.program_ctr += 1

    def __str__(self):
        return f'GOTO 0x{self._pointer:X}'


class PATT(M4ACommand):
    """Execute pattern to PEND and then return to normal execution.

    Parameters
    ----------
    pointer : int
        Address to jump to.

    """

    def __init__(self, pointer):
        ptr_chunks = list(memoryview(pointer.to_bytes(4, 'little')))
        super().__init__(CMD.PATT, *ptr_chunks)
        self._pointer = pointer

    def __call__(self, track: M4ATrack):
        track.call_stack.put_nowait(track.program_ctr)
        track.program_ctr = tuple(track.track_data.keys()).index(self._pointer)
        track.base_ctr = track.program_ctr

    def __str__(self):
        return f'PATT 0x{self._pointer:X}'


class PEND(M4ACommand):
    """Denote end of pattern block."""

    def __init__(self):
        super().__init__(CMD.PEND)

    def __call__(self, track: M4ATrack):
        if not track.call_stack.empty():
            return_ctr = track.call_stack.get_nowait()
            track.program_ctr = track.base_ctr = return_ctr
        track.program_ctr += 1


class REPT(M4ACommand):
    """Repeat all commands from an address to this function call.

    Parameters
    ----------
    loop_count : int
        Number of loops (0 is infinite).
    pointer : int
        Address to jump to.

    """

    def __init__(self, loop_count, pointer):
        ptr_chunks = list(memoryview(pointer.to_bytes(4, 'little')))
        super().__init__(CMD.REPT, loop_count, *ptr_chunks)
        self._pointer = pointer
        self._loop_count = loop_count

    def __call__(self, track: M4ATrack):
        track.program_ctr += 1

    def __str__(self):
        return f'REPT {self._loop_count} {self._pointer}'


class PREV(M4ACommand):
    """Unknown functionality (functions like FINE)."""

    def __init__(self):
        super().__init__(CMD.PREV)

    def __call__(self, track: M4ATrack):
        track.enabled = False
        track.program_ctr += 1


class MEMACC(M4ACommand):
    """Modifies M4A engine memory location.

    Parameters
    ----------
    op_code : int
        Operation to perform on memory area.
    address : int
        Address within memory area.
    data : int
        Byte to write to memory area.

    """

    def __init__(self, op_code, address, data):
        super().__init__(CMD.MEMACC, op_code, address, data)
        self._op_code = MemAccArg(op_code)
        self._address = address
        self._data = data

    def __call__(self, track: M4ATrack):
        track.program_ctr += 1

    def __str__(self):
        return f'MEMACC {self._op_code} {self._address} {self._data}'


class PRIO(M4ACommand):
    """Set track priority.

    Parameters
    ----------
    priority : int
        New track priority.

    """

    def __init__(self, priority):
        super().__init__(CMD.PRIO, priority)
        self._priority = priority

    def __call__(self, track: M4ATrack):
        track.priority = self._priority
        track.program_ctr += 1

    def __str__(self):
        return f'PRIO {self._priority}'


class TEMPO(M4ACommand):
    """Set global tick counter's ticks/second.

    Parameters
    ----------
    tempo : int
        New track tempo.

    """

    def __init__(self, tempo):
        super().__init__(CMD.TEMPO, tempo)
        self._tempo = tempo

    def __call__(self, track: M4ATrack):
        M4ATrack.TEMPO = self._tempo
        track.program_ctr += 1

    def __str__(self):
        return f'TEMPO {self._tempo}'


class KEYSH(M4ACommand):
    """Set track key shift.

    Parameters
    ----------
    key_shift : int
        New track key shift.

    """

    def __init__(self, key_shift):
        super().__init__(CMD.KEYSH, key_shift)
        self._key_shift = key_shift

    def __call__(self, track: M4ATrack):
        M4ATrack.KEY_SHIFT = self._key_shift
        track.program_ctr += 1

    def __str__(self):
        return f'KEYSH {self._key_shift}'


class VOICE(M4ACommand):
    """Set track voice.

    Parameters
    ----------
    voice : int
        New track voice.

    """

    def __init__(self, voice):
        super().__init__(CMD.VOICE, voice)
        self._voice = voice

    def __call__(self, track: M4ATrack):
        track.voice = self._voice
        track.program_ctr += 1

    def __str__(self):
        return f'VOICE {self._voice}'


class VOL(M4ACommand):
    """Set track volume.

    Parameters
    ----------
    volume : int
        New track volume.

    """

    def __init__(self, volume):
        super().__init__(CMD.VOL, volume)
        self._volume = volume

    def __call__(self, track: M4ATrack):
        track.volume = self._volume
        track.out_vol = 0
        note_vol = 0
        for note in track.notes:
            note_vol = round(track.volume * note.volume * 255)
            note.set_volume(note_vol)
        track.out_vol = note_vol
        track.program_ctr += 1

    def __str__(self):
        return f'VOL {self._volume}'


class PAN(M4ACommand):
    """Set track panning.

    Parameters
    ----------
    panning : int
        New track panning.

    """

    def __init__(self, panning):
        super().__init__(CMD.PAN, panning)
        self._panning = panning

    def __call__(self, track: M4ATrack):
        track.panning = self._panning
        for note in track.notes:
            note.set_panning(track.panning)
        track.program_ctr += 1

    def __str__(self):
        return f'PAN {self._panning}'


class BEND(M4ACommand):
    """Set track pitch bend.

    Parameters
    ----------
    pitch_bend : int
        New track pitch bend.

    """

    def __init__(self, pitch_bend):
        super().__init__(CMD.BEND, pitch_bend)
        self._pitch_bend = pitch_bend

    def __call__(self, track: M4ATrack):
        track.pitch_bend = self._pitch_bend
        for note in track.notes:
            frequency = int(note.frequency * track.frequency)
            note.set_frequency(frequency)
        track.program_ctr += 1

    def __str__(self):
        return f'BEND {self._pitch_bend}'


class BENDR(M4ACommand):
    """Set track pitch range.

    Parameters
    ----------
    pitch_range : int
        New track pitch range.

    """

    def __init__(self, pitch_range):
        super().__init__(CMD.BENDR, pitch_range)
        self._pitch_range = pitch_range

    def __call__(self, track: M4ATrack):
        track.pitch_range = self._pitch_range
        for note in track.notes:
            frequency = int(note.frequency * track.frequency)
            note.set_frequency(frequency)
        track.program_ctr += 1

    def __str__(self):
        return f'BENDR {self._pitch_range}'


class LFOS(M4ACommand):
    """Set track LFO speed.

    Parameters
    ----------
    speed : int
        New track LFO speed.

    """

    def __init__(self, speed):
        super().__init__(CMD.LFOS, speed)
        self._speed = speed

    def __call__(self, track: M4ATrack):
        track.lfo_speed = self._speed
        track.program_ctr += 1

    def __str__(self):
        return f'LFOS {self._speed}'


class LFODL(M4ACommand):
    """Set track LFO delay.

    Parameters
    ----------
    delay : int
        New track LFO delay.

    """

    def __init__(self, delay):
        super().__init__(CMD.LFODL, delay)
        self._delay = delay

    def __call__(self, track: M4ATrack):
        track.program_ctr += 1

    def __str__(self):
        return f'LFODL {self._delay}'


class MOD(M4ACommand):
    """Set track modulation depth.

    Parameters
    ----------
    depth : int
        New track modulation depth.

    """

    def __init__(self, depth):
        super().__init__(CMD.MOD, depth)
        self._depth = depth

    def __call__(self, track: M4ATrack):
        track.mod = self._depth
        track.program_ctr += 1

    def __str__(self):
        return f'MOD {self._depth}'


class MODT(M4ACommand):
    """Set track modulation type.

    Parameters
    ----------
    mod : int
        New track modulation type.

    """

    def __init__(self, mod):
        super().__init__(CMD.MODT, mod)
        self._mod = mod
        self._type = ModArg(mod & 0b11)

    def __call__(self, track: M4ATrack):
        track.program_ctr += 1

    def __str__(self):
        return f'MODT {self._type.name}'


class TUNE(M4ACommand):
    """Set track micro-tuning.

    Parameters
    ----------
    micro_tones : int
        New track micro-tuning.

    """

    def __init__(self, micro_tones):
        super().__init__(CMD.TUNE, micro_tones)
        self._tuning = micro_tones

    def __call__(self, track: M4ATrack):
        track.program_ctr += 1

    def __str__(self):
        return f'TUNE {self._tuning}'


class XCMD(M4ACommand):
    """Extension command (primary use for pseudo echo).

    Parameters
    ----------
    extension : int
        Extension command.
    arg : int
        Argument to pass to extension.

    """

    def __init__(self, extension, arg):
        super().__init__(CMD.XCMD, extension, arg)
        self._extension = CMD(extension)
        self._arg = arg

    def __call__(self, track: M4ATrack):
        track.program_ctr += 1

    def __str__(self):
        return f'XCMD {self._extension.name} {self._arg}'


class EOT(M4ACommand):
    """End playback of TIE notes.

    Parameters
    ----------
    key : int, optional
        MIDI key of note to kill (default is None to kill all).

    """

    def __init__(self, key=None):
        super().__init__(NoteCMD.EOT, key)
        if key is not None:
            self._key = KeyArg(key)
        else:
            self._key = None

    def __call__(self, track: M4ATrack):
        if self._key is None:
            for note in track.notes:
                note.release()
        else:
            for note in track.notes:
                if note.midi_note != self._key:
                    continue
                note.release()
        track.program_ctr += 1

    def __str__(self):
        if self._key is not None:
            return f'EOT {self._key.name}'
        else:
            return f'EOT'


class NOTE(M4ACommand):
    """Start playback of a note for a finite number of ticks.

    Parameters
    ----------
    note_cmd : int
        Valid note command.
    key : int
        MIDI key.
    vel : int
        Velocity.
    gate : {1, 2, 3}, optional
        Optional value appended to the original tick length.

    """

    def __init__(self, note_cmd, key, vel, gate=None):
        if note_cmd == NoteCMD.TIE:
            self._ticks = -1
        elif note_cmd > NoteCMD.TIE:
            self._ticks = int(NoteCMD(note_cmd).name[1:])
            if gate is not None:
                self._ticks += gate
        else:
            raise ValueError('Invalid NOTE CMD.')
        self._key = key
        self._velocity = vel
        self._gate = gate
        super().__init__(note_cmd, self._key,
                         self._velocity, self._gate)

    def __call__(self, track: M4ATrack):
        note = FMODNote(self.ticks, self.key, self.velocity, track.voice)
        track.note_queue.put_nowait(note)
        track.program_ctr += 1

    def __str__(self):
        return f'{NoteCMD(self.cmd).name} ' \
               f'{self.key.name} ' \
               f'{self.velocity.name} ' \
               f'{self.gate.name if self._gate is not None else ""}'

    @property
    def ticks(self):
        return self._ticks

    @property
    def key(self):
        return KeyArg(self._key)

    @property
    def velocity(self):
        return VelocityArg(self._velocity)

    @property
    def gate(self):
        return GateArg(self._gate)
