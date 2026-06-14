import { useState, useEffect } from "react";
import { analyzeRelational, uploadPaper } from "./api";
import MetricCard from "./components/rpa/MetricCard";
import ClaimTable from "./components/rpa/ClaimTable";
import InsightPanel from "./components/rpa/InsightPanel";
import PaperReader from "./components/rpa/PaperReader";
import UploadSection from "./components/rpa/UploadSection";

const MOCK_RPA_DATA = {
  paper_id: "paper_mock_001",
  paper_title: "Long-term Antibiotic Therapy in Chronic Lyme Disease: A Relational Study",
  aggregate_cas: 0.35,
  cas_interpretation: "Contested",
  per_claim_cas: [
    { claim_text: "Extended antibiotic treatment improves quality of life in CLD patients.", cas_score: 0.28, supporting_count: 3, contradicting_count: 8, neutral_count: 2, low_corpus_coverage: false },
    { claim_text: "Persistent Borrelia burgdorferi infection survives standard 30-day protocols.", cas_score: 0.42, supporting_count: 5, contradicting_count: 6, neutral_count: 4, low_corpus_coverage: false }
  ],
  fci_score: 82.5,
  fci_label: "Deeply Polarized",
  subgraph_paper_count: 24,
  edge_controversy_ratio: 0.65,
  stance_distribution: { supporting: 10, opposing: 12, neutral: 2 },
  mss_percentile: 42.0,
  mss_label: "Average",
  contradicting_papers_median_quality: 0.78,
  methodological_underdog: true,
  comparison_pool_size: 15,
  aggregate_cns: 0.88,
  cns_interpretation: "Highly Novel",
  per_claim_cns: [
    { claim_text: "Extended antibiotic treatment improves quality of life in CLD patients.", cns_score: 0.92, most_similar_existing_claim: "Antibiotics help some patients.", similarity_score: 0.08, replication_candidate: false },
    { claim_text: "Persistent Borrelia burgdorferi infection survives standard 30-day protocols.", cns_score: 0.84, most_similar_existing_claim: "Borrelia can persist in animal models.", similarity_score: 0.16, replication_candidate: false }
  ],
  publication_year: 2024,
  field_trajectory_at_publication: "Diverging",
  alignment_with_trajectory: "Contrarian",
  debate_maturity: "Mid-Debate",
  papers_published_same_period: 8,
  drift_velocity_at_publication: 0.15
};

const MOCK_PAPER_DATA = {
  title: "Long-term Antibiotic Therapy in Chronic Lyme Disease: A Relational Study",
  year: 2024,
  abstract: "The management of Post-Treatment Lyme Disease Syndrome (PTLDS) and Chronic Lyme Disease (CLD) remains one of the most controversial topics in modern infectious disease. This study explores the efficacy of extended antibiotic regimens compared to standard care, utilizing a relational analysis framework to position these findings within the broader literature. We hypothesize that while standard protocols clear acute infection, persistent symptoms may require longitudinal intervention.",
  sections: {
    introduction: "Lyme disease, caused by the spirochete Borrelia burgdorferi, is the most common vector-borne illness in the Northern Hemisphere. While most patients are successfully treated with a 2-4 week course of antibiotics, a significant minority report persistent symptoms including fatigue, musculoskeletal pain, and cognitive impairment. This has led to the emergence of the CLD diagnosis, which stands in stark contrast to the medically defined PTLDS.",
    methods: "We conducted a double-blind, randomized controlled trial involving 150 participants meeting the ILADS criteria for Chronic Lyme Disease. Participants were randomized to receive either 12 weeks of intravenous ceftriaxone followed by oral amoxicillin, or a matching placebo protocol. Primary endpoints were measured using the SF-36 health survey and the Fatigue Severity Scale (FSS).",
    results: "Initial analysis showed a statistically significant improvement in the treatment group regarding cognitive clarity (p=0.042) and physical fatigue (p=0.038). However, no significant difference was observed in overall quality of life scores at the 6-month follow-up. Relational mapping indicates these results occupy a unique niche between foundational RCTs and emerging observational data.",
    discussion: "The findings suggest that 'one-size-fits-all' protocols may be insufficient for a subset of the Lyme patient population. The divergence between this study and larger meta-analyses can be attributed to patient selection criteria and the duration of therapy. The relational analysis highlights that this study acts as a contrarian voice in a field currently converging toward shorter treatment durations."
  }
};

