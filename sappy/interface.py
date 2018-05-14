# -*- coding: utf-8 -*-
import sys
import typing

import sappy.config as config
import sappy.engine as engine
import sappy.instructions as instructions

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
TABLE = 'Song table: '
SONG = 'Song address: '
VOICE = 'Voice table: '
ECHO = 'Reverb: '
CHANNEL = 'Track '
TEMPO = 'BPM'


HEADER_WIDTH = 16
POINTER_WIDTH = 10
TEMPO_WIDTH = len(TEMPO)
TICK_WIDTH = 2
NOTE_WIDTH = 4
TITLE_WIDTH = len(TITLE_TEXT)

TYPE_OVERRIDE = {
    engine.ChannelTypes.DIRECT: 'DSd',
    engine.ChannelTypes.DRUMKIT: 'Drm',
    engine.ChannelTypes.MULTI: 'Mul',
    engine.ChannelTypes.NOISE: 'Nse',
    engine.ChannelTypes.NULL: 'Nul',
    engine.ChannelTypes.SQUARE1: 'Sq1',
    engine.ChannelTypes.SQUARE2: 'Sq2',
    engine.ChannelTypes.WAVEFORM: 'Wav'
}

# Get width of longest type override
TYPE_WIDTH = len(sorted(TYPE_OVERRIDE.values(), key=len)[-1])

TEMPO_TOP = f'{DOWN_AND_HORIZONTAL}{"":{HORIZONTAL}>{TEMPO_WIDTH + PADDING}}{DOWN_AND_LEFT}'
TEMPO_BOTTOM = f'{VERTICAL_AND_HORIZONTAL}{"":{HORIZONTAL}>{TEMPO_WIDTH + PADDING}}{VERTICAL_AND_LEFT}'


