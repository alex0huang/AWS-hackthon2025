# backend/server.py
import os
import json
from typing import List, Dict, Any, Tuple
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import boto3
import subprocess
import sys
import signal
import atexit
import time # Added for sleep
import boto3
import botocore 

# ========= Load .env file =========
from dotenv import load_dotenv
load_dotenv()
# ======================================

# ========= S3 CONFIG =========
BUCKET_NAME = os.getenv("TXT_BUCKET", "text-description")
# Adjusted prefixes based on screenshot_upload.py, ensure this is correct
PREFIXES = os.getenv("TXT_PREFIXES", "screenshots/").split(",")
REGION = os.getenv("AWS_REGION", "us-east-1")

# ========= BEDROCK CONFIG =========
LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0") # Or your Inference Profile
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "600"))

# ========= Process Management =========
screenshot_process: subprocess.Popen | None = None
# Assume server.py is in the root Hackathon folder now, based on user's structure
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_SCRIPT_PATH = os.path.join(PROJECT_ROOT, "screenshot_upload.py") # server.py and screenshot_upload.py in same dir
print(f"[INFO] Path to screenshot script: {SCREENSHOT_SCRIPT_PATH}")
if not os.path.exists(SCREENSHOT_SCRIPT_PATH):
    print(f"[WARN] Screenshot script not found at expected path: {SCREENSHOT_SCRIPT_PATH}")


# ================================
# AWS Client Functions
# ================================
def s3_client():
    # Credentials should now be loaded from .env if not found elsewhere
    return boto3.client("s3", region_name=REGION)

def bedrock_runtime():
    # Credentials should now be loaded from .env
    return boto3.client("bedrock-runtime", region_name=REGION)

# ================================
# Data Loading and Indexing Functions
# ================================
def read_txt_files_from_s3() -> List[Tuple[str, str]]:
    """Load all .txt files under the configured prefixes."""
    s3 = s3_client()
    docs: List[Tuple[str, str]] = []
    paginator = s3.get_paginator("list_objects_v2")
    print(f"[INFO] Reading from bucket '{BUCKET_NAME}' with prefixes: {PREFIXES}")
    for prefix in PREFIXES:
        prefix = prefix.strip()
        if not prefix:
            continue
        try:
            for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
                if "Contents" not in page:
                    print(f"[INFO] No contents found for prefix: {prefix}")
                    continue
                for obj in page["Contents"]:
                    key = obj["Key"]
                    if not key.endswith(".txt"):
                        continue
                    try:
                        print(f"[INFO] Getting object: {key}")
                        # Check file size if needed: obj['Size'] > 0
                        if obj.get('Size', 0) == 0:
                            print(f"[WARN] Skipping empty file: {key}")
                            continue
                        body = s3.get_object(Bucket=BUCKET_NAME, Key=key)["Body"].read()
                        text = body.decode("utf-8", errors="ignore")
                        if text.strip(): # Ensure content is not just whitespace
                           docs.append((key, text))
                        else:
                            print(f"[WARN] Skipping file with only whitespace: {key}")

                    except Exception as e:
                        print(f"[WARN] failed to load/decode: {key} -> {type(e).__name__}: {e}")
        except Exception as e:
            print(f"[ERROR] Failed to list objects for prefix {prefix}: {type(e).__name__}: {e}")
            # Check bucket existence and permissions
            try:
                s3.head_bucket(Bucket=BUCKET_NAME)
            except botocore.exceptions.ClientError as err:
                 error_code = err.response.get("Error", {}).get("Code")
                 if error_code == '404':
                     print(f"[ERROR] Bucket '{BUCKET_NAME}' not found.")
                 elif error_code == '403':
                     print(f"[ERROR] Access denied to bucket '{BUCKET_NAME}'. Check credentials/permissions.")
                 else:
                     print(f"[ERROR] S3 HeadBucket error: {err}")

    if not docs:
        print(f"[WARN] No non-empty .txt files loaded from S3 bucket '{BUCKET_NAME}' with specified prefixes.")
    return docs

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

