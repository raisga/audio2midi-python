import tempfile
import unittest
from pathlib import Path

from audio2midi.errors import Audio2MidiError
from audio2midi.inputs import collect_input_files, find_output_conflicts


class TestCollectInputFiles(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def make(self, *relatives):
        paths = []
        for relative in relatives:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            paths.append(path)
        return paths

    def test_files_keep_order(self):
        b, a = self.make('b.mp3', 'a.mp3')
        self.assertEqual(collect_input_files([b, a]), [b, a])

    def test_explicit_files_accept_any_extension(self):
        (video,) = self.make('live.mkv')
        self.assertEqual(collect_input_files([video]), [video])

    def test_folder_scan_is_sorted_and_filtered(self):
        b, a, upper = self.make('album/b.wav', 'album/a.mp3', 'album/C.FLAC')
        self.make('album/cover.jpg', 'album/.hidden.mp3', 'album/._a.mp3', 'album/sub/deep.mp3')
        self.assertEqual(collect_input_files([self.root / 'album']), [upper, a, b])

    def test_recursive_scan(self):
        top, deep = self.make('album/a.mp3', 'album/disc 2/b.mp3')
        self.make('album/.cache/c.mp3')
        self.assertEqual(collect_input_files([self.root / 'album'], recursive=True), [top, deep])

    def test_duplicates_are_dropped(self):
        (a,) = self.make('album/a.mp3')
        files = collect_input_files([a, self.root / 'album', self.root / 'album' / '..' / 'album' / 'a.mp3'])
        self.assertEqual(files, [a])

    def test_output_folder_is_skipped(self):
        (song,) = self.make('music/song.mp3')
        self.make('music/output/song/op_mini/bass.mp3')
        files = collect_input_files([self.root / 'music'], recursive=True, output_dir=self.root / 'music' / 'output')
        self.assertEqual(files, [song])

    def test_empty_folder(self):
        self.make('empty/readme.txt')
        with self.assertRaisesRegex(Audio2MidiError, 'No audio files found'):
            collect_input_files([self.root / 'empty'])


class TestOutputConflicts(unittest.TestCase):

    def test_same_stem_conflicts(self):
        conflicts = find_output_conflicts([Path('a/song.mp3'), Path('b/song.wav'), Path('c/other.mp3')])
        self.assertEqual(conflicts, {'song': [Path('a/song.mp3'), Path('b/song.wav')]})

    def test_no_conflicts(self):
        self.assertEqual(find_output_conflicts([Path('a.mp3'), Path('b.mp3')]), {})


if __name__ == '__main__':
    unittest.main()
