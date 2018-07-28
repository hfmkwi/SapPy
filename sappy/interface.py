# -*- coding: utf-8 -*-
"""CLI display and update functionality."""
import curses
from math import fmod

from .cmd import FINE, GOTO, PREV, WAIT
from .m4a import M4ATrack

# Block characters
FULL_BLOCK = '█'
H_ONE_EIGHTH_BLOCK = '▏'
H_ONE_QUARTER_BLOCK = '▎'
H_THREE_EIGHTHS_BLOCK = '▍'
H_HALF_BLOCK = '▌'
H_FIVE_EIGHTHS_BLOCK = '▋'
H_THREE_QUARTERS_BLOCK = '▊'
H_SEVEN_EIGHTHS_BLOCK = '▉'
V_ONE_EIGHTH_BLOCK = '▁'
V_ONE_QUARTER_BLOCK = '▂'
V_THREE_EIGHTHS_BLOCK = '▃'
V_HALF_BLOCK = '▄'
V_FIVE_EIGHTHS_BLOCK = '▅'
V_THREE_QUARTERS_BLOCK = '▆'
V_SEVEN_EIGHTHS_BLOCK = '▇'

H_BLOCK_TABLE = {
    0: FULL_BLOCK,
    1: H_SEVEN_EIGHTHS_BLOCK,
    2: H_THREE_QUARTERS_BLOCK,
    3: H_FIVE_EIGHTHS_BLOCK,
    4: H_HALF_BLOCK,
    5: H_THREE_EIGHTHS_BLOCK,
    6: H_ONE_QUARTER_BLOCK,
    7: H_ONE_EIGHTH_BLOCK
}

V_BLOCK_TABLE = {
    0: FULL_BLOCK,
    1: V_SEVEN_EIGHTHS_BLOCK,
    2: V_THREE_QUARTERS_BLOCK,
    3: V_FIVE_EIGHTHS_BLOCK,
    4: V_HALF_BLOCK,
    5: V_THREE_EIGHTHS_BLOCK,
    6: V_ONE_QUARTER_BLOCK,
    7: V_ONE_EIGHTH_BLOCK
}

NUM_BLOCKS = len(H_BLOCK_TABLE)


class Display(object):
    def __init__(self, tracks):
        self.player_tracks = tracks
        self.scr = curses.initscr()
        self.init_scr()

        self.x, self.y = 0, 0

        self.title = Label(self.scr, 0, 0, 'M4A Engine Emulator', True)
        self.title.draw()
        self.tracks = [Track(self.scr, i, 0, (i + 1) * Track.HEIGHT) for i in
                       range(len(self.player_tracks))]
        self.c_views = []
        for tid, track in enumerate(self.player_tracks):
            x = (Track.WIDTH + 2) + tid * (CMDView.WIDTH + 2)
            self.c_views.append(CMDView(self.scr, tid, track, x, 3))

    def init_scr(self):
        curses.noecho()
        curses.cbreak()
        curses.nonl()
        curses.start_color()

        if curses.has_colors():
            curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
            curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
            curses.init_pair(3, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
            curses.init_pair(4, curses.COLOR_GREEN, curses.COLOR_BLACK)
            curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLACK)

        self.scr.nodelay(True)
        self.scr.keypad(True)
        self.scr.syncok(True)
        self.scr.bkgd(' ', curses.A_BOLD)
        self.scr.clear()

    def exit_scr(self):
        self.scr.syncok(False)
        self.scr.keypad(False)
        self.scr.nodelay(False)
        curses.nl()
        curses.nocbreak()
        curses.echo()
        curses.endwin()

    def update(self):
        c = self.scr.getch()
        if c == -1:
            pass
        elif c & curses.A_CHARTEXT:
            key = chr(c & curses.A_CHARTEXT).lower()
            if key == 'q':
                self.exit_scr()
                return False
            else:
                pass
        self.update_track()
        self.update_views()
        return True

    def update_track(self):
        for track in self.tracks:
            track.update(self.player_tracks[track.track_id])

    def update_views(self):
        for view in self.c_views:
            view.update()

    def draw(self):
        for track in self.tracks:
            track.draw()
        for view in self.c_views:
            view.draw()
        curses.doupdate()

    @staticmethod
    def wait(delay):
        ms = int(delay * 1000)
        if ms <= 0:
            return
        curses.delay_output(ms)


class Label(object):
    def __init__(self, scr, x: int, y: int, text: str, span: bool = False):
        self.text = text
        if span:
            self.width = scr.getmaxyx()[1]
        else:
            self.width = len(self.text) + 4
        self.height = 3
        self.scr = scr.subwin(self.height, self.width, y, x)
        self.scr.border()

    def draw(self):
        self.scr.addstr(1, 2, self.text)