def chunk_text(text: str, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    chunks, i, n = [], 0, len(text)
    if size <= overlap:
        print("[WARN] Chunk size should be greater than overlap. Adjusting overlap.")
        overlap = max(0, size - 100) # Ensure some progress

    while i < n:
        j = min(i + size, n)
        chunk = text[i:j].strip()
        if chunk: # Only add non-empty chunks
            chunks.append(chunk)
        if j == n:
            break
        i = j - overlap
        if i < 0: i = 0 # Prevent negative index
        if i <= (j - size): # Ensure progress if overlap is large relative to size
             i = j - size + 10 # Move forward slightly to prevent infinite loop

    # print(f"[DEBUG] Chunked '{text[:20]}...' into {len(chunks)} chunks.")
    return chunks


def build_corpus():
    docs = read_txt_files_from_s3()
    corpus, meta = [], []
    loaded_files = set()
    for fname, content in docs:
        if not content.strip(): # Skip if content is empty after read
            print(f"[WARN] Skipping empty content from file: {fname}")
            continue
        loaded_files.add(fname.split('/')[0] if '/' in fname else fname)
        chunks = chunk_text(content)
        if not chunks:
             print(f"[WARN] No chunks generated for file: {fname}")
             continue
        for idx, ch in enumerate(chunks):
            corpus.append(ch)
            meta.append({"file": fname, "chunk_id": idx})
    print(f"[INFO] loaded files={len(loaded_files)}, chunks={len(corpus)}")
    return corpus, meta

VECTORIZER = TfidfVectorizer(analyzer="char", ngram_range=(3,5))
CORPUS: List[str] = []
META: List[Dict[str, Any]] = []
MATRIX = None

def build_index():
    global CORPUS, META, MATRIX
    print("[INFO] Building index...")
    CORPUS, META = build_corpus()
    if not CORPUS:
        print("[WARN] Corpus is empty. No text found in S3 to index.")
        MATRIX = None
        return
    try:
        MATRIX = VECTORIZER.fit_transform(CORPUS)
        print(f"[INFO] TF-IDF index built: {MATRIX.shape}")
    except ValueError as ve:
         if "empty vocabulary" in str(ve):
             print("[ERROR] TF-IDF failed: Vocabulary is empty. Check input text content.")
         else:
              print(f"[ERROR] TF-IDF failed during fit_transform: {ve}")
         MATRIX = None
    except Exception as e:
        print(f"[ERROR] Failed to build TF-IDF index: {type(e).__name__}: {e}")
        MATRIX = None

def search(query: str, top_k=5):
    if MATRIX is None or MATRIX.shape[0] == 0:
        print("[WARN] Search attempted but index is not built or empty.")
        return []
    try:
        qv = VECTORIZER.transform([query])
        sims = cosine_similarity(qv, MATRIX)[0]
        order = np.argsort(-sims)
        results = [(float(sims[i]), int(i)) for i in order[:top_k] if sims[i] > 0.01]
        # print(f"[DEBUG] Search hits for '{query[:20]}...': {results}")
        return results
    except Exception as e:
        print(f"[ERROR] TF-IDF search failed: {e}")
        return []

# ================================
# Bedrock Call Function (English Response Requested)
# ================================
def call_bedrock_strict_answer(question: str, passages: List[str]) -> str:
    """
    Call Claude via Bedrock.
    The model must answer ONLY from the provided context; otherwise output <NO_ANSWER>.
    **Requests response in English.**
    """
    if not passages:
        print("[INFO] No passages provided to Bedrock.")
        return "" # Don't call LLM if no context

    context = "\n\n---\n\n".join(passages)
    max_context_len = 10000 # Rough character limit
    if len(context) > max_context_len:
        print(f"[WARN] Truncating context from {len(context)} to {max_context_len} chars for Bedrock.")
        context = context[:max_context_len]

    # --- MODIFIED: System Prompt for English ---
    system_prompt = (
        "You are a careful assistant. "
        "Answer ONLY using the provided context. "
        "If the answer cannot be found in the context, respond with exactly: <NO_ANSWER>. "
        "Keep the answer concise and precise, **in English.**" # Changed language
    )
    # --- END MODIFICATION ---

    # --- MODIFIED: User Message in English ---
    user_msg = (
        f"Question:\n{question}\n\n"
        f"Context (Only refer to this content):\n{context}\n\n"
        "Requirements:\n"
        "1) Answer using only the context provided;\n"
        "2) Be brief and precise;\n"
        "3) If the context does not contain the relevant information, output only: <NO_ANSWER>\n"
    )
    # --- END MODIFICATION ---

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": MAX_TOKENS,
        "temperature": 0.0, # Deterministic
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": user_msg}]}
        ],
    }

    try:
        br = bedrock_runtime()
        print(f"[INFO] Calling Bedrock model: {LLM_MODEL_ID} for question: '{question[:30]}...'")
        resp = br.invoke_model(
            modelId=LLM_MODEL_ID,
            body=json.dumps(body).encode("utf-8"),
            accept="application/json",
            contentType="application/json",
        )
        payload = json.loads(resp["body"].read().decode("utf-8"))

        answer = ""
        content_blocks = payload.get("content", [])
        if content_blocks and isinstance(content_blocks, list):
             for c in content_blocks:
                 if c.get("type") == "text":
                     answer += c.get("text", "")
        elif 'completion' in payload: # Fallback for older formats
            answer = payload.get('completion', '')

        answer = (answer or "").strip()
        print(f"[INFO] Bedrock raw answer: '{answer[:50]}...'")
        if "<NO_ANSWER>" in answer or not answer:
            return ""
        return answer
    except botocore.exceptions.ClientError as error:
         error_code = error.response.get("Error", {}).get("Code")
         error_msg = error.response.get("Error", {}).get("Message")
         print(f"[ERROR] Bedrock ClientError: {error_code} - {error_msg}")
         if error_code == 'AccessDeniedException':
             print("[ERROR] Hint: Check IAM permissions for bedrock:InvokeModel and access to the specific model ID/ARN.")
         elif error_code == 'ValidationException':
             print("[ERROR] Hint: Check if the request body format is correct for the model or if the Model ID is valid/accessible.")
         raise HTTPException(status_code=500, detail=f"Bedrock API Error: {error_msg}")
    except Exception as e:
        print(f"[ERROR] Bedrock invocation failed: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Bedrock invocation failed unexpectedly.")

