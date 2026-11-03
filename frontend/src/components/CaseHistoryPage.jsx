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
import { listCases, getCase, getReviewerToken, setReviewerToken, getReviewerProfile } from "../api";

export default function CaseHistoryPage({ currentResult, onSelectCase }) {
  const [officerKeyInput, setOfficerKeyInput] = useState(getReviewerToken());
  const [reviewer, setReviewer] = useState(null);
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(() => Boolean(getReviewerToken()));
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 5;

  const fetchCases = async () => {
    setLoading(true);
    setError(null);
    try {
      const profile = await getReviewerProfile();
      setReviewer(profile);
      const data = await listCases();
      setCases(data);
    } catch (err) {
      setError(err.message || "Failed to load cases.");
      setReviewer(null);
      setCases([]);
    } finally {
      setLoading(false);
    }
  };

  // Restore a signed-in reviewer session on mount (token kept in sessionStorage).
  useEffect(() => {
    if (!getReviewerToken()) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const profile = await getReviewerProfile();
        const data = await listCases();
        if (!cancelled) {
          setReviewer(profile);
          setCases(data);
        }
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load cases.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSaveKey = (e) => {
    e.preventDefault();
    setReviewerToken(officerKeyInput.trim());
    fetchCases();
  };

  const handleClearKey = () => {
    setReviewerToken("");
    setReviewer(null);
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
          <h1 className="page-title">Case History (Reviewers)</h1>
          <p className="page-subtitle">
            Redacted records of recent screenings in your tenant, kept for the configured retention period.
          </p>
        </div>
      </div>

      {/* Officer Key Authentication Card */}
      <div className="auth-card">
        <div className="auth-card-header">
          <Key size={18} className="auth-icon" />
          <div>
            <h3 className="auth-title">Reviewer sign-in</h3>
            <p className="auth-subtitle">
              Enter the personal reviewer token issued by your administrator. It is kept only for this browser tab.
            </p>
          </div>
        </div>

        <form onSubmit={handleSaveKey} className="auth-form">
          <input
            type="password"
            className="form-input auth-input"
            placeholder="Reviewer access token"
            autoComplete="off"
            value={officerKeyInput}
            onChange={(e) => setOfficerKeyInput(e.target.value)}
          />
          <button type="submit" className="btn-primary" disabled={loading || !officerKeyInput.trim()}>
            Sign in
          </button>
          {getReviewerToken() && (
            <button type="button" className="btn-action-outline" onClick={handleClearKey}>
              Sign out
            </button>
          )}
        </form>
      </div>

      {/* Active Session Fallback if not officer authorized */}
      {!reviewer && currentResult && (

        <div className="active-session-card">
          <div className="session-card-header">
            <ShieldCheck size={20} className="text-green" />
            <div>
              <h4 className="session-title">Your current screening result</h4>
              <p className="session-subtitle">
                You have a screening result from this browser session: case <strong>{currentResult.case_id}</strong>
              </p>
            </div>
          </div>
          <button
            type="button"
            className="btn-action-outline"
            onClick={() => onSelectCase(currentResult)}
          >
            <span>View result</span>
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
      {reviewer && (
        <div className="section-card">
          <p className="page-subtitle">Signed in as {reviewer.display_name} ({reviewer.officer_id}), tenant {reviewer.tenant_id}.</p>
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
