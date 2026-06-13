import { useEffect, useState } from "react";
import { analyzeEnriched, getControversyMap, getVisualizationData, parsePaper, uploadPaper, healthCheck } from "./api";

const TABS = [
  { id: "parsed", label: "Parsed Paper" },
  { id: "analysis", label: "Enriched Analysis" },
  { id: "visualization", label: "Visualization" },
  { id: "controversy", label: "Controversy Map" },
];

function App() {
  const [paperTitle, setPaperTitle] = useState("");
  const [paperSummary, setPaperSummary] = useState("");
  const [paperIntroduction, setPaperIntroduction] = useState("");
  const [paperMethods, setPaperMethods] = useState("");
  const [paperResults, setPaperResults] = useState("");
  const [paperDiscussion, setPaperDiscussion] = useState("");
  const [citations, setCitations] = useState("");

  const [parseResult, setParseResult] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [visualizationResult, setVisualizationResult] = useState(null);
  const [controversyMap, setControversyMap] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [activeTab, setActiveTab] = useState("parsed");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [backendHealthy, setBackendHealthy] = useState(false);
  const [backendStatus, setBackendStatus] = useState("Checking backend...");

  useEffect(() => {
    checkBackendHealth();
    refreshControversy();
  }, []);

  const checkBackendHealth = async () => {
    try {
      const health = await healthCheck();
      setBackendHealthy(health.status === "ok");
      setBackendStatus(health.status === "ok" ? "Backend healthy" : "Backend returned unexpected status");
    } catch (err) {
      setBackendHealthy(false);
      setBackendStatus("Backend unreachable");
    }
  };

  const buildPayload = () => ({
    title: paperTitle,
    abstract: paperSummary,
    introduction: paperIntroduction,
    methods: paperMethods,
    results: paperResults,
    discussion: paperDiscussion,
    citations: citations.split(",").map((item) => item.trim()).filter(Boolean),
    metadata: {},
  });

  const refreshControversy = async () => {
    setStatusMessage("Refreshing controversy map...");
    try {
      const map = await getControversyMap();
      setControversyMap(map);
      setStatusMessage("Controversy map updated.");
    } catch (err) {
      setError(err.message || String(err));
      setStatusMessage("");
    }
  };

  const handleParse = async () => {
    if (!paperTitle.trim() || !paperSummary.trim()) {
      setError("Please provide a paper title and abstract before parsing.");
      return;
    }

    setLoading(true);
    setError("");
    setUploadStatus("");
    setStatusMessage("Sending paper for parsing...");

    try {
      const payload = buildPayload();
      const result = await parsePaper(payload);
      setParseResult(result);
      setAnalysisResult(null);
      setVisualizationResult(null);
      setActiveTab("parsed");
      updateFormFromResponse(result);
      setStatusMessage("Paper parsed successfully.");
    } catch (err) {
      setError(err.message || String(err));
      setStatusMessage("");
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async () => {
    if (!paperTitle.trim() || !paperSummary.trim()) {
      setError("Please provide a paper title and abstract before analysis.");
      return;
    }

    setLoading(true);
    setError("");
    setUploadStatus("");
    setStatusMessage("Running enriched analysis...");

    try {
      const payload = buildPayload();
      const result = await analyzeEnriched(payload);

      // Normalize enriched result into expected shape for UI
      const normalized = {
        title: result?.paper?.title ?? result?.title ?? "",
        abstract: result?.paper?.abstract ?? result?.abstract ?? "",
        sections: result?.sections ?? result?.paper?.sections ?? { introduction: "", methods: "", results: "", discussion: "" },
        claims: result?.claims ?? [],
        stance: result?.analysis?.stance ?? result?.stance ?? {},
        evidence_strength: result?.analysis?.evidence_strength ?? result?.evidence_strength ?? 0,
        methodological_quality: result?.analysis?.methodological_quality ?? result?.methodological_quality ?? 0,
        controversy_cluster: result?.graph_predictions?.controversy_cluster ?? result?.controversy_cluster ?? null,
        citation_role: result?.citation_context?.citation_roles ?? result?.citation_role ?? [],
        semantic_shift_score: result?.semantic_analysis?.drift ?? result?.semantic_shift_score ?? 0,
        uncertainty: result?.analysis?.uncertainty ?? result?.uncertainty ?? 0,
        _raw: result,
      };

      setAnalysisResult(normalized);
      setParseResult(null);
      setActiveTab("analysis");
      updateFormFromResponse(normalized);
      setStatusMessage("Enriched analysis complete.");
    } catch (err) {
      setError(err.message || String(err));
      setStatusMessage("");
    } finally {
      setLoading(false);
    }
  };

  const handleVisualize = async () => {
    if (!paperTitle.trim() || !paperSummary.trim()) {
      setError("Please provide a paper title and abstract before visualization.");
      return;
    }

    setLoading(true);
    setError("");
    setStatusMessage("Requesting visualization data...");

    try {
      const payload = buildPayload();
      const result = await getVisualizationData(payload);
      setVisualizationResult(result);
      setActiveTab("visualization");
      setStatusMessage("Visualization data loaded.");
    } catch (err) {
      setError(err.message || String(err));
      setStatusMessage("");
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (event) => {
    const file = event.target.files?.[0] || null;
    setSelectedFile(file);
    setUploadStatus(file ? `Selected ${file.name}` : "");
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setUploadStatus("Choose a supported file first.");
      return;
    }

    setLoading(true);
    setError("");
    setUploadStatus("Uploading file...");
    setStatusMessage("Uploading paper and requesting analysis...");

    try {
      const result = await uploadPaper(selectedFile);
      // upload returns a parse-like response; show parsed view
      setParseResult(result);
      setAnalysisResult(null);
      setVisualizationResult(null);
      setUploadStatus(`Uploaded and analyzed ${selectedFile.name}`);
      setActiveTab("parsed");
      updateFormFromResponse(result);
      setStatusMessage("File uploaded and analyzed successfully.");
    } catch (err) {
      setError(err.message || String(err));
      setUploadStatus("");
      setStatusMessage("");
    } finally {
      setLoading(false);
    }
  };

  const renderSection = (title, value) => (
    <div className="rounded-2xl bg-surfaceAlt p-4">
      <div className="text-xs uppercase tracking-[0.18em] text-inkSec">{title}</div>
      <div className="mt-2 text-sm text-ink">{value || "Not provided."}</div>
    </div>
  );

  const renderTextInput = (label, value, setter, placeholder, rows = 3) => {
    const inputClass = "w-full rounded-2xl border border-border bg-white px-4 py-3 text-sm text-ink outline-none transition focus:border-ink";
    return (
      <label className="block">
        <div className="text-xs uppercase tracking-[0.18em] text-inkSec mb-2">{label}</div>
        {rows === 1 ? (
          <input
            value={value}
            onChange={(e) => setter(e.target.value)}
            className={inputClass}
            placeholder={placeholder}
          />
        ) : (
          <textarea
            value={value}
            onChange={(e) => setter(e.target.value)}
            rows={rows}
            className={inputClass}
            placeholder={placeholder}
          />
        )}
      </label>
    );
  };

  const updateFormFromResponse = (result) => {
    if (!result) return;
    // accept both parse responses and enriched responses (which nest paper/analysis)
    const paper = result.paper ?? result;
    const sections = paper.sections ?? result.sections ?? { introduction: "", methods: "", results: "", discussion: "" };

    setPaperTitle(paper.title ?? "");
    setPaperSummary(paper.abstract ?? "");
    setPaperIntroduction(sections.introduction ?? "");
    setPaperMethods(sections.methods ?? "");
    setPaperResults(sections.results ?? "");
    setPaperDiscussion(sections.discussion ?? "");
  };

  const summaryCards = (result) => [
    { label: "Controversy", value: result?.controversy_cluster ?? "N/A", color: "text-ink" },
    { label: "Evidence", value: result?.evidence_strength?.toFixed(2) ?? "N/A", color: "text-green" },
    { label: "Uncertainty", value: result?.uncertainty?.toFixed(2) ?? "N/A", color: "text-red" },
  ];

  const renderKeyValue = (label, value) => (
    <div className="grid grid-cols-[1fr_auto] gap-4 rounded-2xl bg-surfaceAlt p-4 text-sm text-inkSec">
      <span className="font-medium text-ink">{label}</span>
      <span className="text-right font-semibold text-ink">{value ?? "N/A"}</span>
    </div>
  );

  const renderVisualizationSummary = (viz) => (
    <div className="space-y-4">
      {renderKeyValue("Total nodes", viz?.stats?.total_nodes ?? "0")}
      {renderKeyValue("Total edges", viz?.stats?.total_edges ?? "0")}
      {renderKeyValue("Network density", viz?.stats?.network_density ?? "0.0")}
      <div className="rounded-2xl border border-border bg-white p-5">
        <div className="font-semibold mb-3">Node breakdown</div>
        <div className="grid gap-3">
          {(viz?.nodes ?? []).slice(0, 6).map((node) => (
            <div key={node.id} className="rounded-2xl bg-surfaceAlt p-3">
              <div className="font-medium text-ink">{node.label}</div>
              <div className="mt-1 text-xs text-inkSec">Type: {node.type}, value: {node.value}</div>
            </div>
          ))}
          {!viz?.nodes?.length ? <div className="text-sm text-inkSec">No nodes available.</div> : null}
        </div>
      </div>
      <div className="rounded-2xl border border-border bg-white p-5">
        <div className="font-semibold mb-3">Edges</div>
        <div className="space-y-2 text-sm text-inkSec">
          {(viz?.edges ?? []).slice(0, 8).map((edge, index) => (
            <div key={index} className="rounded-2xl bg-surfaceAlt p-3">
              <div className="flex items-center justify-between">
                <span>{edge.source} → {edge.target}</span>
                <span className="font-semibold">{edge.weight?.toFixed?.(2) ?? edge.weight}</span>
              </div>
            </div>
          ))}
          {!viz?.edges?.length ? <div>No edges available.</div> : null}
        </div>
      </div>
    </div>
  );

  const renderGraphSvg = (viz) => {
    const nodes = viz?.nodes ?? [];
    const edges = viz?.edges ?? [];
    if (!nodes.length) {
      return <div className="text-sm text-inkSec">No graph visualization available.</div>;
    }

    const width = 560;
    const height = 260;
    const radius = 90;
    const centerX = width / 2;
    const centerY = height / 2;
    const angleStep = (2 * Math.PI) / nodes.length;

    const positioned = nodes.map((node, index) => {
      const angle = index * angleStep;
      return {
        ...node,
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * radius,
      };
    });

    const nodeIndexById = Object.fromEntries(positioned.map((node, index) => [node.id, index]));

    return (
      <div className="overflow-hidden rounded-2xl bg-surfaceAlt p-3">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-[280px]">
          {edges.map((edge, index) => {
            const from = positioned[nodeIndexById[edge.source]];
            const to = positioned[nodeIndexById[edge.target]];
            if (!from || !to) return null;
            return (
              <line
                key={index}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke="#94a3b8"
                strokeWidth={Math.min(4, Math.max(1, (edge.weight ?? 0.5) * 3))}
                opacity="0.8"
              />
            );
          })}
          {positioned.map((node) => (
            <g key={node.id}>
              <circle cx={node.x} cy={node.y} r={20} fill="#1a1814" opacity="0.9" />
              <text x={node.x} y={node.y} textAnchor="middle" dy="0.35em" className="text-xs font-semibold" fill="#fff">
                {node.type === "paper" ? "P" : "C"}
              </text>
            </g>
          ))}
          {positioned.map((node, index) => (
            <text key={`label-${index}`} x={node.x} y={node.y + 34} textAnchor="middle" className="text-[10px] text-inkSec" fill="#1a1814">
              {node.label}
            </text>
          ))}
        </svg>
      </div>
    );
  };

  const renderControversySummary = (map) => (
    <div className="space-y-4">
      {renderKeyValue("Total papers", map?.total_papers ?? "0")}
      {renderKeyValue("Unique clusters", map?.unique_clusters ?? "0")}
      <div className="rounded-2xl border border-border bg-white p-5">
        <div className="font-semibold mb-3">Controversy clusters</div>
        {map?.controversy_clusters ? (
          <div className="space-y-3 text-sm text-inkSec">
            {Object.entries(map.controversy_clusters).map(([cluster, titles]) => (
              <div key={cluster} className="rounded-2xl bg-surfaceAlt p-3">
                <div className="font-medium">Cluster {cluster}</div>
                <div className="mt-1">{titles.join(', ')}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-inkSec">No controversy clusters yet.</div>
        )}
      </div>
      <div className="rounded-2xl border border-border bg-white p-5">
        <div className="font-semibold mb-3">Timeline</div>
        {map?.timeline ? (
          <div className="space-y-3 text-sm text-inkSec">
            {Object.entries(map.timeline).map(([year, stats]) => (
              <div key={year} className="rounded-2xl bg-surfaceAlt p-3">
                <div className="flex items-center justify-between">
                  <span>{year}</span>
                  <span>{stats.papers} papers</span>
                </div>
                <div className="mt-1">Avg controversy: {stats.avg_controversy.toFixed(2)}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-inkSec">No timeline data available.</div>
        )}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-bg text-ink">
      <header className="sticky top-0 z-30 bg-ink text-white px-6 py-5 shadow-panel">
        <div className="mx-auto flex max-w-[1080px] flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="font-playfair text-2xl font-semibold">LingHacks</div>
            <div className="text-sm text-white/70">Frontend interface for backend scientific reasoning.</div>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm text-white/80">
            <span>Backend:</span>
            <span className={`rounded-full border px-3 py-2 ${backendHealthy ? "border-emerald-300 bg-emerald-500/20 text-emerald-100" : "border-red-300 bg-red-500/10 text-red-100"}`}>{backendStatus}</span>
            <span className="rounded-full border border-white/20 bg-white/10 px-3 py-2">/api/parse</span>
            <span className="rounded-full border border-white/20 bg-white/10 px-3 py-2">/api/analyze/enriched</span>
            <span className="rounded-full border border-white/20 bg-white/10 px-3 py-2">/api/visualize</span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1080px] px-6 pb-16">
        <section className="mt-8 rounded-[24px] border border-border bg-surface p-6 shadow-panel">
          <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-3xl font-semibold">Scientific Paper Analyzer</h1>
              <p className="text-sm text-inkSec">Enter paper metadata or upload a file to analyze claims, evidence, and controversy.</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <button onClick={handleParse} disabled={loading || !backendHealthy} className="rounded-2xl bg-green px-4 py-3 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">Parse Paper</button>
              <button onClick={handleAnalyze} disabled={loading || !backendHealthy} className="rounded-2xl border border-border bg-surfaceAlt px-4 py-3 text-sm font-semibold text-ink hover:border-ink disabled:opacity-60">Analyze Enriched</button>
              <button onClick={handleVisualize} disabled={loading || !backendHealthy} className="rounded-2xl border border-border bg-surfaceAlt px-4 py-3 text-sm font-semibold text-ink hover:border-ink disabled:opacity-60">Visualize</button>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            {renderTextInput("Paper title", paperTitle, setPaperTitle, "Enter paper title", 1)}
            {renderTextInput("Abstract", paperSummary, setPaperSummary, "Paste the paper abstract", 4)}
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {renderTextInput("Introduction", paperIntroduction, setPaperIntroduction, "Paste the introduction or summary", 4)}
            {renderTextInput("Methods", paperMethods, setPaperMethods, "Paste the methods section", 4)}
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {renderTextInput("Results", paperResults, setPaperResults, "Paste the results summary", 4)}
            {renderTextInput("Discussion", paperDiscussion, setPaperDiscussion, "Paste the discussion details", 4)}
          </div>

          <div className="mt-4 rounded-2xl border border-border bg-surfaceAlt p-4">
            <label className="block text-xs uppercase tracking-[0.18em] text-inkSec">Citations</label>
            <input
              value={citations}
              onChange={(e) => setCitations(e.target.value)}
              className="mt-2 w-full rounded-2xl border border-border bg-white px-4 py-3 text-sm text-ink"
              placeholder="Add citations separated by commas"
            />
          </div>

          <div className="mt-6 rounded-2xl border border-border bg-surfaceAlt p-4">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm font-semibold">Upload a paper file</div>
                <div className="text-sm text-inkSec">Use this for PDF, HTML, or XML source documents.</div>
              </div>
              <div className="flex flex-wrap gap-3">
                <label className="rounded-2xl border border-border bg-white px-4 py-3 text-sm font-semibold text-ink cursor-pointer">
                  <input type="file" className="hidden" accept=".pdf,.xml,.html,.htm" onChange={handleFileSelect} />
                  {selectedFile ? "Change file" : "Choose file"}
                </label>
                <button onClick={handleUpload} disabled={loading || !selectedFile} className="rounded-2xl bg-ink px-4 py-3 text-sm font-semibold text-white disabled:opacity-60">Upload & Analyze</button>
              </div>
            </div>
            {uploadStatus ? <div className="mt-3 text-sm text-inkSec">{uploadStatus}</div> : null}
          </div>

          {statusMessage ? <div className="mt-4 rounded-2xl bg-blueLight border border-blue px-4 py-3 text-sm text-blue">{statusMessage}</div> : null}
          {error ? <div className="mt-4 rounded-2xl bg-redLight border border-red px-4 py-3 text-sm text-red">{error}</div> : null}
          {loading ? <div className="mt-4 rounded-2xl bg-surfaceAlt px-4 py-3 text-sm text-inkSec">Processing request…</div> : null}
        </section>

        <section className="mt-6 rounded-[24px] border border-border bg-surface p-6 shadow-panel">
          <div className="mb-5 flex flex-wrap gap-3">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${activeTab === tab.id ? "border-ink bg-ink text-white" : "border-border bg-surfaceAlt text-inkSec"}`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === "parsed" && (
            <div className="space-y-5">
              <div className="grid gap-4 lg:grid-cols-3">
                {summaryCards(parseResult).map((card) => (
                  <div key={card.label} className="rounded-2xl bg-surfaceAlt p-5">
                    <div className="text-xs uppercase tracking-[0.18em] text-inkSec">{card.label}</div>
                    <div className={`mt-3 text-3xl font-semibold ${card.color}`}>{card.value}</div>
                  </div>
                ))}
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <div className="rounded-2xl border border-border bg-white p-5">
                  <div className="font-semibold mb-3">Sections</div>
                  <div className="space-y-3 text-sm text-inkSec">
                    <div><strong>Abstract:</strong> {parseResult?.abstract ?? "—"}</div>
                    <div><strong>Introduction:</strong> {parseResult?.sections?.introduction ?? "—"}</div>
                    <div><strong>Methods:</strong> {parseResult?.sections?.methods ?? "—"}</div>
                    <div><strong>Results:</strong> {parseResult?.sections?.results ?? "—"}</div>
                    <div><strong>Discussion:</strong> {parseResult?.sections?.discussion ?? "—"}</div>
                  </div>
                </div>
                <div className="rounded-2xl border border-border bg-white p-5">
                  <div className="font-semibold mb-3">Claims</div>
                  <div className="space-y-3">
                    {parseResult?.claims?.length ? (
                      parseResult.claims.map((claim, index) => (
                        <div key={index} className="rounded-2xl bg-surfaceAlt p-4">
                          <div className="text-sm text-ink">{claim.text}</div>
                          <div className="mt-2 flex items-center justify-between text-xs uppercase tracking-[0.16em] text-inkSec">
                            <span>{claim.polarity}</span>
                            <span>{(claim.confidence * 100).toFixed(0)}%</span>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="text-sm text-inkSec">No parsed claims available.</div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "analysis" && (
            <div className="space-y-5">
              <div className="grid gap-4 lg:grid-cols-3">
                {summaryCards(analysisResult).map((card) => (
                  <div key={card.label} className="rounded-2xl bg-surfaceAlt p-5">
                    <div className="text-xs uppercase tracking-[0.18em] text-inkSec">{card.label}</div>
                    <div className={`mt-3 text-3xl font-semibold ${card.color}`}>{card.value}</div>
                  </div>
                ))}
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <div className="rounded-2xl border border-border bg-white p-5">
                  <div className="font-semibold mb-3">Assessment</div>
                  <div className="space-y-3 text-sm text-inkSec">
                    <div><strong>Method Quality:</strong> {analysisResult?.methodological_quality?.toFixed(2) ?? "N/A"}</div>
                    <div><strong>Citation Roles:</strong> {analysisResult?.citation_role?.join(", ") || "N/A"}</div>
                    <div><strong>Semantic Shift:</strong> {analysisResult?.semantic_shift_score ?? "N/A"}</div>
                  </div>
                </div>
                <div className="rounded-2xl border border-border bg-white p-5">
                  <div className="font-semibold mb-3">Stance Breakdown</div>
                  <div className="space-y-3 text-sm text-inkSec">
                    {analysisResult?.stance ? (
                      Object.entries(analysisResult.stance).map(([label, score]) => (
                        <div key={label} className="flex items-center justify-between">
                          <span>{label}</span>
                          <span>{score.toFixed(2)}</span>
                        </div>
                      ))
                    ) : (
                      <div>No stance data available.</div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "visualization" && (
            <div className="space-y-5">
              <div className="rounded-2xl border border-border bg-white p-5">
                <div className="font-semibold mb-3">Visualization summary</div>
                <div className="text-sm text-inkSec">Backend returns nodes, edges, and visualization metadata optimized for graph display.</div>
              </div>
              {visualizationResult ? (
                <>
                  {renderVisualizationSummary(visualizationResult)}
                  <div className="rounded-2xl border border-border bg-white p-5">
                    <div className="font-semibold mb-3">Graph viewer</div>
                    {renderGraphSvg(visualizationResult)}
                  </div>
                </>
              ) : (
                <div className="rounded-2xl bg-surfaceAlt p-5 text-sm text-inkSec">Run visualization to see graph structure and node statistics.</div>
              )}
            </div>
          )}

          {activeTab === "controversy" && (
            <div className="space-y-5">
              <div className="flex items-center justify-between rounded-2xl border border-border bg-white p-5">
                <div>
                  <div className="font-semibold">Controversy Map</div>
                  <div className="text-sm text-inkSec">Temporal controversy clusters and timeline metadata from backend.</div>
                </div>
                <button onClick={refreshControversy} className="rounded-2xl border border-border px-4 py-2 text-sm">Refresh</button>
              </div>
              {controversyMap ? renderControversySummary(controversyMap) : (
                <div className="rounded-2xl bg-surfaceAlt p-5 text-sm text-inkSec">No controversy data yet. Refresh or run an analysis to populate the map.</div>
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
