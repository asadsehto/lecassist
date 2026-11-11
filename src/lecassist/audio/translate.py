"""English transcript of a lecture, from Aura's transcription.py.

faster-whisper with task="translate" turns mixed Urdu/English speech into English
text, which the summary agent reads more reliably than Urdu script.
Settings are Aura's: model "small", CPU, int8, beam size 5.
"""
from faster_whisper import WhisperModel

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = WhisperModel("small", device="cpu", compute_type="int8")
    return _model


def transcribe_english(audio_path: str) -> str:
    """Audio file (wav, mp3, webm, m4a…) in, English transcript text out."""
    segments, _info = _get_model().transcribe(
        str(audio_path),
        task="translate",
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=400),
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return text or "No audible speech was detected in the recording."