class Track(object):
    WIDTH = 31
    HEIGHT = 3

    INTERVAL = 255 / (WIDTH * NUM_BLOCKS)

    def __init__(self, scr, track_id: int, x: int, y: int):
        self.track_id = track_id
        self.redraw_volume = True
        self.redraw_panning = True
        self.redraw_voice = True

        self.volume = None
        self.panning = None
        self.voice = None
        self.bars = None
        self.pan_pos = None
        self.current_voice = None

        self.voice_type = ''
        self.ticks = ''
        self.vol_output = ''
        self.vol_percent = ''

        self.x, self.y = x, y

        self.scr = scr.subwin(self.HEIGHT, self.WIDTH + 2, y, x)
        self.scr.border()
        self.scr.attrset(curses.A_BOLD)
        self.scr.addstr(0, 1, f'Track {track_id}')
        self.scr.addstr(2, self.WIDTH // 2 + 1, '+', curses.color_pair(5))

    def update(self, track: M4ATrack):
        self.redraw_volume = track.out_vol != self.volume
        self.redraw_panning = track.panning != self.panning
        self.redraw_voice = track.voice != self.voice
        self.volume = track.out_vol
        self.ticks = f'{track.ticks:>2}'
        self.panning = track.panning
        self.voice = track.voice
        if self.redraw_voice:
            self.voice_type = track.type.name
            self.current_voice = track.voice
        if self.redraw_volume:
            bars = self.volume / (255 / self.WIDTH)
            vol_interval = fmod(self.volume, 255 / self.WIDTH)

            block_id = NUM_BLOCKS - int(vol_interval) // int(self.INTERVAL)
            end_bar = H_BLOCK_TABLE.get(block_id, '')
            self.bars = int(bars)
            self.vol_output = f'{FULL_BLOCK * self.bars + end_bar:{self.WIDTH}}'
            self.vol_percent = f'{self.volume / 255:6.1%}'
        if self.redraw_panning:
            self.pan_pos = round(self.panning * (self.WIDTH - 1) / 254) + 1

    def draw(self):
        self.scr.addstr(1, 1, self.vol_output, curses.color_pair(4))
        self.scr.addstr(0, self.WIDTH - 8, self.vol_percent,
                        curses.color_pair(4))

        self.scr.addstr(1, self.pan_pos, FULL_BLOCK, curses.color_pair(5))
        self.scr.addstr(0, self.WIDTH - 1, self.ticks, curses.color_pair(2))
        self.scr.addstr(2, self.WIDTH - 2, f'{self.current_voice:3}')
        self.scr.addstr(2, 1, f'{self.voice_type:-<12}')
        self.scr.noutrefresh()


class CMDView(object):
    WIDTH = 17
    HEIGHT = 10
    BLOCK_TERMINATORS = (GOTO, WAIT, PREV, FINE)

    def __init__(self, scr, track_id, track, x, y):
        self.x, self.y = x, y
        self.track: M4ATrack = track
        self.track_id = track_id
        self.track_data = tuple(track.track_data.items())
        self.pos = 0
        self.prev_pos = 0
        self.redraw = True
        self.pattern = False

        # Init window
        self.scr = scr.subwin(self.HEIGHT + 2, self.WIDTH + 2, self.y, self.x)
        self.scr.box(0, 0)
        self.scr.addstr(0, 1, f'Track {self.track_id}')

    def update(self):
        self.pos = self.track.program_ctr
        self.prev_pos = self.track.base_ctr
        self.pattern = bool(self.track.call_stack)

    def draw(self):
        view = self.track_data[self.prev_pos:self.prev_pos + self.HEIGHT]
        pos = 0
        for pos, cmd in enumerate(view):
            if pos < self.pos - self.prev_pos:
                attr = curses.A_REVERSE
                if self.pattern:
                    attr |= curses.color_pair(5)
                else:
                    attr |= curses.color_pair(4)
            else:
                attr = curses.A_BOLD
            x, y = pos + 1, 1
            out = f'{str(cmd[1])[:self.WIDTH]:{self.WIDTH}}'

            self.scr.addnstr(x, y, out, self.WIDTH, attr)
        self.scr.noutrefresh()

        # Overwrite unmodified lines with whitespace
        for j in range(pos + 2, self.HEIGHT + 1):
            self.scr.addstr(j, 1, ' ' * self.WIDTH)

        # Draw CMD address
        x, y = self.HEIGHT + 1, 1
        if self.track.enabled:
            out = f'0x{self.track_data[self.pos][0]:6X}'
        else:
            out = f'DISABLED'

        if not self.track.enabled:
            attr = curses.color_pair(2)
        elif self.pattern:
            attr = curses.color_pair(5)
        else:
            attr = curses.color_pair(4)
        self.scr.addstr(x, y, out, attr)

        # Draw CMD execution area [UNUSED]
        # self.scr.addstr(self.HEIGHT + 1, 1, f'{self.prev_pos:3}|{self.pos:3}')
        self.scr.noutrefresh()
