import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from audio2midi.core import cache
from audio2midi.core.cache import StemCache, default_cache_dir, parse_size

try:
    import numpy
    import soundfile  # noqa: F401
except ImportError:  # the cache stores FLAC files with soundfile, CI installs both
    numpy = None


class TestSettings(unittest.TestCase):

    def test_parse_size(self):
        self.assertEqual(parse_size('0'), 0)
        self.assertEqual(parse_size('1024'), 1024)
        self.assertEqual(parse_size('500MB'), 500 * 1024**2)
        self.assertEqual(parse_size('2gb'), 2 * 1024**3)
        self.assertEqual(parse_size('1.5G'), int(1.5 * 1024**3))
        self.assertEqual(parse_size(' 3 GiB '), 3 * 1024**3)
        for invalid in ('', 'lots', '-1GB', '2PB'):
            with self.assertRaises(ValueError, msg=invalid):
                parse_size(invalid)

    def test_cache_dir_override(self):
        with mock.patch.dict(os.environ, {'AUDIO2MIDI_CACHE_DIR': '~/stems-cache'}):
            self.assertEqual(default_cache_dir(), Path.home() / 'stems-cache')

    @mock.patch('audio2midi.core.cache.platform.system', return_value='Linux')
    def test_linux_cache_dir(self, _system):
        with mock.patch.dict(os.environ, {'XDG_CACHE_HOME': '/xdg'}, clear=True):
            self.assertEqual(default_cache_dir(), Path('/xdg/audio2midi'))
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(default_cache_dir(), Path.home() / '.cache' / 'audio2midi')

    @mock.patch('audio2midi.core.cache.platform.system', return_value='Darwin')
    def test_macos_cache_dir(self, _system):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(default_cache_dir(), Path.home() / 'Library' / 'Caches' / 'audio2midi')


class CacheTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cache = StemCache(self.root / 'cache', max_size=parse_size('1GB'))

    def write_input(self, name, content=b'audio bytes'):
        path = self.root / name
        path.write_bytes(content)
        return path


class TestKey(CacheTestCase):

    def test_key_follows_content_not_name(self):
        a = self.write_input('a.mp3')
        renamed = self.write_input('renamed.wav')
        other = self.write_input('other.mp3', b'different audio')
        key = self.cache.key(a, 'htdemucs', 1, 0.25)
        self.assertEqual(key, self.cache.key(renamed, 'htdemucs', 1, 0.25))
        self.assertNotEqual(key, self.cache.key(other, 'htdemucs', 1, 0.25))

    def test_key_follows_separation_settings(self):
        a = self.write_input('a.mp3')
        keys = {
            self.cache.key(a, 'htdemucs', 1, 0.25),
            self.cache.key(a, 'htdemucs_ft', 1, 0.25),
            self.cache.key(a, 'htdemucs', 2, 0.25),
            self.cache.key(a, 'htdemucs', 1, 0.5),
        }
        self.assertEqual(len(keys), 4)

    def test_key_follows_demucs_version(self):
        a = self.write_input('a.mp3')
        with mock.patch('audio2midi.core.cache._demucs_version', return_value='4.1.0'):
            old = self.cache.key(a, 'htdemucs', 1, 0.25)
        with mock.patch('audio2midi.core.cache._demucs_version', return_value='4.2.0'):
            new = self.cache.key(a, 'htdemucs', 1, 0.25)
        self.assertNotEqual(old, new)


