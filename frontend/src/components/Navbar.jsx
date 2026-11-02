import React, { useState } from "react";
import { Shield, Menu, X, FileText, CheckCircle2, History, BookOpen, Lock } from "lucide-react";

const STATUS_LABELS = {
  checking: { text: "Checking service…", dot: "offline", title: "Checking the screening engine status." },
  ready: { text: "Engine ready", dot: "healthy", title: "Readiness check passed: OCR, face and registry modules loaded." },
  starting: { text: "Engine starting…", dot: "offline", title: "The screening container is starting or a module is not loaded yet." },
  unavailable: { text: "Engine unavailable", dot: "offline", title: "The screening service did not respond to its readiness check." },
};

export default function Navbar({ activePage, setActivePage, service, hasResult }) {
  const status = STATUS_LABELS[service?.state] || STATUS_LABELS.checking;
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navItems = [
    { id: "home", label: "Overview", icon: Shield },
    { id: "screening", label: "Screening Console", icon: FileText },
    { id: "results", label: "Screening Results", icon: CheckCircle2, badge: hasResult ? "Active" : null },
    { id: "history", label: "Case History", icon: History },
    { id: "methodology", label: "Methodology", icon: BookOpen },
    { id: "privacy", label: "Privacy Policy", icon: Lock },
  ];

  const handleNavClick = (id) => {
    setActivePage(id);
    setMobileMenuOpen(false);
  };

  return (
    <header className="navbar-container">
      <div className="navbar-main">
        {/* Brand */}
        <div 
          className="navbar-brand" 
          onClick={() => handleNavClick("home")}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") handleNavClick("home"); }}
          aria-label="DocShield Home"
        >
          <div className="brand-icon-wrapper">
            <Shield size={24} className="brand-icon" />
          </div>
          <div>
            <div className="brand-title-row">
              <span className="brand-name">DocShield</span>
              <span className="prototype-pill">PROTOTYPE MODE</span>
            </div>
            <div className="brand-tagline">
              AI-assisted document screening (advisory prototype)
            </div>
          </div>
        </div>

        {/* Desktop Nav */}
        <nav className="desktop-nav" aria-label="Main Navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activePage === item.id;
            return (
              <button
                key={item.id}
                type="button"
                className={`nav-link ${isActive ? "active" : ""}`}
                onClick={() => handleNavClick(item.id)}
                aria-current={isActive ? "page" : undefined}
              >
                <Icon size={16} />
                <span>{item.label}</span>
                {item.badge && <span className="nav-item-badge">{item.badge}</span>}
              </button>
            );
          })}
        </nav>

        {/* Right Status Indicator & Mobile Toggle */}
        <div className="navbar-right">
          <div 
            className="system-health-pill" 
            title={status.title}
            aria-live="polite"
          >
            <span className={`status-indicator-dot ${status.dot}`} />
            <span className="status-indicator-text">{status.text}</span>
          </div>

          <button
            type="button"
            className="mobile-menu-toggle"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileMenuOpen}
          >
            {mobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <nav className="mobile-nav" aria-label="Mobile Navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activePage === item.id;
            return (
              <button
                key={item.id}
                type="button"
                className={`mobile-nav-link ${isActive ? "active" : ""}`}
                onClick={() => handleNavClick(item.id)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
                {item.badge && <span className="nav-item-badge">{item.badge}</span>}
              </button>
            );
          })}
        </nav>
      )}

      {/* Global Safety & Prototype Notice Strip */}
      <div className="statutory-notice-strip">
        <span>
          <strong>Notice:</strong> DocShield is an independent AI-assisted document screening prototype and is not an official government verification service. Registry checks are simulated demonstration data.
        </span>
      </div>
    </header>
  );
}
