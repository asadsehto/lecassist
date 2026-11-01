import json
from pathlib import Path


INITIAL_PROMPT = "آج ہم machine learning اور data analysis کے بارے میں بات کریں گے۔"


def transcribe_audio(audio_path, output_path=None, device="cpu", language="ur"):
    """Transcribe audio in Urdu by default and save timestamped segments."""
    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    if device not in {"cpu", "cuda"}:
        raise ValueError("device must be either 'cpu' or 'cuda'")

    try:
        from faster_whisper import WhisperModel
    except ImportError as error:
        raise RuntimeError(
            "faster-whisper is not installed. Install project requirements first."
        ) from error

    compute_type = "int8" if device == "cpu" else "float16"
    model = WhisperModel(
        "large-v3-turbo",
        device=device,
        compute_type=compute_type,
    )
    whisper_segments, _ = model.transcribe(
        str(audio_path),
        language=None if language == "auto" else language,
        word_timestamps=True,
        initial_prompt=INITIAL_PROMPT,
    )
    segments = [
        {"start": segment.start, "end": segment.end, "text": segment.text.strip()}
        for segment in whisper_segments
    ]

    if output_path is None:
        output_path = Path("data/transcripts") / f"{audio_path.stem}_segments.json"
    else:
        output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as transcript_file:
        json.dump(segments, transcript_file, ensure_ascii=False, indent=2)

    return segments