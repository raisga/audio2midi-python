import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lib.core import compress, dependencies
from lib.errors import Audio2MidiError


class TestCompress(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'bass.mp3'
        self.path.write_bytes(b'original')

    @mock.patch('lib.core.compress.shutil.which', return_value='/usr/bin/ffmpeg')
    def test_reencodes_in_place(self, _which):
        def fake_ffmpeg(command, **kwargs):
            Path(command[-1]).write_bytes(b'small')

        with mock.patch('lib.core.compress.subprocess.run', side_effect=fake_ffmpeg) as run:
            compress.compress_mp3(self.path)
        command = run.call_args.args[0]
        self.assertEqual(command[0], '/usr/bin/ffmpeg')
        self.assertIn('libmp3lame', command)
        self.assertEqual(command[command.index('-qscale:a') + 1], '0')
        self.assertEqual(self.path.read_bytes(), b'small')
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [self.path])

    @mock.patch('lib.core.compress.shutil.which', return_value='/usr/bin/ffmpeg')
    def test_failure_keeps_original(self, _which):
        error = subprocess.CalledProcessError(1, 'ffmpeg', stderr='boom')
        with mock.patch('lib.core.compress.subprocess.run', side_effect=error):
            with self.assertRaisesRegex(Audio2MidiError, 'boom'):
                compress.compress_mp3(self.path)
        self.assertEqual(self.path.read_bytes(), b'original')

    @mock.patch('lib.core.compress.shutil.which', return_value=None)
    def test_requires_ffmpeg(self, _which):
        with self.assertRaisesRegex(Audio2MidiError, 'FFmpeg is required'):
            compress.compress_mp3(self.path)


class TestDependencies(unittest.TestCase):

    def test_requirements_file_exists(self):
        self.assertTrue(dependencies.REQUIREMENTS_FILE.is_file())

    @mock.patch('lib.core.dependencies.subprocess.run')
    @mock.patch('lib.core.dependencies.shutil.which', return_value='/usr/bin/ffmpeg')
    def test_installs_requirements(self, _which, run):
        dependencies.install_dependencies()
        command = run.call_args.args[0]
        self.assertEqual(command[1:5], ['-m', 'pip', 'install', '-r'])
        self.assertEqual(run.call_count, 1)

    @mock.patch('lib.core.dependencies.subprocess.run')
    @mock.patch('lib.core.dependencies.platform.system', return_value='Darwin')
    @mock.patch('lib.core.dependencies.shutil.which', side_effect=lambda name: '/opt/brew' if name == 'brew' else None)
    def test_installs_ffmpeg_with_brew(self, _which, _system, run):
        dependencies.ensure_ffmpeg()
        run.assert_called_once_with(['brew', 'install', 'ffmpeg'], check=True)

    @mock.patch('lib.core.dependencies.platform.system', return_value='Linux')
    @mock.patch('lib.core.dependencies.shutil.which', return_value=None)
    def test_ffmpeg_hint_on_linux(self, _which, _system):
        with self.assertRaisesRegex(Audio2MidiError, 'apt install ffmpeg'):
            dependencies.ensure_ffmpeg()

    @mock.patch('lib.core.dependencies.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'pip'))
    def test_pip_failure(self, _run):
        with self.assertRaises(Audio2MidiError):
            dependencies.install_python_packages()


if __name__ == '__main__':
    unittest.main()
