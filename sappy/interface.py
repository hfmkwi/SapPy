# -*- coding: utf-8 -*-
"""CLI display and update functionality."""
import sys
import typing

import sappy.config as config
import sappy.engine as engine
import sappy.cmdset as cmdset

# Box characters
LIGHT = 0
HEAVY = 1
BOX_STYLE = HEAVY
if BOX_STYLE == LIGHT:
    HORIZONTAL = '─'
    VERTICAL = '│'
    DOWN_AND_RIGHT = '┌'
    DOWN_AND_LEFT = '┐'
    UP_AND_RIGHT = '└'
    UP_AND_LEFT = '┘'
    VERTICAL_AND_RIGHT = '├'
    VERTICAL_AND_LEFT = '┤'
    DOWN_AND_HORIZONTAL = '┬'
    UP_AND_HORIZONTAL = '┴'
    VERTICAL_AND_HORIZONTAL = '┼'
elif BOX_STYLE == HEAVY:
    HORIZONTAL = '━'
    VERTICAL = '┃'
    DOWN_AND_RIGHT = '┏'
    DOWN_AND_LEFT = '┓'
    UP_AND_RIGHT = '┗'
    UP_AND_LEFT = '┛'
    VERTICAL_AND_RIGHT = '┣'
    VERTICAL_AND_LEFT = '┫'
    DOWN_AND_HORIZONTAL = '┳'
    UP_AND_HORIZONTAL = '┻'
    VERTICAL_AND_HORIZONTAL = '╋'
else:
    raise ValueError('Invalid line style.')


# Block characters
H_BOX = 0
V_BOX = 1
BLOCK_STYLE = H_BOX
FULL_BLOCK = '█'
if BLOCK_STYLE == H_BOX:
    ONE_EIGHTH_BLOCK = '▏'
    ONE_QUARTER_BLOCK = '▎'
    THREE_EIGHTHS_BLOCK = '▍'
    HALF_BLOCK = '▌'
    FIVE_EIGHTHS_BLOCK = '▋'
    THREE_QUARTERS_BLOCK = '▊'
    SEVEN_EIGHTHS_BLOCK = '▉'
elif BLOCK_STYLE == V_BOX:
    ONE_EIGHTH_BLOCK = '▁'
    ONE_QUARTER_BLOCK = '▂'
    THREE_EIGHTHS_BLOCK = '▃'
    HALF_BLOCK = '▄'
    FIVE_EIGHTHS_BLOCK = '▅'
    THREE_QUARTERS_BLOCK = '▆'
    SEVEN_EIGHTHS_BLOCK = '▇'
else:
    raise ValueError('Invalid block style.')

BLOCK_TABLE = {
    0: FULL_BLOCK,
    1: SEVEN_EIGHTHS_BLOCK,
    2: THREE_QUARTERS_BLOCK,
    3: FIVE_EIGHTHS_BLOCK,
    4: HALF_BLOCK,
    5: THREE_EIGHTHS_BLOCK,
    6: ONE_QUARTER_BLOCK,
    7: ONE_EIGHTH_BLOCK
}

NUM_BLOCKS = len(BLOCK_TABLE)

PADDING = 2
TITLE_TEXT = 'M4A ENGINE EMULATOR'
TABLE = 'Song table:'
SONG = 'Song address:'
VOICE = 'Voice table:'
ECHO = 'Reverb:'
CHANNEL = 'Track'
TEMPO = 'BPM'


HEADER_WIDTH = 16
POINTER_WIDTH = 10
TEMPO_WIDTH = len(TEMPO)
TICK_WIDTH = 2
NOTE_WIDTH = 4
TITLE_WIDTH = len(TITLE_TEXT)

TYPE_OVERRIDE = {
    engine.OutputType.DSOUND: 'DSd',
    engine.OutputType.DRUM: 'Drm',
    engine.OutputType.MULTI: 'Mul',
    engine.OutputType.PSG_NSE: 'Nse',
    engine.OutputType.NULL: 'Nul',
    engine.OutputType.PSG_SQ1: 'Sq1',
    engine.OutputType.PSG_SQ2: 'Sq2',
    engine.OutputType.PSG_WAVE: 'Wav'
}

