# -*- coding: utf-8 -*-
"""CLI runner for SapPy."""
import argparse

from sappy.player import Player


def main():
    player = argparse.ArgumentParser()

    player.add_argument('path', help="path to the ROM to play")
    player.add_argument('song_num', type=int)
    player.add_argument('-st', '--song_table',
                        help="address of song table in rom", default=None)

    args = player.parse_args()
    if args.song_table:
        song_table = int(args.song_table, 16)
    else:
        song_table = None

    player = Player()
    player.play_song(args.path, args.song_num, song_table)


if __name__ == "__main__":
    main()
