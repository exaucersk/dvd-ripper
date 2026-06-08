dvd-ripper
==========

Small utility to batch-rip DVD discs (MakeMKV) and name output files as TV show episodes or movies.

Summary
-------

This tool automates ripping of DVD discs using MakeMKV's command-line tool `makemkvcon`. It scans the disc for titles whose duration falls inside a configured range (default 15–25 minutes for TV episodes, 60–180 minutes for movies), rips each matching title to a specified destination folder, renames the resulting MKV files to a consistent format, and ejects the disc when finished. A notification sound (src/dvd_ripper/ressources/bell.mp3) is played after each disc is finished.

Requirements
------------

- Python 3.14+
- MakeMKV (provides the `makemkvcon` CLI)
- playsound3 (packaged in the project virtualenv)

Installation
------------

1. Ensure `makemkvcon` is installed and available on your PATH. On most Linux distributions you can install MakeMKV from the official site or packaged repos.
2. Ensure you have `uv` installed. You can install it via:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Install the application globally on your machine using `uv`:

   **From this directory:**

   ```bash
   uv tool install .
   ```

   **Or directly from GitHub:**

   ```bash
   uv tool install git+https://github.com/exaucersk/dvd-ripper.git
   ```

This will automatically create an isolated environment and place the `dvd-ripper` command in your PATH.

Usage
-----

Run the tool from your terminal. Examples:

**TV Series Mode:**
```bash
dvd-ripper -S "My Show" -s 1 -d 2 -e 1
```

**Movie Mode:**
```bash
dvd-ripper -m -M "The Matrix" -y 1999
dvd-ripper --movie --movie-name "Inception"
```

Options

- -S: Series Name (required for TV mode)
- -s: Season number (required for TV mode)
- -d: Total number of discs to process (required for TV mode)
- -e: Start episode number (optional; default 1, TV mode only)
- -m, --movie: Enable movie mode
- -M, --movie-name: Movie name (required for movie mode)
- -y, --year: Movie year (optional, for disambiguation)
- -D, --device: MakeMKV device spec (e.g. `disc:0`, `disc:1`, `/dev/sr0`). Default: `disc:0`
- -h: Show usage and exit (exits with code 2)

Behavior

- **Disk space check**: Before ripping, the tool verifies at least 9 GB per disc is free at the save path. If insufficient, it exits with an error.
- **Name sanitization**: Series and movie names are cleaned of invalid characters (slashes, null bytes, leading/trailing dots and spaces) to prevent filesystem issues.
- **Input validation**: Season, total discs, and year are validated for reasonable ranges before processing.
- **TV Mode**: Calls `makemkvcon -r info {device}` to list titles and their durations. Titles with durations between 15 and 25 minutes are considered episodes and ripped. Files are saved under `~/Videos/{Series}/{Season}/` and renamed to the pattern: `{Series} - S{season}E{episode:02d}.mkv`.
- **Movie Mode**: Calls `makemkvcon -r info {device}` to list titles and their durations. Titles with durations between 60 and 180 minutes are considered movies and ripped. Files are saved under `~/Videos/Movies/{Movie Name}/` and renamed to the pattern: `{Movie Name} ({Year}).mkv` or `{Movie Name}.mkv` if no year is provided.
- After each disc is processed the tool ejects the disc and plays `src/dvd_ripper/ressources/bell.mp3`.
- TV mode supports multi-disc sets. Between discs, the tool polls for the next disc (waiting up to 2 minutes) instead of using a blind sleep delay.
- **Overwrite protection**: If a target filename already exists, the tool skips the rename to prevent data loss.
- **Partial file cleanup**: On a failed rip or cancelled operation (Ctrl+C), any partially written files are automatically removed.
- Movie mode assumes single disc only.

Notes & Caveats
---------------

- The tool requires MakeMKV with `makemkvcon` accessible on your PATH.
- It defaults the output base path to `~/Videos/` (inside your home directory).
- The default title-length limits are 15–25 minutes for TV episodes and 60–180 minutes for movies. Adjust `get_valid_titles(min_length, max_length, is_movie)` if needed.
- TV mode and movie mode are mutually exclusive — you cannot use both at the same time.
- Multiple optical drives can be targeted using the `-D`/`--device` flag (e.g. `disc:1`, `/dev/sr1`).

Project files
-------------

- src/dvd_ripper/main.py — main script containing the logic for scanning and ripping
- pyproject.toml — project metadata and dependency declaration
- src/dvd_ripper/ressources/bell.mp3 — notification sound played after ripping a disc
- testing/soundtesting.py — tiny test script to verify the bell sound

License
-------

This project is licensed under the MIT License — see the LICENSE file for details.

Contributing
------------

Open an issue or edit the repository and submit a PR. Small improvements to make the tool safer (configurable output path, better error handling, and unit tests) are recommended.

TODO: Allow Choosing Optical Drive
---------------------------------

✅ **Done:** The `-D`/`--device` flag is now available and defaults to `disc:0`. The device spec is propagated into `get_valid_titles()` and `rip_titles()`. Remaining tasks:

1. Add an environment variable fallback (e.g. `DVD_RIPPER_DEVICE`) so users can set a default device without changing CLI args.
2. Add a small integration test or local test script to exercise multiple drives.

Example usage:

```bash
dvd-ripper -S "My Show" -s 1 -d 2 -e 1 -D disc:1
# or
dvd-ripper -S "My Show" -s 1 -d 2 -D /dev/sr1
```
