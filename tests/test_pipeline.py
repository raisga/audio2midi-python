import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from audio2midi.errors import Audio2MidiError
from audio2midi.pipeline import FileFailure, PipelineConfig, run_pipeline
from audio2midi.utils.logger import setup_logging

SOURCES = ['drums', 'bass', 'other', 'vocals']


class TestPipeline(unittest.TestCase):
    """Runs the pipeline with demucs, basic-pitch and FFmpeg replaced by fakes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output_dir = Path(self.tmp.name)
        setup_logging(verbose=False)

        separator = SimpleNamespace(model=SimpleNamespace(sources=SOURCES))
        stems = {name: float(index) for index, name in enumerate(SOURCES)}
        self.patch('audio2midi.pipeline.separate.resolve_device', return_value='cpu')
        self.load_separator = self.patch('audio2midi.pipeline.separate.load_separator', return_value=separator)
        self.separate = self.patch('audio2midi.pipeline.separate.separate', return_value=(stems, 44100))
        self.save_audio = self.patch('audio2midi.pipeline.audio_io.save_audio')
        self.compress = self.patch('audio2midi.pipeline.compress.compress_mp3')
        self.midi_converter = self.patch('audio2midi.pipeline.MidiConverter')
        self.converter = self.midi_converter.return_value

    def patch(self, target, **kwargs):
        patcher = mock.patch(target, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def run_batch(self, files, on_result=None, **kwargs):
        config = PipelineConfig(output_dir=self.output_dir, **kwargs)
        return run_pipeline(config, [Path(path) for path in files], on_result)

    def run_with(self, **kwargs):
        batch = self.run_batch(['songs/my.song.mp3'], **kwargs)
        self.assertEqual(batch.failures, [])
        return batch.results[0]

    def test_op_mini_layout(self):
        result = self.run_with()
        track_dir = self.output_dir / 'my.song' / 'op_mini'
        self.assertTrue(track_dir.is_dir())
        self.assertEqual(result.output_dir, track_dir)
        self.assertEqual(result.input_file, Path('songs/my.song.mp3'))
        self.assertEqual(result.audio_files, [track_dir / f'{name}.mp3' for name in SOURCES])
        self.assertEqual(result.midi_files, [track_dir / f'{name}.mid' for name in SOURCES])
        self.load_separator.assert_called_once_with(
            'htdemucs_ft', device='cpu', shifts=1, overlap=0.25, jobs=0, progress=False
        )
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
        self.assertIn('Selected operation: op_mini', log_file.read_text())

    def test_models_are_loaded_once_for_a_batch(self):
        batch = self.run_batch(['a.mp3', 'b.wav', 'c.flac'])
        self.assertEqual([result.output_dir.parent.name for result in batch.results], ['a', 'b', 'c'])
        self.load_separator.assert_called_once()
        self.midi_converter.assert_called_once()
        self.assertEqual(self.separate.call_count, 3)
        self.assertEqual(self.converter.convert.call_count, 12)

    def test_each_file_gets_its_own_log(self):
        self.run_batch(['a.mp3', 'b.mp3'], log=True)
        log_a = (self.output_dir / 'a' / 'op_mini' / 'audio2midi.log').read_text()
        log_b = (self.output_dir / 'b' / 'op_mini' / 'audio2midi.log').read_text()
        self.assertIn('Input file: a.mp3', log_a)
        self.assertNotIn('b.mp3', log_a)
        self.assertIn('Input file: b.mp3', log_b)
        self.assertNotIn('a.mp3', log_b)

    def test_failure_does_not_stop_the_batch(self):
        stems = self.separate.return_value
        self.separate.side_effect = [stems, Audio2MidiError('Could not read audio file b.mp3'), stems]
        reported = []
        batch = self.run_batch(['a.mp3', 'b.mp3', 'c.mp3'], log=True,
                               on_result=lambda *args: reported.append(args))  # fmt: skip
        self.assertEqual([result.input_file.name for result in batch.results], ['a.mp3', 'c.mp3'])
        self.assertEqual(batch.failures, [FileFailure(Path('b.mp3'), 'Could not read audio file b.mp3')])
        self.assertEqual([(index, total) for index, total, _ in reported], [(1, 3), (2, 3), (3, 3)])
        self.assertIsInstance(reported[1][2], FileFailure)
        log_b = (self.output_dir / 'b' / 'op_mini' / 'audio2midi.log').read_text()
        self.assertIn('Traceback', log_b)  # details for debugging stay in the log file

    def test_unexpected_errors_name_their_type(self):
        self.save_audio.side_effect = OSError('disk full')
        batch = self.run_batch(['a.mp3'])
        self.assertEqual(batch.failures[0].error, 'OSError: disk full')

    def test_model_error_is_fatal(self):
        self.load_separator.side_effect = Audio2MidiError("Could not load model 'htdemucs_ft'")
        with self.assertRaises(Audio2MidiError):
            self.run_batch(['a.mp3', 'b.mp3'])
        self.separate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