# ================================
# FastAPI Application Setup
# ================================
app = FastAPI(title="S3 TXT RAG API (TF-IDF + Bedrock Claude)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskReq(BaseModel):
    question: str
    top_k: int = 5

class Passage(BaseModel):
    file: str
    chunk_id: int
    score: float
    text: str

class AskResp(BaseModel):
    answer: str
    passages: List[Passage]

@app.on_event("startup")
def _startup():
    print("[INFO] Server starting up, building initial index...")
    build_index()

@app.get("/health")
def health():
    status = {"ok": True, "indexed_chunks": len(CORPUS), "index_ready": MATRIX is not None}
    if MATRIX is not None:
        status["index_shape"] = MATRIX.shape
    status["model_id"] = LLM_MODEL_ID
    # Add check for script process
    status["listener_running"] = screenshot_process is not None and screenshot_process.poll() is None
    if status["listener_running"] and screenshot_process:
        status["listener_pid"] = screenshot_process.pid
    return status

@app.post("/reload")
def reload_index():
    print("[INFO] Reloading index via API call...")
    build_index()
    return {"ok": True, "indexed_chunks": len(CORPUS), "index_ready": MATRIX is not None}

@app.post("/ask", response_model=AskResp)
def ask(req: AskReq):
    q = (req.question or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    print(f"[INFO] Received question for /ask: '{q}'")
    if MATRIX is None:
         print("[WARN] Index not ready, cannot process question.")
         raise HTTPException(status_code=503, detail="Index is not ready. Please wait or reload.")

    hits = search(q, top_k=max(1, min(req.top_k, 20)))

    passages_response = []
    llm_answer = "" # Initialize

    if hits:
        passages_response = [
            Passage(
                file=META[idx]["file"],
                chunk_id=META[idx]["chunk_id"],
                score=round(score, 6),
                text=CORPUS[idx],
            )
            for score, idx in hits if idx < len(CORPUS) # Safety check
        ]
        top_context_texts = [p.text for p in passages_response[:3]]
        try:
             # This now raises HTTPException on Bedrock errors
             llm_answer = call_bedrock_strict_answer(q, top_context_texts)
        except HTTPException as http_exc:
             # Forward the Bedrock error details from call_bedrock_strict_answer
             print(f"[ERROR] Bedrock call failed within /ask: {http_exc.detail}")
             final_answer = f"Error generating AI response: {http_exc.detail}"
             # Still return passages found, but indicate the answer generation failed
             return AskResp(answer=final_answer, passages=passages_response)
        except Exception as e:
             # Catch unexpected errors during the call
             print(f"[ERROR] Unexpected error during Bedrock call in /ask: {e}")
             final_answer = f"Unexpected error generating AI response."
             return AskResp(answer=final_answer, passages=passages_response)

    else:
        print("[INFO] No relevant passages found by search for this question.")
        # No context, so llm_answer remains ""

    # --- MODIFIED: Final answer logic (English fallback) ---
    if not llm_answer:
        # Changed "not found" message to English
        final_answer = f"Information about “{q}” was not mentioned in the context."
    else:
        final_answer = llm_answer
    # --- END MODIFICATION ---

    return AskResp(answer=final_answer, passages=passages_response)


# ================================
# Script Control Endpoints
# ================================
@app.post("/start_script")
def start_script():
    """Starts the screenshot_upload.py script."""
    global screenshot_process

    if screenshot_process and screenshot_process.poll() is None:
        print("[WARN] Attempted to start script, but it seems to be already running.")
        raise HTTPException(status_code=400, detail="Script is already running.")

    if not os.path.exists(SCREENSHOT_SCRIPT_PATH):
         print(f"[ERROR] Screenshot script not found at: {SCREENSHOT_SCRIPT_PATH}")
         raise HTTPException(status_code=500, detail="Screenshot script file not found on server.")

    try:
        python_executable = sys.executable # Use same python as server
        print(f"[INFO] Starting script with command: {python_executable} {SCREENSHOT_SCRIPT_PATH}")

        # Start the script as a background process, run from project root
        screenshot_process = subprocess.Popen(
            [python_executable, SCREENSHOT_SCRIPT_PATH],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE, # Capture stdout
            stderr=subprocess.PIPE, # Capture stderr
            text=True # Decode as text
        )

        print(f"[INFO] Started screenshot script with PID: {screenshot_process.pid}")
        # Short delay to check for immediate errors
        time.sleep(1.0)
        if screenshot_process.poll() is not None:
             stderr_output = screenshot_process.stderr.read() if screenshot_process.stderr else "No stderr captured."
             print(f"[ERROR] Script terminated immediately after starting (exit code {screenshot_process.returncode}). Stderr:\n{stderr_output}")
             screenshot_process = None # Reset state
             raise HTTPException(status_code=500, detail=f"Script failed to start properly. Check server logs. Error: {stderr_output[:200]}...")

        return {"message": "Screenshot script started successfully.", "pid": screenshot_process.pid}
    except Exception as e:
        print(f"[ERROR] Failed to start script: {type(e).__name__}: {e}")
        screenshot_process = None # Ensure state is reset
        raise HTTPException(status_code=500, detail=f"Failed to start script: {e}")

@app.post("/stop_script")
def stop_script():
    """Stops the running screenshot_upload.py script."""
    global screenshot_process

    if screenshot_process is None or screenshot_process.poll() is not None:
        print("[WARN] Attempted to stop script, but it is not running.")
        raise HTTPException(status_code=400, detail="Script is not running.")

    try:
        pid = screenshot_process.pid
        print(f"[INFO] Attempting to stop script with PID: {pid} using SIGINT...")

        # Send SIGINT (Ctrl+C)
        screenshot_process.send_signal(signal.SIGINT)

        try:
            # Wait a few seconds
            screenshot_process.wait(timeout=5)
            print(f"[INFO] Script with PID {pid} terminated gracefully (exit code {screenshot_process.returncode}).")
        except subprocess.TimeoutExpired:
            print(f"[WARN] Script {pid} did not exit via SIGINT, sending SIGKILL.")
            screenshot_process.kill()
            screenshot_process.wait() # Wait for kill
            print(f"[INFO] Script with PID {pid} killed.")
        except Exception as e:
            print(f"[ERROR] Error during script wait/kill: {e}")
            pass # Try to reset state anyway

        process_pid = screenshot_process.pid # Store pid before setting to None
        screenshot_process = None # Reset state
        return {"message": "Stop signal sent to screenshot script.", "pid": process_pid} # Return original pid
    except Exception as e:
        print(f"[ERROR] Failed to send stop signal to script: {type(e).__name__}: {e}")
        # Try to reset state even on error
        current_pid = screenshot_process.pid if screenshot_process else None
        screenshot_process = None
        raise HTTPException(status_code=500, detail=f"Failed to stop script (PID: {current_pid}): {e}")

# ================================
# Server Shutdown Cleanup
# ================================
def cleanup_screenshot_process():
    global screenshot_process
    if screenshot_process and screenshot_process.poll() is None:
        print("[INFO] Server exiting, attempting to stop screenshot script...")
        try:
            stop_script() # Call the existing stop logic
        except HTTPException as e:
             # Log but don't prevent server shutdown
             print(f"[WARN] Error stopping script during server shutdown: {e.detail}")
        except Exception as e:
             print(f"[WARN] Unexpected error stopping script during server shutdown: {e}")


# Register cleanup to run when the server process exits
atexit.register(cleanup_screenshot_process)
