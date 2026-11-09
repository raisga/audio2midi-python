"""Build the track variations exported by each operation.

Variations are derived from a single demucs separation by summing stems, which is
exactly what `demucs --two-stems=<track>` does for the "no_<track>" complement.
Values only need to support `+`, so this works with torch tensors and numpy arrays.
"""

from collections.abc import Mapping, Sequence
from functools import reduce
from itertools import combinations
from operator import add
from typing import TypeVar

from audio2midi.constants import COMBINATION_SEPARATOR, COMPLEMENT_PREFIX, OP_EXTRA, OP_FULL, OPERATIONS

T = TypeVar("T")


def _mix(sources: Sequence[T]) -> T:
    return reduce(add, sources)


def build_variations(stems: Mapping[str, T], tracks: Sequence[str], operation: str) -> dict[str, T]:
    """Return the named audio variations for an operation.

    - op_mini:  every selected track (e.g. "bass").
    - op_full:  op_mini plus each track's complement (e.g. "no_bass": all other stems).
    - op_extra: op_full plus every pair of selected tracks mixed (e.g. "bass_drums").

    Args:
        stems: All stems produced by the separation model, keyed by name.
        tracks: The selected tracks, in the order they should be exported.
        operation: One of `OPERATIONS`.
    """
    if operation not in OPERATIONS:
        raise ValueError(f"Unknown operation: {operation}")
    unknown = [track for track in tracks if track not in stems]
    if unknown:
        raise ValueError(f"Unknown tracks {unknown}, available: {list(stems)}")

    variations = {track: stems[track] for track in tracks}
    if operation in (OP_FULL, OP_EXTRA):
        for track in tracks:
            others = [audio for name, audio in stems.items() if name != track]
            variations[f"{COMPLEMENT_PREFIX}{track}"] = _mix(others)
    if operation == OP_EXTRA:
        for pair in combinations(tracks, 2):
            variations[COMBINATION_SEPARATOR.join(pair)] = _mix([stems[track] for track in pair])
    return variations
