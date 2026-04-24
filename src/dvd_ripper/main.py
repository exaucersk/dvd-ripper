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


def get_valid_titles(min_length: int = 15, max_length: int = 25):
    print("Scanning disc for titles...")

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


def rip_titles(*, titles: list[str], series_name: str, season: str, start_ep: int = 1):
    if not titles:
        print("No titles found matching the length requirements.")
        return start_ep
    else:
        home_path = Path.home()
        save_path = (home_path / "Videos" / series_name / season).absolute()
        save_path.mkdir(parents=True, exist_ok=True)

        # Start ripping each title
        current_ep = start_ep

        output = subprocess.DEVNULL  # Do not output anything

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
                new_filename = f"{series_name} - S{season}E{current_ep:02d}.mkv"
                new_file.rename(save_path / new_filename)
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

    # Set up the argument parser with a custom usage string to match your bash script
    parser = argparse.ArgumentParser(
        prog="dvd_ripper",
        usage="%(prog)s [-S Series Name] [-s Season] [-d Total Disc number] [-e The start episode] [-h help] [-v version]",
        add_help=False,  # We disable default help to handle -h exactly as requested
    )

    # Define the arguments
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

    # Validate that all required arguments are present
    if not args.series_name or not args.season or not args.total_discs:
        print("Error: Missing required arguments.")
        parser.print_usage()
        sys.exit(2)

    episode_counter = args.start_episode

    # Output the result
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