@unittest.skipIf(numpy is None, 'needs numpy and soundfile')
class TestStore(CacheTestCase):

    def stems(self, seed=0, samples=4410):
        rng = numpy.random.default_rng(seed)
        stems = {name: (rng.standard_normal((2, samples)) * 0.2).astype(numpy.float32)
                 for name in ('drums', 'bass', 'other', 'vocals')}  # fmt: skip
        stems['drums'][0, 10] = 1.7  # model output can exceed full scale
        return stems

    def test_round_trip_is_lossless_enough(self):
        stems = self.stems()
        self.assertTrue(self.cache.store('k' * 64, stems, 44100, source='song.mp3'))
        hit = self.cache.load('k' * 64)
        self.assertEqual(hit.samplerate, 44100)
        self.assertEqual(list(hit.stems), ['drums', 'bass', 'other', 'vocals'])
        for name, audio in stems.items():
            self.assertEqual(hit.stems[name].shape, audio.shape)
            # 24-bit precision: far below the 16-bit resolution (3e-5) of exported files.
            numpy.testing.assert_allclose(hit.stems[name], audio, atol=1e-6)
        self.assertAlmostEqual(float(hit.stems['drums'][0, 10]), 1.7, places=5)

    def test_miss(self):
        self.assertIsNone(self.cache.load('0' * 64))

    def test_broken_entry_is_a_miss_and_removed(self):
        self.cache.store('b' * 64, self.stems(), 44100)
        entry = self.cache.entries_dir / 'bb' / ('b' * 64)
        (entry / 'bass.flac').write_bytes(b'corrupt')
        with self.assertLogs('audio2midi.core.cache', 'WARNING'):
            self.assertIsNone(self.cache.load('b' * 64))
        self.assertFalse(entry.exists())

    def test_store_failure_does_not_raise(self):
        (self.root / 'not-a-dir').write_text('')
        broken = StemCache(self.root / 'not-a-dir', max_size=parse_size('1GB'))
        with self.assertLogs('audio2midi.core.cache', 'WARNING'):
            self.assertFalse(broken.store('c' * 64, self.stems(), 44100))

    def test_eviction_removes_least_recently_used(self):
        stems = self.stems()
        self.cache.store('1' * 64, stems, 44100)
        entry_size = self.cache.size()
        self.cache.max_size = int(entry_size * 2.5)  # room for two entries
        self.cache.store('2' * 64, stems, 44100)
        old = time.time() - 60
        for key in ('1' * 64, '2' * 64):
            os.utime(self.cache.entries_dir / key[:2] / key / 'manifest.json', (old, old))
        self.assertIsNotNone(self.cache.load('1' * 64))  # now more recently used than "2"
        self.cache.store('3' * 64, stems, 44100)
        self.assertIsNotNone(self.cache.load('1' * 64))
        self.assertIsNone(self.cache.load('2' * 64))
        self.assertIsNotNone(self.cache.load('3' * 64))

    def test_newest_entry_is_kept_even_over_the_limit(self):
        self.cache.max_size = 1
        self.cache.store('a' * 64, self.stems(), 44100)
        self.assertIsNotNone(self.cache.load('a' * 64))

    def test_stale_temporary_entries_are_removed(self):
        stale = self.cache.entries_dir / 'dd' / f"{'d' * 64}{cache.TMP_MARKER}123"
        stale.mkdir(parents=True)
        (stale / 'bass.flac').write_bytes(b'partial')
        old = time.time() - 2 * cache.STALE_TMP_SECONDS
        os.utime(stale, (old, old))
        self.cache.store('e' * 64, self.stems(), 44100)
        self.assertFalse(stale.exists())

    def test_manifest_records_source(self):
        self.cache.store('f' * 64, self.stems(), 44100, source='song.mp3')
        manifest = json.loads((self.cache.entries_dir / 'ff' / ('f' * 64) / 'manifest.json').read_text())
        self.assertEqual(manifest['source'], 'song.mp3')

    def test_clear(self):
        self.cache.store('a' * 64, self.stems(), 44100)
        size = self.cache.size()
        self.assertGreater(size, 0)
        self.assertEqual(self.cache.clear(), size)
        self.assertEqual(self.cache.size(), 0)
        self.assertIsNone(self.cache.load('a' * 64))


if __name__ == '__main__':
    unittest.main()
