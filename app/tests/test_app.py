import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from click.testing import CliRunner

from lib.constants import VERSION
from lib.errors import Audio2MidiError
from lib.pipeline import PipelineResult
from main import cli


class TestCLI(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()
        self.tmp = tempfile.TemporaryDirectory()
        self.audio_file = os.path.join(self.tmp.name, "song.mp3")
        Path(self.audio_file).touch()
        patcher = mock.patch("main.run_pipeline", return_value=PipelineResult(Path("out/song/op_mini")))
        self.run_pipeline = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def config(self):
        self.run_pipeline.assert_called_once()
        return self.run_pipeline.call_args.args[0]

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
        self.assertEqual(config.input_file, Path(self.audio_file))
        self.assertEqual(config.output_dir, Path('output'))
        self.assertEqual(config.model_name, 'htdemucs_ft')
        self.assertEqual(config.operation, 'op_mini')
        self.assertIsNone(config.tracks)
        self.assertEqual(config.audio_format, 'mp3')
        self.assertFalse(config.compress)
        self.assertTrue(config.midi)
        self.assertIn('Saved 0 audio tracks', result.output)

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

    def test_pipeline_error_is_reported(self):
        self.run_pipeline.side_effect = Audio2MidiError('Could not read audio file')
        result = self.runner.invoke(cli, ['-f', self.audio_file])
        self.assertEqual(result.exit_code, 1)
        self.assertIn('Error: Could not read audio file', result.output)

    @mock.patch('main.install_dependencies')
    def test_install_only(self, install):
        result = self.runner.invoke(cli, ['--install'])
        self.assertEqual(result.exit_code, 0, result.output)
        install.assert_called_once()
        self.run_pipeline.assert_not_called()

    @mock.patch('main.install_dependencies')
    def test_install_then_process(self, install):
        result = self.runner.invoke(cli, ['-i', '-f', self.audio_file])
        self.assertEqual(result.exit_code, 0, result.output)
        install.assert_called_once()
        self.run_pipeline.assert_called_once()


if __name__ == '__main__':
    unittest.main()
