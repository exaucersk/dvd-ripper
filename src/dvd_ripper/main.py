#!/usr/bin/env python3

import sys
import time
import re
import shutil
from pathlib import Path
import argparse
import subprocess
import importlib.metadata
from playsound3 import playsound


__version__ = importlib.metadata.version("dvd_ripper")


def get_valid_titles(
    min_length: int = 15, max_length: int = 25, is_movie: bool = False
):
    print("Scanning disc for titles...")

    if is_movie:
        min_length = 60 * 60
        max_length = 180 * 60
    else:
        min_length = min_length * 60
        max_length = max_length * 60

    # Run makemkvcon in 'robot' mode (-r) just to get info, not to rip
    command = ["makemkvcon", "-r", "info", "disc:0", f"--minlength={min_length}"]
    result = subprocess.run(command, capture_output=True, text=True)

    valid_titles = []

    # MakeMKV robot output formats title lengths like this:
    # TINFO:0,9,0,"1:20:30" (Title 0, attribute 9 is duration, value is 1:20:30)
    # We use regex to hunt for these specific lines
    pattern2 = r'TINFO:(\d+),9,0,"(\d+):(\d+):(\d+)"'

    for line in result.stdout.splitlines():
        match = re.search(pattern2, line)
        if match:
            title_id = match.group(1)
            hours = int(match.group(2))
            minutes = int(match.group(3))
            seconds = int(match.group(4))

            # Convert the timestamp into total seconds
            total_seconds = (hours * 3600) + (minutes * 60) + seconds

            # Check if it falls within our custom min/max range
            if min_length <= total_seconds <= max_length:
                valid_titles.append(title_id)
                print(f"Found valid Title {title_id} ({total_seconds} seconds)")
    return valid_titles


def rip_titles(
    *,
    titles: list[str],
    series_name: str | None = None,
    season: str | None = None,
    start_ep: int = 1,
    movie_name: str | None = None,
    year: str | None = None,
    is_movie: bool = False,
):
    if not titles:
        print("No titles found matching the length requirements.")
        return start_ep if not is_movie else 0
    else:
        home_path = Path.home()

        if is_movie:
            movie_folder = movie_name
            if year:
                movie_folder = f"{movie_name} ({year})"
            save_path = (home_path / "Videos" / "Movies" / movie_folder).absolute()
        else:
            save_path = (home_path / "Videos" / series_name / season).absolute()

        save_path.mkdir(parents=True, exist_ok=True)

        output = subprocess.DEVNULL

        current_ep = start_ep

        for title in titles:
            print(f"\nRipping Title {title}...")

            existing_files = set(save_path.glob("*.mkv"))

            rip_command = ["makemkvcon", "mkv", "disc:0", str(title), str(save_path)]
            result = subprocess.run(rip_command, stderr=output, stdout=output)

            if result.returncode != 0:
                print(f"❌ Failed to rip Title {title}. The process returned an error.")
                continue

            current_files = set(save_path.glob("*.mkv"))
            new_files = current_files - existing_files

            if len(new_files) == 1:
                new_file = new_files.pop()
                if is_movie:
                    if year:
                        new_filename = f"{movie_name} ({year}).mkv"
                    else:
                        new_filename = f"{movie_name}.mkv"
                else:
                    new_filename = f"{series_name} - S{season}E{current_ep:02d}.mkv"
                new_file.rename(save_path / new_filename)
                if is_movie:
                    print(f"✅ Successfully ripped movie: {new_filename}")
                else:
                    print(f"✅ Successfully ripped episode: {new_filename}")
                    current_ep += 1
            elif len(new_files) > 1:
                print(
                    f"⚠️ Warning: Multiple new files appeared. Skipping rename for Title {title} to prevent data loss."
                )
            else:
                print(
                    f"❌ Error: Makemkvcon reported success, but no new MKV file was found for Title {title}."
                )

        subprocess.run(["eject"])
        BASE_DIR = Path(__file__).resolve().parent
        bell_path = BASE_DIR / "ressources" / "bell.mp3"

        try:
            playsound(str(bell_path))
        except Exception as e:
            print(f"Notification sound failed: {e}")

        return current_ep


