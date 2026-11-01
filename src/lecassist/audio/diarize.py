import json
import os
from pathlib import Path


def diarize_audio(audio_path, output_path=None):
    """Find speaker turns with pyannote.audio and optionally save them as JSON."""
    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError(
            "HF_TOKEN is not set. Add your Hugging Face access token to the environment."
        )

    try:
        import torch
        from pyannote.audio import Pipeline
        from pyannote.audio.core.task import Problem, Resolution, Specifications
    except ImportError as error:
        raise RuntimeError(
            "pyannote.audio and its PyTorch dependencies are required. "
            "Install project requirements first."
        ) from error

    try:
        with torch.serialization.safe_globals(
            [
                torch.torch_version.TorchVersion,
                Problem,
                Resolution,
                Specifications,
            ]
        ):
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=token,
            )
        diarization = pipeline(str(audio_path))
    except Exception as error:
        raise RuntimeError(
            "Could not load or run pyannote diarization. Check the HF_TOKEN, "
            "model access terms, and error details: "
            f"{error}"
        ) from error

    turns = [
        {"start": turn.start, "end": turn.end, "speaker": speaker}
        for turn, _, speaker in diarization.itertracks(yield_label=True)
    ]

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as turns_file:
            json.dump(turns, turns_file, ensure_ascii=False, indent=2)

    return turns