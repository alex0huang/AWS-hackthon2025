// src/AIConsoleUI.jsx
import React, { useEffect, useState } from "react";
import "./styles.css";

/** ------- Status Types ------- */
const Status = {
  Idle: "idle",
  Recording: "recording",
  Uploading: "uploading",
  Queued: "queued",
  Processing: "processing",
  Succeeded: "succeeded",
  Failed: "failed",
};

/** ------- Simple Event Bus (Mock Realtime) ------- */
function createBus() {
  const map = new Map();
  return {
    ensure(topic) {
      if (!map.has(topic)) map.set(topic, { listeners: new Set() });
      return map.get(topic);
    },
    push(topic, payload) {
      const t = this.ensure(topic);
      t.listeners.forEach((fn) => fn(payload));
    },
    listen(topic, fn) {
      const t = this.ensure(topic);
      t.listeners.add(fn);
      return () => t.listeners.delete(fn);
    },
  };
}
const bus = createBus();

/** ------- Frontend Mock Adapter (Simulates backend) ------- */
function createMockAdapter() {
  let mediaRecorder = null;
  let chunks = [];
  let timer = null;

  async function startCapture() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunks = [];
      mediaRecorder.ondataavailable = (e) => e.data?.size && chunks.push(e.data);
      mediaRecorder.start();
    } catch {
      mediaRecorder = null;
      chunks = [];
      console.warn("Microphone permission denied. Running in mock mode.");
    }
  }

  async function stopCaptureAndSubmit() {
    if (mediaRecorder) {
      await new Promise((res) => {
        mediaRecorder.onstop = () => res();
        mediaRecorder.stop();
      });
    }
    const clientRunId = crypto.randomUUID();

    // Simulate step-by-step progress
    bus.push(clientRunId, { status: Status.Queued, progress: 0 });
    let p = 0;
    timer = setInterval(() => {
      p = Math.min(100, p + Math.floor(Math.random() * 18 + 5));
      if (p < 100) {
        bus.push(clientRunId, { status: Status.Processing, progress: p });
      } else {
        clearInterval(timer);
        timer = null;
        bus.push(clientRunId, {
          status: Status.Succeeded,
          progress: 100,
          result: {
            summary: "This is a mock analysis summary generated for demo purposes.",
            entities: [
              { type: "Person", value: "Alice" },
              { type: "Topic", value: "AI Discussion" },
            ],
            notes: "Mock notes:\n- Key Insight 1\n- Key Insight 2",
          },
        });
      }
    }, 600);

    return clientRunId;
  }

  function subscribe(clientRunId, onUpdate) {
    return bus.listen(clientRunId, onUpdate);
  }

  return { startCapture, stopCaptureAndSubmit, subscribe };
}

/** ------- UI Component ------- */
export default function AIConsoleUI({ adapter = createMockAdapter() }) {
  const [status, setStatus] = useState(Status.Idle);
  const [progress, setProgress] = useState(0);
  const [clientRunId, setClientRunId] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!clientRunId) return;
    const unsubscribe = adapter.subscribe(clientRunId, (update) => {
      if (update.status) setStatus(update.status);
      if (typeof update.progress === "number") setProgress(update.progress);
      if (update.result) setResult(update.result);
      if (update.error) setError(update.error);
    });
    return () => unsubscribe && unsubscribe();
  }, [clientRunId]);

  const handleStart = async () => {
    setError(null);
    setResult(null);
    setProgress(0);
    try {
      await adapter.startCapture();
      setStatus(Status.Recording);
    } catch (e) {
      setError(e.message || "Failed to start recording.");
      setStatus(Status.Failed);
    }
  };

  const handleStop = async () => {
    setError(null);
    setProgress(5);
    setStatus(Status.Uploading);
    try {
      const id = await adapter.stopCaptureAndSubmit();
      setClientRunId(id);
    } catch (e) {
      setError(e.message || "Failed to submit recording.");
      setStatus(Status.Failed);
    }
  };

  return (
    <div className="container">
      <header className="h1">
        <span>AI Analysis Interface</span>
        <StatusBadge status={status} />
      </header>

      <div className="row">
        <button
          className="btn primary"
          onClick={handleStart}
          disabled={[Status.Recording, Status.Uploading, Status.Queued, Status.Processing].includes(status)}
        >
          Start Recording
        </button>
        <button
          className="btn"
          onClick={handleStop}
          disabled={status !== Status.Recording}
        >
          Stop
        </button>
      </div>

      <ProgressBar value={progress} visible={[Status.Uploading, Status.Queued, Status.Processing, Status.Succeeded].includes(status)} />

      {error && <div className="alert" role="alert">Error: {error}</div>}

      {result && (
        <section className="card">
          <h2>Analysis Result</h2>
          {result.summary && (
            <div>
              <small>Summary</small>
              <p>{result.summary}</p>
            </div>
          )}
          {Array.isArray(result.entities) && (
            <div>
              <small>Entities</small>
              <ul>
                {result.entities.map((e, i) => (
                  <li key={i}>{e.type}: {e.value}</li>
                ))}
              </ul>
            </div>
          )}
          {result.notes && (
            <div>
              <small>Notes</small>
              <pre>{result.notes}</pre>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

/** ------- Sub-components ------- */
function StatusBadge({ status }) {
  const STATES = {
    [Status.Idle]: ["Idle", "#e5e7eb", "#374151"],
    [Status.Recording]: ["Recording...", "#ffe4e6", "#be123c"],
    [Status.Uploading]: ["Uploading...", "#fef3c7", "#b45309"],
    [Status.Queued]: ["Queued...", "#fef3c7", "#b45309"],
    [Status.Processing]: ["Processing...", "#dbeafe", "#1d4ed8"],
    [Status.Succeeded]: ["Completed", "#d1fae5", "#065f46"],
    [Status.Failed]: ["Failed", "#fee2e2", "#b91c1c"],
  }[status] || ["Unknown", "#e5e7eb", "#374151"];

  return (
    <span className="badge" style={{ background: STATES[1], color: STATES[2] }}>
      {STATES[0]}
    </span>
  );
}

function ProgressBar({ value, visible }) {
  if (!visible) return null;
  return (
    <div className="progress">
      <div className="progress-head">
        <span>Progress</span>
        <span>{value}%</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
    </div>
  );
}
