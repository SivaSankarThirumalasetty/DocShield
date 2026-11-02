import React, { useState, useEffect, useRef, useCallback } from "react";
import Navbar from "./components/Navbar";
import HomePage from "./components/HomePage";
import ScreeningPage from "./components/ScreeningPage";
import ResultsView from "./components/ResultsView";
import CaseHistoryPage from "./components/CaseHistoryPage";
import MethodologyPage from "./components/MethodologyPage";
import PrivacyPage from "./components/PrivacyPage";
import Footer from "./components/Footer";
import { checkReadiness, analyzeDocument, submitOfficerReview } from "./api";

export default function App() {
  const [activePage, setActivePage] = useState("home");
  // Service status comes only from /api/ready (Worker + D1 + container models).
  const [service, setService] = useState({ state: "checking", body: null });

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

  const refreshReadiness = useCallback(async (signal) => {
    try {
      const status = await checkReadiness(signal);
      setService(status);
      return status.state;
    } catch {
      return null; // cancelled
    }
  }, []);

  // Poll while the engine is starting (cold start), then stop: polling a ready
  // service would keep the container awake and billing indefinitely.
  useEffect(() => {
    const controller = new AbortController();
    let attempts = 0;
    let timer;
    const tick = async () => {
      const state = await refreshReadiness(controller.signal);
      attempts += 1;
      if (state && state !== "ready" && attempts < 20 && !controller.signal.aborted) {
        timer = setTimeout(tick, 10000);
      }
    };
    tick();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [refreshReadiness]);

  const analysisController = useRef(null);

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
    const controller = new AbortController();
    analysisController.current = controller;
    try {
      const data = await analyzeDocument(docFile, personFile, docTypeHint, controller.signal);
      setResult(data);
      setService((prev) => ({ ...prev, state: "ready" }));
      setActivePage("results");
    } catch (err) {
      setError(err.message || "Document screening failed.");
      refreshReadiness();
    } finally {
      analysisController.current = null;
      setLoading(false);
    }
  };

  const handleCancelAnalysis = () => {
    analysisController.current?.abort();
  };

  const handleOfficerSignoff = async (reviewData) => {
    if (!result?.case_id) return;
    setReviewSubmitting(true);
    setReviewStatusMsg(null);
    try {
      const updated = await submitOfficerReview(result.case_id, reviewData);
      setResult(updated);
      setReviewStatusMsg("Reviewer assessment recorded in the case audit log.");
    } catch (err) {
      setReviewStatusMsg(`Could not record the review: ${err.message}`);
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
        service={service}
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
            onCancel={handleCancelAnalysis}
            serviceState={service.state}
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
