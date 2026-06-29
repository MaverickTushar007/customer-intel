import { useState, useEffect, useRef } from "react";
import axios from "axios";

const API = process.env.REACT_APP_API_URL || "http://localhost:8765";

const PRESET_QUESTIONS = [
  "How many visitors came today?",
  "How many people were in the venue between 8pm and 9pm?",
  "What was the average wait time this hour?",
  "How many people left without being served today?",
  "Which hour had the most visitors?",
  "What was the busiest time period today?",
  "Who stayed the longest and for how long?",
  "How does the abandonment rate look today?",
  "How many visitors came in the last 30 minutes?",
  "What percentage of visitors were served today?",
];

function KPICard({ icon, label, value, detail, color = "#f59e0b" }) {
  return (
    <div
      style={{
        background: "#111827",
        border: "1px solid #1f2937",
        borderRadius: 16,
        padding: "24px 28px",
        flex: 1,
        minWidth: 180,
        borderTop: `3px solid ${color}`,
      }}
    >
      <div style={{ fontSize: 22, marginBottom: 8 }}>{icon}</div>
      <div
        style={{
          color: "#6b7280",
          fontSize: 12,
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: 1,
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div
        style={{
          color: "#f9fafb",
          fontSize: 32,
          fontWeight: 800,
          lineHeight: 1,
          marginBottom: 6,
        }}
      >
        {value}
      </div>
      {detail && <div style={{ color: "#4b5563", fontSize: 12 }}>{detail}</div>}
    </div>
  );
}

function dwellLabel(s) {
  if (!s) return "—";
  if (s < 60) return `${parseFloat(s).toFixed(0)}s`;
  return `${(s / 60).toFixed(1)} min`;
}

function formatTime(iso) {
  if (!iso) return "—";
  return iso.slice(11, 19) + " UTC";
}

function UploadScreen({ onProcessingStart }) {
  const [dragOver, setDragOver] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef();

  const handleFile = async (file) => {
    if (!file) return;
    setUploading(true);
    setError("");
    const form = new FormData();
    form.append("file", file);
    try {
const r = await axios.post(`${API}/upload`, form, {
  headers: { "Content-Type": "multipart/form-data" },
});

console.log("Backend response:", r.data);

onProcessingStart(r.data.job_id);
    } catch (e) {
      setError("Upload failed. Make sure the API is running.");
      setUploading(false);
    }
  };

  const handleDemo = async (key) => {
    setUploading(true);
    setError("");
    try {
      const r = await axios.post(`${API}/demo/${key}`);
      if (r.data.error) { setError(r.data.error); setUploading(false); return; }
      onProcessingStart(r.data.job_id);
    } catch (e) {
      setError("Demo failed. Make sure the API server is running locally.");
      setUploading(false);
    }
  };

  const handleUrl = async () => {
    if (!urlInput.trim()) return;
    setUploading(true);
    setError("");
    try {
      const r = await axios.post(`${API}/upload/url`, { url: urlInput });
      if (r.data.error) {
        setError(r.data.error);
        setUploading(false);
        return;
      }
      onProcessingStart(r.data.job_id);
    } catch (e) {
      setError("Failed to process URL.");
      setUploading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0a0f1a",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 40,
        fontFamily: "'Inter', sans-serif",
      }}
    >
      <div style={{ color: "#f59e0b", fontSize: 11, fontWeight: 700, letterSpacing: 3, textTransform: "uppercase", marginBottom: 12 }}>
        Powered by Computer Vision + AI
      </div>
      <h1 style={{ color: "#f9fafb", fontSize: 36, fontWeight: 800, margin: "0 0 8px", textAlign: "center" }}>
        Customer Intelligence Platform
      </h1>
      <p style={{ color: "#4b5563", fontSize: 15, marginBottom: 48, textAlign: "center", maxWidth: 500 }}>
        Upload your venue footage and get instant insights on visitor behaviour, dwell time, and service efficiency.
      </p>

      <div style={{ width: "100%", maxWidth: 560 }}>
        {/* Drag & Drop */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]); }}
          onClick={() => fileRef.current.click()}
          style={{
            border: `2px dashed ${dragOver ? "#f59e0b" : "#374151"}`,
            borderRadius: 16, padding: "48px 32px", textAlign: "center",
            cursor: "pointer", marginBottom: 24,
            background: dragOver ? "#1a1500" : "#111827", transition: "all 0.2s",
          }}
        >
          <div style={{ fontSize: 40, marginBottom: 12 }}>🎥</div>
          <div style={{ color: "#f9fafb", fontWeight: 600, fontSize: 16, marginBottom: 6 }}>Drop your video here</div>
          <div style={{ color: "#4b5563", fontSize: 13 }}>MP4, MOV, AVI supported · or click to browse</div>
          <input ref={fileRef} type="file" accept="video/*" style={{ display: "none" }} onChange={(e) => handleFile(e.target.files[0])} />
        </div>

        {/* URL input */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
          <div style={{ flex: 1, height: 1, background: "#1f2937" }} />
          <span style={{ color: "#4b5563", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: 1 }}>or paste a YouTube URL</span>
          <div style={{ flex: 1, height: 1, background: "#1f2937" }} />
        </div>
        <div style={{ display: "flex", gap: 12, marginBottom: 24 }}>
          <input
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="https://www.youtube.com/watch?v=..."
            style={{ flex: 1, background: "#111827", border: "1px solid #374151", borderRadius: 10, padding: "12px 18px", color: "#f9fafb", fontSize: 14, outline: "none" }}
          />
          <button
            onClick={handleUrl}
            disabled={uploading}
            style={{ background: "#f59e0b", color: "#0a0f1a", border: "none", borderRadius: 10, padding: "12px 24px", fontWeight: 800, fontSize: 14, cursor: "pointer" }}
          >
            Analyse URL
          </button>
        </div>

        {error && (
          <div style={{ background: "#1c0a00", border: "1px solid #7c2d12", borderRadius: 10, padding: "12px 16px", color: "#f97316", fontSize: 13, marginBottom: 16 }}>
            {error}
          </div>
        )}
        {uploading && (
          <div style={{ textAlign: "center", color: "#6b7280", fontSize: 13, marginBottom: 16 }}>
            Uploading video...
          </div>
        )}

        {/* Demo Videos */}
        <div style={{ marginTop: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <div style={{ flex: 1, height: 1, background: "#1f2937" }} />
            <span style={{ color: "#4b5563", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: 1 }}>or try a demo</span>
            <div style={{ flex: 1, height: 1, background: "#1f2937" }} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {[
              { key: "retail_store", icon: "🏪", title: "Retail Store", desc: "720p CCTV · 97s · 46 visitors", tag: "Best demo" },
              { key: "cafe",         icon: "☕", title: "Cafe (Surabaya)", desc: "1080p · entrance cam · 8 visitors", tag: null },
              { key: "midtown",      icon: "🏙️", title: "Corner Store NYC", desc: "720p · street-level · real footage", tag: null },
              { key: "retail_usa",   icon: "🛒", title: "US Retail Store", desc: "1080p · wide angle · busy floor", tag: null },
            ].map((demo) => (
              <button
                key={demo.key}
                onClick={() => handleDemo(demo.key)}
                disabled={uploading}
                style={{ background: "#111827", border: "1px solid #374151", borderRadius: 12, padding: "16px", textAlign: "left", cursor: uploading ? "not-allowed" : "pointer", opacity: uploading ? 0.5 : 1, transition: "border-color 0.2s", position: "relative" }}
                onMouseEnter={e => e.currentTarget.style.borderColor = "#f59e0b"}
                onMouseLeave={e => e.currentTarget.style.borderColor = "#374151"}
              >
                {demo.tag && (
                  <span style={{ position: "absolute", top: 10, right: 10, background: "#f59e0b", color: "#0a0f1a", fontSize: 9, fontWeight: 800, padding: "2px 7px", borderRadius: 20, textTransform: "uppercase", letterSpacing: 1 }}>{demo.tag}</span>
                )}
                <div style={{ fontSize: 22, marginBottom: 8 }}>{demo.icon}</div>
                <div style={{ color: "#f9fafb", fontWeight: 700, fontSize: 13, marginBottom: 4 }}>{demo.title}</div>
                <div style={{ color: "#4b5563", fontSize: 11 }}>{demo.desc}</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}


function App() {
  const handleProcessingStart = (jobId) => {
    console.log("Job ID:", jobId);
    alert(`Upload successful!\nJob ID: ${jobId}`);
  };

  return (
    <UploadScreen onProcessingStart={handleProcessingStart} />
  );
}

export default App;
