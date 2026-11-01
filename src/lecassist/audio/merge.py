import json
from pathlib import Path


def _overlap_duration(segment, turn):
    """Return the duration shared by a transcript segment and speaker turn."""
    return max(0.0, min(segment["end"], turn["end"]) - max(segment["start"], turn["start"]))


def _speaker_for_segment(segment, speaker_turns):
    """Select the speaker with the greatest overlap, or UNKNOWN if none overlaps."""
    best_turn = None
    best_overlap = 0.0
    for turn in speaker_turns:
        overlap = _overlap_duration(segment, turn)
        if overlap > best_overlap:
            best_turn = turn
            best_overlap = overlap
    return best_turn["speaker"] if best_turn else "UNKNOWN"


def _format_timestamp(seconds):
    """Format seconds as a zero-padded hours, minutes, and seconds timestamp."""
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def merge_transcript(segments, speaker_turns, text_path, json_path):
    """Assign speakers to transcript segments and write readable text and JSON."""
    merged = []
    lines = []
    for segment in segments:
        speaker = _speaker_for_segment(segment, speaker_turns)
        record = {
            "start": segment["start"],
            "end": segment["end"],
            "speaker": speaker,
            "text": segment["text"],
        }
        merged.append(record)
        timestamp = _format_timestamp(segment["start"])
        lines.append(f"[{timestamp}] {speaker}: {segment['text']}")

    text_path = Path(text_path)
    json_path = Path(json_path)
    text_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with json_path.open("w", encoding="utf-8") as merged_file:
        json.dump(merged, merged_file, ensure_ascii=False, indent=2)
    return merged