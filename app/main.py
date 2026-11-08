import click

from lib.constants import APP_NAME, MODEL_TRACKS, VERSION
from lib.core.convert import MidiOptions
from lib.core.dependencies import install_dependencies
from lib.errors import Audio2MidiError
from lib.flags.help import custom_help_option
from lib.flags.options import general_options, midi_options, separation_options
from lib.pipeline import PipelineConfig, run_pipeline
from lib.utils.logger import setup_logging


@click.command(context_settings={"max_content_width": 120})
@custom_help_option
@click.version_option(VERSION, "-V", "--version", prog_name=APP_NAME)
@general_options
@separation_options
@midi_options
@click.pass_context
def cli(ctx, verbose, install, log, input_file, output_dir, model_name, operation, tracks, audio_format, compress,
        device, shifts, overlap, jobs, midi, onset_threshold, frame_threshold, min_note_length, min_frequency,
        max_frequency, multiple_pitch_bends, melodia, midi_tempo):  # fmt: skip
    """Split an audio file into its instrument tracks and convert each track to MIDI.

    \b
    Example:
      python app/main.py -f ./sample/djent_rock.mp3 -s op_full -o ./output -v
    """
    setup_logging(verbose)

    if install:
        _run_or_fail(install_dependencies)
        if input_file is None:
            ctx.exit(0)
    if input_file is None:
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

    config = PipelineConfig(
        input_file=input_file,
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
    )
    result = _run_or_fail(run_pipeline, config)
    summary = f"{len(result.audio_files)} audio tracks"
    if result.midi_files:
        summary += f" and {len(result.midi_files)} MIDI files"
    click.echo(f"Saved {summary} to {result.output_dir}")


def _run_or_fail(func, *args):
    """Report expected errors as a clean message with exit code 1."""
    try:
        return func(*args)
    except Audio2MidiError as error:
        raise click.ClickException(str(error)) from error


if __name__ == "__main__":
    cli()
