# 按下 Enter 键截图上传分析；按空格键录音上传到 Whisper 识别

from pynput import keyboard
from datetime import datetime
from mss import mss
from PIL import Image
import io
import time
import os
import boto3
import botocore
from dotenv import load_dotenv
import sounddevice as sd
from scipy.io.wavfile import write
import numpy as np
import json
from dotenv import load_dotenv
import base64
import pyaudio
import wave
import threading

# --- Load environment variables ---
load_dotenv()

# --- AWS and S3 Config ---
BUCKET_NAME = "primarydata86"
TXT_BUCKET_NAME = "text-description"
REGION = "us-east-1"
LOG_FOLDER = "analysis_logs"

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# --- AWS Clients ---
s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=REGION,
)

bedrock_client = boto3.client(
    service_name="bedrock-runtime",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name="us-east-1",
)

# =====================================================
# IMAGE ANALYSIS SECTION
# =====================================================

def get_description_from_bedrock(image_buffer):
    """Send screenshot to Bedrock for visual analysis"""
    print("\n🤖 Asking Bedrock to analyze the image...")
    try:
        model_id = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
        user_message = "Analyze this image and provide a detailed description."

        image_buffer.seek(0)
        conversation = [
            {
                "role": "user",
                "content": [
                    {
                        "image": {
                            "format": "png",
                            "source": {"bytes": image_buffer.read()},
                        }
                    },
                    {"text": user_message},
                ],
            }
        ]

        response = bedrock_client.converse(
            modelId=model_id,
            messages=conversation,
            inferenceConfig={"maxTokens": 2048, "temperature": 0.5},
        )

        response_actual = response["output"]["message"]["content"]
        response_text = response_actual[0]["text"]

        print("\n--- Response ---")
        print(response_text)
        print("\n" + "=" * 30 + "\n")

        return f"--- Response ---\n{response_text}"

    except Exception as e:
        print(f"❌ BEDROCK ERROR: {e}")
        return None

# =====================================================
# FILE MANAGEMENT
# =====================================================

def save_analysis_to_file(analysis_text, log_filename):
    """Save text to local log folder"""
    try:
        os.makedirs(LOG_FOLDER, exist_ok=True)
        path = os.path.join(LOG_FOLDER, log_filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(analysis_text)
        print(f"✅ Analysis saved to: {path}")
    except Exception as e:
        print(f"❌ Error saving log file: {e}")

def capture_screenshot():
    with mss() as sct:
        # Assuming monitor 1 is your main display. Adjust if needed.
        monitor = sct.monitors[1]
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.rgb)

        # --- RESIZE IMAGE ---
        # Define a maximum width (adjust as needed, 1920 is common HD)
        max_width = 1920
        if img.width > max_width:
            print(f"[INFO] Resizing screenshot from {img.width}x{img.height} to max width {max_width}px...")
            # Calculate new height to maintain aspect ratio
            aspect_ratio = img.height / img.width
            new_height = int(max_width * aspect_ratio)
            # Resize using a high-quality filter
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            print(f"[INFO] Resized to {img.width}x{img.height}")
        # --- END RESIZE ---

        buf = io.BytesIO()
        # Save PNG with compression (level 6 is a good balance)
        img.save(buf, format="PNG", optimize=True, compress_level=6)
        print(f"[INFO] Screenshot saved to buffer with compression. Size: {buf.tell()} bytes")
        buf.seek(0) # Reset buffer position to the beginning
        return buf

def upload_image_to_s3(buf, filename):
    try:
        key = f"screenshots/{filename}"
        buf.seek(0)
        s3.upload_fileobj(
            Fileobj=buf,
            Bucket=BUCKET_NAME,
            Key=key,
            ExtraArgs={"ContentType": "image/png"},
        )
        print(f"✅ Screenshot uploaded: {key}")
    except Exception as e:
        print(f"❌ S3 Upload error: {e}")

