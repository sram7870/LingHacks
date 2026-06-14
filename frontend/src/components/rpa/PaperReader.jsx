import React from 'react';

const PaperReader = ({ paper }) => {
  if (!paper) return null;

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-[24px] border border-border bg-white shadow-panel">
      {/* Sticky Header */}
      <div className="sticky top-0 z-10 border-b border-border bg-surface p-8">
        <div className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-inkSec">
          Research Document • {paper.year || 2026}
        </div>
        <h1 className="font-playfair text-3xl font-bold leading-tight text-ink">
          {paper.title || "Untitled Research Paper"}
        </h1>
        <div className="mt-4 flex flex-wrap gap-4 text-sm text-inkSec">
          <div className="flex items-center gap-1">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <span>{paper.authors?.join(", ") || "Authors unknown"}</span>
          </div>
          <div className="flex items-center gap-1">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span>{paper.year || 2026}</span>
          </div>
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-8 prose prose-slate max-w-none scrollbar-hide">
        <div className="mb-10">
          <h2 className="text-lg font-bold uppercase tracking-wider text-ink mb-3">Abstract</h2>
          <p className="text-base leading-relaxed text-inkSec italic">
            {paper.abstract || "No abstract provided."}
          </p>
        </div>

        {paper.sections && Object.entries(paper.sections).map(([name, content]) => (
          <div key={name} className="mb-8">
            <h2 className="text-lg font-bold uppercase tracking-wider text-ink mb-3 capitalize">{name}</h2>
            <div className="text-base leading-relaxed text-ink space-y-4">
              {content ? (
                content.split('\n\n').map((para, idx) => (
                  <p key={idx}>{para}</p>
                ))
              ) : (
                <p className="text-inkSec italic">Section content not available.</p>
              )}
            </div>
          </div>
        ))}
        
        {!paper.sections && (
          <div className="space-y-8">
            <div className="animate-pulse space-y-3">
              <div className="h-4 w-3/4 bg-surfaceAlt rounded"></div>
              <div className="h-4 w-full bg-surfaceAlt rounded"></div>
              <div className="h-4 w-5/6 bg-surfaceAlt rounded"></div>
            </div>
            <div className="animate-pulse space-y-3">
              <div className="h-4 w-full bg-surfaceAlt rounded"></div>
              <div className="h-4 w-2/3 bg-surfaceAlt rounded"></div>
              <div className="h-4 w-4/5 bg-surfaceAlt rounded"></div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PaperReader;
