import React, { useState } from "react";
import { 
  ShieldCheck, 
  FileCheck, 
  CheckCircle, 
  AlertTriangle, 
  XCircle, 
  AlertOctagon, 
  User, 
  Activity, 
  Eye, 
  ChevronRight, 
  Shield, 
  Check, 
  RotateCcw,
  Printer,
  Info,
  Key
} from "lucide-react";
import { getReviewerToken, setReviewerToken } from "../api";

const VERDICT_LABELS = {
  NO_ADVERSE_INDICATORS: "No adverse indicators from automated checks",
  INCOMPLETE_SCREENING: "Screening incomplete: manual review required",
  MANUAL_REVIEW_RECOMMENDED: "Manual review recommended",
  ESCALATE_FOR_EXPERT_REVIEW: "Escalate for expert review",
};

const REVIEW_DECISIONS = [
  ["CONCUR_NO_FURTHER_ACTION", "Concur with screening: no further action"],
  ["REFER_FOR_PHYSICAL_INSPECTION", "Refer for physical document inspection"],
  ["DOCUMENT_UNVERIFIABLE", "Document could not be verified"],
  ["ESCALATE_TO_SUPERVISOR", "Escalate to supervisor"],
];

const STAGE_BADGE = { COMPLETED: "pass", FAILED: "fail", UNAVAILABLE: "fail", NOT_APPLICABLE: "warn", SKIPPED: "warn" };

function describePersistence(persistence) {
  if (persistence.status === "STORED") {
    const until = persistence.expires_at ? new Date(persistence.expires_at).toLocaleString() : "retention expiry";
    return "stored (redacted) until " + until;
  }
  if (persistence.status === "FAILED") return "NOT stored (storage error)";
  return "not stored";
}