def upload_text_to_s3(text, filename):
    try:
        key = f"screenshots/{filename}"
        s3.put_object(
            Bucket=TXT_BUCKET_NAME,
            Key=key,
            Body=text.encode("utf-8"),
            ContentType="text/plain; charset=utf-8",
        )
        print(f"✅ Text uploaded: {key}")
    except Exception as e:
        print(f"❌ Text upload error: {e}")

# =====================================================
# AUDIO RECORDING + WHISPER TRANSCRIPTION
# =====================================================

recording = []
is_recording = False
stream = None

CHUNK = 1024
FORMAT = pyaudio.paInt16 # Now pyaudio is defined
CHANNELS = 1
RATE = 16000
is_recording = False
audio_frames = []
pyaudio_instance = None # Initialize globally
stream = None

def audio_callback(indata, frames, time, status):
    global recording
    if is_recording:
        recording.append(indata.copy())

def toggle_recording():
    """Shift key: start/stop recording and transcribe directly from memory"""
    global is_recording, recording, stream, pyaudio_instance # Add pyaudio_instance
    if not is_recording:
        print("🎙️ Start recording... Press SHIFT again to stop.")
        is_recording = True
        recording = []
        try:
            pyaudio_instance = pyaudio.PyAudio() # Initialize PyAudio here
            # Check if default device supports 16kHz
            sd.check_input_settings(samplerate=16000, channels=1)
            # Use PyAudio stream for consistency with wave saving
            stream = pyaudio_instance.open(format=FORMAT,
                                           channels=CHANNELS,
                                           rate=RATE,
                                           input=True,
                                           frames_per_buffer=CHUNK,
                                           stream_callback=audio_callback_pyaudio) # Use PyAudio callback
            stream.start_stream()
        except Exception as e:
            print(f"❌ Error starting audio stream: {e}")
            print("   Try checking your microphone settings or sample rate support.")
            is_recording = False
            stream = None
            if pyaudio_instance:
                pyaudio_instance.terminate()
            pyaudio_instance = None
            return

    else:
        print("🛑 Stop recording...")
        is_recording = False
        if stream:
            try:
                stream.stop_stream()
                stream.close()
            except Exception as e:
                 print(f"Error stopping/closing stream: {e}")
            stream = None
        if pyaudio_instance:
             pyaudio_instance.terminate() # Terminate PyAudio
             pyaudio_instance = None

        # --- Process Audio ---
        if not recording:
             print("⚠️ No audio captured.")
             return

        print("...Processing audio in memory...")
        # Save the recorded data to an in-memory WAV buffer
        audio_buffer = io.BytesIO()
        try:
            with wave.open(audio_buffer, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                # Use PyAudio's get_sample_size
                sample_width = pyaudio.PyAudio().get_sample_size(FORMAT)
                wf.setsampwidth(sample_width)
                wf.setframerate(RATE)
                wf.writeframes(b''.join(recording))
            audio_buffer.seek(0) # Rewind buffer to the beginning
            audio_data_bytes = audio_buffer.read()
            print(f"✅ Audio processed in memory ({len(audio_data_bytes)} bytes)")

            # Transcribe directly from memory bytes
            text = transcribe_with_whisper(audio_data_bytes) # Pass bytes
            if text:
                timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                s3_text_filename = f"transcript_{timestamp_str}.txt"
                upload_text_to_s3(text, s3_text_filename) # Upload transcript
        except Exception as e:
             print(f"❌ Error processing or transcribing audio from memory: {e}")
        finally:
            audio_buffer.close() # Close the memory buffer

def audio_callback_pyaudio(in_data, frame_count, time_info, status):
    global recording
    if is_recording:
        recording.append(in_data)
    return (in_data, pyaudio.paContinue)

def transcribe_with_whisper(audio_data_bytes): # Changed parameter
    """Use Bedrock Whisper endpoint for transcription from memory bytes"""
    if not audio_data_bytes:
        print("❌ Cannot transcribe, no audio data provided.")
        return None
    try:
        # Make sure BEDROCK_WHISPER_ARN is set in .env
        whisper_arn = os.getenv("BEDROCK_WHISPER_ARN")
        if not whisper_arn:
             print("❌ BEDROCK_WHISPER_ARN not set in .env file.")
             return None

        # Encode bytes as hex
        hex_audio = audio_data_bytes.hex()

        body = json.dumps({
            "audio_input": hex_audio,
            "language": "english", # Or make this configurable
            "task": "transcribe"
        })

        print("🤖 Asking Bedrock Whisper to transcribe audio...")
        response = bedrock_client.invoke_model(
            modelId=whisper_arn, # Use variable
            contentType='application/json',
            accept='application/json',
            body=body
        )

        response_body_str = response['body'].read().decode('utf-8')
        response_body = json.loads(response_body_str)

        text = ""
        if "text" in response_body and isinstance(response_body["text"], list):
            text = " ".join(response_body["text"])
        elif "transcript" in response_body:
             text = response_body["transcript"]
        else:
            print("❌ WHISPER ERROR: Could not parse transcript from response.")
            print(response_body)
            return None

        # Clean up extra whitespace
        text = ' '.join(text.split())

        print("\n🗣️ Transcribed text:")
        print(text)
        print("\n" + "=" * 30 + "\n")
        return text

    except Exception as e:
        print(f"❌ Transcription error: {type(e).__name__}: {e}")
        return None


# =====================================================
# KEYBOARD HANDLER
# =====================================================

_last_ts = 0

def on_press(key):
    global _last_ts, is_recording # Make sure is_recording is global here

    # --- Check for Esc key ---
    if key == keyboard.Key.esc:
        if is_recording: # Stop recording cleanly if Esc is pressed
             print("\n🛑 Esc pressed, stopping recording...")
             toggle_recording() # Use the toggle function to stop and process
        print("\n👋 Exiting listener... Goodbye!")
        return False # Stop the listener

    # --- Check for Shift key (Audio Toggle) ---
    # We check for both left and right shift
    if key == keyboard.Key.shift or key == keyboard.Key.shift_r:
        now = time.time()
        # Add a short debounce specifically for the toggle key
        if now - _last_ts < 0.5: # 500ms debounce
            return
        _last_ts = now
        toggle_recording() # Call the unified start/stop function
        return # Don't process other keys if shift was pressed

    # --- Check for Enter key (Screenshot) ---
    if key == keyboard.Key.enter:
        if is_recording:
             print("\n⚠️ Cannot take screenshot while recording. Press SHIFT to stop recording first.")
             return # Prevent action while recording

        now = time.time()
        # Use a longer debounce for screenshot action
        if now - _last_ts < 3.0:
            print("... Please wait ...")
            return
        _last_ts = now

        print("\n📸 Capturing screenshot...")
        buf = capture_screenshot()
        analysis = get_description_from_bedrock(buf)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if analysis:
            log_filename = f"analysis_{timestamp}.txt"
            save_analysis_to_file(analysis, log_filename)
            upload_text_to_s3(analysis, log_filename) # Upload analysis text
        # Upload screenshot regardless of analysis result
        upload_image_to_s3(buf, f"screenshot_{timestamp}.png")
        
def verify_aws():
    try:
        sts = boto3.client(
            "sts",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=REGION,
        )
        who = sts.get_caller_identity()
        print(f"✅ AWS OK. Account: {who.get('Account')}  UserId: {who.get('UserId')}")
    except botocore.exceptions.ClientError as e:
        print("❌ AWS credential error:", e)
        raise

def main():
    verify_aws()
    print("📸 Listening for global keys:")
    print("   Enter → Screenshot + Analyze")
    print("   Space → Record voice + Whisper Transcription")
    print("   Esc   → Exit")
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

if __name__ == "__main__":
    main()