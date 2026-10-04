import React from "react";
import { 
  ShieldCheck, 
  Search, 
  FileCheck2, 
  Cpu, 
  UserCheck, 
  AlertTriangle, 
  CheckCircle2, 
  XCircle, 
  ArrowRight, 
  Lock,
  Layers
} from "lucide-react";

export default function HomePage({ onStartScreening, onExploreMethodology }) {
  return (
    <div className="home-container">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-badge">
          <ShieldCheck size={16} />
          <span>Multi-Layer Identity Screening Prototype (SIH 2026)</span>
        </div>

        <h1 className="hero-title">
          Automated Identity Document Screening &amp; Multimodal Forensics
        </h1>

        <p className="hero-description">
          DocShield analyzes identity credentials through multi-signal optical extraction, 
          mathematical checksums, compression discrepancy heuristics, and 1:1 facial biometric embeddings.
          Designed to provide explainable risk indicators for authorized border clearance officers.
        </p>

        <div className="hero-actions">
          <button 
            type="button" 
            className="btn-primary-large"
            onClick={onStartScreening}
          >
            <Search size={18} />
            <span>Launch Screening Console</span>
            <ArrowRight size={16} />
          </button>

          <button 
            type="button" 
            className="btn-secondary-large"
            onClick={onExploreMethodology}
          >
            <span>Read Technical Methodology</span>
          </button>
        </div>

        {/* Prototype Warning Pill */}
        <div className="hero-prototype-notice">
          <AlertTriangle size={16} className="notice-icon" />
          <span>
            <strong>Public Prototype Notice:</strong> DocShield is an independent AI-assisted document screening prototype and is not an official government verification service. Registry checks are simulated demonstration data.
          </span>
        </div>
      </section>

      {/* 4 Pillars Grid */}
      <section className="pillars-section">
        <div className="section-header">
          <h2 className="section-title">Four Independent Verification Layers</h2>
          <p className="section-subtitle">
            Every credential is evaluated through distinct forensic channels to prevent single-point bypasses.
          </p>
        </div>

        <div className="pillars-grid">
          {/* Pillar 1 */}
          <div className="pillar-card">
            <div className="pillar-icon-box">
              <FileCheck2 size={24} />
            </div>
            <h3 className="pillar-title">1. OCR &amp; Standard Layouts</h3>
            <p className="pillar-text">
              Extracts text tokens via dual-engine OCR (EasyOCR / Tesseract), scores token-level mean confidence, and enforces non-guessing classification against statutory anchors.
            </p>
            <div className="pillar-spec">
              <span>Standard:</span> ICAO Doc 9303 Part 4 TD3 / UIDAI Layout
            </div>
          </div>

          {/* Pillar 2 */}
          <div className="pillar-card">
            <div className="pillar-icon-box">
              <Cpu size={24} />
            </div>
            <h3 className="pillar-title">2. Mathematical Checksums</h3>
            <p className="pillar-text">
              Verifies mathematical integrity using the Verhoeff algorithm for 12-digit Aadhaar credentials and 7-3-1 weighting for ICAO passport MRZ check digits.
            </p>
            <div className="pillar-spec">
              <span>Standard:</span> Verhoeff Dihedral D5 &amp; ICAO Modulo-10
            </div>
          </div>

          {/* Pillar 3 */}
          <div className="pillar-card">
            <div className="pillar-icon-box">
              <Layers size={24} />
            </div>
            <h3 className="pillar-title">3. Compression Discrepancies</h3>
            <p className="pillar-text">
              Evaluates differential JPEG compression artifacts via Error Level Analysis (ELA) to identify localized inconsistencies indicative of digital splicing.
            </p>
            <div className="pillar-spec">
              <span>Standard:</span> Calibrated ELA Advisory Signal
            </div>
          </div>

          {/* Pillar 4 */}
          <div className="pillar-card">
            <div className="pillar-icon-box">
              <UserCheck size={24} />
            </div>
            <h3 className="pillar-title">4. 1:1 Facial Biometrics</h3>
            <p className="pillar-text">
              Compares extracted document portraits against live traveller camera photos using 128-dimensional metric learning embeddings, filtering low-resolution and multi-face images.
            </p>
            <div className="pillar-spec">
              <span>Standard:</span> dlib 128-d ResNet (Threshold 0.60)
            </div>
          </div>
        </div>
      </section>

      {/* Trust & Transparency Section: What It Does vs What It Does NOT Do */}
      <section className="transparency-section">
        <div className="section-header">
          <h2 className="section-title">Clear Boundaries &amp; Technical Honesty</h2>
          <p className="section-subtitle">
            DocShield is built with strict technical boundaries. We do not overstate AI capabilities or claim legal authority.
          </p>
        </div>

        <div className="transparency-grid">
          {/* What DocShield DOES */}
          <div className="transparency-card does">
            <div className="transparency-card-header">
              <CheckCircle2 size={20} className="check-icon" />
              <h3>What DocShield Does</h3>
            </div>
            <ul className="transparency-list">
              <li>
                <strong>Multi-factor advisory screening:</strong> Synthesizes OCR, mathematical, forensic, and biometric signals into an explainable risk score.
              </li>
              <li>
                <strong>Strict checksum validation:</strong> Identifies forged or manipulated ID numbers through standard check digit mathematics.
              </li>
              <li>
                <strong>Quality-controlled biometrics:</strong> Rejects ambiguous inputs such as multi-face photos or tiny crops (&lt; 45px) as indeterminate.
              </li>
              <li>
                <strong>Ephemeral in-memory processing:</strong> Uploaded images are discarded immediately after analysis, never stored permanently.
              </li>
              <li>
                <strong>Aadhaar privacy masking:</strong> Masks 12-digit Indian Aadhaar numbers to <code>XXXX-XXXX-1234</code> in compliance with privacy mandates.
              </li>
              <li>
                <strong>Human-in-the-loop review:</strong> Reserves final clearance authority for designated human immigration officers.
              </li>
            </ul>
          </div>

          {/* What DocShield DOES NOT Do */}
          <div className="transparency-card does-not">
            <div className="transparency-card-header">
              <XCircle size={20} className="cross-icon" />
              <h3>What DocShield Does NOT Do</h3>
            </div>
            <ul className="transparency-list">
              <li>
                <strong>Does NOT provide legal clearance:</strong> All outputs are advisory screening indicators, not authoritative government clearance.
              </li>
              <li>
                <strong>Does NOT query live databases:</strong> Operates against an isolated local mock demonstration list; not connected to live UIDAI, Passport Seva, or Interpol.
              </li>
              <li>
                <strong>Does NOT assert definitive forgery:</strong> ELA compression differentials are advisory heuristics and never declared as definite forgery on their own.
              </li>
              <li>
                <strong>Does NOT fabricate unread data:</strong> When OCR fails or tokens are missing, fields remain strictly <code>UNAVAILABLE</code>.
              </li>
              <li>
                <strong>Does NOT confirm legal identity:</strong> Biometric embeddings provide a distance metric; they do not legally certify personhood.
              </li>
              <li>
                <strong>Does NOT transmit data to cloud AI:</strong> All algorithms execute locally; no uploads to third-party commercial LLM or vision APIs.
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* Call to Action Banner */}
      <section className="cta-banner">
        <div className="cta-content">
          <div className="cta-icon-wrapper">
            <Lock size={32} />
          </div>
          <div>
            <h3 className="cta-title">Ready to Test Document Screening?</h3>
            <p className="cta-subtitle">
              Test the end-to-end pipeline with our preloaded synthetic sample credentials or upload test scans.
            </p>
          </div>
        </div>
        <button 
          type="button" 
          className="btn-primary-large"
          onClick={onStartScreening}
        >
          <span>Open Screening Console</span>
          <ArrowRight size={18} />
        </button>
      </section>
    </div>
  );
}
