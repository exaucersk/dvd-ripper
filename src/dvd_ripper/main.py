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

_rip_save_path: Path | None = None
_rip_existing_files: set[Path] | None = None


def sanitize_name(name: str) -> str:
    name = name.replace("/", "").replace("\\", "").replace("\x00", "")
    name = re.sub(r"\.{2,}", "", name)
    name = name.strip(". ")
    return name or "untitled"


def check_disk_space(path: Path, *, disc_count: int = 1) -> bool:
    """Return True if at least 9 GB per disc is free at path."""
    required_bytes = disc_count * 9 * 1024**3
    usage = shutil.disk_usage(path)
    if usage.free < required_bytes:
        free_gb = usage.free / (1024**3)
        needed_gb = required_bytes / (1024**3)
        print(
            f"❌ Not enough disk space at {path}. "
            f"Free: {free_gb:.1f} GB, needed: ~{needed_gb:.1f} GB."
        )
        return False
    return True


def get_valid_titles(
    min_length: int = 15,
    max_length: int = 25,
    is_movie: bool = False,
    device: str = "disc:0",
):
    print("Scanning disc for titles...")

    if is_movie:
        min_length = 60 * 60
        max_length = 180 * 60
    else:
        min_length = min_length * 60
        max_length = max_length * 60

    command = ["makemkvcon", "-r", "info", device, f"--minlength={min_length}"]
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Failed to scan disc: {result.stderr.strip()}")
        sys.exit(1)

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
    device: str = "disc:0",
):
    if not titles:
        print("No titles found matching the length requirements.")
        return start_ep
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

        disc_count = 1 if is_movie else len(titles)
        if not check_disk_space(save_path, disc_count=disc_count):
            sys.exit(1)

        current_ep = start_ep

        for title in titles:
            print(f"\nRipping Title {title}...")

            existing_files = set(save_path.glob("*.mkv"))

            global _rip_save_path, _rip_existing_files
            _rip_save_path = save_path
            _rip_existing_files = existing_files

            rip_command = ["makemkvcon", "mkv", device, str(title), str(save_path)]
            result = subprocess.run(rip_command, capture_output=True, text=True)

            _rip_save_path = None
            _rip_existing_files = None

            if result.returncode != 0:
                print(f"❌ Failed to rip Title {title}.")
                stderr_snippet = result.stderr.strip()[-500:] if result.stderr else ""
                if stderr_snippet:
                    print(f"   makemkvcon: {stderr_snippet}")
                new_files = set(save_path.glob("*.mkv")) - existing_files
                for f in new_files:
                    f.unlink(missing_ok=True)
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
                target = save_path / new_filename
                if target.exists():
                    print(
                        f"⚠️ File '{new_filename}' already exists. Skipping rename to prevent overwrite."
                    )
                else:
                    new_file.rename(target)
                    if is_movie:
                        print(f"✅ Successfully ripped movie: {new_filename}")
                    else:
                        print(f"✅ Successfully ripped episode: {new_filename}")
                        current_ep += 1
            elif len(new_files) > 1:
                print(
                    f"⚠️ Warning: Multiple new files appeared for Title {title}. Skipping rename to prevent data loss."
                )
                if not is_movie:
                    current_ep += 1
            else:
                print(
                    f"❌ Error: Makemkvcon reported success, but no new MKV file was found for Title {title}."
                )

        eject_result = subprocess.run(
            ["eject"], capture_output=True, text=True
        )
        if eject_result.returncode != 0:
            print(
                f"⚠️ Could not eject disc: {eject_result.stderr.strip()}"
            )
        BASE_DIR = Path(__file__).resolve().parent
        bell_path = BASE_DIR / "ressources" / "bell.mp3"

        try:
            playsound(str(bell_path))
        except Exception as e:
            print(f"Notification sound failed: {e}")

        return current_ep


