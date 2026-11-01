from pathlib import Path
import subprocess


def prepare_audio(input_path, output_dir="data/clean", denoise=False):
    """Convert audio to 16 kHz mono WAV and optionally save a denoised copy."""
    input_path = Path(input_path)
    if not input_path.is_file():
        raise FileNotFoundError(f"Input audio file not found: {input_path}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    wav_path = output_dir / f"{input_path.stem}_16k_mono.wav"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(wav_path),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as error:
        raise RuntimeError(
            "FFmpeg was not found. Install FFmpeg and make sure it is on PATH."
        ) from error
    except subprocess.CalledProcessError as error:
        details = error.stderr.strip() or "No FFmpeg error details were provided."
        raise RuntimeError(f"FFmpeg could not convert the audio: {details}") from error

    denoised_path = None
    if denoise:
        try:
            import noisereduce
            import soundfile as sf
        except ImportError as error:
            raise RuntimeError(
                "Denoising requires noisereduce and soundfile. Install project requirements first."
            ) from error

        audio, sample_rate = sf.read(wav_path)
        cleaned_audio = noisereduce.reduce_noise(y=audio, sr=sample_rate)
        denoised_path = output_dir / f"{input_path.stem}_16k_mono_denoised.wav"
        sf.write(denoised_path, cleaned_audio, sample_rate)

    return wav_path, denoised_path