import click

from audio2midi.constants import APP_NAME, MODEL_TRACKS, VERSION
from audio2midi.core.cache import CACHE_SIZE_ENV, StemCache, configured_max_size, default_cache_dir
from audio2midi.core.convert import MidiOptions
from audio2midi.core.dependencies import install_dependencies
from audio2midi.errors import Audio2MidiError
from audio2midi.flags.help import custom_help_option
from audio2midi.flags.options import general_options, input_arguments, midi_options, separation_options
from audio2midi.inputs import collect_input_files, find_output_conflicts
from audio2midi.pipeline import FileFailure, PipelineConfig, PipelineResult, run_pipeline
from audio2midi.utils.logger import setup_logging


@click.command(context_settings={"max_content_width": 120})
@custom_help_option
@click.version_option(VERSION, "-V", "--version", prog_name=APP_NAME)
@general_options
@separation_options
@midi_options
@input_arguments
@click.pass_context
def cli(ctx, verbose, install, log, cache, clear_cache, input_files, recursive, output_dir, model_name, operation, tracks, audio_format,
        compress, device, shifts, overlap, jobs, midi, onset_threshold, frame_threshold, min_note_length,
        min_frequency, max_frequency, multiple_pitch_bends, melodia, midi_tempo, files):  # fmt: skip
    """Split audio files into their instrument tracks and convert each track to MIDI.

    FILES are audio files or folders to process, like -f. Models are loaded once for all of them.

    \b
    Examples:
      audio2midi -f ./sample/djent_rock.mp3 -s op_full -o ./output -v
      audio2midi ./songs/*.mp3 ./more-songs
    """
    setup_logging(verbose)

    paths = [*input_files, *files]
    cache_dir = default_cache_dir()
    if install:
        _run_or_fail(install_dependencies)
    if clear_cache:
        freed = StemCache(cache_dir, max_size=0).clear()
        click.echo(f"Cleared the stems cache in {cache_dir} ({_format_size(freed)} freed)")
    if (install or clear_cache) and not paths:
        ctx.exit(0)
    if not paths:
        click.echo(ctx.get_help())
        ctx.exit(0)

    unsupported = [track for track in tracks if track not in MODEL_TRACKS[model_name]]
    if unsupported:
        raise click.BadParameter(
            f"model '{model_name}' cannot extract {', '.join(unsupported)} "
            f"(available: {', '.join(MODEL_TRACKS[model_name])})",
            ctx,
            param_hint="'-t' / '--tracks'",
        )
    if compress and audio_format != "mp3":
        raise click.UsageError("--compress only applies to the mp3 format", ctx)
    if min_frequency and max_frequency and min_frequency >= max_frequency:
        raise click.UsageError("--min-frequency must be lower than --max-frequency", ctx)
    try:
        cache_max_size = configured_max_size()
    except ValueError as error:
        raise click.UsageError(f"${CACHE_SIZE_ENV}: {error}", ctx) from error

    try:
        audio_files = collect_input_files(paths, recursive=recursive, output_dir=output_dir)
    except Audio2MidiError as error:
        raise click.UsageError(str(error), ctx) from error
    conflicts = find_output_conflicts(audio_files)
    if conflicts:
        details = "; ".join(f"'{stem}': {', '.join(map(str, inputs))}" for stem, inputs in conflicts.items())
        raise click.UsageError(f"several inputs would write to the same output folder ({details})", ctx)

    config = PipelineConfig(
        output_dir=output_dir,
        model_name=model_name,
        operation=operation,
        tracks=tracks or None,
        audio_format=audio_format,
        compress=compress,
        midi=midi,
        midi_options=MidiOptions(
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
            minimum_note_length=min_note_length,
            minimum_frequency=min_frequency,
            maximum_frequency=max_frequency,
            multiple_pitch_bends=multiple_pitch_bends,
            melodia_trick=melodia,
            midi_tempo=midi_tempo,
        ),
        device=device,
        shifts=shifts,
        overlap=overlap,
        jobs=jobs,
        log=log,
        verbose=verbose,
        cache_dir=cache_dir if cache and cache_max_size > 0 else None,
        cache_max_size=cache_max_size,
    )
    if len(audio_files) == 1:
        batch = _run_or_fail(run_pipeline, config, audio_files)
        if batch.failures:
            raise click.ClickException(batch.failures[0].error)
        click.echo(_saved_message(batch.results[0]))
        return

    batch = _run_or_fail(run_pipeline, config, audio_files, _report)
    summary = f"Processed {_plural(len(audio_files), 'file')}: {len(batch.results)} succeeded"
    if batch.failures:
        click.echo(f"{summary}, {len(batch.failures)} failed", err=True)
        ctx.exit(1)
    click.echo(summary)


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _saved_message(result: PipelineResult) -> str:
    summary = _plural(len(result.audio_files), "audio track")
    if result.midi_files:
        summary += f" and {_plural(len(result.midi_files), 'MIDI file')}"
    cached = " (cached stems)" if result.cached else ""
    return f"Saved {summary} to {result.output_dir}{cached}"


def _format_size(size: int) -> str:
    for unit in ("B", "KB", "MB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _report(index: int, total: int, outcome: PipelineResult | FileFailure) -> None:
    """Print each file's outcome as soon as it is processed."""
    prefix = f"[{index}/{total}]"
    if isinstance(outcome, FileFailure):
        click.echo(f"{prefix} Failed {outcome.input_file}: {outcome.error}", err=True)
    else:
        click.echo(f"{prefix} {_saved_message(outcome)}")


def _run_or_fail(func, *args):
    """Report expected errors as a clean message with exit code 1."""
    try:
        return func(*args)
    except Audio2MidiError as error:
        raise click.ClickException(str(error)) from error


if __name__ == "__main__":
    cli()
