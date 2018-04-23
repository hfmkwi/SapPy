from sappy.player import Player
import time
import argparse


def main():

    p = argparse.ArgumentParser()

    p.add_argument('path', help="path to the ROM to play")
    p.add_argument('song_num', type=int)
    p.add_argument('--song_table', help="address of song table in rom", default=None)
    p.add_argument('--width', type=int, help='width of a channel column', default=33)
    args = p.parse_args()
    if args.width < 17:
        width = 17
    else:
        width = args.width
    if args.song_table is not None:
        song_table = int(args.song_table, 16)
    else:
        song_table = None

    player = Player()

    player.WIDTH = width

    player.play_song(args.path, args.song_num, song_table)


if __name__ == "__main__":
    main()
