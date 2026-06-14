import { useEffect, useState } from "react";
import { analyzeEnriched, analyzeUploadedFile, getControversyMap, getVisualizationData, parsePaper, uploadPaper, visualizeUploadedFile, healthCheck } from "./api";

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
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [bulkFiles, setBulkFiles] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
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

  const fetchUploads = async () => {
    try {
      const res = await fetch('/api/uploads');
      const payload = await res.json();
      setUploadedFiles(payload.files || []);
    } catch (err) {
      console.warn('Unable to fetch uploads', err);
    }
  };

  const handleBulkFileSelect = (e) => {
    setBulkFiles(e.target.files);
  };

  const handleBulkUpload = async () => {
    if (!bulkFiles || !bulkFiles.length) return;
    setLoading(true);
    setStatusMessage('Uploading files...');
    try {
      const form = new FormData();
      for (const f of bulkFiles) form.append('files', f);
      const resp = await fetch('/api/upload-multiple', { method: 'POST', body: form });
      const data = await resp.json();
      setStatusMessage('Upload complete.');
      setBulkFiles(null);
      fetchUploads();
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setLoading(false);
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
      setAnalysisResult(result);
      setParseResult(null);
      setActiveTab("analysis");
      updateFormFromResponse(result);
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

  const handleAnalyzeAll = async () => {
    if (!paperTitle.trim() || !paperSummary.trim()) {
      setError("Please provide a paper title and abstract before analysis.");
      return;
    }

    setLoading(true);
    setError("");
    setUploadStatus("");
    setStatusMessage("Analyzing paper...");

    try {
      const payload = buildPayload();
      
      // Parse
      setStatusMessage("Parsing paper...");
      const parseRes = await parsePaper(payload);
      setParseResult(parseRes);
      updateFormFromResponse(parseRes);
      
      // Analyze
      setStatusMessage("Running enriched analysis...");
      const analysisRes = await analyzeEnriched(payload);
      setAnalysisResult(analysisRes);
      updateFormFromResponse(analysisRes);
      
      // Visualize
      setStatusMessage("Generating visualization...");
      const vizRes = await getVisualizationData(payload);
      setVisualizationResult(vizRes);
      
      setActiveTab("analysis");
      setStatusMessage("Analysis complete.");
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
      setAnalysisResult(result);
      setParseResult(null);
      setVisualizationResult(null);
      setUploadStatus(`Uploaded and analyzed ${selectedFile.name}`);
      setActiveTab("analysis");
      updateFormFromResponse(result);
      setStatusMessage("File uploaded and analyzed successfully.");
      fetchUploads();
    } catch (err) {
      setError(err.message || String(err));
      setUploadStatus("");
      setStatusMessage("");
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzeUpload = async (id) => {
    setLoading(true);
    setError("");
    setStatusMessage("Analyzing uploaded file...");
    try {
      const result = await analyzeUploadedFile(id);
      setAnalysisResult(result);
      setParseResult(null);
      setVisualizationResult(null);
      setActiveTab("analysis");
      setStatusMessage("Stored upload analyzed successfully.");
      setLibraryOpen(false);
    } catch (err) {
      setError(err.message || String(err));
      setStatusMessage("");
    } finally {
      setLoading(false);
    }
  };

  const handleVisualizeUpload = async (id) => {
    setLoading(true);
    setError("");
    setStatusMessage("Generating visualization for the stored upload...");
    try {
      const result = await visualizeUploadedFile(id);
      setVisualizationResult(result);
      setActiveTab("visualization");
      setStatusMessage("Stored upload visualization loaded.");
      setLibraryOpen(false);
    } catch (err) {
      setError(err.message || String(err));
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
    const inputClass = "w-full rounded-2xl border-2 border-border bg-white px-4 py-3 text-sm text-ink outline-none transition focus:border-ink focus:shadow-sm focus:bg-white/95 hover:border-border/80";
    return (
      <label className="block">
        <div className="text-xs uppercase tracking-[0.18em] text-inkSec mb-2 font-semibold">{label}</div>
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
    if (!paperTitle && result.title) setPaperTitle(result.title);
    if (!paperSummary && result.abstract) setPaperSummary(result.abstract);
    if (!paperIntroduction && result.sections?.introduction) setPaperIntroduction(result.sections.introduction);
    if (!paperMethods && result.sections?.methods) setPaperMethods(result.sections.methods);
    if (!paperResults && result.sections?.results) setPaperResults(result.sections.results);
    if (!paperDiscussion && result.sections?.discussion) setPaperDiscussion(result.sections.discussion);
  };

  const normalizeAnalysisResult = (result) => {
    if (!result) return null;
    return {
      ...result,
      ...result.analysis,
      citation_role: result.citation_role ?? result.analysis?.citation_roles ?? result.citation_context?.citation_roles,
      semantic_shift_score:
        result.semantic_shift_score ?? 
        result.analysis?.semantic_shift_score ?? 
        result.methodological_assessment?.semantic_shift_score,
      methodological_quality:
        result.methodological_quality ?? result.analysis?.methodological_quality,
      controversy_cluster: result.controversy_cluster ?? result.analysis?.controversy_cluster,
      stance: result.stance ?? result.analysis?.stance,
      evidence_strength: result.evidence_strength ?? result.analysis?.evidence_strength,
      uncertainty: result.uncertainty ?? result.analysis?.uncertainty,
      weaknesses: result.weaknesses ?? result.analysis?.weaknesses,
      study_design: result.study_design ?? result.analysis?.study_design,
      sample_size: result.sample_size ?? result.analysis?.sample_size,
      method_assessment: result.methodological_assessment,
      citation_context: result.citation_context,
      graph_predictions: result.graph_predictions,
    };
  };

  const normalizedAnalysis = normalizeAnalysisResult(analysisResult);

  const summaryCards = (result) => {
    const normalized = normalizeAnalysisResult(result);
    return [
      { label: "Controversy", value: normalized?.controversy_cluster ?? "N/A", color: "text-ink" },
      { label: "Evidence", value: normalized?.evidence_strength?.toFixed(2) ?? "N/A", color: "text-green" },
      { label: "Uncertainty", value: normalized?.uncertainty?.toFixed(2) ?? "N/A", color: "text-red" },
    ];
  };

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
            <g key={node.id} onMouseEnter={() => setHoveredNode(node)} onMouseLeave={() => setHoveredNode(null)}>
              <circle cx={node.x} cy={node.y} r={20} fill={node.type === 'claim' ? '#0ea5a4' : '#1a1814'} opacity="0.95" />
              <text x={node.x} y={node.y} textAnchor="middle" dy="0.35em" className="text-xs font-semibold" fill="#fff">
                {node.type === "paper" ? "P" : node.type === 'claim' ? 'C' : 'N'}
              </text>
            </g>
          ))}
          {positioned.map((node, index) => (
            <text key={`label-${index}`} x={node.x} y={node.y + 34} textAnchor="middle" className="text-[10px] text-inkSec" fill="#1a1814">
              {node.label?.length > 20 ? node.label.slice(0, 20) + '...' : node.label}
            </text>
          ))}
        </svg>
        {hoveredNode ? (
          <div className="absolute right-3 top-3 w-64 rounded-lg bg-white p-3 shadow-md">
            <div className="font-semibold mb-2">{hoveredNode.label}</div>
            <div className="text-sm text-inkSec">Type: {hoveredNode.type}</div>
            {hoveredNode.papers && hoveredNode.papers.length ? (
              <div className="mt-2 text-sm">
                {hoveredNode.papers.slice(0,5).map((p, i) => (
                  <div key={i} className="mb-1">{p.title?.split(' ').slice(0,5).join(' ')}..., {p.author_last || ''}, {p.date || ''}</div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
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
      <header className="sticky top-0 z-30 bg-gradient-to-r from-ink to-ink/95 text-white px-6 py-6 shadow-lg">
        <div className="mx-auto flex max-w-[1080px] items-center justify-between">
          <div>
            <div className="font-playfair text-3xl font-bold tracking-tight">LingHacks</div>
            <div className="text-sm text-white/80 mt-1">Advanced Scientific Paper Analysis</div>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={() => { setLibraryOpen(true); fetchUploads(); }} className="rounded-full border-2 border-white/20 bg-white/10 px-4 py-2 text-sm font-semibold text-white hover:bg-white/20">Library</button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1080px] px-6 pb-16">
        <section className="mt-10 rounded-3xl border-2 border-border bg-surface p-8 shadow-lg">
          <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h1 className="text-4xl font-bold tracking-tight">Paper Analyzer</h1>
              <p className="text-sm text-inkSec mt-2">Upload or enter your paper details to analyze claims, evidence, and scientific controversy.</p>
            </div>
            <div>
              <button onClick={handleAnalyzeAll} disabled={loading} className="rounded-2xl bg-gradient-to-br from-green to-emerald-600 px-8 py-3 text-sm font-bold text-white hover:from-green/90 hover:to-emerald-600/90 disabled:opacity-50 transition-all shadow-md hover:shadow-lg transform hover:scale-105 active:scale-95">
                {loading ? "Analyzing..." : "Analyze Paper"}
              </button>
            </div>
          </div>

          <div className="space-y-6">
            <div className="grid gap-4 lg:grid-cols-2">
              {renderTextInput("Paper title", paperTitle, setPaperTitle, "Enter paper title", 1)}
              {renderTextInput("Abstract", paperSummary, setPaperSummary, "Paste the paper abstract", 4)}
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              {renderTextInput("Introduction", paperIntroduction, setPaperIntroduction, "Paste the introduction or summary", 4)}
              {renderTextInput("Methods", paperMethods, setPaperMethods, "Paste the methods section", 4)}
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              {renderTextInput("Results", paperResults, setPaperResults, "Paste the results summary", 4)}
              {renderTextInput("Discussion", paperDiscussion, setPaperDiscussion, "Paste the discussion details", 4)}
            </div>
          </div>

          <div className="mt-6 rounded-2xl border-2 border-border bg-surfaceAlt p-4">
            <label className="block text-xs uppercase tracking-[0.18em] text-inkSec font-semibold">Citations</label>
            <input
              value={citations}
              onChange={(e) => setCitations(e.target.value)}
              className="mt-3 w-full rounded-2xl border-2 border-border bg-white px-4 py-3 text-sm text-ink outline-none transition focus:border-ink focus:shadow-sm"
              placeholder="Add citations separated by commas"
            />
          </div>

          <div className="mt-6 rounded-2xl border-2 border-border bg-surfaceAlt p-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm font-bold">Upload a Paper File</div>
                <div className="text-sm text-inkSec mt-1">Supports PDF, HTML, or XML source documents</div>
              </div>
              <div className="flex flex-wrap gap-3">
                <label className="rounded-2xl border-2 border-border bg-white px-5 py-3 text-sm font-semibold text-ink cursor-pointer hover:bg-white/50 transition">
                  <input type="file" className="hidden" accept=".pdf,.xml,.html,.htm" onChange={handleFileSelect} />
                  {selectedFile ? "Change file" : "Choose file"}
                </label>
                <button onClick={handleUpload} disabled={loading || !selectedFile} className="rounded-2xl bg-gradient-to-br from-ink to-ink/80 px-6 py-3 text-sm font-bold text-white disabled:opacity-50 transition-all shadow-md hover:shadow-lg transform hover:scale-105 active:scale-95">
                  Upload & Analyze
                </button>
              </div>
            </div>
            {uploadStatus ? <div className="mt-4 text-sm text-inkSec font-medium">{uploadStatus}</div> : null}
          </div>

          {statusMessage ? <div className="mt-4 rounded-2xl bg-blueLight border-2 border-blue px-5 py-4 text-sm text-blue font-medium shadow-sm">{statusMessage}</div> : null}
          {error ? <div className="mt-4 rounded-2xl bg-redLight border-2 border-red px-5 py-4 text-sm text-red font-medium shadow-sm">{error}</div> : null}
          {loading ? <div className="mt-4 rounded-2xl bg-surfaceAlt px-5 py-4 text-sm text-inkSec font-medium">⏳ Processing request…</div> : null}
        </section>

        <section className="mt-10 rounded-3xl border-2 border-border bg-surface p-8 shadow-lg">
          <div className="mb-8 flex flex-wrap gap-3 border-b-2 border-border pb-6">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`rounded-full border-2 px-5 py-2 text-sm font-bold transition transform ${activeTab === tab.id ? "border-ink bg-gradient-to-r from-ink to-ink/90 text-white shadow-md" : "border-border bg-surfaceAlt text-inkSec hover:bg-surfaceAlt/80"}`}
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
                <div className="rounded-2xl border-2 border-border bg-white p-6 shadow-md hover:shadow-lg transition">
                  <div className="font-bold mb-4 text-lg">Assessment</div>
                  <div className="space-y-4 text-sm text-inkSec">
                    <div className="flex justify-between items-center"><span className="font-semibold">Method Quality:</span> <span className="text-ink font-bold">{normalizeAnalysisResult(analysisResult)?.methodological_quality?.toFixed(2) ?? "N/A"}</span></div>
                    <div className="flex justify-between items-center"><span className="font-semibold">Citation Roles:</span> <span className="text-ink font-bold">{normalizeAnalysisResult(analysisResult)?.citation_role?.join(", ") || "N/A"}</span></div>
                    <div className="flex justify-between items-center"><span className="font-semibold">Study Design:</span> <span className="text-ink font-bold">{normalizeAnalysisResult(analysisResult)?.study_design || "N/A"}</span></div>
                    <div className="flex justify-between items-center"><span className="font-semibold">Sample Size:</span> <span className="text-ink font-bold">{normalizeAnalysisResult(analysisResult)?.sample_size || "N/A"}</span></div>
                    <div className="flex justify-between items-center"><span className="font-semibold">Weaknesses:</span> <span className="text-ink font-bold">{normalizeAnalysisResult(analysisResult)?.weaknesses?.length ? normalizeAnalysisResult(analysisResult).weaknesses.slice(0, 2).join("; ") : "None identified"}</span></div>
                  </div>
                </div>
                <div className="rounded-2xl border-2 border-border bg-white p-6 shadow-md hover:shadow-lg transition">
                  <div className="font-bold mb-4 text-lg">Stance Breakdown</div>
                  <div className="space-y-3 text-sm">
                    {normalizeAnalysisResult(analysisResult)?.stance ? (
                      Object.entries(normalizeAnalysisResult(analysisResult).stance).map(([label, score]) => (
                        <div key={label} className="flex items-center justify-between p-3 bg-surfaceAlt rounded-lg">
                          <span className="font-semibold text-inkSec">{label}</span>
                          <span className="font-bold text-ink text-lg">{score.toFixed(2)}</span>
                        </div>
                      ))
                    ) : (
                      <div className="text-inkSec">No stance data available.</div>
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
      {libraryOpen ? (
        <div className="fixed inset-0 z-50 flex">
          <div className="flex-1" onClick={() => setLibraryOpen(false)} />
          <div className="w-[420px] bg-white shadow-xl p-6 overflow-auto">
            <div className="flex items-center justify-between mb-4">
              <div className="font-bold">Library</div>
              <button onClick={() => setLibraryOpen(false)} className="text-sm text-inkSec">Close</button>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-semibold mb-2">Bulk upload files</label>
              <input type="file" multiple onChange={handleBulkFileSelect} className="mb-2" />
              <div className="flex gap-2">
                <button onClick={handleBulkUpload} disabled={loading || !bulkFiles} className="rounded-2xl bg-green px-4 py-2 text-sm font-semibold text-white">Upload</button>
                <button onClick={fetchUploads} className="rounded-2xl border px-4 py-2 text-sm">Refresh</button>
              </div>
            </div>
            <div>
              <div className="text-sm text-inkSec mb-2">Uploaded files</div>
              <div className="space-y-2">
                {uploadedFiles.length ? uploadedFiles.map((f) => (
                  <div key={f.id} className="flex items-center justify-between p-3 rounded-lg bg-surfaceAlt">
                    <div className="text-sm">
                      <div className="font-medium">{f.filename}</div>
                      <div className="text-xs text-inkSec">Uploaded: {new Date(f.uploaded_at).toLocaleString()}</div>
                      {f.title ? <div className="text-xs text-inkSec">Title: {f.title}</div> : null}
                      {f.pub_date ? <div className="text-xs text-inkSec">Year: {f.pub_date}</div> : null}
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => handleAnalyzeUpload(f.id)} disabled={loading} className="rounded-2xl bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-500">Analyze</button>
                      <button onClick={() => handleVisualizeUpload(f.id)} disabled={loading} className="rounded-2xl bg-slate-200 px-3 py-2 text-xs font-semibold text-ink hover:bg-slate-300">Visualize</button>
                      <a href={`/api/uploads/${f.id}/download`} className="text-sm text-ink underline">Download</a>
                    </div>
                  </div>
                )) : <div className="text-sm text-inkSec">No files uploaded yet.</div>}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default App;