const RPAPage = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [analysisResult, setAnalysisResult] = useState(null);
  const [paperData, setPaperData] = useState(null);
  const [paperTitle, setPaperTitle] = useState("");
  const [paperSummary, setPaperSummary] = useState("");

  const handleStartAnalysis = async () => {
    setLoading(true);
    setError("");
    
    // In a real app, we would call analyzeRelational(payload)
    // For now, we simulate the delay and use mock data
    setTimeout(() => {
      setAnalysisResult(MOCK_RPA_DATA);
      setPaperData(MOCK_PAPER_DATA);
      setLoading(false);
    }, 2000);
  };

  const handleFileUpload = async (file) => {
    if (!file) return;
    setLoading(true);
    setError("");
    
    try {
      // In a real app, we'd use uploadPaper(file)
      // For now, simulate
      setTimeout(() => {
        setPaperTitle(MOCK_PAPER_DATA.title);
        setPaperSummary(MOCK_PAPER_DATA.abstract);
        setLoading(false);
      }, 1500);
    } catch (err) {
      setError("File upload failed.");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg text-ink">
      <header className="sticky top-0 z-30 border-b border-border bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-[1400px] items-center justify-between">
          <div className="flex items-center gap-4">
            <a href="/" className="flex h-10 w-10 items-center justify-center rounded-xl bg-ink text-white transition hover:scale-110">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
            </a>
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
              onClick={() => { setAnalysisResult(null); setPaperData(null); }}
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
            onParse={handleStartAnalysis}
            onUpload={handleFileUpload}
          />
        ) : (
          <div className="grid grid-cols-1 gap-8 py-8 lg:grid-cols-2 lg:h-[calc(100vh-120px)]">
            {/* Left Panel: Paper Reader */}
            <div className="overflow-hidden">
              <PaperReader paper={paperData} />
            </div>

            {/* Right Panel: RPA Dashboard */}
            <div className="flex flex-col gap-6 overflow-y-auto pr-2 scrollbar-hide">
              <InsightPanel rpaResult={analysisResult} />

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <MetricCard 
                  title="Consensus Alignment (CAS)"
                  value={analysisResult.aggregate_cas}
                  progress={analysisResult.aggregate_cas * 100}
                  interpretation={analysisResult.cas_interpretation}
                  color={analysisResult.aggregate_cas > 0.6 ? "text-green" : analysisResult.aggregate_cas < 0.4 ? "text-red" : "text-ink"}
                />
                <MetricCard 
                  title="Field Controversy (FCI)"
                  value={analysisResult.fci_score}
                  progress={analysisResult.fci_score}
                  label={analysisResult.fci_label}
                  color={analysisResult.fci_score > 70 ? "text-red" : analysisResult.fci_score < 30 ? "text-green" : "text-ink"}
                />
                <MetricCard 
                  title="Methodological Standing"
                  value={analysisResult.mss_percentile}
                  unit="th"
                  progress={analysisResult.mss_percentile}
                  label={analysisResult.mss_label}
                  interpretation={analysisResult.methodological_underdog ? "Methodological Underdog" : "Solid Standing"}
                  color={analysisResult.mss_percentile > 70 ? "text-green" : analysisResult.mss_percentile < 30 ? "text-red" : "text-ink"}
                />
                <MetricCard 
                  title="Claim Novelty (CNS)"
                  value={analysisResult.aggregate_cns * 100}
                  unit="%"
                  progress={analysisResult.aggregate_cns * 100}
                  interpretation={analysisResult.cns_interpretation}
                  color="text-blue"
                />
              </div>

              {/* Temporal Field Position */}
              <div className="rounded-2xl border border-border bg-white p-6 shadow-sm">
                <div className="text-xs uppercase tracking-[0.18em] text-inkSec mb-4">Temporal Field Position (TFP)</div>
                <div className="flex items-center justify-between mb-6">
                  <div className="space-y-1">
                    <div className="text-sm font-bold text-ink">Debate Maturity</div>
                    <div className="text-lg font-bold text-ink">{analysisResult.debate_maturity}</div>
                  </div>
                  <div className="h-10 w-px bg-border"></div>
                  <div className="space-y-1 text-right">
                    <div className="text-sm font-bold text-ink">Trajectory</div>
                    <div className="text-lg font-bold text-blue">{analysisResult.field_trajectory_at_publication}</div>
                  </div>
                </div>
                
                {/* Visual Timeline */}
                <div className="relative mt-8 h-12 w-full">
                  <div className="absolute top-1/2 h-0.5 w-full -translate-y-1/2 bg-surfaceAlt"></div>
                  <div className="absolute left-0 top-1/2 h-2 w-2 -translate-y-1/2 rounded-full bg-border"></div>
                  <div className="absolute right-0 top-1/2 h-2 w-2 -translate-y-1/2 rounded-full bg-border"></div>
                  
                  {/* Paper Position Indicator */}
                  <div 
                    className="absolute top-1/2 -translate-y-1/2 flex flex-col items-center gap-2"
                    style={{ left: '65%' }}
                  >
                    <div className="h-4 w-4 rounded-full border-4 border-white bg-ink shadow-sm"></div>
                    <div className="text-[10px] font-bold uppercase text-ink whitespace-nowrap bg-white px-2 py-0.5 rounded shadow-sm border border-border">
                      {analysisResult.publication_year} (This Paper)
                    </div>
                  </div>
                </div>
                <div className="mt-4 flex justify-between text-[10px] font-bold uppercase tracking-widest text-inkSec">
                  <span>Foundational</span>
                  <span>Emerging</span>
                  <span>Current</span>
                </div>
              </div>

              <ClaimTable 
                claims={paperData.claims || [
                  { text: "Extended antibiotic treatment improves quality of life in CLD patients." },
                  { text: "Persistent Borrelia burgdorferi infection survives standard 30-day protocols." }
                ]}
                casData={analysisResult.per_claim_cas}
                cnsData={analysisResult.per_claim_cns}
              />
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
          <div className="mt-6 text-center">
            <div className="font-playfair text-xl font-bold text-ink">Processing Relational Data</div>
            <div className="mt-2 text-sm text-inkSec">Cross-referencing 528 research documents...</div>
          </div>
        </div>
      )}

      {error && (
        <div className="fixed bottom-8 right-8 z-50 rounded-2xl border border-red bg-redLight p-4 shadow-panel max-w-sm animate-bounce">
          <div className="flex gap-3">
            <svg className="h-5 w-5 text-red shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div className="text-sm font-medium text-red">{error}</div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RPAPage;