def main():
    if not shutil.which("makemkvcon"):
        print("Error: 'makemkvcon' not found in PATH. Please install MakeMKV.")
        sys.exit(1)
    if not shutil.which("eject"):
        print("Error: 'eject' not found in PATH.")
        sys.exit(1)

    # Set up the argument parser with a custom usage string
    parser = argparse.ArgumentParser(
        prog="dvd_ripper",
        usage="%(prog)s [-S Series Name] [-s Season] [-d Total Disc number] [-e Start episode] [-m] [-M Movie Name] [-y Year] [-h help] [-v version]",
        add_help=False,
    )

    # TV Series arguments
    parser.add_argument("-S", dest="series_name", help="Series Name")
    parser.add_argument("-s", dest="season", help="Season")
    parser.add_argument("-d", dest="total_discs", type=int, help="Total Discs")
    parser.add_argument(
        "-e",
        dest="start_episode",
        type=int,
        default=1,
        help="Which episode to start at.",
    )

    # Movie arguments
    parser.add_argument(
        "-m", "--movie", action="store_true", dest="is_movie", help="Movie mode"
    )
    parser.add_argument("-M", "--movie-name", dest="movie_name", help="Movie Name")
    parser.add_argument("-y", "--year", dest="year", help="Movie Year (optional)")

    parser.add_argument(
        "-h", action="store_true", dest="help", help="Show help message and exit"
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )

    # Parse the arguments from the command line
    args = parser.parse_args()

    # Handle the help flag manually to match the bash exit code (2)
    if args.help:
        parser.print_usage()
        sys.exit(2)

    # Validate mutual exclusivity between TV and Movie modes
    tv_mode = args.series_name or args.season or args.total_discs
    movie_mode = args.is_movie or args.movie_name

    if tv_mode and movie_mode:
        print("Error: Cannot use TV series mode and movie mode together.")
        parser.print_usage()
        sys.exit(2)

    # Validate TV mode requirements
    if tv_mode:
        if not args.series_name or not args.season or not args.total_discs:
            print(
                "Error: TV mode requires -S (Series Name), -s (Season), and -d (Total Discs)."
            )
            parser.print_usage()
            sys.exit(2)

    # Validate movie mode requirements
    if args.is_movie and not args.movie_name:
        print("Error: Movie mode requires -M (Movie Name).")
        parser.print_usage()
        sys.exit(2)

    if args.movie_name and not args.is_movie:
        print("Error: -M (Movie Name) requires -m (Movie mode) flag.")
        parser.print_usage()
        sys.exit(2)

    # Movie mode
    if args.is_movie:
        print(f"Starting movie rip for: {args.movie_name}")
        if args.year:
            print(f"Year: {args.year}")

        titles = get_valid_titles(is_movie=True)
        rip_titles(
            titles=titles,
            movie_name=args.movie_name,
            year=args.year,
            is_movie=True,
        )

        print(f"Ripping complete for {args.movie_name}!")
    else:
        # TV mode
        episode_counter = args.start_episode

        print(
            f"Starting batch rip for: {args.series_name}. Total Discs: {args.total_discs}"
        )

        for disc in range(1, args.total_discs + 1):
            print(f"{args.series_name} - Season {args.season} - Disc {disc}")

            padded_season = str(args.season).zfill(2)

            titles = get_valid_titles()
            episode_counter = rip_titles(
                titles=titles,
                series_name=args.series_name,
                season=padded_season,
                start_ep=episode_counter,
            )

            if disc < args.total_discs:
                input(
                    f"\n✅ Disc {disc} complete! Insert Disc {disc + 1} and press enter..."
                )
                print("\n\nLoading disc...")
                time.sleep(30)

        print(f"Ripping complete for {args.series_name} Season {args.season}!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nRipping cancelled.")
