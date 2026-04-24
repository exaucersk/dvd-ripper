#!/usr/bin/env python3

import sys
import time
import re
from pathlib import Path
import argparse
import subprocess
from playsound3 import playsound


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
    # pattern = r"Title #(\d+) was added \(\d cell\(s\), (\d+):(\d+):(\d+)\)"
    # strin = 'TINFO:7,9,0,"0:05:42"'

    pattern2 = r'TINFO:(\d+),\d,\d,"(\d):(\d+):(\d+)"'

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
        save_path = Path(home_path / f"/Videos/{series_name}/{season}").absolute()
        save_path.mkdir(parents=True, exist_ok=True)

        # Start ripping each title
        current_ep = start_ep

        output = subprocess.DEVNULL  # Do not output anything

        for title in titles:
            print(f"\nRipping Title {title}...")
            rip_command = ["makemkvcon", "mkv", "disc:0", title, save_path]
            subprocess.run(rip_command, stderr=output, stdout=output)

            # Rename all files in there
            for file in save_path.glob("*.mkv"):
                if f" - S{season}E" not in file.name:
                    new_filename = f"{series_name} - S{season}E{current_ep:02d}.mkv"
                    file.rename(save_path / new_filename)
                    print(f"✅ Successfully ripped episode: {new_filename}")

                    current_ep += 1
                    break

        subprocess.run(["eject"])
        BASE_DIR = Path(__file__).resolve().parent
        bell_path = BASE_DIR / "ressources" / "bell.mp3"
        playsound(str(bell_path))
        return current_ep


def main():
    # Set up the argument parser with a custom usage string to match your bash script
    parser = argparse.ArgumentParser(
        usage="%(prog)s [-S Series Name] [-s Season] [-d Total Disc number] [-e The start episode] [-h help]",
        add_help=False,  # We disable default help to handle -h exactly as requested
    )

    # Define the arguments
    parser.add_argument("-S", dest="series_name", help="Series Name")
    parser.add_argument("-s", dest="season", help="Season")
    parser.add_argument("-d", dest="total_discs", help="Total Discs")
    parser.add_argument("-e", dest="start_episode", help="Which episode to start at.")
    parser.add_argument(
        "-h", action="store_true", dest="help", help="Show help message and exit"
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

    total_discs = int(args.total_discs)

    if args.start_episode:
        episode_counter = int(args.start_episode)
    else:
        episode_counter = 1

    # Output the result
    print(f"Starting batch rip for: {args.series_name}. Total Discs: {total_discs}")

    for disc in range(1, total_discs + 1):
        print(f"{args.series_name} - Season {args.season} - Disc {disc}")

        padded_season = str(args.season).zfill(2)

        titles = get_valid_titles()
        episode_counter = rip_titles(
            titles=titles,
            series_name=args.series_name,
            season=padded_season,
            start_ep=episode_counter,
        )

        if disc < total_discs:
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
