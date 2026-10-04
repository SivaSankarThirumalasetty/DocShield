import React, { useState, useEffect } from "react";
import Navbar from "./components/Navbar";
import HomePage from "./components/HomePage";
import ScreeningPage from "./components/ScreeningPage";
import ResultsView from "./components/ResultsView";
import CaseHistoryPage from "./components/CaseHistoryPage";
import MethodologyPage from "./components/MethodologyPage";
import PrivacyPage from "./components/PrivacyPage";
import Footer from "./components/Footer";
import { checkHealth, analyzeDocument, submitOfficerReview } from "./api";

export default function App() {
  const [activePage, setActivePage] = useState("home");
  const [health, setHealth] = useState(null);

  // Screening form state
  const [docFile, setDocFile] = useState(null);
  const [docPreview, setDocPreview] = useState(null);
  const [personFile, setPersonFile] = useState(null);
  const [personPreview, setPersonPreview] = useState(null);
  const [docTypeHint, setDocTypeHint] = useState("auto");

  // Analysis result state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  // Officer sign-off state
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [reviewStatusMsg, setReviewStatusMsg] = useState(null);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const data = await checkHealth();
        if (active) setHealth(data);
      } catch {
        if (active) setHealth((prev) => (prev?.status === "healthy" ? prev : { status: "offline" }));
      }
    };
    poll();
    const interval = setInterval(poll, health?.status === "healthy" ? 30000 : 5000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [health?.status]);

  const fetchHealth = async () => {
    try {
      const data = await checkHealth();
      setHealth(data);
    } catch {
      setHealth({ status: "offline" });
    }
  };

  const handleLoadPreset = async (presetType) => {
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

      // Switch to screening view if on another page
      setActivePage("screening");
    } catch {
      setError("Failed to load sample fixture assets.");
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
      setActivePage("results");
    } catch (err) {
      setError(err.message || "Failed to execute document analysis.");
    } finally {
      setLoading(false);
    }
  };

  const handleOfficerSignoff = async (reviewData) => {
    if (!result?.case_id) return;
    setReviewSubmitting(true);
    setReviewStatusMsg(null);
    try {
      const updated = await submitOfficerReview(result.case_id, reviewData);
      setResult(updated);
      setReviewStatusMsg("Officer Adjudication officially recorded and signed into docket.");
    } catch (err) {
      setReviewStatusMsg(`Error submitting adjudication: ${err.message}`);
    } finally {
      setReviewSubmitting(false);
    }
  };

  const handleSelectCaseFromHistory = (caseData) => {
    setResult(caseData);
    setActivePage("results");
  };

  return (
    <div className="app-container">
      {/* Top Navigation */}
      <Navbar
        activePage={activePage}
        setActivePage={setActivePage}
        health={health}
        hasResult={Boolean(result)}
      />

      {/* Main Page Routing */}
      <main className="main-content" id="main-content">
        {activePage === "home" && (
          <HomePage
            onStartScreening={() => setActivePage("screening")}
            onExploreMethodology={() => setActivePage("methodology")}
          />
        )}

        {activePage === "screening" && (
          <ScreeningPage
            docFile={docFile}
            setDocFile={setDocFile}
            docPreview={docPreview}
            setDocPreview={setDocPreview}
            personFile={personFile}
            setPersonFile={setPersonFile}
            personPreview={personPreview}
            setPersonPreview={setPersonPreview}
            docTypeHint={docTypeHint}
            setDocTypeHint={setDocTypeHint}
            loading={loading}
            error={error}
            onAnalyze={handleAnalyze}
            onReset={handleReset}
            onLoadPreset={handleLoadPreset}
          />
        )}

        {activePage === "results" && (
          <ResultsView
            result={result}
            onStartNew={() => {
              handleReset();
              setActivePage("screening");
            }}
            onSubmitOfficerReview={handleOfficerSignoff}
            reviewSubmitting={reviewSubmitting}
            reviewStatusMsg={reviewStatusMsg}
          />
        )}

        {activePage === "history" && (
          <CaseHistoryPage
            currentResult={result}
            onSelectCase={handleSelectCaseFromHistory}
          />
        )}

        {activePage === "methodology" && <MethodologyPage />}

        {activePage === "privacy" && <PrivacyPage />}
      </main>

      {/* Footer */}
      <Footer onNavigate={(pageId) => setActivePage(pageId)} />
    </div>
  );
}
