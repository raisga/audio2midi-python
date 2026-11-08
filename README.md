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
- **Track Selection, Compression and Logging**: Pick only the tracks you need, shrink mp3 output, keep a log file per run.

## Prerequisites

- **Python 3.10** (see `.python-version`; basic-pitch does not support newer versions on every platform)
- **FFmpeg**: used to read audio files and compress mp3 output

## Installation

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python app/main.py --install   # or: make install
```

`--install` installs `requirements.txt` with pip and checks for FFmpeg (installed with Homebrew on macOS; on other platforms the command to run is printed).

> On Linux without an NVIDIA GPU, install the CPU build of PyTorch first to save ~2 GB of downloads:
> `pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu`

Models are downloaded on first use (~80 MB per Demucs model, `htdemucs_ft` bundles four).

## Usage

### Basic

```bash
python app/main.py -f ./sample/djent_rock.mp3
```

### Advanced

```bash
python app/main.py \
  --verbose \
  --file ./sample/djent_rock.mp3 \
  --select op_full \
  --outdir ./output \
  --model htdemucs_ft \
  --tracks bass,drums \
  --compress \
  --log
```

The tool will:
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
| `-i, --install` | Install dependencies (exits afterwards unless `-f` is given) | |
| `-l, --log` | Save a log file in the output directory | off |
| `-f, --file FILE` | Input audio file | |
| `-o, --outdir DIR` | Output directory | `output` |
| `-m, --model NAME` | `htdemucs`, `htdemucs_ft`, `htdemucs_6s`, `hdemucs_mmi`, `mdx`, `mdx_extra`, `mdx_q`, `mdx_extra_q` | `htdemucs_ft` |
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
make test                                   # python -m unittest discover -s app/tests -t app
make run FILE=./sample/somber-minimalistic-bass.wav ARGS="-s op_extra"
```

The unit tests mock Demucs, Basic Pitch and FFmpeg, so they only need `click` installed.

```
app/
├── main.py              # CLI entry point
└── lib/
    ├── constants.py     # operations, models, tracks, defaults
    ├── pipeline.py      # separate -> variations -> save -> MIDI -> compress
    ├── core/            # demucs, basic-pitch, ffmpeg and installer wrappers
    ├── flags/           # click options
    └── utils/           # logging
```

## Limitations

- **Audio Quality**: Separation and MIDI accuracy depend on the recording quality and complexity. Basic Pitch is built for pitched instruments, so drum MIDI is a rough approximation.
- **Processing Time**: Depends on the file length and hardware. On CPU, `htdemucs_ft` is about 4x slower than `htdemucs`.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **Demucs**: Open-source AI for music separation.
- **Basic Pitch**: MIDI generation tool by Spotify.
