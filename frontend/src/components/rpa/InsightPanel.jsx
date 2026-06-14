import React from 'react';

const InsightPanel = ({ rpaResult }) => {
  if (!rpaResult) return null;

  const getInsights = () => {
    const insights = [];
    
    // CAS Insight
    if (rpaResult.aggregate_cas > 0.7) {
      insights.push("This paper aligns strongly with current consensus.");
    } else if (rpaResult.aggregate_cas < 0.3) {
      insights.push("This paper significantly departs from the established scientific consensus.");
    }

    // FCI Insight
    if (rpaResult.fci_score > 70) {
      insights.push("The field remains highly contested and polarized.");
    } else if (rpaResult.fci_score < 30) {
      insights.push("The topic shows high levels of convergence and agreement.");
    }

    // MSS Insight
    if (rpaResult.methodological_underdog) {
      insights.push("This paper is methodologically weaker than most contradicting studies.");
    } else if (rpaResult.mss_percentile > 80) {
      insights.push("This paper ranks in the top tier of methodological rigor for this topic.");
    }

    // CNS Insight
    if (rpaResult.aggregate_cns > 0.8) {
      insights.push("The claims presented here represent highly novel contributions to the field.");
    }

    return insights;
  };

  const insights = getInsights();

  return (
    <div className="rounded-2xl border border-blue bg-blueLight p-6 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <svg className="h-5 w-5 text-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <h3 className="text-sm font-bold uppercase tracking-wider text-blue">Research Insights</h3>
      </div>
      <ul className="space-y-3">
        {insights.map((insight, idx) => (
          <li key={idx} className="flex gap-3 text-sm text-ink font-medium">
            <span className="text-blue mt-1">•</span>
            {insight}
          </li>
        ))}
        {insights.length === 0 && (
          <li className="text-sm text-inkSec italic">No significant outliers detected in the relational analysis.</li>
        )}
      </ul>
    </div>
  );
};

export default InsightPanel;
