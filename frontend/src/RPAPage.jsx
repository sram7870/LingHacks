import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { 
  rpaUploadPaper, 
  rpaAnalyzePaper, 
  listLandscapes
} from "./api";
import MetricCard from "./components/rpa/MetricCard";
import ClaimTable from "./components/rpa/ClaimTable";
import InsightPanel from "./components/rpa/InsightPanel";
import PaperReader from "./components/rpa/PaperReader";
import UploadSection from "./components/rpa/UploadSection";

const RPAPage = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [analysisResult, setAnalysisResult] = useState(null);
  const [paperData, setPaperData] = useState(null);
  const [paperTitle, setPaperTitle] = useState("");
  const [paperSummary, setPaperSummary] = useState("");
  
  const [landscapes, setLandscapes] = useState([]);
  const [selectedLandscape, setSelectedLandscape] = useState("");
  const [uploadedPaperId, setUploadedPaperId] = useState(null);

  useEffect(() => {
    fetchLandscapes();
  }, []);

  const fetchLandscapes = async () => {
    try {
      const data = await listLandscapes();
      setLandscapes(data || []);
      setSelectedLandscape((current) => current || data?.[0]?.id || "");
    } catch (err) {
      console.error("Failed to fetch landscapes", err);
    }
  };

  const handleStartAnalysis = async (overrideLandscapeId = undefined) => {
    const landscapeId = overrideLandscapeId !== undefined ? overrideLandscapeId : selectedLandscape;
    
    if (!uploadedPaperId) {
      setError("Please upload a paper first.");
      return;
    }

    if (!landscapeId) {
      setError("Select an existing landscape before running relational analysis.");
      return;
    }
    
    setLoading(true);
    setError("");
    setStatusMessage("Performing Relational Paper Analysis...");
    
    try {
      const result = await rpaAnalyzePaper(uploadedPaperId, landscapeId);
      
      setAnalysisResult(result.rpa);
      
      // Construct paperData for Reader
      setPaperData({
        title: result.paper.title,
        abstract: result.paper.abstract,
        year: result.paper.year,
        authors: result.paper.authors || [],
        sections: result.paper.sections || {},
        claims: result.paper.claims || []
      });
      
      setStatusMessage("Relational analysis complete.");
    } catch (err) {
      setError(err.message || "Relational analysis failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (file) => {
    if (!file) return;
    setLoading(true);
    setError("");
    setStatusMessage("Registering paper...");
    
    try {
      const res = await rpaUploadPaper(file, selectedLandscape || null);
      
      setUploadedPaperId(res.paper_id);
      setPaperTitle(res.title);
      
      if (selectedLandscape) {
        await fetchLandscapes();
      }
      
      setStatusMessage("Paper registered. Ready for relational analysis.");
    } catch (err) {
      setError(err.message || "File registration failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleLandscapeChange = (newId) => {
    setSelectedLandscape(newId);
    if (analysisResult) {
      // If we already have results, trigger a re-analysis with the new landscape immediately
      handleStartAnalysis(newId);
    }
  };

  const shouldShowRpaWarning = Boolean(
    analysisResult?.corpus_too_small ||
    (analysisResult?.message && analysisResult?.aggregate_cas == null)
  );

  return (
    <div className="min-h-screen bg-bg text-ink">
      <header className="sticky top-0 z-30 border-b border-border bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-[1400px] items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/" className="flex h-10 w-10 items-center justify-center rounded-xl bg-ink text-white transition hover:scale-110">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
            </Link>
            <div>
              <div className="font-playfair text-xl font-bold">LingHacks</div>
              <div className="text-[10px] uppercase tracking-widest text-inkSec font-bold">Relational Analysis Suite</div>
            </div>
          </div>
          
          <div className="hidden md:flex items-center gap-6">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-inkSec">
              <span className="h-2 w-2 rounded-full bg-green animate-pulse"></span>
              Live RPA Engine
            </div>
            <div className="h-8 w-px bg-border"></div>
            <button 
              onClick={() => { 
                setAnalysisResult(null); 
                setPaperData(null); 
                setUploadedPaperId(null);
                setPaperTitle("");
                setPaperSummary("");
                setStatusMessage("");
              }}
              className="text-xs font-bold uppercase tracking-widest text-ink hover:text-inkSec transition"
            >
              New Analysis
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1400px] px-6">
        {!analysisResult ? (
          <UploadSection 
            loading={loading}
            paperTitle={paperTitle}
            setPaperTitle={setPaperTitle}
            paperSummary={paperSummary}
            setPaperSummary={setPaperSummary}
            onParse={() => handleStartAnalysis()}
            onUpload={handleFileUpload}
            landscapes={landscapes}
            selectedLandscape={selectedLandscape}
            setSelectedLandscape={handleLandscapeChange}
          />
        ) : (
          <div className="grid grid-cols-1 gap-8 py-8 lg:grid-cols-2 lg:h-[calc(100vh-120px)]">
            {/* Left Panel: Paper Reader */}
            <div className="overflow-hidden">
              <PaperReader paper={paperData} />
            </div>

            {/* Right Panel: RPA Dashboard */}
            <div className="flex flex-col gap-6 overflow-y-auto pr-2 scrollbar-hide pb-10">
              {/* Landscape Switcher (Interactive) */}
              <div className="rounded-2xl border-2 border-border bg-white p-4 shadow-sm flex items-center justify-between">
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-widest text-inkSec">Comparison Context</div>
                  <div className="text-sm font-bold text-ink">Active Landscape</div>
                </div>
                <select 
                  value={selectedLandscape} 
                  onChange={(e) => handleLandscapeChange(e.target.value)}
                  className="rounded-xl border-2 border-border bg-surfaceAlt px-4 py-2 text-sm font-bold text-ink outline-none focus:border-ink transition"
                >
                  {landscapes.map(l => (
                    <option key={l.id} value={l.id}>{l.name} ({l.paper_ids?.length || 0})</option>
                  ))}
                </select>
              </div>

              <InsightPanel rpaResult={analysisResult} />

              {shouldShowRpaWarning ? (
                <div className="rounded-2xl border-2 border-amber-200 bg-amber-50 p-8 text-center shadow-sm">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-100 text-amber-600 mb-4">
                    <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <h3 className="text-lg font-bold text-amber-800">
                    {analysisResult.corpus_too_small ? "Insufficient Comparative Data" : "Relational Analysis Unavailable"}
                  </h3>
                  <p className="mt-2 text-sm text-amber-700 leading-relaxed">
                    {analysisResult.message || "Add at least 2 analyzed papers to this collection on the homepage to unlock metrics."}
                  </p>
                  <Link to="/" className="mt-6 inline-block rounded-xl bg-amber-600 px-6 py-2 text-xs font-bold text-white shadow-sm hover:bg-amber-700">
                    Go to Homepage
                  </Link>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <MetricCard 
                      title="Consensus Alignment (CAS)"
                      value={analysisResult.aggregate_cas}
                      progress={(analysisResult.aggregate_cas || 0.5) * 100}
                      interpretation={analysisResult.cas_interpretation}
                      color={(analysisResult.aggregate_cas > 0.6) ? "text-green" : (analysisResult.aggregate_cas < 0.4 ? "text-red" : "text-ink")}
                    />
                    <MetricCard 
                      title="Field Controversy (FCI)"
                      value={analysisResult.fci_score}
                      progress={analysisResult.fci_score || 50}
                      label={analysisResult.fci_label}
                      color={(analysisResult.fci_score > 70) ? "text-red" : (analysisResult.fci_score < 30 ? "text-green" : "text-ink")}
                    />
                    <MetricCard 
                      title="Methodological Standing"
                      value={analysisResult.mss_percentile}
                      unit="th"
                      progress={analysisResult.mss_percentile || 50}
                      label={analysisResult.mss_label}
                      interpretation={analysisResult.methodological_underdog ? "Methodological Underdog" : "Solid Standing"}
                      color={(analysisResult.mss_percentile > 70) ? "text-green" : (analysisResult.mss_percentile < 30 ? "text-red" : "text-ink")}
                    />
                    <MetricCard 
                      title="Claim Novelty (CNS)"
                      value={(analysisResult.aggregate_cns || 0) * 100}
                      unit="%"
                      progress={(analysisResult.aggregate_cns || 0) * 100}
                      interpretation={analysisResult.aggregate_cns > 0.15 ? analysisResult.cns_interpretation : "Replication Candidate"}
                      color="text-blue"
                    />
                  </div>

                  {/* Temporal Field Position */}
                  <div className="rounded-2xl border-2 border-border bg-white p-6 shadow-sm">
                    <div className="text-xs uppercase tracking-[0.18em] text-inkSec mb-4 font-bold">Temporal Field Position (TFP)</div>
                    <div className="flex items-center justify-between mb-6">
                      <div className="space-y-1">
                        <div className="text-sm font-bold text-inkSec">Debate Maturity</div>
                        <div className="text-lg font-bold text-ink">{analysisResult.debate_maturity || "Mid-Debate"}</div>
                      </div>
                      <div className="h-10 w-px bg-border"></div>
                      <div className="space-y-1 text-right">
                        <div className="text-sm font-bold text-inkSec">Trajectory</div>
                        <div className="text-lg font-bold text-blue">{analysisResult.field_trajectory_at_publication || "Stable"}</div>
                      </div>
                    </div>
                    
                    {/* Visual Timeline */}
                    <div className="relative mt-8 h-12 w-full px-4">
                      <div className="absolute top-1/2 left-0 h-0.5 w-full -translate-y-1/2 bg-surfaceAlt"></div>
                      <div className="absolute left-0 top-1/2 h-2 w-2 -translate-y-1/2 rounded-full bg-border"></div>
                      <div className="absolute right-0 top-1/2 h-2 w-2 -translate-y-1/2 rounded-full bg-border"></div>
                      
                      {/* Paper Position Indicator */}
                      <div 
                        className="absolute top-1/2 -translate-y-1/2 flex flex-col items-center gap-2 transition-all duration-700"
                        style={{ left: '50%' }}
                      >
                        <div className="h-4 w-4 rounded-full border-4 border-white bg-ink shadow-lg scale-110"></div>
                        <div className="text-[10px] font-bold uppercase text-ink whitespace-nowrap bg-white px-2 py-0.5 rounded shadow-sm border border-border">
                          {analysisResult.publication_year || 2026} (This Paper)
                        </div>
                      </div>
                    </div>
                    <div className="mt-4 flex justify-between text-[10px] font-bold uppercase tracking-widest text-inkSec px-2">
                      <span>Foundational</span>
                      <span>Emerging</span>
                      <span>Current</span>
                    </div>
                  </div>

                  <ClaimTable 
                    claims={paperData?.claims || analysisResult.per_claim_cas?.map(c => ({ text: c.claim_text })) || []}
                    casData={analysisResult.per_claim_cas}
                    cnsData={analysisResult.per_claim_cns}
                  />
                </>
              )}
            </div>
          </div>
        )}
      </main>

      {loading && (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-white bg-opacity-90 backdrop-blur-sm">
          <div className="relative h-20 w-20">
            <div className="absolute inset-0 rounded-full border-4 border-surfaceAlt"></div>
            <div className="absolute inset-0 rounded-full border-4 border-ink border-t-transparent animate-spin"></div>
          </div>
          <div className="mt-6 text-center px-4">
            <div className="font-playfair text-xl font-bold text-ink">{statusMessage || "Processing Relational Data"}</div>
            <div className="mt-2 text-sm text-inkSec max-w-xs mx-auto leading-relaxed">
              Synchronizing paper metadata with our multi-agent knowledge graph...
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="fixed bottom-8 right-8 z-50 rounded-2xl border-2 border-red bg-redLight p-4 shadow-panel max-w-md animate-in slide-in-from-bottom-4">
          <div className="flex gap-3">
            <svg className="h-6 w-6 text-red shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <div className="text-sm font-bold text-red">System Alert</div>
              <div className="mt-1 text-sm text-ink font-medium leading-snug">{error}</div>
            </div>
            <button onClick={() => setError("")} className="ml-auto text-inkSec hover:text-ink">
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default RPAPage;
