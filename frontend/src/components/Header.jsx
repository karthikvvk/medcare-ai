import React from 'react';

const PAGE_META = {
  overview:   { title: 'Executive Overview',        subtitle: 'Real-time supply chain sensor network and replenishment optimization' },
  forecast:   { title: 'Demand Sensing',             subtitle: 'Forecasting model comparison horizon vs real-time warehouse actuals' },
  inventory:  { title: 'Inventory Status',           subtitle: 'Stock boundaries, safety levels, and storage utilization parameters' },
  expiry:     { title: 'Expiry Management',          subtitle: 'FEFO consumption simulation and value at wastage risk' },
  replenish:  { title: 'Replenishment Orders',       subtitle: 'MOQ-rounded replenishment suggestions matching safety targets' },
  transfers:  { title: 'Inter-DC Transfers',         subtitle: 'Rebalancing stock from surplus distribution centers to shortage targets' },
  actions:    { title: 'Action Center',              subtitle: 'Operations escalation reviews and automated ERP instructions' },
  simulation: { title: 'What-If Simulation Studio', subtitle: 'Stress test the supply chain network under shifted variables' },
  explorer:   { title: 'Data Explorer',              subtitle: 'Preprocessed relational database table browser and CSV export' },
};

export default function Header({ activePage, theme, onToggleTheme, onRefreshPrediction }) {
  const meta = PAGE_META[activePage] || PAGE_META.overview;
  return (
    <header className="app-header">
      <div className="header-info">
        <h1>{meta.title}</h1>
        <p>{meta.subtitle}</p>
      </div>
      <div className="header-controls">
        <button
          className="theme-toggle-btn"
          onClick={onToggleTheme}
          title="Toggle Theme"
          style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-glass)', color: 'var(--text-primary)', padding: '8px 12px', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1rem', transition: 'var(--transition-smooth)' }}
        >
          <i className={`fa-solid ${theme === 'dark' ? 'fa-moon' : 'fa-sun'}`} />
        </button>
        <button
          className="status-badge"
          onClick={onRefreshPrediction}
          style={{ cursor: 'pointer', background: 'transparent', border: '1px solid var(--border-glass)', color: 'var(--text-primary)', fontFamily: 'inherit', fontSize: 'inherit', transition: 'var(--transition-smooth)' }}
        >
          <i className="fa-solid fa-arrows-rotate" /> Refresh Prediction
        </button>
      </div>
    </header>
  );
}