def update_interface(player) -> str:
    """Update the user interface with the player data.

    The interface is divided into columns representing a channel each.
    Each column contains the current note volume, a visual representaion
    of the volume, all notes playing, and the number of remaining ticks.

    Notes
    -----
        The Z-order of the elements in ascending order is:
        bar, note/ticks, pan

        Sample interface column:

        | [  VOL/PAN  ] [NOTES] [TICKS] |

    """
    MAX_VOLUME = 255
    lines = []
    for channel in player.song.channels:
        channel: engine.Channel
        column = [" "] * config.CHANNEL_WIDTH
        vol_bar = ''

        if config.DISPLAY & 0b1: # Volume bar
            bars, vol_intvl = divmod(channel.output_volume, MAX_VOLUME / config.CHANNEL_WIDTH)

            bar_intvl = MAX_VOLUME / (config.CHANNEL_WIDTH * NUM_BLOCKS)
            end_bar = BLOCK_TABLE.get(NUM_BLOCKS - (vol_intvl // bar_intvl), '')

            vol_bar = FULL_BLOCK * int(bars) + end_bar
            insert_edpt = len(vol_bar)
            column[:insert_edpt] = vol_bar


        if config.DISPLAY & 0b100: # Notes
            names = []
            active_notes = filter(lambda x: not player.note_arr[x].note_off, channel.notes_playing)
            notes = list(map(lambda x: engine.get_note(player.note_arr[x].note_num), active_notes))
            names = ''.join([f'{note:>{NOTE_WIDTH}}' for note in notes][:config.CHANNEL_WIDTH // NOTE_WIDTH - 1])
            insert_stpt = config.CHANNEL_WIDTH - len(names) - NOTE_WIDTH
            insert_edpt = insert_stpt + len(names)
            column[insert_stpt:insert_edpt] = names

        if config.DISPLAY & 0b1000:
            insert_stpt = config.CHANNEL_WIDTH - TICK_WIDTH - 1
            insert_edpt = insert_stpt + TICK_WIDTH
            column[insert_stpt:insert_edpt] = f'{channel.wait_ticks:{TICK_WIDTH}}'

        if config.DISPLAY & 0b10: # Panning
            column[config.CHANNEL_WIDTH // 2] = VERTICAL
            insert_pt = round(channel.panning * (config.CHANNEL_WIDTH - 1) / instructions.mxv)
            column[insert_pt] = chr(0x2573)

        column = ''.join(column)
        t = TYPE_OVERRIDE.get(channel.type)
        lines.append(f'{t:^{TYPE_WIDTH + PADDING}}{VERTICAL}{column:<{config.CHANNEL_WIDTH}}')

    output = f'{VERTICAL}{VERTICAL.join(lines)}{VERTICAL} {player.tempo*2:>{TEMPO_WIDTH}} {VERTICAL}'
    return output


def print_exit_message(player) -> None:
    sys.stdout.write('\n')
    seperator = [f'{"":{HORIZONTAL}>{TYPE_WIDTH + PADDING}}{UP_AND_HORIZONTAL}{"":{HORIZONTAL}>{config.CHANNEL_WIDTH}}'] * len(player.song.channels)
    exit_str = UP_AND_RIGHT + UP_AND_HORIZONTAL.join(seperator) + f'{UP_AND_HORIZONTAL}{"":{HORIZONTAL}>{TEMPO_WIDTH + PADDING}}{UP_AND_LEFT}'
    sys.stdout.write('\n'.join((exit_str, 'Exiting...')))
    return


def get_player_info(player, meta_data) -> str:
    """Construct the interface header.

    Constructs a column-based display, with each column representing one
    channel. Each column contains the channel's ID and output type.

    """

    TITLE         = f'{VERTICAL} {TITLE_TEXT} {VERTICAL}'
    TITLE_TOP     = f'{DOWN_AND_RIGHT}{"":{HORIZONTAL}>{TITLE_WIDTH + PADDING}}{DOWN_AND_LEFT}'
    TITLE_BOTTOM  = f'{UP_AND_RIGHT}{"":{HORIZONTAL}>{TITLE_WIDTH + PADDING}}{UP_AND_LEFT}'
    HEADER_TOP    = f'{DOWN_AND_RIGHT}{"":{HORIZONTAL}>{HEADER_WIDTH}}{DOWN_AND_LEFT}'
    HEADER_ROM    = f'{VERTICAL}{meta_data.rom_name:^{HEADER_WIDTH}}{VERTICAL}'
    HEADER_CODE   = f'{VERTICAL}{meta_data.code:^{HEADER_WIDTH}}{VERTICAL}'
    TOP           = f'{VERTICAL_AND_RIGHT}{"":{HORIZONTAL}>{HEADER_WIDTH}}{VERTICAL_AND_HORIZONTAL}{"":{HORIZONTAL}>{POINTER_WIDTH}}{DOWN_AND_LEFT}'
    TABLE_POINTER = f'{VERTICAL}{TABLE:>{HEADER_WIDTH}}{VERTICAL}{f" 0x{meta_data.song_ptr:X}":<{POINTER_WIDTH}}{VERTICAL}'
    SONG_PTR      = f'{VERTICAL}{SONG:>{HEADER_WIDTH}}{VERTICAL}{f" 0x{meta_data.header_ptr:X}":<{POINTER_WIDTH}}{VERTICAL}'
    VOICE_PTR     = f'{VERTICAL}{VOICE:>{HEADER_WIDTH}}{VERTICAL}{f" 0x{meta_data.voice_ptr:X}":<{POINTER_WIDTH}}{VERTICAL}'
    REVERB        = f'{VERTICAL}{ECHO:>{HEADER_WIDTH}}{VERTICAL}{f" {(meta_data.echo-instructions.mxv-1)/instructions.mxv:<2.0%}" if meta_data.echo_enabled else " DISABLED":<{POINTER_WIDTH}}{VERTICAL}'
    BOTTOM        = f'{UP_AND_RIGHT}{"":{HORIZONTAL}>{HEADER_WIDTH}}{UP_AND_HORIZONTAL}{"":{HORIZONTAL}>{POINTER_WIDTH}}{UP_AND_LEFT}'

    info = '\n'.join(
        (TITLE_TOP, TITLE, TITLE_BOTTOM, HEADER_TOP, HEADER_ROM, HEADER_CODE,
         TOP, TABLE_POINTER, SONG_PTR, VOICE_PTR, REVERB, BOTTOM)) + '\n'

    return info + get_channel_table(player)


def get_channel_table(player) -> str:
    header = []
    for chan_id in range(len(player.song.channels)):
        header.append(f'{f"{CHANNEL}{chan_id}":^{config.CHANNEL_WIDTH + PADDING * 3}}')
    header.append(f'{TEMPO:^{TEMPO_WIDTH + PADDING}}')
    header = VERTICAL + VERTICAL.join(header) + VERTICAL

    TOP = [f'{"":{HORIZONTAL}>{config.CHANNEL_WIDTH + PADDING * 3}}'] * len(player.song.channels)
    BOTTOM = [f'{"":{HORIZONTAL}>{TYPE_WIDTH + PADDING}}{DOWN_AND_HORIZONTAL}{"":{HORIZONTAL}>{config.CHANNEL_WIDTH}}'] * len(player.song.channels)
    top = DOWN_AND_RIGHT + DOWN_AND_HORIZONTAL.join(TOP) + TEMPO_TOP
    bot = VERTICAL_AND_RIGHT + VERTICAL_AND_HORIZONTAL.join(BOTTOM) + TEMPO_BOTTOM
    return top + '\n' + header + '\n' + bot


def display(player) -> None:
    """Update and display the interface."""
    out = update_interface(player)
    sys.stdout.write(out + '\r')
    sys.stdout.flush()


def print_header(player, meta_data) -> None:
    header = get_player_info(player, meta_data)
    sys.stdout.write(header + '\n')
