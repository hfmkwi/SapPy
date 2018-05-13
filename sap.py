from sappy.player import Player
import sappy.romio as romio
import sappy.config as config
import time
import argparse


def main():

    player = argparse.ArgumentParser()

    player.add_argument('path', help="path to the ROM to play")
    player.add_argument('song_num', type=int)
    player.add_argument('-st', '--song_table', help="address of song table in rom", default=None)
    player.add_argument('-w', '--width', type=int, help='width of a channel column', default=0)

    mixer = player.add_argument_group()
    mixer.add_argument('-mo', '--mixer_override', help='override default mixer', default=hex(config.DEFAULT_MIXER))
    args = player.parse_args()
    mixer_code = int(args.mixer_override, 16)
    if mixer_code != config.DEFAULT_MIXER:
        engine_mixer = romio.parse_mixer(mixer_code)
        if not romio.check_mixer(engine_mixer):
            print('Invalid mixer; using default mixer.')
            engine_mixer = None
    else:
        engine_mixer = None
    if args.width < 17:
        config.CHANNEL_WIDTH = 17
    else:
        config.CHANNEL_WIDTH = args.width
    if args.song_table:
        song_table = int(args.song_table, 16)
    else:
        song_table = None

    player = Player()
    player.play_song(args.path, args.song_num, song_table, engine_mixer)


if __name__ == "__main__":
    main()
