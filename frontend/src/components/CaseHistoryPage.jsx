import React, { useState, useEffect } from "react";
import { 
  History, 
  Key, 
  Search, 
  CheckCircle, 
  AlertTriangle, 
  ArrowRight, 
  ShieldCheck, 
  RotateCw, 
  Eye 
} from "lucide-react";
import { listCases, getCase, getOfficerKey, setOfficerKey } from "../api";

export default function CaseHistoryPage({ currentResult, onSelectCase }) {
  const [officerKeyInput, setOfficerKeyInput] = useState(getOfficerKey());
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 5;

  useEffect(() => {
    if (getOfficerKey()) {
      fetchCases();
    }
  }, []);

  const fetchCases = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listCases();
      setCases(data);
    } catch (err) {
      setError(err.message || "Failed to load case dockets.");
      setCases([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveKey = (e) => {
    e.preventDefault();
    setOfficerKey(officerKeyInput.trim());
    fetchCases();
  };

  const handleClearKey = () => {
    setOfficerKey("");
    setOfficerKeyInput("");
    setCases([]);
    setError(null);
  };

  const handleInspectDocket = async (caseId) => {
    try {
      setLoading(true);
      const caseData = await getCase(caseId);
      onSelectCase(caseData);
    } catch (err) {
      setError(`Cannot load case ${caseId}: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Filter cases by search term
  const filteredCases = cases.filter((c) => {
    const term = searchTerm.toLowerCase();
    return (
      c.case_id?.toLowerCase().includes(term) ||
      c.document_type?.toLowerCase().includes(term) ||
      c.verdict?.toLowerCase().includes(term)
    );
  });

  const totalPages = Math.max(1, Math.ceil(filteredCases.length / pageSize));
  const paginatedCases = filteredCases.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  return (
    <div className="history-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Authorized Case Docket History</h1>
          <p className="page-subtitle">
            Browse and inspect previous multi-layer document screening records and officer review sign-offs.
          </p>
        </div>
      </div>

      {/* Officer Key Authentication Card */}
      <div className="auth-card">
        <div className="auth-card-header">
          <Key size={18} className="auth-icon" />
          <div>
            <h3 className="auth-title">Officer Key Authorization Required</h3>
            <p className="auth-subtitle">
              Screening dockets are protected under privacy isolation controls. Enter your authorized Officer Key to access the case log.
            </p>
          </div>
        </div>

        <form onSubmit={handleSaveKey} className="auth-form">
          <input
            type="password"
            className="form-input auth-input"
            placeholder="Enter X-Officer-Key (e.g., dev-officer-key-409)"
            value={officerKeyInput}
            onChange={(e) => setOfficerKeyInput(e.target.value)}
          />
          <button type="submit" className="btn-primary" disabled={loading || !officerKeyInput.trim()}>
            Authorize Access
          </button>
          {getOfficerKey() && (
            <button type="button" className="btn-action-outline" onClick={handleClearKey}>
              Clear Key
            </button>
          )}
        </form>
      </div>

      {/* Active Session Fallback if not officer authorized */}
      {!getOfficerKey() && currentResult && (
        <div className="active-session-card">
          <div className="session-card-header">
            <ShieldCheck size={20} className="text-green" />
            <div>
              <h4 className="session-title">Current Session Docket Available</h4>
              <p className="session-subtitle">
                You have an active screening result in this browser session: Docket <strong>{currentResult.case_id}</strong>
              </p>
            </div>
          </div>
          <button
            type="button"
            className="btn-action-outline"
            onClick={() => onSelectCase(currentResult)}
          >
            <span>View Active Docket in Results</span>
            <ArrowRight size={14} />
          </button>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="error-alert" role="alert">
          <AlertTriangle size={18} className="error-icon" />
          <div className="error-body">{error}</div>
        </div>
      )}

      {/* Case List if Authorized */}
      {getOfficerKey() && (
        <div className="section-card">
          <div className="table-controls-bar">
            <div className="search-box">
              <Search size={16} />
              <input
                type="text"
                placeholder="Search by Docket ID, Document Type..."
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setCurrentPage(1);
                }}
              />
            </div>

            <button type="button" className="btn-action-outline" onClick={fetchCases} disabled={loading}>
              <RotateCw size={14} className={loading ? "spinner-icon" : ""} />
              <span>Refresh Log</span>
            </button>
          </div>

          {loading ? (
            <div className="loading-state">
              <RotateCw size={24} className="spinner-icon" />
              <p>Querying authorized case repository...</p>
            </div>
          ) : paginatedCases.length === 0 ? (
            <div className="empty-state">
              <History size={36} className="empty-icon" />
              <h4>No Case Dockets Found</h4>
              <p>No screening records match your current filter criteria.</p>
            </div>
          ) : (
            <>
              <table className="docket-table full-table">
                <thead>
                  <tr>
                    <th>Docket ID</th>
                    <th>Timestamp</th>
                    <th>Document Type</th>
                    <th>Risk Level</th>
                    <th>Verdict</th>
                    <th>Adjudication</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedCases.map((c) => (
                    <tr key={c.case_id}>
                      <td className="mono bold">{c.case_id}</td>
                      <td className="mono muted">{c.timestamp?.slice(0, 19).replace("T", " ")}</td>
                      <td>
                        <span className="doc-pill">{c.document_type}</span>
                      </td>
                      <td>
                        <span className={`status-badge ${c.risk_level === "LOW" ? "pass" : c.risk_level === "MEDIUM" ? "warn" : "fail"}`}>
                          {c.risk_level} ({c.risk_score}/100)
                        </span>
                      </td>
                      <td className="bold">{c.verdict?.replace(/_/g, " ")}</td>
                      <td>
                        {c.officer_decision || c.officer_review?.reviewed ? (
                          <span className="status-badge pass">
                            <CheckCircle size={12} /> Signed
                          </span>
                        ) : (
                          <span className="status-badge warn">
                            <AlertTriangle size={12} /> Pending
                          </span>
                        )}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn-inspect-docket"
                          onClick={() => handleInspectDocket(c.case_id)}
                          title="Inspect docket details in Results view"
                        >
                          <Eye size={13} />
                          <span>Inspect</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Pagination controls */}
              {totalPages > 1 && (
                <div className="pagination-bar">
                  <span className="page-count">
                    Page {currentPage} of {totalPages} ({filteredCases.length} total records)
                  </span>
                  <div className="pagination-buttons">
                    <button
                      type="button"
                      className="btn-page"
                      disabled={currentPage <= 1}
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    >
                      Previous
                    </button>
                    <button
                      type="button"
                      className="btn-page"
                      disabled={currentPage >= totalPages}
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
