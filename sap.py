from sappy.player import Player
import time
import argparse


def main():

    p = argparse.ArgumentParser()

    p.add_argument('path', help="path to the ROM to play")
    p.add_argument('song_num', type=int)
    p.add_argument('--song_table', type=int, help="address of song table in rom", default=None)
    p.add_argument('--width', type=int, help='width of a channel column', default=33)
    args = p.parse_args()

    player = Player()
    if args.width < 17:
        width = 17
    else:
        width = args.width
    player.WIDTH = width
    try:
        player.play_song(args.path, args.song_num, args.song_table)

    except KeyboardInterrupt:
        print("Exiting...")
        player.stop_song()
        exit(0)


if __name__ == "__main__":
    main()