# Get width of longest type override
TYPE_WIDTH = len(sorted(TYPE_OVERRIDE.values(), key=len)[-1])

TEMPO_TOP = f'{DOWN_AND_HORIZONTAL}{"":{HORIZONTAL}>{TEMPO_WIDTH + PADDING}}{DOWN_AND_LEFT}'
TEMPO_BOTTOM = f'{VERTICAL_AND_HORIZONTAL}{"":{HORIZONTAL}>{TEMPO_WIDTH + PADDING}}{VERTICAL_AND_LEFT}'


def update_track_display(player) -> str:
    """Update the user interface with the player data.

    Notes
    -----
        Z-order of output elements (ascending):
        Volume bar, notes, ticks, pan gauge

    """
    MAX_VOLUME = 255
    lines = []
    for channel in player.song.tracks:
        channel: engine.Track
        column = [" "] * config.CHANNEL_WIDTH
        vol_bar = ''

        if config.DISPLAY & 0b1: # Volume bar
            bars, vol_intvl = divmod(channel.out_vol, MAX_VOLUME / config.CHANNEL_WIDTH)

            bar_intvl = MAX_VOLUME / (config.CHANNEL_WIDTH * NUM_BLOCKS)
            end_bar = BLOCK_TABLE.get(NUM_BLOCKS - (vol_intvl // bar_intvl), '')

            vol_bar = FULL_BLOCK * int(bars) + end_bar
            insert_edpt = len(vol_bar)
            column[:insert_edpt] = vol_bar

        if config.DISPLAY & 0b100: # Notes
            active_notes = filter(lambda x: not player.note_arr[x].note_off, channel.used_notes)
            notes = map(lambda x: engine.get_note_name(player.note_arr[x].midi_note), active_notes)
            insert_pt = config.CHANNEL_WIDTH - NOTE_WIDTH - PADDING
            if config.DISPLAY & 0b1000:
                insert_pt -= TICK_WIDTH
            for note in notes:
                insert_pt += NOTE_WIDTH - len(note)
                if insert_pt < 0:
                    break
                column[insert_pt:insert_pt+len(note)] = note
                insert_pt -= len(note) + PADDING + 1

        if config.DISPLAY & 0b1000:
            tick_label = str(channel.wait_ticks)
            insert_stpt = config.CHANNEL_WIDTH - 1 - len(tick_label)
            column[insert_stpt:insert_stpt + len(tick_label)] = tick_label

        if config.DISPLAY & 0b10: # Panning
            column[config.CHANNEL_WIDTH // 2] = VERTICAL
            insert_pt = round(channel.panning * (config.CHANNEL_WIDTH - 1) / cmdset.mxv)
            column[insert_pt] = chr(0x2573)

        column = ''.join(column)
        t = TYPE_OVERRIDE.get(channel.type)
        lines.append(f'{t:^{TYPE_WIDTH + PADDING}}{VERTICAL}{column:<{config.CHANNEL_WIDTH}}')

    output = f'{VERTICAL}{VERTICAL.join(lines)}{VERTICAL} {player.tempo*2:>{TEMPO_WIDTH}} {VERTICAL}'
    return output


def print_exit_message(player) -> None:
    """Close off the track display and display an exit message."""
    sys.stdout.write('\n')
    seperator = [f'{"":{HORIZONTAL}>{TYPE_WIDTH + PADDING}}{UP_AND_HORIZONTAL}{"":{HORIZONTAL}>{config.CHANNEL_WIDTH}}'] * len(player.song.tracks)
    exit_str = UP_AND_RIGHT + UP_AND_HORIZONTAL.join(seperator) + f'{UP_AND_HORIZONTAL}{"":{HORIZONTAL}>{TEMPO_WIDTH + PADDING}}{UP_AND_LEFT}'
    sys.stdout.write('\n'.join((exit_str, 'Exiting...')))


def get_player_info(player, meta_data) -> str:
    """Construct the CLI interface header."""
    TITLE_TOP     = f'{DOWN_AND_RIGHT}{"":{HORIZONTAL}>{TITLE_WIDTH + PADDING}}{DOWN_AND_LEFT}'
    TITLE         = f'{VERTICAL} {TITLE_TEXT} {VERTICAL}'
    TITLE_BOTTOM  = f'{UP_AND_RIGHT}{"":{HORIZONTAL}>{TITLE_WIDTH + PADDING}}{UP_AND_LEFT}'
    HEADER_TOP    = f'{DOWN_AND_RIGHT}{"":{HORIZONTAL}>{HEADER_WIDTH}}{DOWN_AND_LEFT}'
    HEADER_ROM    = f'{VERTICAL} {meta_data.rom_name:^{HEADER_WIDTH - PADDING}} {VERTICAL}'
    HEADER_CODE   = f'{VERTICAL} {meta_data.code:^{HEADER_WIDTH - PADDING}} {VERTICAL}'
    TOP           = f'{VERTICAL_AND_RIGHT}{"":{HORIZONTAL}>{HEADER_WIDTH}}{VERTICAL_AND_HORIZONTAL}{"":{HORIZONTAL}>{POINTER_WIDTH}}{DOWN_AND_LEFT}'
    TABLE_POINTER = f'{VERTICAL} {TABLE:>{HEADER_WIDTH - PADDING}} {VERTICAL} {f"0x{meta_data.song_ptr:X}":<{POINTER_WIDTH - PADDING}} {VERTICAL}'
    SONG_PTR      = f'{VERTICAL} {SONG:>{HEADER_WIDTH - PADDING}} {VERTICAL} {f"0x{meta_data.main_ptr:X}":<{POINTER_WIDTH - PADDING}} {VERTICAL}'
    VOICE_PTR     = f'{VERTICAL} {VOICE:>{HEADER_WIDTH - PADDING}} {VERTICAL} {f"0x{meta_data.voice_ptr:X}":<{POINTER_WIDTH - PADDING}} {VERTICAL}'
    REVERB        = f'{VERTICAL} {ECHO:>{HEADER_WIDTH - PADDING}} {VERTICAL} {f"{(meta_data.reverb-cmdset.mxv-1)/cmdset.mxv:<2.0%}" if meta_data.echo_enabled else "DISABLED":<{POINTER_WIDTH - PADDING}} {VERTICAL}'
    BOTTOM        = f'{UP_AND_RIGHT}{"":{HORIZONTAL}>{HEADER_WIDTH}}{UP_AND_HORIZONTAL}{"":{HORIZONTAL}>{POINTER_WIDTH}}{UP_AND_LEFT}'

    info = '\n'.join(
        (TITLE_TOP, TITLE, TITLE_BOTTOM, HEADER_TOP, HEADER_ROM, HEADER_CODE,
         TOP, TABLE_POINTER, SONG_PTR, VOICE_PTR, REVERB, BOTTOM)) + '\n'

    return info + generate_track_display(player)


def generate_track_display(player) -> str:
    """Draw the table around the track display."""
    header = []
    for chan_id in range(len(player.song.tracks)):
        header.append(f'{f" {CHANNEL} {chan_id} ":>{config.CHANNEL_WIDTH + PADDING * 3}}')
    header.append(f'{TEMPO:^{TEMPO_WIDTH + PADDING}}')
    header = VERTICAL + VERTICAL.join(header) + VERTICAL

    TOP = DOWN_AND_HORIZONTAL.join([f'{"":{HORIZONTAL}>{config.CHANNEL_WIDTH + PADDING * 3}}'] * len(player.song.tracks))
    BOTTOM = VERTICAL_AND_HORIZONTAL.join([f'{"":{HORIZONTAL}>{TYPE_WIDTH + PADDING}}{DOWN_AND_HORIZONTAL}{"":{HORIZONTAL}>{config.CHANNEL_WIDTH}}'] * len(player.song.tracks))
    top = DOWN_AND_RIGHT + TOP + TEMPO_TOP
    bot = VERTICAL_AND_RIGHT + BOTTOM + TEMPO_BOTTOM
    return top + '\n' + header + '\n' + bot


def display(player) -> None:
    """Update and display track output."""
    out = update_track_display(player)
    sys.stdout.write(out + '\r')
    sys.stdout.flush()


def print_header(player, meta_data) -> None:
    """Display ROM and track meta-data."""
    header = get_player_info(player, meta_data)
    sys.stdout.write(header + '\n')
