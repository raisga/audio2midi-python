"""Real-model smoke tests: run the installed CLI end to end with demucs, basic-pitch and FFmpeg.

They are slow (CPU inference) and download ~500 MB of models on the first run, so they are
skipped unless AUDIO2MIDI_SMOKE=1 is set. Run them with `make smoke` (needs `pip install .`).
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SMOKE = os.environ.get("AUDIO2MIDI_SMOKE") == "1"
SAMPLE = Path(__file__).resolve().parents[1] / "sample" / "somber-minimalistic-bass.wav"
CLIP_START, CLIP_SECONDS = 5, 8  # an 8 second excerpt keeps CPU inference short
MODEL_SAMPLERATE, MODEL_CHANNELS = 44100, 2
BASS_MAX_MEDIAN_PITCH = 55  # G3, the sample is a low bass line


@unittest.skipUnless(SMOKE, "set AUDIO2MIDI_SMOKE=1 to run the real-model smoke tests")
class TestSmoke(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import soundfile

        cls.tmp = tempfile.TemporaryDirectory()
        cls.workdir = Path(cls.tmp.name)
        samplerate = soundfile.info(str(SAMPLE)).samplerate
        clip, _ = soundfile.read(
            str(SAMPLE),
            start=CLIP_START * samplerate,
            frames=CLIP_SECONDS * samplerate,
            dtype="float32",
            always_2d=True,
        )
        cls.clip = cls.workdir / "clip.wav"
        soundfile.write(str(cls.clip), clip, samplerate)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_cli(self, *args, input_file=None, expect_success=True):
        """Run `python -m audio2midi`, returning the process and the tracks directory parent."""
        input_file = Path(input_file or self.clip)
        output_dir = self.workdir / self._testMethodName
        command = [sys.executable, "-m", "audio2midi", "-f", str(input_file), "-o", str(output_dir), "-d", "cpu", *args]
        process = subprocess.run(command, capture_output=True, text=True, timeout=1800, check=False)
        if expect_success:
            self.assertEqual(process.returncode, 0, f"{process.stdout}\n{process.stderr}")
        return process, output_dir / input_file.stem

    def read_audio(self, path):
        import soundfile

        audio, samplerate = soundfile.read(str(path), always_2d=True)
        self.assertEqual(samplerate, MODEL_SAMPLERATE, path.name)
        self.assertEqual(audio.shape[1], MODEL_CHANNELS, path.name)
        self.assertAlmostEqual(len(audio) / samplerate, CLIP_SECONDS, delta=0.1, msg=path.name)
        return audio

    def assert_bass_midi(self, path):
        import numpy
        import pretty_midi

        notes = [note for instrument in pretty_midi.PrettyMIDI(str(path)).instruments for note in instrument.notes]
        self.assertTrue(notes, f"{path.name} has no notes")
        self.assertLess(numpy.median([note.pitch for note in notes]), BASS_MAX_MEDIAN_PITCH)

    def assert_files(self, directory, expected):
        self.assertEqual(sorted(path.name for path in directory.iterdir()), sorted(expected))

    def test_default_model_op_full(self):
        """htdemucs_ft (the default bag of 4 models): stems, complements and MIDI."""
        import numpy

        process, track_dir = self.run_cli("-s", "op_full", "-F", "wav")
        track_dir = track_dir / "op_full"
        stems = ["drums", "bass", "other", "vocals"]
        names = stems + [f"no_{stem}" for stem in stems]
        self.assert_files(track_dir, [f"{name}.{ext}" for name in names for ext in ("wav", "mid")])
        self.assertEqual(process.stdout.strip().splitlines(), [f"Saved 8 audio tracks and 8 MIDI files to {track_dir}"])

        audio = {name: self.read_audio(track_dir / f"{name}.wav") for name in names}
        others = audio["drums"] + audio["other"] + audio["vocals"]
        numpy.testing.assert_allclose(audio["no_bass"], others, atol=1e-3)

        # The sample is instrumental: separation should find a strong bass and (almost) no vocals.
        rms = {name: float(numpy.sqrt(numpy.mean(audio[name] ** 2))) for name in stems}
        self.assertGreater(rms["bass"], 0.02, rms)
        self.assertLess(rms["vocals"], rms["bass"] / 10, rms)
        self.assert_bass_midi(track_dir / "bass.mid")

    def test_six_stems_model_tracks(self):
        """htdemucs_6s: guitar and piano tracks only, flac, no MIDI."""
        _, track_dir = self.run_cli("-m", "htdemucs_6s", "-t", "guitar,piano", "-F", "flac", "--no-midi")
        track_dir = track_dir / "op_mini"
        self.assert_files(track_dir, ["guitar.flac", "piano.flac"])
        for name in ("guitar", "piano"):
            self.read_audio(track_dir / f"{name}.flac")

    def test_op_extra_compressed_mp3(self):
        """htdemucs: op_extra variations, compressed mp3, MIDI and log file."""
        _, track_dir = self.run_cli("-m", "htdemucs", "-s", "op_extra", "-t", "bass,drums", "-c", "-l")
        track_dir = track_dir / "op_extra"
        names = ["drums", "bass", "no_drums", "no_bass", "drums_bass"]
        self.assert_files(track_dir, [f"{name}.{ext}" for name in names for ext in ("mp3", "mid")] + ["audio2midi.log"])

        # Uncompressed exports are 320 kbps CBR (~322 KB here), compressed VBR ones ~190-210 KB.
        max_compressed_size = 0.8 * 320_000 / 8 * CLIP_SECONDS
        for name in names:
            path = track_dir / f"{name}.mp3"
            self.read_audio(path)
            self.assertLess(path.stat().st_size, max_compressed_size, f"{name}.mp3 was not compressed")
        self.assert_bass_midi(track_dir / "bass.mid")
        self.assertIn("Selected operation: op_extra", (track_dir / "audio2midi.log").read_text())

    def test_batch_folder(self):
        """A folder of files: one model load, a bad file reported, the others still processed."""
        folder = self.workdir / "batch"
        folder.mkdir()
        for name in ("first", "second"):
            (folder / f"{name}.wav").write_bytes(self.clip.read_bytes())
        (folder / "broken.mp3").write_text("this is not audio")

        process, _ = self.run_cli("-v", "-m", "htdemucs", "-t", "bass", "--no-midi",
                                  input_file=folder, expect_success=False)  # fmt: skip
        output = process.stdout + process.stderr
        self.assertEqual(process.returncode, 1, output)
        self.assertEqual(output.count("> Loading model htdemucs"), 1, output)
        self.assertIn(f"[1/3] Failed {folder / 'broken.mp3'}: Could not read audio file", output)
        self.assertIn("Processed 3 files: 2 succeeded, 1 failed", output)
        for name in ("first", "second"):
            track_dir = self.workdir / self._testMethodName / name / "op_mini"
            self.assert_files(track_dir, ["bass.mp3"])
            self.read_audio(track_dir / "bass.mp3")

    def test_unreadable_file(self):
        bad_file = self.workdir / "not_audio.mp3"
        bad_file.write_text("this is not audio")
        process, _ = self.run_cli("-m", "htdemucs", input_file=bad_file, expect_success=False)
        self.assertEqual(process.returncode, 1)
        self.assertIn("Could not read audio file", process.stdout + process.stderr)


if __name__ == "__main__":
    unittest.main()
