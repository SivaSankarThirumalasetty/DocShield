import React, { useState, useEffect } from "react";
import { 
  Shield, 
  CheckCircle, 
  AlertTriangle, 
  XCircle, 
  FileText, 
  User, 
  Search, 
  Layers, 
  Eye, 
  Activity,
  ChevronRight,
  ShieldCheck,
  AlertOctagon,
  FileCheck,
  Check,
  RotateCcw,
  Info
} from "lucide-react";
import { checkHealth, analyzeDocument, submitOfficerReview } from "./api";

export default function App() {
  const [health, setHealth] = useState(null);
  const [docFile, setDocFile] = useState(null);
  const [docPreview, setDocPreview] = useState(null);
  const [personFile, setPersonFile] = useState(null);
  const [personPreview, setPersonPreview] = useState(null);
  const [docTypeHint, setDocTypeHint] = useState("auto");
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [showEla, setShowEla] = useState(false);

  // Officer Review Form State (Stage 12)
  const [officerId, setOfficerId] = useState("SSB-OFC-409");
  const [officerName, setOfficerName] = useState("Insp. Rajesh Sharma");
  const [officerDecision, setOfficerDecision] = useState("CLEARED_FOR_ENTRY");
  const [overrideAi, setOverrideAi] = useState(false);
  const [officerNotes, setOfficerNotes] = useState("");
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [reviewStatusMsg, setReviewStatusMsg] = useState(null);

  useEffect(() => {
    fetchHealth();
  }, []);

  const fetchHealth = async () => {
    try {
      const data = await checkHealth();
      setHealth(data);
    } catch {
      setHealth({ status: "offline" });
    }
  };

  const handleDocChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setDocFile(file);
      setDocPreview(URL.createObjectURL(file));
      setResult(null);
      setReviewStatusMsg(null);
    }
  };

  const handlePersonChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setPersonFile(file);
      setPersonPreview(URL.createObjectURL(file));
    }
  };

  const loadPreset = async (presetType) => {
    setError(null);
    setResult(null);
    setReviewStatusMsg(null);
    try {
      let docUrl = "";
      let personUrl = "/samples/sample_person.png";
      let hint = "auto";

      if (presetType === "aadhaar_valid") {
        docUrl = "/samples/aadhaar_valid.png";
        hint = "AADHAAR";
      } else if (presetType === "aadhaar_invalid") {
        docUrl = "/samples/aadhaar_invalid_checksum.png";
        hint = "AADHAAR";
      } else if (presetType === "passport") {
        docUrl = "/samples/passport_sample.png";
        hint = "PASSPORT";
      }

      // Fetch doc
      const dRes = await fetch(docUrl);
      const dBlob = await dRes.blob();
      const dFile = new File([dBlob], docUrl.split("/").pop(), { type: "image/png" });
      setDocFile(dFile);
      setDocPreview(docUrl);
      setDocTypeHint(hint);

      // Fetch person
      const pRes = await fetch(personUrl);
      const pBlob = await pRes.blob();
      const pFile = new File([pBlob], "sample_person.png", { type: "image/png" });
      setPersonFile(pFile);
      setPersonPreview(personUrl);
    } catch {
      setError("Failed to load sample card assets.");
    }
  };

  const handleReset = () => {
    setDocFile(null);
    setDocPreview(null);
    setPersonFile(null);
    setPersonPreview(null);
    setResult(null);
    setError(null);
    setReviewStatusMsg(null);
    setActiveTab("overview");
  };

  const handleAnalyze = async () => {
    if (!docFile) {
      setError("Please select or drop an identity document image to screen.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const data = await analyzeDocument(docFile, personFile, docTypeHint);
      setResult(data);
      setActiveTab("overview");
      // Pre-fill officer recommendation based on AI verdict
      if (data.risk_assessment?.verdict === "CLEARED") {
        setOfficerDecision("CLEARED_FOR_ENTRY");
      } else if (data.risk_assessment?.verdict === "SECONDARY_INSPECTION") {
        setOfficerDecision("REFERRED_TO_SECONDARY");
      } else {
        setOfficerDecision("DETAINED");
      }
    } catch (err) {
      setError(err.message || "Failed to execute document analysis.");
    } finally {
      setLoading(false);
    }
  };

  const handleOfficerSignoff = async (e) => {
    e.preventDefault();
    if (!result?.case_id) return;

    setReviewSubmitting(true);
    setReviewStatusMsg(null);
    try {
      const updated = await submitOfficerReview(result.case_id, {
        officer_id: officerId,
        officer_name: officerName,
        decision: officerDecision,
        override_ai_verdict: overrideAi,
        notes: officerNotes || "Standard border screening protocol verified.",
      });
      setResult(updated);
      setReviewStatusMsg("Officer Review officially signed and recorded in case docket.");
    } catch (err) {
      setReviewStatusMsg(`Error submitting sign-off: ${err.message}`);
    } finally {
      setReviewSubmitting(false);
    }
  };

  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="top-header">
        <div className="brand-section">
          <Shield size={32} color="#1e3a8a" />
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
              <span className="brand-title">DocShield</span>
              <span className="badge-agency">MHA / SSB Border Screening System</span>
            </div>
            <div className="brand-subtitle">
              Smart India Hackathon 2026 (SIH26188) — Multi-Layer Document Forensics & Biometric Verification
            </div>
          </div>
        </div>

        <div className="header-right">
          <div className="health-status">
            <div className={`status-dot ${health?.status === "healthy" ? "online" : "offline"}`} />
            <span>
              {health?.status === "healthy" 
                ? `Border Screening Engine Online (v${health.version})` 
                : "Connecting to Screening Service..."}
            </span>
          </div>
        </div>
      </header>

      {/* Statutory AI Prototype Advisory Banner */}
      <div className="disclaimer-banner">
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <Info size={16} style={{ flexShrink: 0 }} />
          <span>
            <strong>Statutory Protocol Notice:</strong> This is an AI-assisted screening prototype for SIH 2026. 
            Does not claim real government database connectivity. The AI provides forensic evidence and risk assessment; an authorized border officer makes the final clearance decision.
          </span>
        </div>
        <span style={{ fontSize: "0.72rem", opacity: 0.8, textTransform: "uppercase", fontWeight: 700 }}>
          SSB Immigration Station
        </span>
      </div>

      {/* Main Content Area */}
      <main className="main-content">
        <div className="grid-main">
          {/* Left Column: Intake & Controls Station */}
          <div>
            <div className="card">
              <h2 className="card-title">
                <FileText size={18} color="#2563eb" />
                Traveller Intake & Document Upload
              </h2>

              {/* Sample Presets for Easy Evaluation */}
              <div className="presets-container">
                <div className="presets-label">Quick Test Scenarios (1-Click Presets)</div>
                <div className="presets-grid">
                  <button 
                    type="button" 
                    className="btn-preset" 
                    onClick={() => loadPreset("aadhaar_valid")}
                  >
                    1. Valid Aadhaar Card
                  </button>
                  <button 
                    type="button" 
                    className="btn-preset" 
                    onClick={() => loadPreset("aadhaar_invalid")}
                  >
                    2. Tampered Verhoeff Checksum
                  </button>
                  <button 
                    type="button" 
                    className="btn-preset" 
                    onClick={() => loadPreset("passport")}
                  >
                    3. Indian Passport + MRZ
                  </button>
                  <button 
                    type="button" 
                    className="btn-preset" 
                    onClick={handleReset}
                  >
                    <RotateCcw size={12} style={{ display: "inline", marginRight: "4px" }} />
                    Reset Intake Form
                  </button>
                </div>
              </div>

              {/* Document Scan Upload (Stage 1) */}
              <div className="upload-group">
                <label className="upload-label">
                  1. Identity Document Scan / Photo (Aadhaar, Passport, PAN)
                </label>
                <div className="dropzone">
                  <input type="file" accept="image/*" onChange={handleDocChange} />
                  {docPreview ? (
                    <div>
                      <img src={docPreview} alt="Document Preview" className="dropzone-preview" />
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.3rem" }}>
                        {docFile?.name || "Selected Document"}
                      </div>
                    </div>
                  ) : (
                    <div style={{ padding: "1.2rem 0", color: "var(--text-muted)" }}>
                      <Layers size={32} style={{ margin: "0 auto 0.4rem", color: "var(--navy-accent)" }} />
                      <p style={{ fontWeight: 600, fontSize: "0.85rem", color: "var(--text-primary)" }}>
                        Click or Drop Document Image
                      </p>
                      <p style={{ fontSize: "0.75rem", marginTop: "0.2rem" }}>
                        Auto-deskew, OCR, & ELA forensic analysis active
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Document Type Hint */}
              <div className="upload-group">
                <label className="upload-label">Document Classification Hint</label>
                <select 
                  className="select-control"
                  value={docTypeHint} 
                  onChange={(e) => setDocTypeHint(e.target.value)}
                >
                  <option value="auto">Auto-Classify (Heuristic & OCR Layout)</option>
                  <option value="AADHAAR">Aadhaar Card (UIDAI 12-Digit)</option>
                  <option value="PASSPORT">Indian Passport (ICAO Doc 9303)</option>
                  <option value="PAN">Permanent Account Number (PAN)</option>
                  <option value="VOTER_ID">Election Commission Voter ID</option>
                </select>
              </div>

              {/* Live Person Image Upload (Stage 2) */}
              <div className="upload-group">
                <label className="upload-label">
                  2. Traveller Live Camera Photo / Selfie (Biometric Verification)
                </label>
                <div className="dropzone">
                  <input type="file" accept="image/*" onChange={handlePersonChange} />
                  {personPreview ? (
                    <div>
                      <img src={personPreview} alt="Person Preview" className="dropzone-preview" />
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.3rem" }}>
                        {personFile?.name || "Live Traveller Face"}
                      </div>
                    </div>
                  ) : (
                    <div style={{ padding: "1rem 0", color: "var(--text-muted)" }}>
                      <User size={28} style={{ margin: "0 auto 0.4rem", color: "var(--navy-accent)" }} />
                      <p style={{ fontWeight: 600, fontSize: "0.85rem", color: "var(--text-primary)" }}>
                        Click to Upload Traveller Live Face
                      </p>
                      <p style={{ fontSize: "0.75rem" }}>
                        1:1 Biometric matching against ID portrait
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {error && (
                <div style={{ padding: "0.75rem", background: "var(--color-red-bg)", border: "1px solid var(--color-red-border)", borderRadius: "6px", color: "var(--color-red)", fontSize: "0.82rem", marginBottom: "1rem" }}>
                  {error}
                </div>
              )}

              {/* Start Verification Action (Stage 3 & 4) */}
              <button 
                className="btn-primary" 
                onClick={handleAnalyze} 
                disabled={loading || !docFile}
              >
                {loading ? (
                  <>
                    <Activity size={18} />
                    Executing Screening Pipeline...
                  </>
                ) : (
                  <>
                    <Search size={18} />
                    Execute Multi-Layer Verification
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Right Column: Screening Dossier & Officer Review Station */}
          <div>
            {!result ? (
              <div className="card" style={{ textAlign: "center", padding: "5rem 2rem", color: "var(--text-muted)" }}>
                <ShieldCheck size={52} style={{ margin: "0 auto 1.25rem", color: "var(--navy-accent)", opacity: 0.35 }} />
                <h3 style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--navy-primary)" }}>
                  No Active Screening Docket
                </h3>
                <p style={{ fontSize: "0.88rem", marginTop: "0.5rem", maxWidth: "480px", margin: "0.5rem auto 1.5rem" }}>
                  Select or drop a document image on the intake station, or choose one of the quick test scenarios on the left to initiate multi-signal border inspection.
                </p>
                <div style={{ display: "inline-flex", gap: "0.5rem" }}>
                  <button className="btn-preset" onClick={() => loadPreset("aadhaar_valid")}>
                    Test Valid Aadhaar
                  </button>
                  <button className="btn-preset" onClick={() => loadPreset("passport")}>
                    Test Passport with MRZ
                  </button>
                </div>
              </div>
            ) : (
              <div>
                {/* Risk Verdict Banner (Stage 10 Prototype Risk Assessment) */}
                <div className={`verdict-banner ${result.risk_assessment.level}`}>
                  <div>
                    <div style={{ fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-secondary)", fontWeight: 700 }}>
                      AI Risk Assessment Advisory
                    </div>
                    <div className={`verdict-title ${result.risk_assessment.level}`}>
                      {result.risk_assessment.verdict.replace(/_/g, " ")} ({result.risk_assessment.level} RISK)
                    </div>
                    <div style={{ fontSize: "0.85rem", marginTop: "0.25rem", color: "var(--text-secondary)" }}>
                      {result.risk_assessment.recommended_action}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className="score-badge">
                      {result.risk_assessment.score} <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>/100</span>
                    </div>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                      Risk Index
                    </div>
                  </div>
                </div>

                {/* Case Metadata Bar */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "1rem", padding: "0 0.5rem" }}>
                  <span>Docket ID: <strong style={{ color: "var(--navy-primary)", fontFamily: "var(--font-mono)" }}>{result.case_id}</strong></span>
                  <span>Processing Time: <strong style={{ color: "var(--navy-primary)" }}>{result.processing_time_ms} ms</strong></span>
                  <span>
                    Status: {result.officer_review?.reviewed ? (
                      <span className="badge-status pass"><Check size={12} /> Officer Signed</span>
                    ) : (
                      <span className="badge-status warn"><AlertTriangle size={12} /> Pending Officer Adjudication</span>
                    )}
                  </span>
                </div>

                {/* Tabs Navigation */}
                <div className="tabs-nav">
                  <button 
                    className={`tab-btn ${activeTab === "overview" ? "active" : ""}`}
                    onClick={() => setActiveTab("overview")}
                  >
                    1. Overview
                  </button>
                  <button 
                    className={`tab-btn ${activeTab === "ocr" ? "active" : ""}`}
                    onClick={() => setActiveTab("ocr")}
                  >
                    2. OCR & MRZ
                  </button>
                  <button 
                    className={`tab-btn ${activeTab === "validation" ? "active" : ""}`}
                    onClick={() => setActiveTab("validation")}
                  >
                    3. Field Checksums
                  </button>
                  <button 
                    className={`tab-btn ${activeTab === "forensics" ? "active" : ""}`}
                    onClick={() => setActiveTab("forensics")}
                  >
                    4. Image Forensics (ELA)
                  </button>
                  <button 
                    className={`tab-btn ${activeTab === "biometrics" ? "active" : ""}`}
                    onClick={() => setActiveTab("biometrics")}
                  >
                    5. Face Biometrics
                  </button>
                  <button 
                    className={`tab-btn ${activeTab === "fusion" ? "active" : ""}`}
                    onClick={() => setActiveTab("fusion")}
                  >
                    6. Evidence Fusion
                  </button>
                  <button 
                    className={`tab-btn ${activeTab === "officer" ? "active" : ""}`}
                    onClick={() => setActiveTab("officer")}
                    style={{ fontWeight: 800, color: activeTab === "officer" ? "var(--navy-accent)" : "var(--blue-primary)" }}
                  >
                    7. Officer Review (Final)
                  </button>
                </div>

                {/* TAB 1: OVERVIEW */}
                {activeTab === "overview" && (
                  <div className="card">
                    <h3 className="card-title">
                      <ShieldCheck size={18} color="#2563eb" />
                      Screening Summary & Multi-Factor Signals
                    </h3>

                    {/* Quick Metric Grid */}
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.75rem", marginBottom: "1.25rem" }}>
                      <div style={{ background: "var(--bg-subtle)", padding: "0.85rem", borderRadius: "6px", border: "1px solid var(--border-light)" }}>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Document Class</div>
                        <div style={{ fontSize: "1rem", fontWeight: 700, color: "var(--navy-primary)", marginTop: "0.2rem" }}>
                          {result.document_info.document_type}
                        </div>
                      </div>

                      <div style={{ background: "var(--bg-subtle)", padding: "0.85rem", borderRadius: "6px", border: "1px solid var(--border-light)" }}>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Checksum Validation</div>
                        <div style={{ fontSize: "1rem", fontWeight: 700, marginTop: "0.2rem", color: result.validation.overall_valid ? "var(--color-green)" : "var(--color-red)" }}>
                          {result.validation.checks_passed} / {result.validation.checks_total} Checks
                        </div>
                      </div>

                      <div style={{ background: "var(--bg-subtle)", padding: "0.85rem", borderRadius: "6px", border: "1px solid var(--border-light)" }}>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Watchlist Status</div>
                        <div style={{ fontSize: "1rem", fontWeight: 700, marginTop: "0.2rem", color: result.watchlist.is_flagged ? "var(--color-red)" : "var(--color-green)" }}>
                          {result.watchlist.status}
                        </div>
                      </div>

                      <div style={{ background: "var(--bg-subtle)", padding: "0.85rem", borderRadius: "6px", border: "1px solid var(--border-light)" }}>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Biometric Facial Match</div>
                        <div style={{ fontSize: "1rem", fontWeight: 700, marginTop: "0.2rem", color: result.face_verification.match_verdict === "MATCH" ? "var(--color-green)" : "var(--color-red)" }}>
                          {result.face_verification.match_verdict} ({result.face_verification.similarity_score}%)
                        </div>
                      </div>
                    </div>

                    {/* Primary Holder Information */}
                    <div style={{ marginBottom: "1.25rem" }}>
                      <div style={{ fontSize: "0.82rem", fontWeight: 700, marginBottom: "0.4rem", color: "var(--navy-primary)" }}>
                        Recognized Document Attributes
                      </div>
                      <table className="data-table">
                        <tbody>
                          <tr>
                            <td className="data-label">Document Number</td>
                            <td className="data-val mono">{result.document_info.document_number || "Unreadable / Missing"}</td>
                          </tr>
                          <tr>
                            <td className="data-label">Holder Name</td>
                            <td className="data-val">{result.document_info.name || "Unreadable"}</td>
                          </tr>
                          <tr>
                            <td className="data-label">Date of Birth</td>
                            <td className="data-val">{result.document_info.dob || "N/A"}</td>
                          </tr>
                          <tr>
                            <td className="data-label">Gender</td>
                            <td className="data-val">{result.document_info.gender || "N/A"}</td>
                          </tr>
                          {result.document_info.expiry_date && (
                            <tr>
                              <td className="data-label">Expiration Date</td>
                              <td className="data-val">{result.document_info.expiry_date}</td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>

                    {/* Key Findings List */}
                    <div>
                      <div style={{ fontSize: "0.82rem", fontWeight: 700, marginBottom: "0.4rem", color: "var(--navy-primary)" }}>
                        Forensic Explainability Log
                      </div>
                      <ul className="reasons-list">
                        {result.risk_assessment.reasons.map((r, i) => {
                          const isAlert = r.includes("ALERT") || r.includes("Failure") || r.includes("Mismatch") || r.includes("CRITICAL");
                          const isWarn = r.includes("Inconclusive") || r.includes("moderate") || r.includes("non-standard");
                          return (
                            <li key={i} className={`reason-item ${isAlert ? "alert" : isWarn ? "warn" : "pass"}`}>
                              <ChevronRight size={14} style={{ marginTop: "2px", flexShrink: 0 }} />
                              <span>{r}</span>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  </div>
                )}

                {/* TAB 2: OCR & MRZ RESULTS (Stage 5) */}
                {activeTab === "ocr" && (
                  <div className="card">
                    <h3 className="card-title">
                      <FileCheck size={18} color="#2563eb" />
                      Optical Character Recognition & Machine-Readable Zone (MRZ)
                    </h3>

                    {result.document_info.mrz_data ? (
                      <div style={{ marginBottom: "1.5rem" }}>
                        <div style={{ fontSize: "0.82rem", fontWeight: 700, marginBottom: "0.5rem", color: "var(--navy-primary)" }}>
                          Parsed ICAO Doc 9303 Standard Fields
                        </div>
                        <table className="data-table" style={{ marginBottom: "1rem" }}>
                          <tbody>
                            <tr>
                              <td className="data-label">MRZ Format</td>
                              <td className="data-val">{result.document_info.mrz_data.format}</td>
                            </tr>
                            <tr>
                              <td className="data-label">Document Code</td>
                              <td className="data-val mono">{result.document_info.mrz_data.document_code}</td>
                            </tr>
                            <tr>
                              <td className="data-label">Issuing State</td>
                              <td className="data-val mono">{result.document_info.mrz_data.issuing_state}</td>
                            </tr>
                            <tr>
                              <td className="data-label">Passport / ID Number</td>
                              <td className="data-val mono">
                                {result.document_info.mrz_data.document_number} (Check Digit: {result.document_info.mrz_data.document_number_check})
                              </td>
                            </tr>
                            <tr>
                              <td className="data-label">Nationality</td>
                              <td className="data-val mono">{result.document_info.mrz_data.nationality}</td>
                            </tr>
                            <tr>
                              <td className="data-label">Date of Birth</td>
                              <td className="data-val">
                                {result.document_info.mrz_data.dob} (Check Digit: {result.document_info.mrz_data.dob_check})
                              </td>
                            </tr>
                            <tr>
                              <td className="data-label">Date of Expiry</td>
                              <td className="data-val">
                                {result.document_info.mrz_data.expiry_date} (Check Digit: {result.document_info.mrz_data.expiry_check})
                              </td>
                            </tr>
                          </tbody>
                        </table>

                        <div style={{ background: "var(--bg-subtle)", padding: "0.75rem", borderRadius: "6px", border: "1px solid var(--border-light)" }}>
                          <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-muted)", marginBottom: "0.25rem" }}>Raw MRZ Lines</div>
                          <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.82rem", letterSpacing: "0.08em", color: "var(--navy-primary)", wordBreak: "break-all" }}>
                            <div>{result.document_info.mrz_data.line1}</div>
                            <div>{result.document_info.mrz_data.line2}</div>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div style={{ padding: "0.75rem", background: "var(--bg-subtle)", borderRadius: "6px", marginBottom: "1.25rem", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                        No standard ICAO 9303 MRZ zone was detected on this document. Document is processed as a standard National Identity Card.
                      </div>
                    )}

                    <div>
                      <div style={{ fontSize: "0.82rem", fontWeight: 700, marginBottom: "0.4rem", color: "var(--navy-primary)" }}>
                        Extracted Text Tokens
                      </div>
                      <div style={{ background: "var(--bg-subtle)", padding: "0.85rem", borderRadius: "6px", border: "1px solid var(--border-light)", fontSize: "0.82rem", fontFamily: "var(--font-mono)", whiteSpace: "pre-wrap", color: "var(--text-secondary)", maxHeight: "200px", overflowY: "auto" }}>
                        {result.document_info.raw_text_preview || "No raw text available."}
                      </div>
                    </div>
                  </div>
                )}

                {/* TAB 3: FIELD & RULES VALIDATION (Stage 6) */}
                {activeTab === "validation" && (
                  <div className="card">
                    <h3 className="card-title">
                      <CheckCircle size={18} color="#2563eb" />
                      Field Validation & Mathematical Checksums
                    </h3>

                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Check Description</th>
                          <th>Field Target</th>
                          <th>Status</th>
                          <th>Audit Message</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.validation.checks.map((chk, i) => (
                          <tr key={i}>
                            <td style={{ fontWeight: 600 }}>{chk.check_name}</td>
                            <td className="mono" style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{chk.field}</td>
                            <td>
                              {chk.passed ? (
                                <span className="badge-status pass"><Check size={12} /> PASS</span>
                              ) : (
                                <span className={`badge-status ${chk.severity === "critical" ? "fail" : "warn"}`}>
                                  {chk.severity === "critical" ? <XCircle size={12} /> : <AlertTriangle size={12} />}
                                  FAIL
                                </span>
                              )}
                            </td>
                            <td style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>{chk.message}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* TAB 4: FORENSICS & TAMPERING (Stage 7) */}
                {activeTab === "forensics" && (
                  <div className="card">
                    <h3 className="card-title">
                      <AlertOctagon size={18} color="#2563eb" />
                      Image Forensics & Error Level Analysis (ELA)
                    </h3>

                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.25rem" }}>
                      <div style={{ background: "var(--bg-subtle)", padding: "1rem", borderRadius: "6px", border: "1px solid var(--border-light)" }}>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>ELA Discrepancy Score</div>
                        <div style={{ fontSize: "1.5rem", fontWeight: 800, color: result.tampering.has_anomalies ? "var(--color-red)" : "var(--color-green)", marginTop: "0.2rem" }}>
                          {result.tampering.ela_score} <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>/ 100</span>
                        </div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                          {result.tampering.anomaly_regions} localized compression anomaly zone(s) detected.
                        </div>
                      </div>

                      <div style={{ background: "var(--bg-subtle)", padding: "1rem", borderRadius: "6px", border: "1px solid var(--border-light)" }}>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Splicing Verdict</div>
                        <div style={{ fontSize: "1.2rem", fontWeight: 700, color: result.tampering.has_anomalies ? "var(--color-red)" : "var(--color-green)", marginTop: "0.3rem" }}>
                          {result.tampering.has_anomalies ? "SUSPICIOUS COMPRESSION PROFILE" : "AUTHENTIC / UNALTERED"}
                        </div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                          In-memory JPEG recompression difference test
                        </div>
                      </div>
                    </div>

                    {result.tampering.ela_image_base64 && (
                      <div style={{ marginBottom: "1.25rem" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                          <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--navy-primary)" }}>
                            Error Level Analysis Heatmap
                          </span>
                          <button 
                            className="btn-preset"
                            onClick={() => setShowEla(!showEla)}
                            style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem" }}
                          >
                            <Eye size={13} />
                            {showEla ? "Hide Heatmap" : "View ELA Heatmap"}
                          </button>
                        </div>
                        {showEla && (
                          <div style={{ textAlign: "center", padding: "1rem", background: "var(--bg-subtle)", borderRadius: "6px", border: "1px solid var(--border-light)" }}>
                            <img 
                              src={result.tampering.ela_image_base64} 
                              alt="ELA Heatmap" 
                              style={{ maxWidth: "100%", maxHeight: "250px", borderRadius: "4px", border: "1px solid var(--border-medium)" }} 
                            />
                            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.5rem" }}>
                              Bright regions indicate differential JPEG compression levels, which typically indicate digital splicing, copy-paste alterations, or font modifications.
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    <div>
                      <div style={{ fontSize: "0.82rem", fontWeight: 700, marginBottom: "0.4rem", color: "var(--navy-primary)" }}>
                        Forensic Observations
                      </div>
                      <ul className="reasons-list">
                        {result.tampering.forensic_notes.map((note, idx) => (
                          <li key={idx} className="reason-item pass">
                            <ChevronRight size={14} style={{ marginTop: "2px", flexShrink: 0 }} />
                            <span>{note}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}

                {/* TAB 5: BIOMETRIC FACE VERIFICATION (Stage 8) */}
                {activeTab === "biometrics" && (
                  <div className="card">
                    <h3 className="card-title">
                      <User size={18} color="#2563eb" />
                      1:1 Biometric Facial Verification
                    </h3>

                    <div style={{ display: "flex", alignItems: "center", gap: "1.5rem", background: "var(--bg-subtle)", padding: "1.25rem", borderRadius: "8px", border: "1px solid var(--border-light)", marginBottom: "1.5rem" }}>
                      <div style={{ textAlign: "center" }}>
                        {result.face_verification.document_face_crop_base64 ? (
                          <img 
                            src={result.face_verification.document_face_crop_base64} 
                            alt="Document Face" 
                            style={{ width: "90px", height: "90px", objectFit: "cover", borderRadius: "6px", border: "1px solid var(--border-medium)" }} 
                          />
                        ) : (
                          <div style={{ width: "90px", height: "90px", background: "#ffffff", border: "1px dashed var(--border-medium)", borderRadius: "6px", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            No ID Face
                          </div>
                        )}
                        <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", marginTop: "0.3rem" }}>
                          Document Portrait
                        </div>
                      </div>

                      <div style={{ textAlign: "center" }}>
                        {result.face_verification.person_face_crop_base64 ? (
                          <img 
                            src={result.face_verification.person_face_crop_base64} 
                            alt="Live Face" 
                            style={{ width: "90px", height: "90px", objectFit: "cover", borderRadius: "6px", border: "1px solid var(--border-medium)" }} 
                          />
                        ) : (
                          <div style={{ width: "90px", height: "90px", background: "#ffffff", border: "1px dashed var(--border-medium)", borderRadius: "6px", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            No Live Face
                          </div>
                        )}
                        <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", marginTop: "0.3rem" }}>
                          Live Traveller
                        </div>
                      </div>

                      <div style={{ flex: 1, paddingLeft: "0.5rem" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                          <span className={`badge-status ${result.face_verification.match_verdict === "MATCH" ? "pass" : "fail"}`}>
                            {result.face_verification.match_verdict}
                          </span>
                          <strong style={{ fontSize: "1.1rem", color: "var(--navy-primary)" }}>
                            {result.face_verification.similarity_score}% Match
                          </strong>
                        </div>
                        <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginTop: "0.35rem" }}>
                          {result.face_verification.notes || "Biometric comparison complete."}
                        </div>
                        {result.face_verification.face_distance !== null && (
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
                            Embedding Distance: <span className="mono">{result.face_verification.face_distance}</span> (Threshold: 0.60)
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* TAB 6: EVIDENCE FUSION (Stage 9 & 11) */}
                {activeTab === "fusion" && (
                  <div className="card">
                    <h3 className="card-title">
                      <Activity size={18} color="#2563eb" />
                      Multi-Factor Evidence Fusion & Penalties
                    </h3>

                    <div style={{ marginBottom: "1.5rem" }}>
                      <div style={{ fontSize: "0.82rem", fontWeight: 700, marginBottom: "0.5rem", color: "var(--navy-primary)" }}>
                        Risk Signal Penalties Breakdown
                      </div>
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Signal Component</th>
                            <th>Penalty Weight</th>
                            <th>Status Assessment</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td>Watchlist & Stolen Registry</td>
                            <td className="mono" style={{ fontWeight: 700, color: result.watchlist.is_flagged ? "var(--color-red)" : "var(--color-green)" }}>
                              {result.risk_assessment.breakdown?.watchlist_penalty || result.risk_assessment.breakdown?.stolen_id_penalty || "0.0"} pts
                            </td>
                            <td>{result.watchlist.status}</td>
                          </tr>
                          <tr>
                            <td>Document Checksums & Structure</td>
                            <td className="mono" style={{ fontWeight: 700, color: !result.validation.overall_valid ? "var(--color-red)" : "var(--color-green)" }}>
                              {result.risk_assessment.breakdown?.validation_failure_penalty || "0.0"} pts
                            </td>
                            <td>{result.validation.overall_valid ? "Mathematical Checks Passed" : "Format / Checksum Anomaly"}</td>
                          </tr>
                          <tr>
                            <td>Image Forensics (ELA)</td>
                            <td className="mono" style={{ fontWeight: 700, color: result.tampering.has_anomalies ? "var(--color-red)" : "var(--color-green)" }}>
                              {result.risk_assessment.breakdown?.tampering_penalty || "0.0"} pts
                            </td>
                            <td>Score: {result.tampering.ela_score}/100</td>
                          </tr>
                          <tr>
                            <td>Biometric Face Match</td>
                            <td className="mono" style={{ fontWeight: 700, color: result.face_verification.match_verdict === "MISMATCH" ? "var(--color-red)" : "var(--color-green)" }}>
                              {result.risk_assessment.breakdown?.biometric_mismatch_penalty || "0.0"} pts
                            </td>
                            <td>{result.face_verification.match_verdict} ({result.face_verification.similarity_score}%)</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    <div>
                      <div style={{ fontSize: "0.82rem", fontWeight: 700, marginBottom: "0.4rem", color: "var(--navy-primary)" }}>
                        Complete Audit Rationale (Stage 11 Supporting Evidence)
                      </div>
                      <ul className="reasons-list">
                        {result.risk_assessment.reasons.map((r, i) => (
                          <li key={i} className="reason-item pass">
                            <ChevronRight size={14} style={{ marginTop: "2px", flexShrink: 0 }} />
                            <span>{r}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}

                {/* TAB 7: OFFICER REVIEW STATION (Stage 12 - FINAL STAGE) */}
                {activeTab === "officer" && (
                  <div className="card">
                    <h3 className="card-title">
                      <Shield size={18} color="#1e3a8a" />
                      Stage 12: Authorized Border Officer Clearance Console
                    </h3>

                    <div style={{ padding: "0.75rem 1rem", background: "var(--blue-light)", border: "1px solid var(--blue-border)", borderRadius: "6px", marginBottom: "1.25rem", fontSize: "0.82rem", color: "var(--navy-accent)" }}>
                      <strong>Protocol Requirement:</strong> AI verification provides advisory evidence and automated risk classification. An authorized duty immigration or border officer must make the final statutory adjudication and sign off on this docket.
                    </div>

                    {result.officer_review?.reviewed ? (
                      <div style={{ background: "var(--color-green-bg)", border: "1px solid var(--color-green-border)", borderRadius: "8px", padding: "1.25rem", marginBottom: "1.5rem" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--color-green)", fontWeight: 700, fontSize: "1rem" }}>
                          <CheckCircle size={20} />
                          DOCKET OFFICIALLY SIGNED AND ADJUDICATED
                        </div>
                        <table className="data-table" style={{ marginTop: "0.75rem", background: "#ffffff", borderRadius: "6px" }}>
                          <tbody>
                            <tr>
                              <td className="data-label">Adjudicating Officer</td>
                              <td className="data-val">{result.officer_review.officer_name} ({result.officer_review.officer_id})</td>
                            </tr>
                            <tr>
                              <td className="data-label">Final Decision</td>
                              <td className="data-val mono" style={{ color: "var(--navy-accent)" }}>
                                {result.officer_review.decision.replace(/_/g, " ")}
                              </td>
                            </tr>
                            <tr>
                              <td className="data-label">AI Verdict Override</td>
                              <td className="data-val">{result.officer_review.override_ai_verdict ? "YES (Officer Discretion Exercised)" : "NO (Concurs with AI Recommendation)"}</td>
                            </tr>
                            <tr>
                              <td className="data-label">Officer Case Notes</td>
                              <td className="data-val">{result.officer_review.notes}</td>
                            </tr>
                            <tr>
                              <td className="data-label">Timestamp</td>
                              <td className="data-val mono">{result.officer_review.timestamp}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    ) : null}

                    {/* Officer Form */}
                    <form onSubmit={handleOfficerSignoff} className="officer-console">
                      <div className="officer-header">
                        <div className="officer-title">
                          <ShieldCheck size={20} color="#1e3a8a" />
                          Official Border Screening Adjudication Form
                        </div>
                        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                          SSB / MHA Docket Signature
                        </span>
                      </div>

                      <div className="form-row">
                        <div className="form-group">
                          <label>Duty Officer Badge ID</label>
                          <input 
                            type="text" 
                            required 
                            value={officerId} 
                            onChange={(e) => setOfficerId(e.target.value)} 
                            placeholder="e.g. SSB-DEL-409"
                          />
                        </div>
                        <div className="form-group">
                          <label>Officer Full Name & Rank</label>
                          <input 
                            type="text" 
                            required 
                            value={officerName} 
                            onChange={(e) => setOfficerName(e.target.value)} 
                            placeholder="e.g. Insp. Rajesh Sharma"
                          />
                        </div>
                      </div>

                      <div className="form-row">
                        <div className="form-group">
                          <label>Final Adjudication Decision</label>
                          <select 
                            value={officerDecision} 
                            onChange={(e) => setOfficerDecision(e.target.value)}
                          >
                            <option value="CLEARED_FOR_ENTRY">CLEARED FOR ENTRY (Grant Border Passage)</option>
                            <option value="REFERRED_TO_SECONDARY">REFERRED TO SECONDARY INSPECTION (Mandatory Physical Check)</option>
                            <option value="DENIED_ENTRY">DENIED ENTRY (Refusal of Entry / Void Travel Document)</option>
                            <option value="DETAINED">DETAIN / IMMEDIATE SUPERVISOR ALERT (Security Escalation)</option>
                          </select>
                        </div>

                        <div className="form-group" style={{ justifyContent: "center" }}>
                          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", marginTop: "1rem" }}>
                            <input 
                              type="checkbox" 
                              checked={overrideAi} 
                              onChange={(e) => setOverrideAi(e.target.checked)} 
                            />
                            <span>Override Advisory AI Assessment under Officer Discretion</span>
                          </label>
                        </div>
                      </div>

                      <div className="form-group" style={{ marginBottom: "1.25rem" }}>
                        <label>Officer Case Remarks & Audit Justification</label>
                        <textarea 
                          rows={3}
                          value={officerNotes}
                          onChange={(e) => setOfficerNotes(e.target.value)}
                          placeholder="Provide forensic or operational remarks justifying this clearance decision..."
                        />
                      </div>

                      {reviewStatusMsg && (
                        <div style={{ padding: "0.6rem 0.85rem", background: "var(--color-green-bg)", border: "1px solid var(--color-green-border)", borderRadius: "6px", color: "var(--color-green)", fontSize: "0.82rem", marginBottom: "1rem" }}>
                          {reviewStatusMsg}
                        </div>
                      )}

                      <button 
                        type="submit" 
                        className="btn-signoff"
                        disabled={reviewSubmitting}
                      >
                        {reviewSubmitting ? (
                          <>
                            <Activity size={16} />
                            Submitting Official Sign-off...
                          </>
                        ) : (
                          <>
                            <CheckCircle size={16} />
                            Sign & Record Official Officer Decision
                          </>
                        )}
                      </button>
                    </form>
                  </div>
                )}

              </div>
            )}
          </div>
        </div>
      </main>

      {/* Official Footer */}
      <footer className="app-footer">
        <div>
          <strong>DocShield</strong> — Smart India Hackathon 2026 (SIH26188) | Sashastra Seema Bal (SSB) / Ministry of Home Affairs (MHA)
        </div>
        <div style={{ display: "flex", gap: "1rem" }}>
          <span>Verhoeff Checksum Active</span>
          <span>•</span>
          <span>ICAO Doc 9303 MRZ Active</span>
          <span>•</span>
          <span>128-d Biometrics Active</span>
        </div>
      </footer>
    </div>
  );
}

