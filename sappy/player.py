import logging
import math
import os
import random
import sys
import time
import typing

import colorama

import sappy.decoder as decoder
import sappy.engine as engine
import sappy.fileio as fileio
import sappy.fmod as fmod

BASE = math.pow(2, 1 / 12)

CURSOR_UP_ONE = '\x1b[1A'
ERASE_LINE = '\x1b[2K'

colorama.init(autoreset=True)


class Player(object):
    DEBUG = False
    GB_SQ_MULTI = 0.5 / 4
    SAPPY_PPQN = 24
    WIDTH = 33

    if DEBUG:
        logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger(name=__name__)

    if WIDTH < 17:
        WIDTH = 17

    def __init__(self, volume=255):
        self._gbl_vol = volume
        self.looped = False
        self.gb1_channel = 255
        self.gb2_channel = 255
        self.gb3_channel = 255
        self.gb4_channel = 255
        self.tempo = 0
        self.note_arr = engine.Collection([engine.Note(*[0] * 6)] * 32)
        self.noise_wavs = [[[] for i in range(10)] for i in range(2)]
        self.channels = engine.ChannelQueue()
        self.directs = engine.DirectQueue()
        self.drumkits = engine.DrumKitQueue()
        self.insts = engine.InstrumentQueue()
        self.note_queue = engine.NoteQueue()
        self.samples = engine.SampleQueue()
        self.transpose = 0

        sz = 2048
        if not sz:
            sz = 2048
        for i in range(10):
            for _ in range(sz):
                self.noise_wavs[0][i].append(chr(int(random.random() * 153)))
            self.noise_wavs[0][i] = "".join(self.noise_wavs[0][i])
            for _ in range(256):
                self.noise_wavs[1][i].append(chr(int(random.random() * 153)))
            self.noise_wavs[1][i] = "".join(self.noise_wavs[1][i])

    @property
    def gbl_vol(self) -> int:
        """Global volume of the player."""
        return self._gbl_vol

    @gbl_vol.setter
    def gbl_vol(self, vol: int) -> None:
        fmod.setMasterVolume(vol)
        self._gbl_vol = vol

    def reset_player(self) -> None:
        self.channels.clear()
        self.drumkits.clear()
        self.samples.clear()
        self.insts.clear()
        self.directs.clear()
        self.note_queue.clear()

        for i in range(31, -1, -1):
            self.note_arr[i].enable = False

        self.gb1_channel = 255
        self.gb2_channel = 255
        self.gb3_channel = 255
        self.gb4_channel = 255

        self.tempo = 120

    def free_note(self) -> int:
        """Get a free note number.

        Notes
        ----
        On an actual AGB, only up to 32 notes may be played in tandem.

        Returns
        -------
        int
            On success, a number between 0 and 32. -1 otherwise.
        """
        for i in range(31, -1, -1):
            item = self.note_arr[i]
            if item.enable is False:
                return i
        return 255

    def dct_exists(self, dcts: engine.DirectQueue, dct_id: int) -> bool:
        """Check if a direct exists in a specfied `engine.DirectQueue`."""
        for dct in dcts:
            dct: engine.Direct
            if dct.key == str(dct_id):
                return True
        return False

    def drm_exists(self, patch: int) -> bool:
        """Check if a drumkit on the specified MIDI patch exists."""
        for drm in self.drumkits:
            if drm.key == str(patch):
                return True
        return False

    def inst_exists(self, patch: int) -> bool:
        """Check if an instrument on the specified MIDI patch is defined."""
        for inst in self.insts:
            if inst.key == str(patch):
                return True
        return False

    def load_sample(self,
                    fpath: str,
                    offset: typing.Union[int, str] = 0,
                    size: int = 0,
                    loop: bool = True,
                    gb_wave: bool = True):
        mode = fmod.FSoundModes._8BITS + fmod.FSoundModes.LOADRAW + fmod.FSoundModes.MONO
        if loop:
            mode += fmod.FSoundModes.LOOP_NORMAL
        if gb_wave:
            mode += fmod.FSoundModes.UNSIGNED
        else:
            mode += fmod.FSoundModes.SIGNED
        fpath = fpath.encode('ascii')
        index = fmod.FSoundChannelSampleMode.FREE
        return fmod.sampleLoad(index, fpath, mode, offset, size)

    def load_directsound(self, fpath: str) -> None:
        for smp in self.samples:
            smp: engine.Sample
            if smp.gb_wave is True:
                if self.val(smp.smp_data) == 0:
                    with fileio.open_new_file('temp.raw', 2) as f:
                        f.wr_str(smp.smp_data)
                    smp.fmod_smp = self.load_sample('temp.raw')
                    os.remove('temp.raw')
                else:
                    smp.fmod_smp = self.load_sample(fpath, smp.smp_data,
                                                    smp.size)
                self.log.debug(
                    f'| FMOD | CODE: {fmod.getError():4} | LOAD SMP   | S{smp.fmod_smp} | SIZE: {smp.size} |'
                )
                fmod.setLoopPoints(smp.fmod_smp, 0, 31)
                self.log.debug(
                    f'| FMOD | CODE: {fmod.getError():4} | SET LOOP   | 0-31')
                continue

            if self.val(smp.smp_data) == 0:
                with fileio.open_new_file('temp.raw', 2) as f:
                    f.wr_str(smp.smp_data)
                smp.fmod_smp = self.load_sample(
                    'temp.raw', loop=smp.loop, gb_wave=False)
                os.remove('temp.raw')
            else:
                smp.fmod_smp = self.load_sample(fpath, smp.smp_data, smp.size,
                                                smp.loop, False)
            self.log.debug(
                f'| FMOD | CODE: {fmod.getError():4} | LOAD SMP   | S{smp.fmod_smp} | SIZE: {smp.size} |'
            )
            fmod.setLoopPoints(smp.fmod_smp, smp.loop_start, smp.size - 1)
            self.log.debug(
                f'| FMOD | CODE: {fmod.getError():4} | SET LOOP   | {smp.loop_start}-{smp.size - 1}'
            )

    def load_square(self) -> None:
        high = chr(int(0x80 + 0x7F * self.GB_SQ_MULTI))
        low = chr(int(0x80 - 0x7F * self.GB_SQ_MULTI))
        for mx2 in range(4):
            sq = f'square{mx2}'
            f_sq = f'{sq}.raw'
            self.samples.add(sq)
            sample = self.samples[sq]
            if mx2 == 3:
                l = [high] * 24
                r = [low] * 8
                sample.smp_data = "".join(l + r)
            else:
                l = [high] * (2**(mx2 + 2))
                r = [low] * (32 - 2**(mx2 + 2))
                sample.smp_data = "".join(l + r)
            sample.freq = 7040
            sample.size = 32
            with fileio.open_new_file(f_sq, 2) as f:
                f.wr_str(sample.smp_data)

            sample.fmod_smp = self.load_sample(f_sq, 0, 0)
            self.log.debug(
                f'| FMOD | CODE: {fmod.getError():4} | LOAD SQRE{mx2} | S{sample.fmod_smp}'
            )
            fmod.setLoopPoints(sample.fmod_smp, 0, 31)
            self.log.debug(
                f'| FMOD | CODE: {fmod.getError():4} | SET LOOP   | (00, 31)')
            os.remove(f_sq)

    def load_noise(self) -> None:
        for i in range(10):
            nse = f'noise0{i}'
            self.samples.add(nse)
            f_nse = f'{nse}.raw'
            with self.samples[nse] as smp:
                smp.smp_data = self.noise_wavs[0][i]
                smp.freq = 7040
                smp.size = 16384
                with fileio.open_new_file(f_nse, 2) as f:
                    f.wr_str(smp.smp_data)
                smp.fmod_smp = self.load_sample(f_nse)
                self.log.debug(
                    f'| FMOD | CODE: {fmod.getError():4} | LOAD NSE0{i} | S{smp.fmod_smp}'
                )
                fmod.setLoopPoints(smp.fmod_smp, 0, 16383)
                self.log.debug(
                    f'| FMOD | CODE: {fmod.getError():4} | SET LOOP   | (0, 16383)'
                )
                os.remove(f_nse)

            nse = f'noise1{i}'
            self.samples.add(nse)
            f_nse = f'{nse}.raw'
            with self.samples[nse] as smp:
                smp.smp_data = self.noise_wavs[1][i]
                smp.freq = 7040
                smp.size = 256
                with fileio.open_new_file(f_nse, 2) as f:
                    f.wr_str(smp.smp_data)
                smp.fmod_smp = self.load_sample(f_nse)
                self.log.debug(
                    f'| FMOD | CODE: {fmod.getError():4} | LOAD NSE1{i} | S{smp.fmod_smp}'
                )
                fmod.setLoopPoints(smp.fmod_smp, 0, 255)
                self.log.debug(
                    f'| FMOD | CODE: {fmod.getError():4} | SET LOOP   | (0, 255)'
                )
                os.remove(f_nse)

    def init_player(self, fpath: str) -> None:
        fmod.setOutput(1)
        fmod.systemInit(44100, 64, 0)
        self.log.debug(f'| FMOD | CODE: {fmod.getError():4} | INIT       |')
        fmod.setMasterVolume(self.gbl_vol)
        self.log.debug(
            f'| FMOD | CODE: {fmod.getError():4} | SET VOL    | {self.gbl_vol}')

        self.load_directsound(fpath)
        self.load_noise()
        self.load_square()

        self.log.debug(f'| FMOD | CODE: {fmod.getError():4} | FINISH     |')

    def update_vibrato(self) -> None:
        for chan in self.channels:
            if not chan.enable or chan.vib_rate == 0 or chan.vib_depth == 0:
                continue
            for nid in chan.notes:
                item = self.note_arr[nid.note_id]
                if not item.enable or item.note_off:
                    continue
                v_pos = math.sin(math.pi * item.vib_pos) * chan.vib_depth
                pitch = (
                    chan.pitch_bend - 0x40 + v_pos) / 0x40 * chan.pitch_range
                freq = int(item.freq * math.pow(BASE, pitch))
                fmod.setFrequency(item.fmod_channel, freq)
                item.vib_pos += 1 / (96 / chan.vib_rate)
                item.vib_pos = math.fmod(item.vib_pos, 2)

    def update_notes(self) -> None:
        for item in self.note_arr:
            item: engine.Note
            if item.enable and item.wait_ticks > 0:
                item.wait_ticks -= 1
            if item.wait_ticks <= 0 and item.enable is True and item.note_off is False:
                if self.channels[item.parent].sustain is False:
                    item.reset()
                    if item.note_num in self.channels[item.parent].playing:
                        self.channels[item.parent].playing.remove(item.note_num)

    def update_channels(self) -> None:
        in_for = True
        for plat, chan in enumerate(self.channels):
            if chan.enable is False:
                self.log.debug(f'| CHAN: {plat:>4} | SKIP EXEC  |')
                continue
            if chan.wait_ticks > 0:
                chan.wait_ticks -= 1
            while chan.wait_ticks <= 0:
                evt_queue: engine.Event = chan.evt_queue[chan.pgm_ctr]
                cmd_byte = evt_queue.cmd_byte
                args = evt_queue.arg1, evt_queue.arg2, evt_queue.arg3

                if cmd_byte in (0xB1, 0xB6):
                    chan.enable = False
                    chan.sustain = False
                    in_for = False
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | STOP EXEC  |'
                    )
                    return
                elif cmd_byte == 0xB9:
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | COND JUMP  |'
                    )
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xBA:
                    chan.priority = args[0]
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xBB:
                    self.tempo = args[0] * 2
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET TEMPO  | TEMPO: {self.tempo:3}'
                    )
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xBC:
                    chan.transpose = engine.sbyte_to_int(args[0])
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET TRNPSE | TRNPSE: {chan.transpose:2}'
                    )
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xBD:
                    chan.patch_num = args[0]
                    if self.dct_exists(self.directs, chan.patch_num):
                        chan.output = self.directs[str(chan.patch_num)].output
                    elif self.inst_exists(chan.patch_num):
                        chan.output = engine.ChannelTypes.MULTI
                    elif self.drm_exists(chan.patch_num):
                        chan.output = engine.ChannelTypes.DRUMKIT
                    else:
                        chan.output = engine.ChannelTypes.NULL
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET OUTPUT | PATCH: {chan.patch_num:3} | T: {chan.output.name:>7}'
                    )
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xBE:
                    chan.main_vol = args[0]
                    for nid in chan.notes:
                        note: engine.Note = self.note_arr[nid.note_id]
                        if not note.enable or note.parent != plat:
                            continue
                        iv = note.velocity / 0x7F
                        cv = chan.main_vol / 0x7F
                        ie = note.env_pos / 0xFF
                        dav = iv * cv * ie * 255
                        vol = 0 if chan.mute else int(dav)
                        chan.volume = vol
                        fmod.setVolume(note.fmod_channel, vol)
                        self.log.debug(
                            f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | CODE: {fmod.getError():4} | SET VOLUME | FMOD: {note.fmod_channel:4} | NOTE: {nid.note_id:>4} | VOL: {chan.main_vol:5} | DAV: {dav:5}'
                        )
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xBF:
                    chan.panning = args[0]
                    pan = chan.panning * 2
                    for nid in chan.notes:
                        note = self.note_arr[nid.note_id]
                        if not note.enable or note.parent != plat:
                            continue
                        fmod.setPan(note.fmod_channel, pan)
                        self.log.debug(
                            f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | CODE: {fmod.getError():4} | SET PAN    | FMOD: {note.fmod_channel:4} | NOTE: {nid.note_id:>4} | PAN: {chan.panning:5} | DAP: {pan:5}'
                        )
                    chan.pgm_ctr += 1
                elif cmd_byte in (0xC0, 0xC1):
                    if cmd_byte == 0xC0:
                        chan.pitch_bend = args[0]
                    else:
                        chan.pitch_range = engine.sbyte_to_int(args[0])
                    chan.pgm_ctr += 1
                    for nid in chan.notes:
                        note: engine.Note = self.note_arr[nid.note_id]
                        if not note.enable or note.parent != plat:
                            continue
                        pitch = (
                            chan.pitch_bend - 0x40) / 0x40 * chan.pitch_range
                        freq = int(note.freq * math.pow(BASE, pitch))
                        fmod.setFrequency(note.fmod_channel, freq)
                        self.log.debug(
                            f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | PBEND      | CODE: {fmod.getError():4} | FMOD: {note.fmod_channel:4} | NOTE: {nid.note_id:>4} | BEND: {chan.pitch_bend:4} | DAP: {freq:5}'
                        )
                elif cmd_byte == 0xC2:
                    chan.vib_rate = chan.evt_queue[chan.pgm_ctr].arg1
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET VIBDP  | DEPTH: {chan.vib_rate:3}'
                    )
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xC4:
                    chan.vib_depth = chan.evt_queue[chan.pgm_ctr].arg1
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | SET VIBRT  | RATE: {chan.vib_depth:4}'
                    )
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xCE:
                    chan.sustain = False
                    for nid in chan.notes:
                        note: engine.Note = self.note_arr[nid.note_id]
                        if not note.enable or note.note_off:
                            continue
                        note.reset()
                        if note.note_num in chan.playing:
                            chan.playing.remove(note.note_num)
                        self.log.debug(
                            f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#6x} | CTRL: {cmd_byte:<#4x} | NOTE OFF   | NOTE: {nid.note_id:>4}'
                        )
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | NOTE OFF   | '
                    )
                    chan.pgm_ctr += 1
                elif cmd_byte == 0xB3:
                    chan.pgm_ctr = chan.subs[chan.sub_ctr].evt_q_ptr
                    chan.sub_ctr += 1
                    chan.rtn_ptr += 1
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | CALL SUB   | RTN: {chan.rtn_ptr:<#5x}'
                    )
                    chan.in_sub = True
                elif cmd_byte == 0xB4:
                    if chan.in_sub:
                        chan.pgm_ctr = chan.rtn_ptr
                        chan.in_sub = False
                        self.log.debug(
                            f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | END SUB    |'
                        )
                    else:
                        chan.pgm_ctr += 1
                    for nid in chan.notes:
                        note: engine.Note = self.note_arr[nid.note_id]
                        note.reset()
                        if note.note_num in chan.playing:
                            chan.playing.remove(note.note_num)
                elif cmd_byte == 0xB2:
                    self.looped = True
                    chan.in_sub = False
                    chan.pgm_ctr = chan.loop_ptr
                    chan.sustain = False
                    for nid in chan.notes:
                        note: engine.Note = self.note_arr[nid.note_id]
                        note.reset()
                        if note.note_num in chan.playing:
                            chan.playing.remove(note.note_num)
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | JUMP ADDR  | PTR: {chan.loop_ptr:<#5x}'
                    )
                elif cmd_byte >= 0xCF:
                    ll = engine.stlen_to_ticks(cmd_byte - 0xCF) + 1
                    if cmd_byte == 0xCF:
                        chan.sustain = True
                        ll = -1
                    nn, vv, uu = args
                    self.note_queue.add(nn, vv, plat, uu, ll, chan.patch_num)
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | ADD NOTE   | NOTE: {engine.note_to_name(nn):>4} | VEL: {vv:5} | LEN: {ll:5} | PATCH: {chan.patch_num:3}'
                    )
                    chan.pgm_ctr += 1
                elif cmd_byte <= 0xB0:
                    if self.looped:
                        self.looped = False
                        chan.wait_ticks = 0
                        continue
                    n_evt_queue = chan.evt_queue[chan.pgm_ctr + 1]
                    if chan.pgm_ctr > 0:
                        chan.wait_ticks = n_evt_queue.ticks - evt_queue.ticks
                    else:
                        chan.wait_ticks = n_evt_queue.ticks
                    chan.pgm_ctr += 1
                else:
                    self.log.debug(
                        f'| CHAN: {plat:>4} | PGM: {chan.pgm_ctr:<#5x} | CTRL: {cmd_byte:<#4x} | UNIMPLMTD  |'
                    )
                    chan.pgm_ctr += 1
            if not in_for:
                self.log.debug(f'| CHAN: {plat:>4} | STOP EXEC  | ')
                break

    def set_note(self, note: engine.Note, direct: engine.Direct):
        note.output = direct.output
        note.env_attn = direct.env_attn
        note.env_dcy = direct.env_dcy
        note.env_sus = direct.env_sus
        note.env_rel = direct.env_rel

    def get_delta_smp_freq(self, item: engine.Note):
        patch = str(item.patch_num)
        note_num = item.note_num
        das = daf = ''
        std_out = (engine.DirectTypes.DIRECT, engine.DirectTypes.WAVE)
        sqr_out = (engine.DirectTypes.SQUARE1, engine.DirectTypes.SQUARE2)
        if self.dct_exists(self.directs, patch):
            dct: engine.Direct = self.directs[patch]
            self.set_note(item, dct)
            self.log.debug(
                f'| CHAN: {item.parent:>4} | DCT EXISTS | NOTE: {note_num:4} | T: {item.output:>7} | ATTN: {item.env_attn:4} | DCY: {item.env_dcy:5} | SUS: {item.env_sus:5} | REL: {item.env_rel:5}'
            )
            if dct.output in std_out:
                das = str(self.directs[patch].smp_id)
                daf = engine.note_to_freq(note_num +
                                          (60 - self.directs[patch].drum_key),
                                          self.samples[das].freq)
                if self.samples[das].gb_wave:
                    daf /= 2
                self.log.debug(
                    f'| CHAN: {item.parent:>4} | DCT EXISTS | NOTE: {note_num:4} | STD OUT    | GB: {self.samples[das].gb_wave:6} | DAS: {das:>18} | DAF: {daf:>18}'
                )
            elif dct.output in sqr_out:
                das = f'square{self.directs[patch].gb1 % 4}'
                daf = engine.note_to_freq(note_num +
                                          (60 - self.directs[patch].drum_key))
            elif dct.output == engine.DirectTypes.NOISE:
                das = f'noise{self.directs[patch].gb1 % 2}{int(random.random() * 3)}'
                daf = engine.note_to_freq(note_num +
                                          (60 - self.directs[patch].drum_key))
        elif self.inst_exists(patch):
            dct: engine.Direct = self.insts[patch].directs[str(
                self.insts[patch].kmaps[str(note_num)].assign_dct)]
            self.set_note(item, dct)
            self.log.debug(
                f'| CHAN: {item.parent:>4} | INST EXIST | NOTE: {note_num:4} | T: {item.output:>7} | ATTN: {item.env_attn:4} | DCY: {item.env_dcy:5} | SUS: {item.env_sus:5} | REL: {item.env_rel:5}'
            )
            if dct.output in std_out:
                das = str(dct.smp_id)
                if dct.fix_pitch:
                    daf = self.samples[das].freq
                else:
                    daf = engine.note_to_freq(note_num, -2
                                              if self.samples[das].gb_wave else
                                              self.samples[das].freq)
                self.log.debug(
                    f'| CHAN: {item.parent:>4} | INST EXIST | NOTE: {note_num:4} | STD OUT    | FIX: {dct.fix_pitch:5} | DAS: {das:>18} | DAF: {daf:>18}'
                )
            elif dct.output in sqr_out:
                das = f'square{dct.gb1 % 4}'
                daf = engine.note_to_freq(note_num)
        elif self.drm_exists(patch):
            dct: engine.Direct = self.drumkits[patch].directs[str(note_num)]
            self.set_note(item, dct)
            self.log.debug(
                f'| CHAN: {item.parent:>4} | DRM EXISTS | NOTE: {note_num:4} | T: {item.output:>7} | ATTN: {item.env_attn:4} | DCY: {item.env_dcy:5} | SUS: {item.env_sus:5} | REL: {item.env_rel:5}'
            )
            if dct.output in std_out:
                das = str(dct.smp_id)
                if dct.fix_pitch and not self.samples[das].gb_wave:
                    daf = self.samples[das].freq
                else:
                    daf = engine.note_to_freq(dct.drum_key, -2
                                              if self.samples[das].gb_wave else
                                              self.samples[das].freq)
                self.log.debug(
                    f'| CHAN: {item.parent:>4} | DRM EXISTS | NOTE: {note_num:4} | STD OUT    | FIX: {dct.fix_pitch:5} | GB: {self.samples[das].gb_wave:6} | DAS: {das:>18} | DAF: {daf:>18}'
                )
            elif dct.output in sqr_out:
                das = f'square{dct.gb1 % 4}'
                daf = engine.note_to_freq(dct.drum_key)
            elif dct.output == engine.DirectTypes.NOISE:
                das = f'noise{dct.gb1 % 2}{int(random.random() * 10)}'
                daf = engine.note_to_freq(dct.drum_key)

        return das, daf

    def play_notes(self) -> None:
        for item in self.note_queue:
            note_num = self.free_note()
            self.log.debug(
                f'| FREE NOTE  | NOTE: {note_num:4} | ID: {engine.note_to_name(item.note_num):>6} |'
            )
            if note_num == 255:
                continue

            self.note_arr[note_num] = item
            chan = self.channels[item.parent]

            for nid in chan.notes:
                note = self.note_arr[nid.note_id]
                if note.enable is True and note.note_off is False:
                    if note.wait_ticks == -1:
                        if not chan.sustain:
                            note.reset()
                    else:
                        if chan.sustain:
                            note.reset()
                    if note.note_num in chan.playing:
                        chan.playing.remove(note.note_num)
                    self.log.debug(
                        f'| CHAN: {item.parent:>4} | NOTE: {nid.note_id:4} | NOTE OFF   |'
                    )

            chan.notes.add(note_num, str(note_num))
            if self.note_arr[note_num].note_num not in chan.playing:
                chan.playing.append(self.note_arr[note_num].note_num)
            das, daf = self.get_delta_smp_freq(item)
            if not das:
                return
            daf *= math.pow(BASE, self.transpose)
            dav = (item.velocity / 0x7F) * (chan.main_vol / 0x7F) * 255
            out_type = self.note_arr[note_num].output

            if out_type == engine.NoteTypes.SQUARE1:
                if self.gb1_channel < 32:
                    gb_note = self.note_arr[self.gb1_channel]
                    fmod.stopSound(gb_note.fmod_channel)
                    fmod.disableFX(gb_note.fmod_channel)
                    self.log.debug(
                        f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {fmod.getError():4} | STOP SQ1   | F{gb_note.fmod_channel:<9}'
                    )
                    gb_note.fmod_channel = 0
                    self.channels[gb_note.parent].notes.remove(
                        str(self.gb1_channel))
                    gb_note.enable = False
                self.gb1_channel = note_num
            elif out_type == engine.NoteTypes.SQUARE2:
                if self.gb2_channel < 32:
                    gb_note = self.note_arr[self.gb2_channel]
                    fmod.stopSound(gb_note.fmod_channel)
                    fmod.disableFX(gb_note.fmod_channel)
                    self.log.debug(
                        f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {fmod.getError():4} | STOP SQ2   | F{gb_note.fmod_channel:<9}'
                    )
                    gb_note.fmod_channel = 0
                    self.channels[gb_note.parent].notes.remove(
                        str(self.gb2_channel))
                    gb_note.enable = False
                self.gb2_channel = note_num
            elif out_type == engine.NoteTypes.WAVE:
                if self.gb3_channel < 32:
                    gb_note = self.note_arr[self.gb3_channel]
                    fmod.stopSound(gb_note.fmod_channel)
                    self.log.debug(
                        f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {fmod.getError():4} | STOP WAV   | F{gb_note.fmod_channel:<9}'
                    )
                    gb_note.fmod_channel = 0
                    self.channels[gb_note.parent].notes.remove(
                        str(self.gb3_channel))
                    gb_note.enable = False
                self.gb3_channel = note_num
            elif out_type == engine.NoteTypes.NOISE:
                if self.gb4_channel < 32:
                    gb_note = self.note_arr[self.gb4_channel]
                    fmod.stopSound(gb_note.fmod_channel)
                    self.log.debug(
                        f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {fmod.getError():4} | STOP NSE   | F{gb_note.fmod_channel:<9}'
                    )
                    gb_note.fmod_channel = 0
                    self.channels[gb_note.parent].notes.remove(
                        str(self.gb4_channel))
                    gb_note.enable = False
                self.gb4_channel = note_num

            pitch = (chan.pitch_bend - 0x40) / 0x40 * chan.pitch_range
            freq = int(daf * math.pow(BASE, pitch))
            pan = chan.panning * 2
            vol = 0 if chan.mute else int(dav)
            chan.volume = vol
            note: engine.Note = self.note_arr[note_num]
            note.freq = daf
            note.phase = engine.NotePhases.INITIAL
            if note.output == engine.NoteTypes.NOISE:
                continue

            note.fmod_channel = fmod.playSound(
                note_num, self.samples[das].fmod_smp, None, True)

            note.fmod_fx = fmod.enableFX(note.fmod_channel, 3)
            fmod.setEcho(note.fmod_fx, 0, 0, 333, 333, False)
            fmod.setFrequency(note.fmod_channel, freq)
            fmod.setVolume(note.fmod_channel, vol)
            fmod.setPan(note.fmod_channel, pan)
            fmod.setPaused(note.fmod_channel, False)
            assert fmod.getError() == 0
            self.log.debug(
                f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {fmod.getError():4} | PLAY SOUND | F{note.fmod_channel:<9} | DAS: {das:<5}'
            )
            self.log.debug(
                f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {fmod.getError():4} | SET FREQ   | DAF: {daf:>5}'
            )
            self.log.debug(
                f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {fmod.getError():4} | SET VOLUME | VOL: {vol:>5}'
            )
            self.log.debug(
                f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {fmod.getError():4} | SET PAN    | PAN: {pan:>5}'
            )
        self.note_queue.clear()

    def advance_notes(self) -> None:
        for note_id, item in enumerate(self.note_arr):
            if item.enable is False:
                continue
            if item.note_off and item.phase < engine.NotePhases.RELEASE:
                item.env_step = 0
                item.phase = engine.NotePhases.RELEASE
            if item.env_step == 0 or (item.env_pos == item.env_dest) or (
                    item.env_step == 0 and item.env_pos <= item.env_dest) or (
                        item.env_step >= 0 and item.env_pos >= item.env_dest):
                if item.output == engine.NoteTypes.DIRECT:

                    if item.phase == engine.NotePhases.INITIAL:
                        item.phase = engine.NotePhases.ATTACK
                        item.env_pos = 0
                        item.env_dest = 255
                        item.env_step = item.env_attn
                    elif item.phase == engine.NotePhases.ATTACK:
                        item.phase = engine.NotePhases.DECAY
                        item.env_dest = item.env_sus
                        item.env_step = (item.env_dcy - 0x100) / 2
                    elif item.phase in (engine.NotePhases.DECAY,
                                        engine.NotePhases.SUSTAIN):
                        item.phase = engine.NotePhases.SUSTAIN
                        item.env_step = 0
                    elif item.phase == engine.NotePhases.RELEASE:
                        item.phase = engine.NotePhases.NOTEOFF
                        item.env_dest = 0
                        item.env_step = item.env_rel - 0x100
                    elif item.phase == engine.NotePhases.NOTEOFF:
                        fmod.stopSound(item.fmod_channel)
                        self.log.debug(
                            f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {fmod.getError():4} | STOP SOUND | F{item.fmod_channel:<9}'
                        )
                        item.fmod_channel = 0
                        self.channels[item.parent].notes.remove(str(note_id))
                        item.enable = False
                else:
                    if item.phase == engine.NotePhases.INITIAL:
                        item.phase = engine.NotePhases.ATTACK
                        item.env_pos = 0
                        item.env_dest = 255
                        item.env_step = 0x100 - (item.env_attn * 8)
                    elif item.phase == engine.NotePhases.ATTACK:
                        item.phase = engine.NotePhases.DECAY
                        item.env_dest = 255 / item.env_sus * 2
                        item.env_step = (-item.env_dcy) / 2
                    elif item.phase == engine.NotePhases.RELEASE:
                        item.phase = engine.NotePhases.NOTEOFF
                        item.env_dest = 0
                        item.env_step = (0x8 - item.env_rel) * 2
                    elif item.phase in (engine.NotePhases.DECAY,
                                        engine.NotePhases.SUSTAIN):
                        item.phase = engine.NotePhases.SUSTAIN
                        item.env_step = 0
                    elif item.phase == engine.NotePhases.NOTEOFF:
                        if item.output == engine.NoteTypes.SQUARE1:
                            self.gb1_channel = 255
                        elif item.output == engine.NoteTypes.SQUARE2:
                            self.gb2_channel = 255
                        elif item.output == engine.NoteTypes.WAVE:
                            self.gb3_channel = 255
                        elif item.output == engine.NoteTypes.NOISE:
                            self.gb4_channel = 255
                        fmod.stopSound(item.fmod_channel)
                        self.log.debug(
                            f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {fmod.getError():4} | STOP SOUND | F{item.fmod_channel:<9}'
                        )
                        item.fmod_channel = 0
                        self.channels[item.parent].notes.remove(str(note_id))
                        item.enable = False

            nex = item.env_pos + item.env_step
            if nex > item.env_dest and item.env_step > 0 or nex < item.env_dest and item.env_step < 0:
                nex = item.env_dest
            item.env_pos = nex
            dav = (item.velocity / 0x7F) * (
                self.channels[item.parent].main_vol / 0x7F) * (
                    item.env_pos / 0xFF) * 255
            vol = 0 if self.channels[item.parent].mute else int(dav)
            self.channels[item.parent].volume = vol
            fmod.setVolume(item.fmod_channel, vol)
            self.log.debug(
                f'| CHAN: {item.parent:>4} | FMOD EXEC  | CODE: {fmod.getError():4} | SET VOLUME | VOL: {vol:>5}'
            )

    def evt_processor_timer(self) -> None:
        self.update_vibrato()
        self.update_notes()
        self.update_channels()
        self.play_notes()
        self.advance_notes()
        for channel in self.channels:
            if channel.enable:
                return 1
        fmod.systemClose()
        return None

    def get_player_header(self) -> str:
        self.update_channels()

        top = []
        for i, c in enumerate(self.channels):
            top.append(f'| CHAN{i:<2}{c.output.name:>{self.WIDTH - 8}} ')
        top.append('| TEMPO |')
        top = ''.join(top)
        bottom = '+' + '+'.join(
            [f'{"":->{self.WIDTH}}'] * self.channels.count) + '+-------+'
        return top + '\n' + bottom

    def display(self) -> None:
        out = self.update_interface()
        sys.stdout.write(out + '\r')
        sys.stdout.flush()

    def update_interface(self) -> str:
        lines = []
        for c in self.channels:
            c: engine.Channel
            vol = round(c.volume / (512 / (self.WIDTH - 1)))
            bar = f'{"":=>{vol}}'
            notes = []
            for n in map(engine.note_to_name, c.playing):
                notes.append(f'{n:^4}')
            notes.append(f'{c.wait_ticks:^3}')
            notes = ''.join(notes)
            double_bar = list(f'{bar + "|" + bar:^{self.WIDTH}}')
            vol = str(c.volume)
            double_bar[1:len(vol) + 1] = vol
            insert_pt = self.WIDTH - len(notes)
            double_bar[insert_pt:] = notes
            insert_pt = round(c.panning / (128 / (self.WIDTH - 1)))
            double_bar[insert_pt] = ':'
            bar = ''.join(double_bar)
            lines.append(f'{bar:^{self.WIDTH - 1}}')
        out = ['']
        for line in lines:
            out.append(f'{line:{self.WIDTH - 1}}')
        out.append('')
        out = f'{"|".join(out)}{self.tempo:>5}  |'
        return out

    def play_song(self, fpath: str, song_num: int, song_table: int) -> None:
        d = decoder.Decoder()
        self.reset_player()
        self.channels, self.drumkits, self.samples, self.insts, self.directs, self.meta_data = d.load_song(
            fpath, song_num, song_table)
        if len(self.channels) == 0:
            return
        self.init_player(fpath)

        header = self.get_player_header()
        print(header)
        self.process()

    def process(self):
        e = self.evt_processor_timer
        s = time.sleep
        r = round
        t = time.time
        while True:
            st = t()
            self.display()
            if e() is None:
                break
            tm = 60000.0 / (self.tempo * 24.0) / 1000.0
            if (t() - st) > tm:
                s(0)
                continue
            s(r(tm - (t() - st), 3))

    def val(self, expr: str) -> typing.Union[float, int]:
        if expr is None:
            return None
        try:
            f = float(expr)
            i = int(f)
            if f == i:
                return i
            return f
        except ValueError:
            out = []
            is_float = False
            is_signed = False
            is_hex = False
            is_octal = False
            is_bin = False
            sep = 0
            for char in expr:
                if char in '0123456789':
                    out.append(char)
                elif char in '-+':
                    if is_signed:
                        break
                    is_signed = True
                    out.append(char)
                elif char == '.':
                    if is_float:
                        break
                    if char not in out:
                        is_float = True
                        out.append(char)
                elif char == 'x':
                    if is_hex:
                        break
                    if char not in out and len(out) == 1 and out[0] == '0':
                        is_hex = True
                        out.append(char)
                    else:
                        return 0
                elif char == 'o':
                    if is_octal:
                        break
                    if char not in out and len(out) == 1 and out[0] == '0':
                        is_octal = True
                        out.append(char)
                    else:
                        return 0
                elif char == 'b':
                    if is_bin:
                        break
                    if char not in out and len(out) == 1 and out[0] == '0':
                        is_bin = True
                        out.append(char)
                    else:
                        return 0
                elif char in 'ABCDEFabcdef':
                    if is_hex:
                        out.append(char)
                        sep += 1
                elif char == '_':
                    if sep >= 0:
                        sep = 0
                        out.append(char)
                    else:
                        break
                elif char == ' ':
                    continue
                else:
                    break
            try:
                return eval(''.join(out))
            except SyntaxError:
                return 0

    def stop_song(self):
        self.reset_player()
        fmod.systemClose()
