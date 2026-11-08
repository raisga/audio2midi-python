"""Write audio tensors to disk."""

from pathlib import Path

from lib.constants import DEFAULT_MP3_BITRATE


def save_audio(wav, path: Path, samplerate: int, bitrate: int = DEFAULT_MP3_BITRATE) -> Path:
    """Save a (channels, samples) tensor as mp3, wav or flac, based on the path suffix.

    The audio is rescaled when needed so mixed variations never clip.
    """
    wav = wav.detach().cpu().float()
    wav = wav / max(1.01 * wav.abs().max().item(), 1.0)
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        from demucs.audio import encode_mp3

        encode_mp3(wav, path, samplerate=samplerate, bitrate=bitrate)
    elif suffix in (".wav", ".flac"):
        import soundfile

        soundfile.write(str(path), wav.t().numpy(), samplerate, subtype="PCM_16")
    else:
        raise ValueError(f"Unsupported audio format: {suffix}")
    return path
