dvd-ripper
==========

Small utility to batch-rip DVD discs (MakeMKV) and name output files as TV show episodes.

Summary
-------
This tool automates ripping of DVD discs using MakeMKV's command-line tool `makemkvcon`. It scans the disc for titles whose duration falls inside a configured range (default 15–25 minutes), rips each matching title to a specified destination folder, renames the resulting MKV files to a consistent "Series - SxxExx.mkv" format, and ejects the disc when finished. A notification sound (ressources/bell.mp3) is played after each disc is finished.

Requirements
------------
- Python 3.14+
- MakeMKV (provides the `makemkvcon` CLI)
- playsound3 (packaged in the project virtualenv)

Installation
------------
1. Ensure `makemkvcon` is installed and available on your PATH. On most Linux distributions you can install MakeMKV from the official site or packaged repos.
2. Create a virtual environment and install Python dependencies (optional but recommended):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt || python -m pip install playsound3
```

Note: This repository includes a small virtualenv under `.venv` for convenience. You may prefer to create your own.

Usage
-----
Run the script from the project root. Example:

```bash
./main.py -S "My Show" -s 1 -d 2 -e 1
```

Options
- -S: Series Name (required)
- -s: Season number (required)
- -d: Total number of discs to process (required)
- -e: Start episode number (optional; default 1)
- -h: Show usage and exit (exits with code 2)

Behavior
- The script calls `makemkvcon -r info disc:0` to list titles and their durations.
- Titles with durations between 15 and 25 minutes (configurable in code via get_valid_titles) are considered episodes and ripped.
- Files are saved under `/home/exo/Videos/{Series}/{Season}/` and renamed to the pattern: `{Series} - S{season}E{episode:02d}.mkv`.
- After each disc is processed the script ejects the disc and plays `ressources/bell.mp3`.

Notes & Caveats
----------------
- The script assumes a single optical drive with MakeMKV accessible as `makemkvcon`.
- It currently hardcodes the output base path to `/home/exo/Videos/` — change `save_path` in `rip_titles` if you want a different destination.
- The default title-length limits are in minutes (15–25). Adjust `get_valid_titles(min_length, max_length)` if needed.
- The script suppresses makemkvcon output (redirects stdout/stderr to /dev/null). Remove that behavior in `rip_titles` if you want to see progress logs.

Project files
-------------
- main.py — main script containing the logic for scanning and ripping
- pyproject.toml — project metadata and dependency declaration
- ressources/bell.mp3 — notification sound played after ripping a disc
- testing/soundtesting.py — tiny test script to verify the bell sound

License
-------
This project is licensed under the MIT License — see the LICENSE file for details.

Contributing
------------
Open an issue or edit the repository and submit a PR. Small improvements to make the script safer (configurable output path, better error handling, and unit tests) are recommended.

TODO: Allow Choosing Optical Drive
---------------------------------
Provide an option so users can select which optical drive / device to use (instead of the current hardcoded "disc:0"). Suggested tasks:

1. Add a CLI flag (e.g. `-D` / `--drive`) that accepts a MakeMKV device spec (e.g. `disc:0`, `disc:1`) or a system path (`/dev/sr0`). Default should remain `disc:0`.
2. Propagate the chosen device into `get_valid_titles()` and `rip_titles()` so the commands use the provided device instead of the hardcoded `disc:0`.
3. Validate the device early by running `makemkvcon -r info <device>` and display a clear error if it fails.
4. Add an environment variable fallback (e.g. `DVD_RIPPER_DEVICE`) so users can set a default device without changing CLI args.
5. Update usage examples in this README and add a small integration test or local test script to exercise multiple drives.

Example usage once implemented:

```bash
./main.py -S "My Show" -s 1 -d 2 -e 1 -D disc:1
# or
./main.py -S "My Show" -s 1 -d 2 -D /dev/sr1
```

This TODO is deliberately small and actionable so contributors can pick individual items.
