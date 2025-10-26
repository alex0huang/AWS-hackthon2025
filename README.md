 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/README.md b/README.md
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
diff --git a/requirements.txt b/requirements.txt
index 56c095c85e74e7234788b9fe1f982c8742476d84..cae94cea6b8b4eccaa986961abac5d7f0eb083d2 100644
GIT binary patch
literal 520
zcmZXQO=}}D42JLi6@tRjJ!Cd%8%hIn2&AX(ZUbq_p_HN-D~%hEZ7ez2`S;aKpnE7f
z>En6zN*A!D26h=cI>mf|AHbB4l+6xVFga6>u8ldoXcjDH`)X2eF^Fqls6*#pjk$p3
zb_1K$gK46~>$;v*H`8i9A5(?te}%6lW8fX-x}H|En`%1XD-_hte}0=#y3`wP-NDJk
z6Xr1VpT&76j#zigK8A^nLg6^bYM76XIHBx^Tt&ZzP^c(b*H_h@Hd17n8g~Ci?p9Zq
z?7eH$@KrTGJK40EDDXat`gx$fiF&dMhE&9K%x3MpkEikGVqJvGUCh8=)LThDqODT@
zQ+@w^e7ax2x?hf?mJ$Wa5Ch1bU>&oZ8{D%{2Wll_?kfcWI&2>|3urQ(zy*E2_mGsp
uL28^>QR6WDdTvUPvH&hN0w$TflYA#;cN0rTJ><-DEWv8QwKP0iU;YWU3#()R

literal 804
zcmZ{iK}*9x5QXO~_#cFV=)q#tA|5;xdaHs^#Dj>mW=o^ZrexFB{(1GA*<_)LEZHPG
zZ{EK5cE7)RawJdUWX5|gwM?btZz~nwAFLho1XgO<*nB7l;HIoK%quBGSJqSud9yAr
z&u!I94yI;)G1N+Sw&Lkk^fQblh(eYvLb-bEI7HKg_e4fAw%!@s4bP?AGBWAQm7FsV
z7~0j<qXzd6D$w7UOOM96IZ{4l%3$pCrEHy!5$e=u%;8?{tm5%o;(cd-0Vf4n6(G-W
z;=tG9_jn$usY}HaAc9qup^*iyJe|2YbbN1;di9wZ_TA1Uu&XLsBt%rMdVjMi&Y?8!
ztS&ELyD^V_(3PE1^czt1nK(1KPD!lsvNYwhHhX0mq<WXsgcNG_Q~kj_HEn8R)^>J2
z@h)^)JsMP<{+IN`Odc$!CF-_&2@b*L)GAm{I61wadNcp-`U-M|;)<klbZRcADer0G
V(R~A`HHveFYwxf#Y&=!%{Q+0rd{Y1b

 
EOF
)