def wait_for_disc(device: str = "disc:0", timeout: int = 120, interval: int = 3) -> bool:
    print("Waiting for disc...")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["makemkvcon", "-r", "info", device],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return True
        time.sleep(interval)
    print("❌ Timed out waiting for disc.")
    return False


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
        usage="%(prog)s [-S Series Name] [-s Season] [-d Total Disc number] [-e Start episode] [-m] [-M Movie Name] [-y Year] [-D Device] [-h help] [-v version]",
        add_help=False,
    )

    # TV Series arguments
    parser.add_argument("-S", dest="series_name", help="Series Name")
    parser.add_argument("-s", dest="season", type=int, help="Season number")
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
    parser.add_argument("-y", "--year", dest="year", type=int, help="Movie Year (optional)")
    parser.add_argument(
        "-D", "--device", dest="device", default="disc:0",
        help="MakeMKV device spec (e.g. disc:0, disc:1, /dev/sr0). Default: disc:0",
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

    # Validate mutual exclusivity between TV and Movie modes
    tv_mode = args.series_name or args.season or args.total_discs
    movie_mode = args.is_movie or args.movie_name

    if tv_mode and movie_mode:
        print("Error: Cannot use TV series mode and movie mode together.")
        parser.print_usage()
        sys.exit(2)

    # Validate TV mode requirements
    if tv_mode:
        if not args.series_name or args.season is None or not args.total_discs:
            print(
                "Error: TV mode requires -S (Series Name), -s (Season), and -d (Total Discs)."
            )
            parser.print_usage()
            sys.exit(2)
        if args.season < 1:
            print("Error: Season must be a positive integer.")
            sys.exit(2)
        if args.total_discs < 1:
            print("Error: Total Discs must be a positive integer.")
            sys.exit(2)
        args.series_name = sanitize_name(args.series_name)

    # Validate movie mode requirements
    if args.is_movie and not args.movie_name:
        print("Error: Movie mode requires -M (Movie Name).")
        parser.print_usage()
        sys.exit(2)

    if args.movie_name and not args.is_movie:
        print("Error: -M (Movie Name) requires -m (Movie mode) flag.")
        parser.print_usage()
        sys.exit(2)

    if args.movie_name:
        args.movie_name = sanitize_name(args.movie_name)
    if args.year is not None and (args.year < 1888 or args.year > 2100):
        print("Error: Year must be between 1888 and 2100.")
        sys.exit(2)

    # Movie mode
    if args.is_movie:
        print(f"Starting movie rip for: {args.movie_name}")
        if args.year:
            print(f"Year: {args.year}")

        titles = get_valid_titles(is_movie=True, device=args.device)
        rip_titles(
            titles=titles,
            movie_name=args.movie_name,
            year=args.year,
            is_movie=True,
            device=args.device,
        )

        print(f"Ripping complete for {args.movie_name}!")
    else:
        # TV mode
        episode_counter = args.start_episode

        print(
            f"Starting batch rip for: {args.series_name}. Total Discs: {args.total_discs}"
        )

        tv_save_path = (
            Path.home() / "Videos" / args.series_name / str(args.season).zfill(2)
        )
        tv_save_path.mkdir(parents=True, exist_ok=True)
        if not check_disk_space(tv_save_path, disc_count=args.total_discs):
            sys.exit(1)

        for disc in range(1, args.total_discs + 1):
            print(f"{args.series_name} - Season {args.season} - Disc {disc}")

            padded_season = str(args.season).zfill(2)

            titles = get_valid_titles(device=args.device)
            episode_counter = rip_titles(
                titles=titles,
                series_name=args.series_name,
                season=padded_season,
                start_ep=episode_counter,
                device=args.device,
            )

            if disc < args.total_discs:
                input(
                    f"\n✅ Disc {disc} complete! Insert Disc {disc + 1} and press enter..."
                )
                if not wait_for_disc(device=args.device):
                    print("❌ Disc not detected. Aborting batch rip.")
                    sys.exit(1)

        print(f"Ripping complete for {args.series_name} Season {args.season}!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        if _rip_save_path is not None and _rip_existing_files is not None:
            current_files = set(_rip_save_path.glob("*.mkv"))
            partial_files = current_files - _rip_existing_files
            for f in partial_files:
                f.unlink(missing_ok=True)
            print(f"\n\nRipping cancelled. Removed {len(partial_files)} partial file(s).")
        else:
            print("\n\nRipping cancelled.")
