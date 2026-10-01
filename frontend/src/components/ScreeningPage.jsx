import React, { useState, useRef } from "react";
import { 
  UploadCloud, 
  User, 
  Search, 
  RotateCcw, 
  AlertCircle, 
  CheckCircle2, 
  Clock, 
  X, 
  ShieldAlert, 
  HelpCircle, 
  Sparkles 
} from "lucide-react";

export default function ScreeningPage({
  docFile,
  setDocFile,
  docPreview,
  setDocPreview,
  personFile,
  setPersonFile,
  personPreview,
  setPersonPreview,
  docTypeHint,
  setDocTypeHint,
  loading,
  error,
  onAnalyze,
  onReset,
  onLoadPreset
}) {
  const [docDragging, setDocDragging] = useState(false);
  const [personDragging, setPersonDragging] = useState(false);
  const [processingStage, setProcessingStage] = useState(0);

  const docInputRef = useRef(null);
  const [clientError, setClientError] = useState(null);

  const validateAndSetDoc = (file) => {
    setClientError(null);
    if (!file) return;
    if (file.size === 0) {
      setClientError("Selected document file is empty (0 bytes).");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setClientError(`Document exceeds 10MB limit (${(file.size / (1024 * 1024)).toFixed(1)}MB). Please upload a smaller scan.`);
      return;
    }
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) && !file.name.match(/\.(jpe?g|png|webp)$/i)) {
      setClientError("Unsupported format. Please select an authentic JPEG, PNG, or WebP image.");
      return;
    }
    setDocFile(file);
    setDocPreview(URL.createObjectURL(file));
  };

  const validateAndSetPerson = (file) => {
    setClientError(null);
    if (!file) return;
    if (file.size === 0) {
      setClientError("Selected selfie file is empty (0 bytes).");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setClientError(`Traveller photo exceeds 10MB limit (${(file.size / (1024 * 1024)).toFixed(1)}MB).`);
      return;
    }
    setPersonFile(file);
    setPersonPreview(URL.createObjectURL(file));
  };

  // Drag and drop handlers for document
  const handleDocDragOver = (e) => {
    e.preventDefault();
    setDocDragging(true);
  };
  const handleDocDragLeave = () => setDocDragging(false);
  const handleDocDrop = (e) => {
    e.preventDefault();
    setDocDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetDoc(e.dataTransfer.files[0]);
    }
  };

  // Drag and drop handlers for person
  const handlePersonDragOver = (e) => {
    e.preventDefault();
    setPersonDragging(true);
  };
  const handlePersonDragLeave = () => setPersonDragging(false);
  const handlePersonDrop = (e) => {
    e.preventDefault();
    setPersonDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetPerson(e.dataTransfer.files[0]);
    }
  };

  const handleDocFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetDoc(e.target.files[0]);
    }
  };

  const handlePersonFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetPerson(e.target.files[0]);
    }
  };

  const stages = [
    { title: "MIME & Integrity Check", desc: "Validating file signature, stripping metadata" },
    { title: "OCR & Token Extraction", desc: "Dual-engine OCR parsing & token confidence scoring" },
    { title: "Mathematical Checksum Validation", desc: "Computing Verhoeff and ICAO 7-3-1 check digits" },
    { title: "Compression Discrepancy Signal", desc: "Differential JPEG Error Level Analysis (ELA)" },
    { title: "1:1 Facial Biometrics", desc: "128-d metric learning embedding distance" },
    { title: "Evidence Fusion & Risk Assessment", desc: "Multimodal signal integration & penalty scoring" },
  ];

  return (
    <div className="screening-layout">
      {/* Header bar */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Identity Document Screening Console</h1>
          <p className="page-subtitle">
            Upload document credentials and optional traveller photos to execute multi-layer verification.
          </p>
        </div>

        {/* Prototype notice banner */}
        <div className="prototype-advisory-box">
          <ShieldAlert size={16} />
          <span>
            <strong>Synthetic Data Mode:</strong> For testing, click a preset below. Do not upload live government credentials.
          </span>
        </div>
      </div>

      {/* 1-Click Test Scenarios Bar */}
      <div className="presets-card">
        <div className="presets-card-header">
          <div className="presets-card-title">
            <Sparkles size={16} className="sparkle-icon" />
            <span>Quick Test Scenarios (1-Click Presets)</span>
          </div>
          <span className="presets-hint">Preloaded test fixtures from sample_data/</span>
        </div>

        <div className="presets-button-group">
          <button
            type="button"
            className="preset-btn"
            onClick={() => onLoadPreset("aadhaar_valid")}
            disabled={loading}
          >
            <span className="preset-number">1</span>
            <span className="preset-name">Valid Aadhaar Card</span>
          </button>

          <button
            type="button"
            className="preset-btn"
            onClick={() => onLoadPreset("aadhaar_invalid")}
            disabled={loading}
          >
            <span className="preset-number">2</span>
            <span className="preset-name">Tampered Checksum (Aadhaar)</span>
          </button>

          <button
            type="button"
            className="preset-btn"
            onClick={() => onLoadPreset("passport")}
            disabled={loading}
          >
            <span className="preset-number">3</span>
            <span className="preset-name">Indian Passport + MRZ</span>
          </button>

          <button
            type="button"
            className="preset-btn reset-btn"
            onClick={onReset}
            disabled={loading || (!docFile && !personFile)}
          >
            <RotateCcw size={14} />
            <span>Reset Intake</span>
          </button>
        </div>
      </div>

      {/* Main Screening Form Grid */}
      <div className="intake-grid">
        {/* Left Column: Document Upload */}
        <div className="intake-card">
          <div className="intake-card-header">
            <div className="step-badge">1</div>
            <div>
              <h2 className="intake-title">Identity Document Scan / Photo</h2>
              <p className="intake-subtitle">Required: Aadhaar, Passport, PAN, or Voter ID (JPG, PNG)</p>
            </div>
          </div>

          <div
            className={`dropzone-box ${docDragging ? "dragging" : ""} ${docPreview ? "has-file" : ""}`}
            onDragOver={handleDocDragOver}
            onDragLeave={handleDocDragLeave}
            onDrop={handleDocDrop}
            onClick={() => docInputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") docInputRef.current?.click(); }}
            aria-label="Upload identity document scan"
          >
            <input
              ref={docInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={handleDocFileChange}
              style={{ display: "none" }}
            />

            {docPreview ? (
              <div className="preview-container">
                <img src={docPreview} alt="Document Scan Preview" className="preview-image" />
                <div className="preview-meta">
                  <span className="file-name">{docFile?.name || "Selected Document"}</span>
                  <button
                    type="button"
                    className="btn-remove-file"
                    onClick={(e) => {
                      e.stopPropagation();
                      setDocFile(null);
                      setDocPreview(null);
                    }}
                    title="Remove document"
                    aria-label="Remove document"
                  >
                    <X size={14} />
                  </button>
                </div>
              </div>
            ) : (
              <div className="dropzone-empty">
                <UploadCloud size={36} className="upload-icon" />
                <p className="upload-prompt">
                  <strong>Click to browse</strong> or drag &amp; drop document image
                </p>
                <p className="upload-specs">PNG, JPEG, WebP up to 10MB</p>
              </div>
            )}
          </div>

          {/* Document Classification Selector */}
          <div className="form-field-group">
            <label htmlFor="docTypeHint" className="form-label">
              <span>Document Classification Mode</span>
              <span className="label-tag">Hint</span>
            </label>
            <select
              id="docTypeHint"
              className="form-select"
              value={docTypeHint}
              onChange={(e) => setDocTypeHint(e.target.value)}
              disabled={loading}
            >
              <option value="auto">Auto-Classify (Heuristics &amp; OCR Anchors)</option>
              <option value="AADHAAR">Aadhaar Card (UIDAI 12-Digit)</option>
              <option value="PASSPORT">Indian Passport (ICAO Doc 9303)</option>
              <option value="PAN">Permanent Account Number (PAN)</option>
              <option value="VOTER_ID">Election Commission Voter ID</option>
            </select>
            <p className="field-hint">
              Auto-classify strictly preserves UNKNOWN if no official layout anchors are identified.
            </p>
          </div>
        </div>

        {/* Right Column: Person/Traveller Photo */}
        <div className="intake-card">
          <div className="intake-card-header">
            <div className="step-badge secondary">2</div>
            <div>
              <h2 className="intake-title">Traveller Live Photo / Selfie</h2>
              <p className="intake-subtitle">Optional: Required for 1:1 facial biometric matching</p>
            </div>
          </div>

          <div
            className={`dropzone-box ${personDragging ? "dragging" : ""} ${personPreview ? "has-file" : ""}`}
            onDragOver={handlePersonDragOver}
            onDragLeave={handlePersonDragLeave}
            onDrop={handlePersonDrop}
            onClick={() => personInputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") personInputRef.current?.click(); }}
            aria-label="Upload traveller live photo"
          >
            <input
              ref={personInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={handlePersonFileChange}
              style={{ display: "none" }}
            />

            {personPreview ? (
              <div className="preview-container">
                <img src={personPreview} alt="Traveller Selfie Preview" className="preview-image" />
                <div className="preview-meta">
                  <span className="file-name">{personFile?.name || "Traveller Photo"}</span>
                  <button
                    type="button"
                    className="btn-remove-file"
                    onClick={(e) => {
                      e.stopPropagation();
                      setPersonFile(null);
                      setPersonPreview(null);
                    }}
                    title="Remove traveller photo"
                    aria-label="Remove traveller photo"
                  >
                    <X size={14} />
                  </button>
                </div>
              </div>
            ) : (
              <div className="dropzone-empty">
                <User size={36} className="upload-icon" />
                <p className="upload-prompt">
                  <strong>Click to browse</strong> or drag &amp; drop traveller selfie
                </p>
                <p className="upload-specs">Single frontal face recommended for 128-d matching</p>
              </div>
            )}
          </div>

          {/* Biometrics Info */}
          <div className="biometrics-info-box">
            <HelpCircle size={16} className="info-icon" />
            <div className="info-content">
              <strong>Quality Threshold:</strong> The engine automatically rejects multi-face photos or low-resolution crops ($&lt; 45\text{px}$) as <code>INDETERMINATE</code>.
            </div>
          </div>
        </div>
      </div>

      {/* Client-side File Validation Alert */}
      {clientError && (
        <div className="error-alert" role="alert">
          <AlertCircle size={20} className="error-icon" />
          <div className="error-body">
            <strong>Input Validation Error:</strong>
            <p>{clientError}</p>
          </div>
          <button
            type="button"
            className="btn-retry"
            onClick={() => setClientError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Error Banner with Retry */}
      {error && (
        <div className="error-alert" role="alert">
          <AlertCircle size={20} className="error-icon" />
          <div className="error-body">
            <strong>Screening Pipeline Error:</strong>
            <p>{error}</p>
          </div>
          <button
            type="button"
            className="btn-retry"
            onClick={onAnalyze}
            disabled={loading || !docFile}
          >
            Retry Verification
          </button>
        </div>
      )}

      {/* Multi-Stage Loading Progress Bar */}
      {loading ? (
        <div className="processing-card" aria-live="polite">
          <div className="processing-header">
            <Clock size={20} className="spinner-icon" />
            <div>
              <h3 className="processing-title">Executing Multi-Layer Verification Pipeline...</h3>
              <p className="processing-subtitle">Analyzing document structure, checksums, ELA discrepancies, and face biometrics</p>
            </div>
          </div>

          <div className="stages-progress-list">
            {stages.map((stage, idx) => (
              <div key={idx} className="stage-progress-item">
                <div className="stage-status-icon active">
                  <CheckCircle2 size={16} />
                </div>
                <div className="stage-content">
                  <span className="stage-title">{stage.title}</span>
                  <span className="stage-desc">{stage.desc}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        /* Action Execution Button */
        <div className="intake-actions">
          <button
            type="button"
            className="btn-execute-verification"
            onClick={onAnalyze}
            disabled={!docFile || loading}
          >
            <Search size={20} />
            <span>Execute Multi-Layer Verification</span>
          </button>
        </div>
      )}
    </div>
  );
}
