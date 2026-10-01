import React from "react";
import { Lock, ShieldCheck, FileText, Database, EyeOff, Server, AlertCircle } from "lucide-react";

export default function PrivacyPage() {
  return (
    <div className="privacy-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Privacy Policy &amp; Data Security Architecture</h1>
          <p className="page-subtitle">
            How DocShield handles, processes, protects, and discards sensitive identity credential data.
          </p>
        </div>
      </div>

      {/* Warning Box */}
      <div className="prototype-advisory-box">
        <AlertCircle size={18} />
        <div>
          <strong>Public Demonstration Safeguard:</strong> This application is a hackathon demonstration. 
          Please do <em>not</em> upload live, unredacted passports, Aadhaar cards, or national IDs. Use the provided synthetic test presets.
        </div>
      </div>

      <div className="privacy-grid">
        {/* Policy 1: Ephemeral Processing */}
        <div className="privacy-card">
          <div className="privacy-card-icon">
            <Server size={22} />
          </div>
          <h3 className="privacy-card-title">1. Ephemeral In-Memory Processing</h3>
          <p className="privacy-card-text">
            All uploaded document scans and selfie photographs are ingested directly into volatile server memory as temporary byte buffers. 
            Once feature extraction, OCR parsing, and biometric comparisons are complete, the in-memory images are immediately released for garbage collection. 
            <strong>Raw image files are never written to disk or permanent storage.</strong>
          </p>
        </div>

        {/* Policy 2: Aadhaar Act Compliance */}
        <div className="privacy-card">
          <div className="privacy-card-icon">
            <EyeOff size={22} />
          </div>
          <h3 className="privacy-card-title">2. Mandatory Aadhaar Redaction</h3>
          <p className="privacy-card-text">
            In compliance with the Aadhaar Act (2016) and UIDAI privacy directives, any recognized 12-digit Indian Aadhaar number 
            is automatically masked to <code>XXXX-XXXX-1234</code> prior to any database persistence or client-side rendering. 
            Unmasked Aadhaar numbers are never logged or stored.
          </p>
        </div>

        {/* Policy 3: Zero Third-Party Cloud AI Sharing */}
        <div className="privacy-card">
          <div className="privacy-card-icon">
            <Lock size={22} />
          </div>
          <h3 className="privacy-card-title">3. Zero External AI Transmission</h3>
          <p className="privacy-card-text">
            Every computer vision, OCR, forensic, and biometric model runs 100% locally inside the DocShield application container. 
            <strong>No credential data, names, dates of birth, or biometric embeddings are ever transmitted to third-party cloud AI vendors</strong> (such as OpenAI, Google Cloud Vision, or AWS Rekognition).
          </p>
        </div>

        {/* Policy 4: Cryptographic Docket Isolation */}
        <div className="privacy-card">
          <div className="privacy-card-icon">
            <ShieldCheck size={22} />
          </div>
          <h3 className="privacy-card-title">4. Cryptographic Session Isolation</h3>
          <p className="privacy-card-text">
            Each screening transaction issues a 32-byte cryptographically secure session token (<code>X-Session-Token</code>) stored as a SHA-256 hash. 
            Other users cannot browse, search, or enumerate your screening docket without holding either your session token or an authorized clearance officer key.
          </p>
        </div>

        {/* Policy 5: Anti-Caching Headers */}
        <div className="privacy-card">
          <div className="privacy-card-icon">
            <FileText size={22} />
          </div>
          <h3 className="privacy-card-title">5. Defensive Anti-Caching Headers</h3>
          <p className="privacy-card-text">
            All screening API responses are served with strict HTTP defensive headers (<code>Cache-Control: no-store, no-cache, must-revalidate, private, max-age=0</code>) 
            to prevent intermediate proxies, browser caches, or device disks from persisting sensitive document metadata.
          </p>
        </div>

        {/* Policy 6: Local Mock Database */}
        <div className="privacy-card">
          <div className="privacy-card-icon">
            <Database size={22} />
          </div>
          <h3 className="privacy-card-title">6. Mock Demonstration Watchlist</h3>
          <p className="privacy-card-text">
            The security registry check operates against an isolated 7-record mock demonstration database (<code>DEMO_WATCHLIST</code>). 
            DocShield is not connected to live government criminal registries, UIDAI CIDR, or Interpol databases.
          </p>
        </div>
      </div>
    </div>
  );
}
