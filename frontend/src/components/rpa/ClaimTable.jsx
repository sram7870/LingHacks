import React from 'react';

const ClaimTable = ({ claims, casData, cnsData }) => {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-white shadow-sm">
      <div className="bg-surfaceAlt px-6 py-4 border-b border-border">
        <h3 className="text-sm font-bold uppercase tracking-wider text-ink">Detailed Claim Analysis</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border bg-surface text-xs uppercase tracking-wider text-inkSec">
              <th className="px-6 py-4 font-semibold">Claim Text</th>
              <th className="px-6 py-4 font-semibold">CAS</th>
              <th className="px-6 py-4 font-semibold">CNS</th>
              <th className="px-6 py-4 font-semibold text-center">Support</th>
              <th className="px-6 py-4 font-semibold text-center">Contradict</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {claims.map((claim, idx) => {
              const cas = casData?.[idx] || {};
              const cns = cnsData?.[idx] || {};
              
              return (
                <tr key={idx} className="hover:bg-surfaceAlt transition-colors">
                  <td className="px-6 py-4 font-medium text-ink max-w-md">{claim.text}</td>
                  <td className="px-6 py-4">
                    <span className={`font-mono font-bold ${cas.cas_score > 0.7 ? 'text-green' : cas.cas_score < 0.3 ? 'text-red' : 'text-ink'}`}>
                      {cas.cas_score?.toFixed(2) ?? '—'}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono">{cns.cns_score?.toFixed(2) ?? '—'}</td>
                  <td className="px-6 py-4 text-center">
                    <span className="rounded-full bg-emerald-100 px-2 py-1 text-xs font-bold text-emerald-700">
                      {cas.supporting_count ?? 0}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <span className="rounded-full bg-red-100 px-2 py-1 text-xs font-bold text-red-700">
                      {cas.contradicting_count ?? 0}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ClaimTable;
