# AWS Hackathon 2025 Toolkit

A prototype assistant that connects AWS Bedrock models with S3-hosted knowledge so you can ask questions about your own content. The project ships with:

- A FastAPI retrieval-augmented backend that pulls `.txt` documents from S3, indexes them with TF-IDF, and prompts Bedrock for grounded answers.
- A keyboard-driven desktop helper (`screenshot_upload.py`) that can capture screenshots, send them to Bedrock for vision analysis, and optionally record audio for transcription.
- Lightweight front-ends (a vanilla HTML page and a Vite/React UI prototype) for testing the `/ask` endpoint.

## Repository layout

```
.
├── server.py              # FastAPI application with retrieval + Bedrock orchestration
├── screenshot_upload.py   # Keyboard listener for screenshots and audio capture
├── bedrock.py             # Minimal Claude text example
├── converse.py            # Streaming Bedrock example
├── index.html             # One-page UI that calls /ask
├── src/                   # React prototype (Vite) with AI console components
├── requirements.txt       # Python dependencies
└── README.md
```

## Backend overview (`server.py`)

- Loads environment variables from `.env` and builds an S3-backed corpus using prefixes defined in `TXT_PREFIXES`.
- Chunks documents with configurable `CHUNK_SIZE` / `CHUNK_OVERLAP` and creates a TF-IDF matrix.
- Exposes endpoints:
  - `GET /health` – index status, active model ID, and whether the screenshot helper is running.
  - `POST /reload` – rebuild the TF-IDF index from the latest S3 content.
  - `POST /ask` – returns an answer plus the top passages used for grounding.
  - `POST /start_script` / `POST /stop_script` – start or stop `screenshot_upload.py` as a child process of the server.
- Calls the Bedrock model indicated by `LLM_MODEL_ID`, forcing the model to answer only from the supplied passages (otherwise it returns `<NO_ANSWER>`).

## Screenshot & audio helper (`screenshot_upload.py`)

- Global hotkeys:
  - **Enter**: capture the active monitor, resize/compress, upload to the configured S3 bucket, and request a Bedrock vision analysis.
  - **Shift**: toggle microphone recording; audio is saved in memory, uploaded to S3, and can be handed to a transcription workflow.
  - **Space**: start recording with SoundDevice (Whisper-compatible WAV output).
- Persists analysis text locally under `analysis_logs/` and mirrors it to the `text-description` bucket for retrieval by the backend.
- Requires desktop dependencies (`pynput`, `mss`, `Pillow`, `sounddevice`, `pyaudio`, etc.) along with PortAudio system libraries.

## Front-end options

- `index.html`: a static HTML/JS helper pointing at `http://127.0.0.1:8001/ask`.
- `src/`: a Vite + React prototype (`main.jsx`, `App.jsx`, `AIConsoleUI.jsx`, `ChatBox.jsx`, and CSS assets). Install Node.js 18+ and Vite tooling to iterate on this UI.

## Prerequisites

### System packages

Some optional tools (notably audio recording) rely on PortAudio:

- **macOS**: `brew install portaudio`
- **Debian/Ubuntu**: `sudo apt-get install portaudio19-dev`

### Python environment

1. Create and activate a virtual environment.
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies.
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

### Environment variables (`.env`)

Copy `.env.example` (if provided) or create a new `.env` containing at least:

- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION` (defaults to `us-east-1`)
- Retrieval settings: `TXT_BUCKET`, optional comma-separated `TXT_PREFIXES`, `CHUNK_SIZE`, `CHUNK_OVERLAP`
- Model settings: `LLM_MODEL_ID`, `MAX_TOKENS`
- Optional overrides for the screenshot helper (e.g., different S3 buckets)

## Running the FastAPI server

```bash
uvicorn server:app --reload --port 8001
```

The startup hook immediately builds the TF-IDF index. Use `POST /reload` if you add new `.txt` files to your S3 bucket.

### Example `curl`

```bash
curl -X POST http://127.0.0.1:8001/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What incidents were logged yesterday?"}'
```

### Managing the screenshot helper via API

```bash
curl -X POST http://127.0.0.1:8001/start_script
curl -X POST http://127.0.0.1:8001/stop_script
```

Logs from the child process are streamed to the server console. The `/health` endpoint reports whether it is currently running.

## Running `screenshot_upload.py` manually

You can also start the helper without the API wrapper:

```bash
python screenshot_upload.py
```

Ensure the required S3 buckets exist (`primarydata86` for images and `text-description` for generated text by default) or override them via environment variables.

## React prototype (optional)

```bash
cd src
npm install
npm run dev
```

Update the fetch URL inside the React components to match your backend host if necessary.

## Additional utilities

- `bedrock.py`: one-off text invocation of the configured Claude/Bedrock model.
- `converse.py`: demonstrates streaming responses with `converse_stream`.

These scripts assume the same `.env` credentials.

## Troubleshooting tips

- Use `GET /health` to verify the index is ready and see the active Bedrock model.
- If `/ask` returns "Information … was not mentioned", either no passages were retrieved or the model declined to answer without evidence—check your `TXT_PREFIXES` and ensure S3 text uploads succeed.
- Audio capture errors usually point to missing PortAudio libraries or lack of microphone permissions.
- Bedrock permission errors (`AccessDeniedException`) typically require IAM changes for `bedrock:InvokeModel` on the chosen model.
