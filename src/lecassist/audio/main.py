import argparse
import sys
from pathlib import Path

from audio_prep import prepare_audio
from diarize import diarize_audio
from evaluate import evaluate_transcript
from merge import merge_transcript
from transcribe import transcribe_audio


def parse_args():
    """Parse command-line options for the offline transcription pipeline."""
    parser = argparse.ArgumentParser(description="Transcribe and diarize a lecture.")
    parser.add_argument("input", type=Path, help="Path to an audio or video file")
    parser.add_argument(
        "--denoise",
        action="store_true",
        help="Save and use an additional noise-reduced audio file",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        help="Optional hand-written reference text file for WER evaluation",
    )
    parser.add_argument(
        "--device",
        choices=("cpu", "cuda"),
        default="cpu",
        help="Whisper inference device (default: cpu)",
    )
    parser.add_argument(
        "--language",
        choices=("ur", "en", "hi", "auto"),
        default="ur",
        help="Whisper language code, or auto for detection (default: ur)",
    )
    return parser.parse_args()


def main():
    """Run audio preparation, transcription, diarization, merging, and evaluation."""
    args = parse_args()
    stem = args.input.stem
    transcript_dir = Path("data/transcripts")
    segments_path = transcript_dir / f"{stem}_segments.json"
    turns_path = transcript_dir / f"{stem}_speaker_turns.json"
    merged_text_path = transcript_dir / f"{stem}_transcript.txt"
    merged_json_path = transcript_dir / f"{stem}_transcript.json"

    try:
        print("[1/4] Preparing audio...")
        clean_path, denoised_path = prepare_audio(args.input, denoise=args.denoise)
        audio_path = denoised_path if args.denoise else clean_path

        print("[2/4] Transcribing lecture...")
        segments = transcribe_audio(
            audio_path,
            segments_path,
            device=args.device,
            language=args.language,
        )

        print("[3/4] Identifying speakers...")
        speaker_turns = diarize_audio(audio_path, turns_path)

        print("[4/4] Merging transcript and speaker turns...")
        merge_transcript(segments, speaker_turns, merged_text_path, merged_json_path)

        print(f"Transcript: {merged_text_path}")
        print(f"Transcript JSON: {merged_json_path}")
        if args.reference:
            print("Evaluating against reference...")
            scores = evaluate_transcript(args.reference, merged_json_path)
            print(f"WER: {scores['wer']:.4f}")
            print(f"Substitutions: {scores['substitutions']}")
            print(f"Deletions: {scores['deletions']}")
            print(f"Insertions: {scores['insertions']}")
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())