export default function ResultsView({ 
  result, 
  onStartNew, 
  onSubmitOfficerReview,
  reviewSubmitting,
  reviewStatusMsg 
}) {
  const [activeTab, setActiveTab] = useState("overview");
  const [showEla, setShowEla] = useState(false);

  // Reviewer form state. Reviewer identity is taken from the bearer token on the server.
  const [officerDecision, setOfficerDecision] = useState("REFER_FOR_PHYSICAL_INSPECTION");
  const [overrideAi, setOverrideAi] = useState(false);
  const [officerNotes, setOfficerNotes] = useState("");
  const [tokenInput, setTokenInput] = useState(getReviewerToken());

  if (!result) {
    return (
      <div className="empty-results-card">
        <ShieldCheck size={56} className="empty-icon" />
        <h2>No Active Screening Docket</h2>
        <p>
          Select a test preset or upload a credential scan in the Screening Console to generate a forensic dossier.
        </p>
        <button type="button" className="btn-primary" onClick={onStartNew}>
          Open Screening Console
        </button>
      </div>
    );
  }

  const handleOfficerSubmit = (e) => {
    e.preventDefault();
    if (tokenInput.trim()) setReviewerToken(tokenInput.trim());
    onSubmitOfficerReview({
      decision: officerDecision,
      override_ai_verdict: overrideAi,
      notes: officerNotes || null,
    });
  };

  const riskLevel = result.risk_assessment?.level || "MEDIUM";
  const verdictText = VERDICT_LABELS[result.risk_assessment?.verdict] || "Result unavailable";
  const unavailable = result.risk_assessment?.unavailable_signals || [];
  const persistence = result.persistence || {};

  return (
    <div className="results-container">
      {/* Top Advisory Banner */}
      <div className={`advisory-verdict-banner ${riskLevel.toLowerCase()}`}>
        <div className="verdict-main-info">
          <div className="advisory-label-row">
            <span className="advisory-pill">PROTOTYPE · ADVISORY ONLY</span>
            <span className="accuracy-disclaimer" role="note">
              {result.advisory_notice ||
                "DocShield is an AI-assisted screening prototype, not a government verification service. Registry checks use simulated demo data. A qualified human reviewer is responsible for every decision."}
            </span>
          </div>

          <h2 className="verdict-title">
            {verdictText} ({riskLevel} indicator level)
          </h2>

          <p className="verdict-action">
            {result.risk_assessment?.recommended_action || "Manual review by a qualified reviewer is required."}
          </p>
          {unavailable.length > 0 && (
            <p className="verdict-action">
              <strong>Not evaluated:</strong> {unavailable.join(", ").replace(/_/g, " ")}
            </p>
          )}
        </div>

        <div className="verdict-score-box">
          <div className="score-value">
            {result.risk_assessment?.score ?? 0}
            <span className="score-max"> / 100</span>
          </div>
          <span className="score-label" title={result.risk_assessment?.score_interpretation}>
            Heuristic score (not a probability)
          </span>
        </div>
      </div>

      {/* Docket Metadata & Actions Bar */}
      <div className="docket-meta-bar">
        <div className="meta-items">
          <span className="meta-item">
            Case ID: <strong className="mono">{result.case_id}</strong>
          </span>
          <span className="meta-separator">•</span>
          <span className="meta-item">
            Latency: <strong>{result.processing_time_ms ? `${result.processing_time_ms} ms` : "N/A"}</strong>
          </span>
          <span className="meta-separator">•</span>
          <span className="meta-item">
            Status:{" "}
            {result.officer_review?.reviewed ? (
              <span className="status-badge pass">
                <Check size={12} /> Reviewed
              </span>
            ) : (
              <span className="status-badge warn">
                <AlertTriangle size={12} /> Awaiting human review
              </span>
            )}
          </span>
          <span className="meta-separator">•</span>
          <span className="meta-item">
            Case record: <strong>{describePersistence(persistence)}</strong>
          </span>
        </div>

        <div className="meta-actions">
          <button 
            type="button" 
            className="btn-action-outline" 
            onClick={() => window.print()}
            title="Print or save screening report"
          >
            <Printer size={14} />
            <span>Print Report</span>
          </button>
          <button 
            type="button" 
            className="btn-action-outline" 
            onClick={onStartNew}
          >
            <RotateCcw size={14} />
            <span>New Screening</span>
          </button>
        </div>
      </div>

      {/* Tabs Navigation */}
      <nav className="results-tabs-nav" aria-label="Screening details tabs">
        <button
          type="button"
          className={`tab-link ${activeTab === "overview" ? "active" : ""}`}
          onClick={() => setActiveTab("overview")}
        >
          1. Overview
        </button>
        <button
          type="button"
          className={`tab-link ${activeTab === "ocr" ? "active" : ""}`}
          onClick={() => setActiveTab("ocr")}
        >
          2. OCR &amp; MRZ
        </button>
        <button
          type="button"
          className={`tab-link ${activeTab === "checksums" ? "active" : ""}`}
          onClick={() => setActiveTab("checksums")}
        >
          3. Field Checksums
        </button>
        <button
          type="button"
          className={`tab-link ${activeTab === "forensics" ? "active" : ""}`}
          onClick={() => setActiveTab("forensics")}
        >
          4. Image Forensics (ELA)
        </button>
        <button
          type="button"
          className={`tab-link ${activeTab === "biometrics" ? "active" : ""}`}
          onClick={() => setActiveTab("biometrics")}
        >
          5. Biometrics
        </button>
        <button
          type="button"
          className={`tab-link ${activeTab === "fusion" ? "active" : ""}`}
          onClick={() => setActiveTab("fusion")}
        >
          6. Evidence Fusion
        </button>
        <button
          type="button"
          className={`tab-link officer-tab ${activeTab === "officer" ? "active" : ""}`}
          onClick={() => setActiveTab("officer")}
        >
          7. Reviewer Console
        </button>
      </nav>

      {Array.isArray(result.pipeline) && result.pipeline.length > 0 && (
        <div className="section-card" aria-label="Pipeline stages executed">
          <h3 className="section-card-title">
            <Activity size={18} />
            <span>Pipeline stages (as reported by the backend)</span>
          </h3>
          <table className="docket-table">
            <tbody>
              {result.pipeline.map((st) => (
                <tr key={st.stage}>
                  <td className="table-label">{st.stage.replace(/_/g, " ")}</td>
                  <td className="table-value">
                    <span className={`status-badge ${STAGE_BADGE[st.status] || "warn"}`}>{st.status}</span>
                    {st.detail ? <span className="mono"> {st.detail}</span> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* TAB 1: OVERVIEW */}
      {activeTab === "overview" && (
        <div className="tab-pane">
          <div className="section-card">
            <h3 className="section-card-title">
              <ShieldCheck size={18} />
              <span>Screening Overview &amp; Key Signals</span>
            </h3>

            {/* Quick Metrics Grid */}
            <div className="metrics-grid">
              <div className="metric-box">
                <span className="metric-label">Document Classification</span>
                <span className="metric-value">
                  {result.document_info?.document_type || "UNKNOWN"}
                </span>
              </div>

              <div className="metric-box">
                <span className="metric-label">Mathematical Checksums</span>
                <span className={`metric-value ${result.validation?.overall_valid ? "text-green" : "text-red"}`}>
                  {result.validation?.checks_passed ?? 0} / {result.validation?.checks_total ?? 0} Checks
                </span>
              </div>

              <div className="metric-box">
                <span className="metric-label">Watchlist Registry (Demo)</span>
                <span className={`metric-value ${result.watchlist?.is_flagged ? "text-red" : "text-green"}`}>
                  {result.watchlist?.status || "CLEARED"}
                </span>
              </div>

              <div className="metric-box">
                <span className="metric-label">1:1 Biometric Facial Match</span>
                <span className={`metric-value ${result.face_verification?.match_verdict === "MATCH" ? "text-green" : (result.face_verification?.match_verdict === "INDETERMINATE" ? "text-amber" : "text-red")}`}>
                  {result.face_verification?.match_verdict || "NOT_APPLICABLE"} ({result.face_verification?.similarity_score ?? 0}%)
                </span>
              </div>
            </div>

            {/* Extracted Document Attributes */}
            <div className="sub-section">
              <h4 className="sub-section-title">Extracted Identity Attributes</h4>
              <table className="docket-table">
                <tbody>
                  <tr>
                    <td className="table-label">Document Number</td>
                    <td className="table-value mono">
                      {result.document_info?.document_number || "Unreadable / Missing"}
                    </td>
                  </tr>
                  <tr>
                    <td className="table-label">Holder Name</td>
                    <td className="table-value">
                      {result.document_info?.name || "Unreadable / Not Identified"}
                    </td>
                  </tr>
                  <tr>
                    <td className="table-label">Date of Birth</td>
                    <td className="table-value mono">
                      {result.document_info?.dob || "N/A"}
                    </td>
                  </tr>
                  <tr>
                    <td className="table-label">Gender</td>
                    <td className="table-value">
                      {result.document_info?.gender || "N/A"}
                    </td>
                  </tr>
                  {result.document_info?.expiry_date && (
                    <tr>
                      <td className="table-label">Expiration Date</td>
                      <td className="table-value mono">
                        {result.document_info?.expiry_date}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Explainability Log */}
            <div className="sub-section">
              <h4 className="sub-section-title">Forensic Explainability Log</h4>
              <ul className="explainability-list">
                {result.risk_assessment?.reasons?.map((reason, idx) => {
                  const isAlert = reason.includes("ALERT") || reason.includes("Failure") || reason.includes("Mismatch") || reason.includes("CRITICAL");
                  const isWarn = reason.includes("Inconclusive") || reason.includes("moderate") || reason.includes("non-standard") || reason.includes("DEMO");
                  return (
                    <li key={idx} className={`reason-item ${isAlert ? "alert" : isWarn ? "warn" : "pass"}`}>
                      <ChevronRight size={14} className="reason-chevron" />
                      <span>{reason}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: OCR & MRZ */}
      {activeTab === "ocr" && (
        <div className="tab-pane">
          <div className="section-card">
            <h3 className="section-card-title">
              <FileCheck size={18} />
              <span>Optical Character Recognition &amp; ICAO MRZ</span>
            </h3>

            {/* Token Confidence Summary */}
            <div className="metrics-grid">
              <div className="metric-box">
                <span className="metric-label">Mean OCR Token Confidence</span>
                <span className="metric-value">
                  {result.document_info?.ocr_confidence ? `${(result.document_info.ocr_confidence * 100).toFixed(1)}%` : "N/A"}
                </span>
              </div>
              <div className="metric-box">
                <span className="metric-label">Classification Anchor Integrity</span>
                <span className={`metric-value ${result.document_info?.document_type === "UNKNOWN" ? "text-amber" : "text-green"}`}>
                  {result.document_info?.document_type === "UNKNOWN" ? "UNKNOWN (No layout anchors)" : result.document_info?.document_type}
                </span>
              </div>
            </div>

            {/* MRZ Fields if present */}
            {result.document_info?.mrz_data ? (
              <div className="sub-section">
                <h4 className="sub-section-title">Parsed ICAO Doc 9303 Part 4 TD3 Fields</h4>
                <table className="docket-table">
                  <tbody>
                    <tr>
                      <td className="table-label">MRZ Format</td>
                      <td className="table-value">{result.document_info.mrz_data.format}</td>
                    </tr>
                    <tr>
                      <td className="table-label">Document Code</td>
                      <td className="table-value mono">{result.document_info.mrz_data.document_code}</td>
                    </tr>
                    <tr>
                      <td className="table-label">Issuing State</td>
                      <td className="table-value mono">{result.document_info.mrz_data.issuing_state}</td>
                    </tr>
                    <tr>
                      <td className="table-label">Document Number</td>
                      <td className="table-value mono">
                        {result.document_info.mrz_data.document_number} (Check Digit: {result.document_info.mrz_data.document_number_check})
                      </td>
                    </tr>
                    <tr>
                      <td className="table-label">Date of Birth</td>
                      <td className="table-value mono">
                        {result.document_info.mrz_data.dob} (Check Digit: {result.document_info.mrz_data.dob_check})
                      </td>
                    </tr>
                    <tr>
                      <td className="table-label">Expiration Date</td>
                      <td className="table-value mono">
                        {result.document_info.mrz_data.expiry_date} (Check Digit: {result.document_info.mrz_data.expiry_check})
                      </td>
                    </tr>
                  </tbody>
                </table>

                <div className="raw-mrz-box">
                  <div className="raw-mrz-label">Raw MRZ Lines:</div>
                  <div className="raw-mrz-lines">
                    <div>{result.document_info.mrz_data.line1}</div>
                    <div>{result.document_info.mrz_data.line2}</div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="info-box">
                <Info size={16} />
                <span>No ICAO Doc 9303 MRZ zone detected. Document was processed as a standard National ID card.</span>
              </div>
            )}

            {/* Extracted Tokens Box */}
            <div className="sub-section">
              <h4 className="sub-section-title">Raw Extracted Text Tokens</h4>
              <pre className="raw-tokens-pre">
                {result.document_info?.raw_text_preview || "No raw text available."}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: FIELD CHECKSUMS */}
      {activeTab === "checksums" && (
        <div className="tab-pane">
          <div className="section-card">
            <h3 className="section-card-title">
              <CheckCircle size={18} />
              <span>Field Validation &amp; Mathematical Checksums</span>
            </h3>

            <table className="docket-table full-table">
              <thead>
                <tr>
                  <th>Check Description</th>
                  <th>Field Target</th>
                  <th>Status</th>
                  <th>Audit Message</th>
                </tr>
              </thead>
              <tbody>
                {result.validation?.checks?.map((chk, idx) => (
                  <tr key={idx}>
                    <td className="bold">{chk.check_name}</td>
                    <td className="mono muted">{chk.field}</td>
                    <td>
                      {chk.passed ? (
                        <span className="status-badge pass">
                          <Check size={12} /> PASS
                        </span>
                      ) : (
                        <span className={`status-badge ${chk.severity === "critical" ? "fail" : "warn"}`}>
                          {chk.severity === "critical" ? <XCircle size={12} /> : <AlertTriangle size={12} />}
                          FAIL
                        </span>
                      )}
                    </td>
                    <td className="audit-msg">{chk.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 4: FORENSICS (ELA) */}
      {activeTab === "forensics" && (
        <div className="tab-pane">
          <div className="section-card">
            <h3 className="section-card-title">
              <AlertOctagon size={18} />
              <span>Image Forensics &amp; Error Level Analysis (ELA)</span>
            </h3>

            <div className="metrics-grid">
              <div className="metric-box">
                <span className="metric-label">Compression Discrepancy Index</span>
                <span className={`metric-value ${result.tampering?.has_anomalies ? "text-red" : "text-green"}`}>
                  {result.tampering?.ela_score ?? 0} <span className="score-max">/ 100</span>
                </span>
                <span className="metric-subtext">
                  {result.tampering?.anomaly_regions ?? 0} localized anomaly region(s)
                </span>
              </div>

              <div className="metric-box">
                <span className="metric-label">Compression Signal (Advisory Only)</span>
                <span className={`metric-value ${result.tampering?.has_anomalies ? "text-red" : "text-green"}`}>
                  {result.tampering?.has_anomalies ? "COMPRESSION ANOMALY DETECTED" : "COMPRESSION CONTINUOUS"}
                </span>
                <span className="metric-subtext">
                  Confidence: {((result.tampering?.analysis_confidence ?? 0.6) * 100).toFixed(0)}% (resolution dependent)
                </span>
              </div>
            </div>

            {/* ELA Heatmap Viewer Toggle */}
            {result.tampering?.ela_image_base64 && (
              <div className="sub-section">
                <div className="heatmap-header">
                  <h4 className="sub-section-title">Error Level Analysis Heatmap</h4>
                  <button
                    type="button"
                    className="btn-action-outline"
                    onClick={() => setShowEla(!showEla)}
                  >
                    <Eye size={14} />
                    <span>{showEla ? "Hide Heatmap" : "View ELA Heatmap"}</span>
                  </button>
                </div>

                {showEla && (
                  <div className="heatmap-container">
                    <img
                      src={result.tampering.ela_image_base64}
                      alt="ELA Discrepancy Heatmap"
                      className="heatmap-img"
                    />
                    <p className="heatmap-caption">
                      Bright regions indicate differential JPEG compression levels, which typically indicate digital re-saving or compression discontinuities.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Forensic Limitations Box */}
            {result.tampering?.forensic_limitations && result.tampering.forensic_limitations.length > 0 && (
              <div className="forensic-limitations-box">
                <div className="limitations-header">
                  <AlertTriangle size={16} />
                  <span>Forensic Signal Limitations &amp; Technical Disclosures</span>
                </div>
                <ul className="limitations-list">
                  {result.tampering.forensic_limitations.map((lim, idx) => (
                    <li key={idx}>{lim}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Forensic Notes */}
            <div className="sub-section">
              <h4 className="sub-section-title">Forensic Observations</h4>
              <ul className="explainability-list">
                {result.tampering?.forensic_notes?.map((note, idx) => (
                  <li key={idx} className="reason-item pass">
                    <ChevronRight size={14} className="reason-chevron" />
                    <span>{note}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: BIOMETRIC FACE VERIFICATION */}
      {activeTab === "biometrics" && (
        <div className="tab-pane">
          <div className="section-card">
            <h3 className="section-card-title">
              <User size={18} />
              <span>1:1 Biometric Facial Verification</span>
            </h3>

            {/* Face Comparison Card */}
            <div className="biometric-comparison-card">
              <div className="face-crop-box">
                {result.face_verification?.document_face_crop_base64 ? (
                  <img
                    src={result.face_verification.document_face_crop_base64}
                    alt="Document Portrait"
                    className="face-crop-img"
                  />
                ) : (
                  <div className="face-placeholder">No ID Face</div>
                )}
                <span className="face-label">Document Portrait</span>
              </div>

              <div className="face-crop-box">
                {result.face_verification?.person_face_crop_base64 ? (
                  <img
                    src={result.face_verification.person_face_crop_base64}
                    alt="Live Traveller Face"
                    className="face-crop-img"
                  />
                ) : (
                  <div className="face-placeholder">No Live Face</div>
                )}
                <span className="face-label">Live Traveller Selfie</span>
              </div>

              <div className="biometric-details">
                <div className="verdict-row">
                  <span className={`status-badge ${result.face_verification?.match_verdict === "MATCH" ? "pass" : (result.face_verification?.match_verdict === "INDETERMINATE" || result.face_verification?.match_verdict === "NOT_APPLICABLE") ? "warn" : "fail"}`}>
                    {result.face_verification?.match_verdict || "NOT_APPLICABLE"}
                  </span>
                  <strong className="similarity-text">
                    {result.face_verification?.similarity_score ?? 0}% Similarity
                  </strong>
                </div>

                <p className="biometric-notes">
                  {result.face_verification?.notes || "Biometric comparison complete."}
                </p>

                <div className="biometric-meta">
                  <span>Model: <strong className="mono">{result.face_verification?.biometric_model || "dlib 128-d ResNet"}</strong></span>
                  {result.face_verification?.face_distance !== null && result.face_verification?.face_distance !== undefined && (
                    <span> | Embedding Distance: <strong className="mono">{result.face_verification.face_distance}</strong> (Threshold: 0.60)</span>
                  )}
                </div>

                {result.face_verification?.quality_flags && result.face_verification.quality_flags.length > 0 && (
                  <div className="quality-flags-row">
                    {result.face_verification.quality_flags.map((flag, idx) => (
                      <span key={idx} className="quality-flag-tag">
                        {flag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 6: EVIDENCE FUSION */}
      {activeTab === "fusion" && (
        <div className="tab-pane">
          <div className="section-card">
            <h3 className="section-card-title">
              <Activity size={18} />
              <span>Multi-Factor Evidence Fusion &amp; Penalties</span>
            </h3>

            <div className="sub-section">
              <h4 className="sub-section-title">Signal Components &amp; Evidence States</h4>
              <table className="docket-table full-table">
                <thead>
                  <tr>
                    <th>Signal Component</th>
                    <th>Evidence State</th>
                    <th>Penalty Weight</th>
                    <th>Status Assessment</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Watchlist &amp; Stolen Registry</td>
                    <td>
                      <span className="status-badge warn">
                        {result.risk_assessment?.evidence_states?.watchlist_evidence || result.watchlist?.evidence_state || "DEMO"}
                      </span>
                    </td>
                    <td className="mono bold">
                      {result.risk_assessment?.breakdown?.watchlist_penalty || result.risk_assessment?.breakdown?.stolen_id_penalty || "0.0"} pts
                    </td>
                    <td>{result.watchlist?.status || "CLEARED"}</td>
                  </tr>
                  <tr>
                    <td>Document Checksums &amp; Structure</td>
                    <td>
                      <span className={`status-badge ${result.validation?.overall_valid ? "pass" : "fail"}`}>
                        {result.risk_assessment?.evidence_states?.checksum_evidence || (result.validation?.overall_valid ? "PASS" : "FAIL")}
                      </span>
                    </td>
                    <td className="mono bold">
                      {result.risk_assessment?.breakdown?.validation_failure_penalty || "0.0"} pts
                    </td>
                    <td>{result.validation?.overall_valid ? "Mathematical Checks Passed" : "Format / Checksum Anomaly"}</td>
                  </tr>
                  <tr>
                    <td>Image Forensics (ELA)</td>
                    <td>
                      <span className={`status-badge ${result.tampering?.evidence_state === "INDETERMINATE" ? "warn" : result.tampering?.has_anomalies ? "fail" : "pass"}`}>
                        {result.risk_assessment?.evidence_states?.tampering_evidence || result.tampering?.evidence_state || "INDETERMINATE"}
                      </span>
                    </td>
                    <td className="mono bold">
                      {result.risk_assessment?.breakdown?.tampering_penalty || "0.0"} pts
                    </td>
                    <td>Score: {result.tampering?.ela_score ?? 0}/100</td>
                  </tr>
                  <tr>
                    <td>Biometric Face Match</td>
                    <td>
                      <span className={`status-badge ${result.face_verification?.match_verdict === "MATCH" ? "pass" : (result.face_verification?.match_verdict === "INDETERMINATE" || result.face_verification?.match_verdict === "NOT_APPLICABLE") ? "warn" : "fail"}`}>
                        {result.risk_assessment?.evidence_states?.biometric_evidence || (result.face_verification?.match_verdict === "MATCH" ? "PASS" : (result.face_verification?.match_verdict === "INDETERMINATE" ? "INDETERMINATE" : "FAIL"))}
                      </span>
                    </td>
                    <td className="mono bold">
                      {result.risk_assessment?.breakdown?.biometric_mismatch_penalty || "0.0"} pts
                    </td>
                    <td>{result.face_verification?.match_verdict || "NOT_APPLICABLE"} ({result.face_verification?.similarity_score ?? 0}%)</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="sub-section">
              <h4 className="sub-section-title">Complete Audit Rationale</h4>
              <ul className="explainability-list">
                {result.risk_assessment?.reasons?.map((reason, idx) => (
                  <li key={idx} className="reason-item pass">
                    <ChevronRight size={14} className="reason-chevron" />
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* TAB 7: REVIEWER CONSOLE */}
      {activeTab === "officer" && (
        <div className="tab-pane">
          <div className="section-card">
            <h3 className="section-card-title">
              <Shield size={18} />
              <span>Human Reviewer Console</span>
            </h3>

            <div className="info-box">
              <Info size={16} />
              <span>
                Automated screening provides advisory signals only. A qualified reviewer must examine the
                document and record their own assessment. Recording a review does not grant or deny anything
                to anyone; it is an entry in the case audit log.
              </span>
            </div>

            {result.officer_review?.reviewed && (
              <div className="signed-docket-banner">
                <div className="signed-title">
                  <CheckCircle size={20} />
                  <span>Reviewer assessment recorded</span>
                </div>
                <table className="docket-table">
                  <tbody>
                    <tr>
                      <td className="table-label">Reviewer</td>
                      <td className="table-value">
                        {result.officer_review.officer_name} ({result.officer_review.officer_id})
                      </td>
                    </tr>
                    <tr>
                      <td className="table-label">Assessment</td>
                      <td className="table-value bold mono">
                        {result.officer_review.decision?.replace(/_/g, " ")}
                      </td>
                    </tr>
                    <tr>
                      <td className="table-label">Differs from automated result</td>
                      <td className="table-value">{result.officer_review.override_ai_verdict ? "Yes" : "No"}</td>
                    </tr>
                    <tr>
                      <td className="table-label">Notes</td>
                      <td className="table-value">{result.officer_review.notes || "None"}</td>
                    </tr>
                    <tr>
                      <td className="table-label">Timestamp</td>
                      <td className="table-value mono">{result.officer_review.timestamp}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}

            {persistence.status !== "STORED" ? (
              <div className="form-status-alert">
                This result was not stored, so a review cannot be recorded against it.
              </div>
            ) : (
            <form onSubmit={handleOfficerSubmit} className="officer-form">
              <div className="form-grid-2">
                <div className="form-field-group">
                  <label className="form-label" htmlFor="officerDecision">Reviewer assessment</label>
                  <select
                    id="officerDecision"
                    className="form-select"
                    value={officerDecision}
                    onChange={(e) => setOfficerDecision(e.target.value)}
                  >
                    {REVIEW_DECISIONS.map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </div>

                <div className="form-field-group checkbox-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={overrideAi}
                      onChange={(e) => setOverrideAi(e.target.checked)}
                    />
                    <span>My assessment differs from the automated result</span>
                  </label>
                </div>
              </div>

              <div className="form-field-group">
                <label className="form-label" htmlFor="reviewerToken">
                  <span>Reviewer access token</span>
                </label>
                <input
                  id="reviewerToken"
                  type="password"
                  autoComplete="off"
                  className="form-input"
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  placeholder="Personal reviewer token issued by your administrator"
                />
              </div>

              <div className="form-field-group">
                <label className="form-label" htmlFor="officerNotes">Case Remarks &amp; Audit Justification</label>
                <textarea
                  id="officerNotes"
                  rows={3}
                  className="form-textarea"
                  value={officerNotes}
                  onChange={(e) => setOfficerNotes(e.target.value)}
                  maxLength={2000}
                  placeholder="Record what you examined and why you reached this assessment"
                />
              </div>

              {reviewStatusMsg && (
                <div className="form-status-alert">
                  {reviewStatusMsg}
                </div>
              )}

              <button
                type="submit"
                className="btn-submit-officer"
                disabled={reviewSubmitting}
              >
                <CheckCircle size={18} />
                <span>{reviewSubmitting ? "Recording…" : "Record reviewer assessment"}</span>
              </button>
            </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
