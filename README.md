# audio2midi-python

A command line tool that splits an audio file into its individual instrument tracks and generates MIDI files from each track. It turns simple recordings (demos, quick ideas) into files ready for use in a Digital Audio Workstation (DAW).

Python port of [audio2midi](https://github.com/raisga/audio2midi) (bash), with every planned feature of the original implemented.

## Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Operations](#operations)
- [Options](#options)
- [Development](#development)
- [Limitations](#limitations)
- [License](#license)

## Features

- **Track Separation**: Splits audio into instrument tracks (drums, bass, other, vocals, plus guitar and piano with `htdemucs_6s`) using [Demucs](https://github.com/facebookresearch/demucs).
- **MIDI Generation**: Creates a MIDI file from each track with Spotify's [Basic Pitch](https://github.com/spotify/basic-pitch), with tunable parameters.
- **Track Variations**: Exports complements (`no_vocals`, the whole mix without vocals) and track pairs (`bass_drums`).
- **Any Input Format**: mp3, wav, flac and anything else FFmpeg can read; exports mp3, wav or flac.
- **Batch Processing**: Process several files or whole folders in one run, loading the models only once.
- **Stems Cache**: Re-running a file with other options skips the slow separation.
- **Track Selection, Compression and Logging**: Pick only the tracks you need, shrink mp3 output, keep a log file per file.

## Prerequisites

- **Python 3.10 or 3.11**. 3.10 is recommended (see `.python-version`): on Linux, basic-pitch pulls in TensorFlow (~600 MB) on 3.11, and it cannot be installed at all on 3.12+.
- **FFmpeg**: used to read formats demucs can't decode natively and to compress mp3 output

## Installation

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install a2m
audio2midi --install   # checks FFmpeg (installs it with Homebrew on macOS)
```

This installs the `audio2midi` command, also available as `a2m` (`python -m audio2midi` works too). To install from a clone instead, run `pip install .` (or `make install`). `audio2midi --install` also reinstalls missing Python dependencies, and prints the command to install FFmpeg on Linux and Windows.

> On Linux without an NVIDIA GPU, install the CPU build of PyTorch first to save ~2 GB of downloads:
> `pip install torch --index-url https://download.pytorch.org/whl/cpu`

Models are downloaded from the Hugging Face hub on first use (~80 MB per Demucs model, `htdemucs_ft` bundles four).

## Usage

### Basic

```bash
audio2midi -f ./sample/djent_rock.mp3
```

### Advanced

```bash
audio2midi \
  --verbose \
  --file ./sample/djent_rock.mp3 \
  --select op_full \
  --outdir ./output \
  --model htdemucs_ft \
  --tracks bass,drums \
  --compress \
  --log
```

### Several files

```bash
audio2midi ./songs/*.mp3              # files as arguments (shell globs work)
audio2midi -f intro.wav -f outro.wav  # or repeated -f
audio2midi ./album                    # audio files in a folder
audio2midi -r ./discography           # ... and in its subfolders
```

Models are loaded once and reused for every file. A file that fails (unreadable, corrupt) is reported and the others are still processed; the exit code is 1 if any file failed:

```
[1/3] Saved 4 audio tracks and 4 MIDI files to output/intro/op_mini
[2/3] Failed album/broken.mp3: Could not read audio file album/broken.mp3
[3/3] Saved 4 audio tracks and 4 MIDI files to output/outro/op_mini
Processed 3 files: 2 succeeded, 1 failed
```

When scanning folders, hidden files and the output directory are skipped, and only audio extensions are picked up (mp3, wav, flac, ogg, opus, m4a, aac, aiff, alac, wma); files given explicitly are always processed. Inputs with the same name (`a/song.mp3` and `b/song.wav`) would share an output folder, so the run is refused before anything is processed.

### Output

For each file, the tool will:
1. Split the audio file into separate instrument tracks.
2. Build the track variations of the selected operation.
3. Convert each track to a MIDI file.
4. Save everything to `<outdir>/<audio file name>/<operation>/`:

```
output/djent_rock/op_full/
├── audio2midi.log      # with --log
├── bass.mp3
├── bass.mid
├── drums.mp3
├── drums.mid
├── no_bass.mp3
├── no_bass.mid
├── no_drums.mp3
└── no_drums.mid
```

### Stems cache

Separation is the slow step (minutes per song on CPU), so the separated stems are cached. Running a file again with a different `--select`, `--tracks`, `--format`, `--compress` or MIDI option reuses them, and the model is not even loaded:

```
$ audio2midi -f song.mp3                      # separates and caches the stems
$ audio2midi -f song.mp3 -s op_extra -F wav   # seconds, from the cache
Saved 14 audio tracks and 14 MIDI files to output/song/op_extra (cached stems)
```

- Entries are keyed by the file *content*, so a renamed or moved file is still found. Changing `--model`, `--shifts` or `--overlap`, or upgrading demucs, separates again.
- All stems are cached as lossless 24-bit FLAC, whatever `--tracks` selects: about 100 MB per 4 minutes of audio, more for dense mixes.
- The cache lives in `~/.cache/audio2midi` (`~/Library/Caches/audio2midi` on macOS, `%LOCALAPPDATA%\audio2midi` on Windows), or `$AUDIO2MIDI_CACHE_DIR`.
- It is limited to 2 GB by default, dropping the least recently used songs first. Set `$AUDIO2MIDI_CACHE_SIZE` to change it (`500MB`, `10GB`, `0` disables the cache).
- `--no-cache` skips it for one run, `--clear-cache` empties it.

## Operations

Separation runs once per file; every variation is mixed from the separated stems.

| Operation | Exports | 4 stems model |
|-----------|---------|---------------|
| `op_mini` (default) | each track: `bass` | 4 files |
| `op_full` | `op_mini` + each track's complement: `no_bass` (everything but the bass) | 8 files |
| `op_extra` | `op_full` + every pair of tracks mixed: `bass_drums` | 14 files |

With `--tracks`, only the selected tracks (and their complements / pairs) are exported. A complement is always the full mix minus that track.

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-h, --help` | Show the help message and exit | |
| `-V, --version` | Show the version and exit | |
| `-v, --verbose` | Show progress and details | off |
| `-i, --install` | Install dependencies (exits afterwards unless files are given) | |
| `-l, --log` | Save a log file in each output directory | off |
| `--cache / --no-cache` | Reuse cached stems from earlier runs (see [Stems cache](#stems-cache)) | on |
| `--clear-cache` | Delete the cached stems (exits afterwards unless files are given) | |
| `FILES...` / `-f, --file PATH` | Audio files or folders to process, `-f` is repeatable | |
| `-r, --recursive` | Also process audio files in the subfolders of folders | off |
| `-o, --outdir DIR` | Output directory | `output` |
| `-m, --model NAME` | `htdemucs`, `htdemucs_ft`, `htdemucs_6s`, `hdemucs_mmi`, `mdx`, `mdx_extra`, `mdx_q`, `mdx_extra_q` (the `_q` models need `pip install diffq`) | `htdemucs_ft` |
| `-s, --select OP` | `op_mini`, `op_full`, `op_extra` | `op_mini` |
| `-t, --tracks TRACKS` | Repeatable or comma separated: `drums`, `bass`, `other`, `vocals` (+ `guitar`, `piano` with `htdemucs_6s`) | all |
| `-F, --format FMT` | `mp3`, `wav`, `flac` | `mp3` |
| `-c, --compress` | Re-encode mp3 tracks as VBR with FFmpeg, stripping metadata | off |
| `-d, --device DEV` | `auto`, `cpu`, `cuda`, `mps` | `auto` |
| `--shifts N` | Demucs random shifts, better quality but N times slower | `1` |
| `--overlap X` | Overlap between separation windows | `0.25` |
| `-j, --jobs N` | Parallel separation jobs | `0` |
| `--midi / --no-midi` | Convert tracks to MIDI | on |
| `--onset-threshold X` | Basic Pitch onset threshold (0-1) | `0.5` |
| `--frame-threshold X` | Basic Pitch frame threshold (0-1) | `0.3` |
| `--min-note-length MS` | Minimum note length in milliseconds | `127.7` |
| `--min-frequency HZ` / `--max-frequency HZ` | Limit detected note frequencies | none |
| `--multiple-pitch-bends` | Allow overlapping notes to pitch bend | off |
| `--melodia / --no-melodia` | Apply the melodia trick | on |
| `--midi-tempo BPM` | Tempo written to the MIDI files | `120` |

## Development

```bash
make dev    # pip install -e ".[dev]"
make test   # unit tests
make smoke  # real-model smoke tests (slow, downloads ~500 MB of models once)
make lint   # ruff
make build  # sdist and wheel in dist/, checked with twine
make release  # GitHub release of the current version, which publishes it to PyPI
make run FILE=./sample/somber-minimalistic-bass.wav ARGS="-s op_extra"
```

The unit tests mock Demucs, Basic Pitch and FFmpeg, so they run without installing the package: `make test` only needs `click`.
The smoke tests (`tests/test_smoke.py`, skipped unless `AUDIO2MIDI_SMOKE=1`) run the installed CLI on an 8 second excerpt of the sample with the `htdemucs_ft`, `htdemucs_6s` and `htdemucs` models, and check the audio files, MIDI notes, compression and error handling.

CI runs lint and unit tests on every push and pull request. The smoke tests run weekly, on demand, and on pull requests that touch the dependencies or the code wrapping them.

```
src/audio2midi/
├── cli.py           # `audio2midi` command
├── __main__.py      # `python -m audio2midi`
├── constants.py     # operations, models, tracks, defaults
├── pipeline.py      # separate -> variations -> save -> MIDI -> compress
├── core/            # demucs, basic-pitch, ffmpeg and installer wrappers
├── flags/           # click options
└── utils/           # logging
tests/
```

### Dependency notes

- **Demucs 4.1+** is used through its `demucs.api.Separator` API and no longer needs torchaudio.
- **Basic Pitch** always runs its ONNX model with onnxruntime. Basic Pitch would otherwise pick the unmaintained `tflite-runtime` on Linux, which breaks with numpy 2. Both backends produce the same notes.
- **`setuptools<81`** is required because `resampy` (pinned `<0.4.3` by Basic Pitch) imports `pkg_resources`.

## Limitations

- **Audio Quality**: Separation and MIDI accuracy depend on the recording quality and complexity. Basic Pitch is built for pitched instruments, so drum MIDI is a rough approximation.
- **Processing Time**: Depends on the file length and hardware. On CPU, `htdemucs_ft` is about 4x slower than `htdemucs`.

## License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/raisga/audio2midi-python/blob/main/LICENSE) file for details.

## Acknowledgments

- **Demucs**: Open-source AI for music separation.
- **Basic Pitch**: MIDI generation tool by Spotify.
