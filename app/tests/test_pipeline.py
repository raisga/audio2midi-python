import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from lib.errors import Audio2MidiError
from lib.pipeline import PipelineConfig, run_pipeline
from lib.utils.logger import setup_logging

SOURCES = ['drums', 'bass', 'other', 'vocals']


class TestPipeline(unittest.TestCase):
    """Runs the pipeline with demucs, basic-pitch and FFmpeg replaced by fakes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output_dir = Path(self.tmp.name)
        setup_logging(verbose=False)

        model = SimpleNamespace(sources=SOURCES)
        stems = {name: float(index) for index, name in enumerate(SOURCES)}
        self.patch('lib.pipeline.separate.resolve_device', return_value='cpu')
        self.load_model = self.patch('lib.pipeline.separate.load_model', return_value=model)
        self.separate = self.patch('lib.pipeline.separate.separate', return_value=(stems, 44100))
        self.save_audio = self.patch('lib.pipeline.audio_io.save_audio')
        self.compress = self.patch('lib.pipeline.compress.compress_mp3')
        self.converter = self.patch('lib.pipeline.MidiConverter').return_value

    def patch(self, target, **kwargs):
        patcher = mock.patch(target, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def run_with(self, **kwargs):
        config = PipelineConfig(input_file=Path('songs/my.song.mp3'), output_dir=self.output_dir, **kwargs)
        return run_pipeline(config)

    def test_op_mini_layout(self):
        result = self.run_with()
        track_dir = self.output_dir / 'my.song' / 'op_mini'
        self.assertTrue(track_dir.is_dir())
        self.assertEqual(result.output_dir, track_dir)
        self.assertEqual(result.audio_files, [track_dir / f'{name}.mp3' for name in SOURCES])
        self.assertEqual(result.midi_files, [track_dir / f'{name}.mid' for name in SOURCES])
        self.load_model.assert_called_once_with('htdemucs_ft')
        self.assertEqual(self.converter.convert.call_count, 4)
        self.compress.assert_not_called()

    def test_tracks_keep_model_order(self):
        result = self.run_with(operation='op_full', tracks=('vocals', 'drums'), audio_format='wav')
        names = [path.name for path in result.audio_files]
        self.assertEqual(names, ['drums.wav', 'vocals.wav', 'no_drums.wav', 'no_vocals.wav'])
        saved_no_vocals = self.save_audio.call_args_list[3].args
        self.assertEqual(saved_no_vocals[0], 0.0 + 1.0 + 2.0)  # drums + bass + other

    def test_op_extra(self):
        result = self.run_with(operation='op_extra')
        self.assertEqual(len(result.audio_files), 14)

    def test_no_midi_and_compress(self):
        result = self.run_with(midi=False, compress=True)
        self.converter.convert.assert_not_called()
        self.assertEqual(result.midi_files, [])
        self.assertEqual([c.args[0] for c in self.compress.call_args_list], result.audio_files)

    def test_track_not_in_model(self):
        with self.assertRaises(Audio2MidiError):
            self.run_with(tracks=('guitar',))
        self.separate.assert_not_called()

    def test_log_file(self):
        self.run_with(log=True)
        log_file = self.output_dir / 'my.song' / 'op_mini' / 'audio2midi.log'
        setup_logging(verbose=False)  # closes the file handler
        self.assertIn('Selected operation: op_mini', log_file.read_text())


if __name__ == '__main__':
    unittest.main()
