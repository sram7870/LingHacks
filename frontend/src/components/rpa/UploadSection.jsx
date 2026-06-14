import React from 'react';

const UploadSection = ({ onUpload, onParse, loading, paperTitle, setPaperTitle, paperSummary, setPaperSummary }) => {
  return (
    <div className="mx-auto max-w-4xl space-y-8 py-12">
      <div className="text-center">
        <h2 className="font-playfair text-4xl font-bold text-ink">Relational Paper Analysis</h2>
        <p className="mt-4 text-lg text-inkSec">
          Position your research within the broader scientific landscape using cross-literature metrics.
        </p>
      </div>

      <div className="rounded-[32px] border border-border bg-white p-10 shadow-panel">
        <div className="space-y-6">
          <div className="grid gap-6">
            <div className="space-y-2">
              <label className="text-xs font-bold uppercase tracking-[0.2em] text-inkSec">Paper Title</label>
              <input
                type="text"
                value={paperTitle}
                onChange={(e) => setPaperTitle(e.target.value)}
                placeholder="Enter the full title of the research paper..."
                className="w-full rounded-2xl border border-border bg-surfaceAlt px-6 py-4 text-lg font-medium text-ink outline-none transition focus:border-ink focus:bg-white"
              />
            </div>
            
            <div className="space-y-2">
              <label className="text-xs font-bold uppercase tracking-[0.2em] text-inkSec">Abstract</label>
              <textarea
                value={paperSummary}
                onChange={(e) => setPaperSummary(e.target.value)}
                rows={6}
                placeholder="Paste the paper abstract here for claim extraction and relational mapping..."
                className="w-full rounded-2xl border border-border bg-surfaceAlt px-6 py-4 text-base text-ink outline-none transition focus:border-ink focus:bg-white"
              />
            </div>
          </div>

          <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
            <div className="flex-1">
              <div className="flex items-center gap-4 rounded-2xl border border-dashed border-border p-4 transition hover:border-ink">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-surfaceAlt text-inkSec">
                  <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                </div>
                <div className="flex-1">
                  <div className="text-sm font-bold text-ink">Upload Document</div>
                  <div className="text-xs text-inkSec text-nowrap">PDF, XML, HTML supported</div>
                </div>
                <label className="cursor-pointer rounded-xl bg-ink px-4 py-2 text-xs font-bold text-white transition hover:bg-opacity-90">
                  Browse
                  <input type="file" className="hidden" accept=".pdf,.xml,.html,.htm" onChange={(e) => onUpload(e.target.files[0])} />
                </label>
              </div>
            </div>

            <div className="h-px bg-border sm:h-12 sm:w-px"></div>

            <button
              onClick={onParse}
              disabled={loading || !paperTitle || !paperSummary}
              className="group relative flex h-14 items-center justify-center gap-3 overflow-hidden rounded-2xl bg-ink px-8 py-4 font-bold text-white transition-all hover:scale-[1.02] active:scale-[0.98] disabled:scale-100 disabled:opacity-50"
            >
              <span className="relative z-10">Start Relational Analysis</span>
              <svg className="relative z-10 h-5 w-5 transition-transform group-hover:translate-x-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
              <div className="absolute inset-0 z-0 bg-gradient-to-r from-emerald-600 to-teal-600 opacity-0 transition-opacity group-hover:opacity-100"></div>
            </button>
          </div>
        </div>
      </div>
      
      <div className="grid gap-6 sm:grid-cols-3">
        {[
          { icon: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z", title: "Consensus Mapping", desc: "Alignment with established field findings." },
          { icon: "M13 7h8m0 0v8m0-8l-8 8-4-4-6 6", title: "Trend Trajectory", desc: "Debate maturity and future direction." },
          { icon: "M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z", title: "Methodological Peer Review", desc: "Quality relative to contradicting studies." }
        ].map((feat, i) => (
          <div key={i} className="flex gap-4 rounded-2xl bg-surface p-5 border border-border">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white text-ink shadow-sm">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={feat.icon} />
              </svg>
            </div>
            <div>
              <div className="text-sm font-bold text-ink">{feat.title}</div>
              <div className="mt-1 text-xs text-inkSec leading-relaxed">{feat.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default UploadSection;
