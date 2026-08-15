import React from 'react';

const MENU_ITEMS = [
  { id: 'overview',     icon: 'fa-chart-line',      label: 'Executive Overview' },
  { id: 'forecast',     icon: 'fa-arrow-trend-up',   label: 'Demand Sensing' },
  { id: 'inventory',    icon: 'fa-boxes-stacked',    label: 'Inventory Status' },
  { id: 'expiry',       icon: 'fa-hourglass-half',   label: 'Expiry Management' },
  { id: 'surge',        icon: 'fa-bolt',             label: 'Surge Management' },
  { id: 'replenish',    icon: 'fa-truck-ramp-box',   label: 'Replenishments' },
  { id: 'transfers',    icon: 'fa-right-left',       label: 'Inter-DC Transfers' },
  { id: 'actions',      icon: 'fa-shield-halved',    label: 'Action Center' },
  { id: 'simulation',   icon: 'fa-flask',            label: 'What-If Simulation' },
  { id: 'live-scenario', icon: 'fa-triangle-exclamation', label: 'Live AI Scenario' },
  { id: 'explorer',     icon: 'fa-database',         label: 'Data Explorer' },
];

export default function Sidebar({ activePage, onNavigate }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h2>MEDCARE PHARMA</h2>
        <span>Control Tower</span>
      </div>
      <nav className="sidebar-menu">
        {MENU_ITEMS.map(item => (
          <a
            key={item.id}
            href="#"
            className={`menu-item${activePage === item.id ? ' active' : ''}`}
            onClick={e => { e.preventDefault(); onNavigate(item.id); }}
          >
            <i className={`fa-solid ${item.icon}`} />
            {item.label}
          </a>
        ))}
      </nav>
      <div className="sidebar-footer">
        <p>MedCare Control Tower v2.0.0</p>
      </div>
    </aside>
  );
}
