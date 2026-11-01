# Offline Lecture Transcription Prototype

This Windows prototype converts audio or video to 16 kHz mono WAV, transcribes it with faster-whisper, identifies speaker turns with pyannote.audio, and writes a merged transcript. The models are downloaded on first use and then run locally.

## Setup on Windows

1. Install Python 3.10 or newer. From the project folder, create and activate a virtual environment and install the dependencies:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. Install FFmpeg and ensure `ffmpeg.exe` is on `PATH`. For example:

   ```powershell
   winget install Gyan.FFmpeg.Shared
   ```

   Open a new PowerShell window and verify it is available:

   ```powershell
   ffmpeg -version
   ```

3. Sign in to Hugging Face, accept the access conditions for [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) and [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0), then create a read token. Set the token in the PowerShell window used to run the pipeline:

   ```powershell
   $env:HF_TOKEN = "hf_your_token"
   ```

   This environment variable applies to the current PowerShell window. Creating a token on Hugging Face does not automatically make it available to Python. You can check that it is set without printing the secret:

   ```powershell
   python -c "import os; print('HF_TOKEN available:', bool(os.getenv('HF_TOKEN')))"
   ```

## Run a clip

Activate the virtual environment and run the script from the project folder. Input files may be anywhere, as long as you pass their path. For example, if the clip is in `data/raw`:

```powershell
.\.venv\Scripts\Activate.ps1
python main.py .\data\raw\lec1_trim1.mp3
```

Noise reduction is optional. When enabled, the pipeline uses the separately saved denoised WAV for both transcription and diarization:

```powershell
python main.py .\data\raw\lec1_trim1.mp3 --denoise
```

Urdu is the default transcription language, with English words supported by a mixed Urdu-English prompt. To let Whisper detect the language instead, use `--language auto`. `--language en` and `--language hi` are also available. CPU is the default; `--device cuda` requests CUDA for Whisper if it is supported by your installation:

```powershell
python main.py .\data\raw\lec1_trim1.mp3 --language auto --device cuda
```

## Optional reference scoring

`--reference` is optional and is only used to calculate word error rate (WER) after the transcript has been generated. It must point to an existing plain-text file containing a human-written reference transcription. For example, create `reference.txt` in the project folder, write the words as spoken, and run:

```powershell
python main.py .\data\raw\lec1_trim1.mp3 --reference .\reference.txt
```

To enable noise reduction as well:

```powershell
python main.py .\data\raw\lec1_trim1.mp3 --denoise --reference .\reference.txt
```

If you do not have a reference file, omit `--reference`. If you provide a path that does not exist, the pipeline reports `Reference text file not found`; transcription and merging may already have completed, but evaluation cannot run. The reference should be an independent ground-truth transcript, not the generated transcript being evaluated.

## Outputs and runtime

- `data/clean/<clip>_16k_mono.wav`: converted audio.
- `data/clean/<clip>_16k_mono_denoised.wav`: additional denoised audio, when `--denoise` is used.
- `data/transcripts/<clip>_segments.json`: Whisper segments and timestamps.
- `data/transcripts/<clip>_speaker_turns.json`: diarized speaker turns.
- `data/transcripts/<clip>_transcript.txt` and `data/transcripts/<clip>_transcript.json`: merged transcript.

The first run downloads the Whisper and pyannote models; subsequent runs can use the local model cache. Loading and CPU inference may take several minutes, depending on the machine and clip length. Each run transcribes and diarizes the clip again.