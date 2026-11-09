import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from click.testing import CliRunner

from audio2midi.cli import cli
from audio2midi.constants import VERSION
from audio2midi.errors import Audio2MidiError
from audio2midi.pipeline import BatchResult, FileFailure, PipelineResult


class TestCLI(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()
        self.tmp = tempfile.TemporaryDirectory()
        self.audio_file = os.path.join(self.tmp.name, "song.mp3")
        Path(self.audio_file).touch()
        self.failing = set()  # file names the fake pipeline fails on
        self.cached = set()  # file names the fake pipeline finds in the cache
        self.cache_dir = Path(self.tmp.name) / 'cache'
        env = mock.patch.dict(os.environ, {'AUDIO2MIDI_CACHE_DIR': str(self.cache_dir)})
        env.start()
        self.addCleanup(env.stop)
        patcher = mock.patch("audio2midi.cli.run_pipeline", side_effect=self.fake_run_pipeline)
        self.run_pipeline = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def fake_run_pipeline(self, config, files, on_result=None):
        batch = BatchResult()
        for index, path in enumerate(files, start=1):
            if path.name in self.failing:
                outcome = FileFailure(path, f'Could not read audio file {path}')
                batch.failures.append(outcome)
            else:
                outcome = PipelineResult(path, config.track_dir(path), [Path('bass.mp3')], [Path('bass.mid')],
                                         cached=path.name in self.cached)
                batch.results.append(outcome)
            if on_result is not None:
                on_result(index, len(files), outcome)
        return batch

    def make_file(self, relative):
        path = Path(self.tmp.name) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return path

    def config(self):
        self.run_pipeline.assert_called_once()
        return self.run_pipeline.call_args.args[0]

    def files(self):
        self.run_pipeline.assert_called_once()
        return self.run_pipeline.call_args.args[1]

    def test_no_args(self):
        result = self.runner.invoke(cli)
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Usage:', result.output)
        self.run_pipeline.assert_not_called()

    def test_help_flag(self):
        for flag in ('--help', '-h'):
            result = self.runner.invoke(cli, [flag])
            self.assertEqual(result.exit_code, 0)
            self.assertIn('Show this help message and exit', result.output)

    def test_version_flag(self):
        result = self.runner.invoke(cli, ['--version'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(VERSION, result.output)

    def test_invalid_option(self):
        result = self.runner.invoke(cli, ['--nope'])
        self.assertEqual(result.exit_code, 2)
        self.assertIn('No such option', result.output)

    def test_missing_file(self):
        result = self.runner.invoke(cli, ['-f', os.path.join(self.tmp.name, 'missing.mp3')])
        self.assertEqual(result.exit_code, 2)
        self.assertIn('does not exist', result.output)

    def test_file_argument_required(self):
        result = self.runner.invoke(cli, ['-f'])
        self.assertEqual(result.exit_code, 2)
        self.assertIn('requires an argument', result.output)

    def test_defaults(self):
        result = self.runner.invoke(cli, ['-f', self.audio_file])
        self.assertEqual(result.exit_code, 0, result.output)
        config = self.config()
        self.assertEqual(self.files(), [Path(self.audio_file)])
        self.assertEqual(config.output_dir, Path('output'))
        self.assertEqual(config.model_name, 'htdemucs_ft')
        self.assertEqual(config.operation, 'op_mini')
        self.assertIsNone(config.tracks)
        self.assertEqual(config.audio_format, 'mp3')
        self.assertFalse(config.compress)
        self.assertTrue(config.midi)
        self.assertEqual(result.output, 'Saved 1 audio track and 1 MIDI file to output/song/op_mini\n')

    def test_advanced_options(self):
        result = self.runner.invoke(cli, [
            '--verbose', '--file', self.audio_file, '--select', 'op_full', '--outdir', 'out',
            '--model', 'htdemucs_6s', '-t', 'guitar,bass', '-t', 'piano', '--compress', '--log',
            '--no-midi', '--device', 'cpu', '--shifts', '2', '--onset-threshold', '0.6',
            '--min-frequency', '40', '--max-frequency', '400', '--no-melodia', '--midi-tempo', '90',
        ])
        self.assertEqual(result.exit_code, 0, result.output)
        config = self.config()
        self.assertEqual(config.operation, 'op_full')
        self.assertEqual(config.output_dir, Path('out'))
        self.assertEqual(config.model_name, 'htdemucs_6s')
        self.assertEqual(config.tracks, ('guitar', 'bass', 'piano'))
        self.assertTrue(config.compress and config.log and config.verbose)
        self.assertFalse(config.midi)
        self.assertEqual((config.device, config.shifts), ('cpu', 2))
        options = config.midi_options
        self.assertEqual(options.onset_threshold, 0.6)
        self.assertEqual((options.minimum_frequency, options.maximum_frequency), (40, 400))
        self.assertFalse(options.melodia_trick)
        self.assertEqual(options.midi_tempo, 90)

    def test_invalid_operation(self):
        result = self.runner.invoke(cli, ['-f', self.audio_file, '-s', 'op_mega'])
        self.assertEqual(result.exit_code, 2)
        self.run_pipeline.assert_not_called()

    def test_invalid_track(self):
        result = self.runner.invoke(cli, ['-f', self.audio_file, '-t', 'kazoo'])
        self.assertEqual(result.exit_code, 2)
        self.assertIn("'kazoo' is not one of", result.output)

    def test_track_not_supported_by_model(self):
        result = self.runner.invoke(cli, ['-f', self.audio_file, '-t', 'guitar'])
        self.assertEqual(result.exit_code, 2)
        self.assertIn("cannot extract guitar", result.output)
        self.run_pipeline.assert_not_called()

    def test_compress_requires_mp3(self):
        result = self.runner.invoke(cli, ['-f', self.audio_file, '-c', '-F', 'wav'])
        self.assertEqual(result.exit_code, 2)
        self.assertIn('--compress only applies to the mp3 format', result.output)

    def test_frequency_range(self):
        result = self.runner.invoke(cli, ['-f', self.audio_file, '--min-frequency', '500', '--max-frequency', '100'])
        self.assertEqual(result.exit_code, 2)

    def test_model_error_is_reported(self):
        self.run_pipeline.side_effect = Audio2MidiError("Could not load model 'htdemucs_ft'")
        result = self.runner.invoke(cli, ['-f', self.audio_file])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error: Could not load model", result.output)

    def test_single_file_failure_is_reported(self):
        self.failing.add('song.mp3')
        result = self.runner.invoke(cli, ['-f', self.audio_file])
        self.assertEqual(result.exit_code, 1)
        self.assertIn('Error: Could not read audio file', result.output)

    @mock.patch('audio2midi.cli.install_dependencies')
    def test_install_only(self, install):
        result = self.runner.invoke(cli, ['--install'])
        self.assertEqual(result.exit_code, 0, result.output)
        install.assert_called_once()
        self.run_pipeline.assert_not_called()

    @mock.patch('audio2midi.cli.install_dependencies')
    def test_install_then_process(self, install):
        result = self.runner.invoke(cli, ['-i', '-f', self.audio_file])
        self.assertEqual(result.exit_code, 0, result.output)
        install.assert_called_once()
        self.run_pipeline.assert_called_once()

    def test_positional_files_and_folders(self):
        first, second = self.make_file('a.wav'), self.make_file('album/b.flac')
        self.make_file('album/notes.txt')
        result = self.runner.invoke(cli, ['-f', str(first), str(Path(self.tmp.name) / 'album'), self.audio_file])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.files(), [first, second, Path(self.audio_file)])

    def test_recursive_flag(self):
        nested = self.make_file('album/disc1/track.mp3')
        result = self.runner.invoke(cli, ['-r', str(Path(self.tmp.name) / 'album')])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.files(), [nested])

    def test_duplicates_are_processed_once(self):
        result = self.runner.invoke(cli, ['-f', self.audio_file, self.audio_file])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.files(), [Path(self.audio_file)])

    def test_empty_folder(self):
        empty = Path(self.tmp.name) / 'empty'
        empty.mkdir()
        result = self.runner.invoke(cli, [str(empty)])
        self.assertEqual(result.exit_code, 2)
        self.assertIn('No audio files found in', result.output)
        self.run_pipeline.assert_not_called()

    def test_output_folder_conflict(self):
        other = self.make_file('other/song.wav')
        result = self.runner.invoke(cli, [self.audio_file, str(other)])
        self.assertEqual(result.exit_code, 2)
        self.assertIn("same output folder ('song'", result.output)
        self.run_pipeline.assert_not_called()

    def test_batch_reports_each_file(self):
        second = self.make_file('other.mp3')
        result = self.runner.invoke(cli, [self.audio_file, str(second)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(result.output.splitlines(), [
            '[1/2] Saved 1 audio track and 1 MIDI file to output/song/op_mini',
            '[2/2] Saved 1 audio track and 1 MIDI file to output/other/op_mini',
            'Processed 2 files: 2 succeeded',
        ])

    def test_batch_continues_after_failure(self):
        bad, good = self.make_file('bad.mp3'), self.make_file('good.mp3')
        self.failing.add('bad.mp3')
        result = self.runner.invoke(cli, [str(bad), str(good)])
        self.assertEqual(result.exit_code, 1)
        lines = result.output.splitlines()
        self.assertEqual(lines[0], f'[1/2] Failed {bad}: Could not read audio file {bad}')
        self.assertEqual(lines[1], '[2/2] Saved 1 audio track and 1 MIDI file to output/good/op_mini')
        self.assertEqual(lines[2], 'Processed 2 files: 1 succeeded, 1 failed')

    def test_cache_enabled_by_default(self):
        result = self.runner.invoke(cli, [self.audio_file])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.config().cache_dir, self.cache_dir)
        self.assertEqual(self.config().cache_max_size, 2 * 1024**3)

    def test_no_cache(self):
        result = self.runner.invoke(cli, ['--no-cache', self.audio_file])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIsNone(self.config().cache_dir)

    def test_cache_size_env(self):
        with mock.patch.dict(os.environ, {'AUDIO2MIDI_CACHE_SIZE': '500MB'}):
            self.runner.invoke(cli, [self.audio_file])
        self.assertEqual(self.config().cache_max_size, 500 * 1024**2)

    def test_cache_size_zero_disables_cache(self):
        with mock.patch.dict(os.environ, {'AUDIO2MIDI_CACHE_SIZE': '0'}):
            self.runner.invoke(cli, [self.audio_file])
        self.assertIsNone(self.config().cache_dir)

    def test_invalid_cache_size(self):
        with mock.patch.dict(os.environ, {'AUDIO2MIDI_CACHE_SIZE': 'lots'}):
            result = self.runner.invoke(cli, [self.audio_file])
        self.assertEqual(result.exit_code, 2)
        self.assertIn('$AUDIO2MIDI_CACHE_SIZE', result.output)
        self.run_pipeline.assert_not_called()

    def test_clear_cache_only(self):
        entry = self.cache_dir / 'stems' / 'ab' / 'abc'
        entry.mkdir(parents=True)
        (entry / 'bass.flac').write_bytes(b'x' * 2048)
        result = self.runner.invoke(cli, ['--clear-cache'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(result.output, f'Cleared the stems cache in {self.cache_dir} (2.0 KB freed)\n')
        self.assertFalse(entry.exists())
        self.run_pipeline.assert_not_called()

    def test_clear_cache_then_process(self):
        result = self.runner.invoke(cli, ['--clear-cache', self.audio_file])
        self.assertEqual(result.exit_code, 0, result.output)
        self.run_pipeline.assert_called_once()

    def test_cached_result_is_reported(self):
        self.cached.add('song.mp3')
        result = self.runner.invoke(cli, [self.audio_file])
        self.assertEqual(result.output, 'Saved 1 audio track and 1 MIDI file to output/song/op_mini (cached stems)\n')


if __name__ == '__main__':
    unittest.main()
