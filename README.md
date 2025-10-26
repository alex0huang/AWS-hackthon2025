# Hackathdiff --git a/README.md b/README.md
index 021113549ece2551c17b5554ac4fca19131cd15b..56e3f2eef408f2fd64167f93b13ad226057f3567 100644
--- a/README.md
+++ b/README.md
@@ -1 +1,35 @@
-# Hackathon
\ No newline at end of file
+# Hackathon
+
+## Prerequisites
+
+### System packages
+Some optional tools (such as the screenshot/audio helper) rely on PyAudio,
+which requires the PortAudio system library. Install it before running
+`pip install -r requirements.txt`:
+
+- **macOS:** `brew install portaudio`
+- **Debian/Ubuntu:** `sudo apt-get install portaudio19-dev`
+
+### Python environment
+```
+python -m venv .venv
+source .venv/bin/activate
+pip install -r requirements.txt
+```
+
+Create a `.env` file (you can start from an `.env.example` template if one is available)
+and fill in your AWS credentials, S3 bucket/prefix, and Bedrock model details.
+
+## Running the FastAPI server
+```
+uvicorn server:app --reload --port 8001
+```
+
+Once the server is up you can test the `/ask` endpoint with `curl` or by
+opening `index.html` in a browser, which will call the API from a simple UI.
+
+## Front-end sources
+The `src/` directory contains a Vite/React prototype (`main.jsx`, `App.jsx`,
+`AIConsoleUI.jsx`, `ChatBox.jsx`, `styles.css`). To run it you need a Node.js
+setup with Vite tooling (not included in this repository); once dependencies
+are installed you can start the dev server with `npm run dev`.
