import React from "react";
import { Shield } from "lucide-react";

export default function Footer({ onNavigate }) {
  return (
    <footer className="footer-container">
      <div className="footer-content">
        <div className="footer-brand-col">
          <div className="footer-brand-title">
            <Shield size={20} className="footer-shield" />
            <span>DocShield</span>
          </div>
          <p className="footer-tagline">
            Smart India Hackathon 2026 (SIH26188) — Open Document Forensics &amp; Biometric Screening Prototype.
          </p>
          <div className="footer-disclaimer">
            <strong>Public Prototype Notice:</strong> DocShield is an independent AI-assisted document screening prototype and is not an official government verification service. Registry checks are simulated demonstration data.
          </div>
        </div>

        <div className="footer-links-col">
          <h4 className="footer-links-title">Navigation</h4>
          <ul className="footer-nav-list">
            <li><button type="button" onClick={() => onNavigate("home")}>Platform Overview</button></li>
            <li><button type="button" onClick={() => onNavigate("screening")}>Screening Console</button></li>
            <li><button type="button" onClick={() => onNavigate("results")}>Screening Results</button></li>
            <li><button type="button" onClick={() => onNavigate("history")}>Case History</button></li>
            <li><button type="button" onClick={() => onNavigate("methodology")}>Technical Methodology</button></li>
            <li><button type="button" onClick={() => onNavigate("privacy")}>Privacy Policy</button></li>
          </ul>
        </div>

        <div className="footer-specs-col">
          <h4 className="footer-links-title">Forensic Standards</h4>
          <ul className="footer-specs-list">
            <li><span>ICAO Doc 9303 Part 4 TD3 (MRZ)</span></li>
            <li><span>Verhoeff Checksum Algorithm (D5)</span></li>
            <li><span>128-d Metric Learning (dlib ResNet)</span></li>
            <li><span>Error Level Analysis (ELA 90% JPEG)</span></li>
            <li><span>Section 29 Aadhaar Privacy Masking</span></li>
          </ul>
        </div>
      </div>

      <div className="footer-bottom">
        <span>© 2026 DocShield Project • Smart India Hackathon 2026 Prototype</span>
        <span>Advisory Screening System • Human-in-the-Loop Final Clearance</span>
      </div>
    </footer>
  );
}
