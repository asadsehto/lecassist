import json
import unicodedata
from pathlib import Path


def normalize_text(text):
    """Lowercase text, remove Unicode punctuation, and collapse whitespace."""
    text = text.lower()
    text = "".join(
        " " if unicodedata.category(character).startswith("P") else character
        for character in text
    )
    return " ".join(text.split())


def _read_transcript(path):
    """Read transcript text while excluding timestamps and speaker labels."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as transcript_file:
            records = json.load(transcript_file)
        return " ".join(record.get("text", "") for record in records)

    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("[") and "] " in line:
            line = line.split("] ", 1)[1]
            if ": " in line:
                line = line.split(": ", 1)[1]
        lines.append(line)
    return " ".join(lines)


def evaluate_transcript(reference_path, transcript_path):
    """Compute WER and substitution, deletion, and insertion counts."""
    reference_path = Path(reference_path)
    transcript_path = Path(transcript_path)
    if not reference_path.is_file():
        raise FileNotFoundError(f"Reference text file not found: {reference_path}")
    if not transcript_path.is_file():
        raise FileNotFoundError(f"Generated transcript not found: {transcript_path}")

    try:
        from jiwer import process_words
    except ImportError as error:
        raise RuntimeError(
            "jiwer is not installed. Install project requirements first."
        ) from error

    reference = normalize_text(reference_path.read_text(encoding="utf-8"))
    hypothesis = normalize_text(_read_transcript(transcript_path))
    if not reference:
        raise ValueError("The normalized reference text is empty; WER cannot be computed.")

    result = process_words(reference, hypothesis)
    return {
        "wer": result.wer,
        "substitutions": result.substitutions,
        "deletions": result.deletions,
        "insertions": result.insertions,
    }