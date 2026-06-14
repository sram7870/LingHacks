import React from 'react';

const MetricCard = ({ title, value, interpretation, label, unit = "", progress = null, color = "text-ink" }) => {
  return (
    <div className="rounded-2xl border border-border bg-white p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="text-xs uppercase tracking-[0.18em] text-inkSec mb-3">{title}</div>
      <div className="flex items-baseline gap-1">
        <div className={`text-3xl font-bold ${color}`}>
          {typeof value === 'number' ? value.toFixed(2) : value}
          <span className="text-sm font-normal text-inkSec ml-1">{unit}</span>
        </div>
        {label && (
          <div className="ml-auto rounded-full bg-surfaceAlt px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-inkSec">
            {label}
          </div>
        )}
      </div>
      
      {progress !== null && (
        <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-surfaceAlt">
          <div 
            className={`h-full transition-all duration-1000 ${color.replace('text-', 'bg-')}`} 
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
      
      {interpretation && (
        <div className="mt-3 text-sm text-inkSec italic">
          {interpretation}
        </div>
      )}
    </div>
  );
};

export default MetricCard;
