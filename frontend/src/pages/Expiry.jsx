import React, { useEffect, useState, useCallback } from 'react';
import { getExpiryPredictions } from '../api';
import Badge from '../components/Badge';

/* ─────────────────────────────────────────────
   Suggestion Banner (no internal UI — wires to Action Center)
───────────────────────────────────────────── */
function SuggestionBanner({ tier, suggestion, onNavigate }) {
  if (!suggestion) return null;

  const tierMeta = {
    CRITICAL: {
      border: 'var(--accent-rose)',
      bg: 'rgba(244,63,94,0.07)',
      actionPriority: 'CRITICAL',
      icon: '🚨',
      label: 'CRITICAL',
    },
    HIGH: {
      border: 'var(--accent-orange)',
      bg: 'rgba(249,115,22,0.07)',
      actionPriority: 'HIGH',
      icon: '⚠️',
      label: 'HIGH RISK',
    },
    WATCH: {
      border: 'var(--accent-yellow)',
      bg: 'rgba(245,158,11,0.07)',
      actionPriority: 'HIGH',   // WATCH maps to HIGH tab in Action Center
      icon: '👁️',
      label: 'WATCH',
    },
  };
  const meta = tierMeta[tier] || tierMeta.WATCH;

  return (
    <div style={{
      border: `1.5px solid ${meta.border}`,
      borderRadius: '12px',
      background: meta.bg,
      padding: '16px 20px',
      marginBottom: '24px',
      display: 'flex',
      alignItems: 'center',
      gap: '16px',
      flexWrap: 'wrap',
    }}>
      {/* Label pill */}
      <div style={{
        background: meta.border,
        color: '#fff',
        fontSize: '10px',
        fontWeight: 700,
        padding: '4px 12px',
        borderRadius: '20px',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        flexShrink: 0,
      }}>
        {meta.icon} AI Suggestion · {meta.label}
      </div>

      {/* Status text */}
      <div style={{
        fontSize: '13px',
        color: 'var(--text-primary)',
        fontWeight: 500,
        lineHeight: 1.5,
        flex: 1,
        minWidth: '200px',
      }}>
        {suggestion.status}
      </div>

      {/* CTA — navigate to Action Center */}
      <button
        onClick={() => onNavigate('actions', { actionPriority: meta.actionPriority })}
        style={{
          padding: '9px 20px',
          borderRadius: '9px',
          border: `1.5px solid ${meta.border}`,
          background: `${meta.border}22`,
          color: meta.border,
          fontWeight: 700,
          fontSize: '13px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          whiteSpace: 'nowrap',
          flexShrink: 0,
          transition: 'background 0.15s',
        }}
        onMouseEnter={e => e.currentTarget.style.background = `${meta.border}44`}
        onMouseLeave={e => e.currentTarget.style.background = `${meta.border}22`}
      >
        <i className="fa-solid fa-shield-halved" />
        View Suggestion in Action Center
        <i className="fa-solid fa-arrow-right" style={{ fontSize: '11px' }} />
      </button>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Warehouse Risk Card
───────────────────────────────────────────── */
function WarehouseCard({ wh }) {
  const riskColors = {
    CRITICAL: { border: 'var(--accent-rose)',   bg: 'rgba(244,63,94,0.08)',  dot: '#f43f5e' },
    HIGH:     { border: 'var(--accent-orange)', bg: 'rgba(249,115,22,0.08)', dot: '#f97316' },
    WATCH:    { border: 'var(--accent-yellow)', bg: 'rgba(245,158,11,0.08)', dot: '#f59e0b' },
    LOW:      { border: 'var(--border)',        bg: 'rgba(99,102,241,0.04)', dot: '#6366f1' },
  };
  const c = riskColors[wh.worst_risk_level] || riskColors.LOW;

  return (
    <div
      style={{
        border: `1.5px solid ${c.border}`,
        borderRadius: '14px',
        background: c.bg,
        padding: '18px 20px',
        position: 'relative',
        backdropFilter: 'blur(4px)',
        transition: 'transform 0.15s, box-shadow 0.15s',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.transform = 'translateY(-3px)';
        e.currentTarget.style.boxShadow = `0 8px 28px ${c.border}33`;
      }}
      onMouseLeave={e => {
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      {/* Risk badge */}
      <div style={{ position: 'absolute', top: '14px', right: '14px' }}>
        <span style={{
          background: c.dot, color: '#fff', fontSize: '10px', fontWeight: 700,
          padding: '3px 9px', borderRadius: '20px', letterSpacing: '0.06em',
        }}>
          {wh.worst_risk_level}
        </span>
      </div>

      <div style={{ fontWeight: 700, fontSize: '15px', marginBottom: '4px', paddingRight: '90px' }}>
        {wh.dc_name}
      </div>
      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '14px' }}>
        📍 {wh.dc_location}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
        {[
          { label: 'Total Batches',  val: wh.total_batches },
          { label: 'SKUs Affected',  val: wh.skus_affected },
          { label: 'At-Risk Units',  val: wh.total_at_risk_units.toLocaleString() },
          { label: 'Projected Loss', val: `₹${wh.total_projected_loss_inr.toLocaleString(undefined, { maximumFractionDigits: 0 })}` },
        ].map(s => (
          <div key={s.label} style={{ background: 'rgba(255,255,255,0.04)', borderRadius: '8px', padding: '8px 10px' }}>
            <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '2px' }}>{s.label}</div>
            <div style={{ fontWeight: 700, fontSize: '14px' }}>{s.val}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '8px', marginTop: '12px', flexWrap: 'wrap' }}>
        {wh.critical_batches > 0 && <span style={{ fontSize: '11px', color: '#f43f5e', fontWeight: 600 }}>🔴 {wh.critical_batches} Critical</span>}
        {wh.high_batches     > 0 && <span style={{ fontSize: '11px', color: '#f97316', fontWeight: 600 }}>🟠 {wh.high_batches} High</span>}
        {wh.watch_batches    > 0 && <span style={{ fontSize: '11px', color: '#f59e0b', fontWeight: 600 }}>🟡 {wh.watch_batches} Watch</span>}
        {wh.low_batches      > 0 && <span style={{ fontSize: '11px', color: 'var(--text-secondary)', fontWeight: 600 }}>🟢 {wh.low_batches} Safe</span>}
      </div>

      <div style={{ marginTop: '12px' }}>
        <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
          Worst Risk Score: <strong style={{ color: c.dot }}>{(wh.worst_risk_score * 100).toFixed(0)}%</strong>
        </div>
        <div style={{ height: '4px', background: 'rgba(255,255,255,0.08)', borderRadius: '99px', overflow: 'hidden' }}>
          <div style={{
            height: '100%', width: `${wh.worst_risk_score * 100}%`,
            background: c.dot, borderRadius: '99px', transition: 'width 0.8s ease',
          }} />
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Inventory Table (per tier)
───────────────────────────────────────────── */
function TierTable({ items }) {
  if (!items || items.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)', fontSize: '14px' }}>
        <i className="fa-solid fa-circle-check" style={{ fontSize: '28px', color: '#22c55e', marginBottom: '12px', display: 'block' }} />
        No batches in this category — inventory is well managed.
      </div>
    );
  }

  const riskBg = {
    CRITICAL: 'rgba(244,63,94,0.05)',
    HIGH:     'rgba(249,115,22,0.05)',
    WATCH:    'rgba(245,158,11,0.05)',
    LOW:      'transparent',
  };

  return (
    <div className="table-container" style={{ marginTop: 0 }}>
      <table>
        <thead>
          <tr>
            <th>Batch ID</th>
            <th>SKU</th>
            <th>Medication</th>
            <th>Warehouse</th>
            <th>Available Qty</th>
            <th>Expiry Date</th>
            <th>Days Left</th>
            <th>Write-off Est.</th>
            <th>Risk Score</th>
            <th>Risk Level</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r, idx) => (
            <tr key={idx} style={{ backgroundColor: riskBg[r.expiry_risk] || 'transparent' }}>
              <td><strong>{r.batch_id}</strong></td>
              <td>{r.sku_id}</td>
              <td>{r.sku_name}</td>
              <td>{r.dc_name}</td>
              <td>{r.available_quantity.toLocaleString()}</td>
              <td>{r.expiry_date}</td>
              <td>
                <strong style={{ color: r.days_to_expiry < 0 ? 'var(--accent-rose)' : r.days_to_expiry <= 30 ? 'var(--accent-orange)' : 'inherit' }}>
                  {r.days_to_expiry < 0 ? 'EXPIRED' : `${r.days_to_expiry}d`}
                </strong>
              </td>
              <td>
                <span style={{ color: r.expected_writeoff_quantity > 0 ? 'var(--accent-rose)' : 'var(--text-secondary)' }}>
                  {r.expected_writeoff_quantity.toLocaleString()} units
                </span>
              </td>
              <td>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <div style={{ width: '48px', height: '5px', background: 'rgba(255,255,255,0.08)', borderRadius: '99px', overflow: 'hidden' }}>
                    <div style={{
                      height: '100%',
                      width: `${r.expiry_risk_score * 100}%`,
                      background: r.expiry_risk === 'CRITICAL' ? '#f43f5e' : r.expiry_risk === 'HIGH' ? '#f97316' : '#f59e0b',
                      borderRadius: '99px',
                    }} />
                  </div>
                  <span style={{ fontSize: '11px', fontWeight: 600 }}>{(r.expiry_risk_score * 100).toFixed(0)}%</span>
                </div>
              </td>
              <td><Badge label={r.expiry_risk} /></td>
              <td style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                {r.recommended_action.replace(/_/g, ' ')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Main Expiry Page
───────────────────────────────────────────── */
export default function Expiry({ refreshKey, onNavigate }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('critical');

  const load = useCallback(() => {
    setLoading(true);
    getExpiryPredictions()
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load, refreshKey]);

  const summary    = data?.summary || {};
  const warehouses = data?.warehouses_at_risk || [];

  const tabs = [
    { id: 'critical', label: '🔴 Critical',  count: summary.critical_count || 0, items: data?.critical_items || [], suggestion: data?.suggestions_critical, tier: 'CRITICAL', color: 'var(--accent-rose)'   },
    { id: 'high',     label: '🟠 High Risk', count: summary.high_count     || 0, items: data?.high_items     || [], suggestion: data?.suggestions_high,     tier: 'HIGH',     color: 'var(--accent-orange)' },
    { id: 'watch',    label: '👁️ Watch',     count: summary.watch_count    || 0, items: data?.watch_items    || [], suggestion: data?.suggestions_watch,    tier: 'WATCH',    color: 'var(--accent-yellow)' },
  ];

  const activeTabData = tabs.find(t => t.id === activeTab);

  return (
    <div className="page card">
      <h2 className="section-title">
        <i className="fa-solid fa-hourglass-half" /> Expiry Management
      </h2>

      {loading ? (
        <div className="loading">
          <i className="fa-solid fa-circle-notch fa-spin" /> Running Expiry Aware Allocation Model...
        </div>
      ) : (
        <>
          {/* ── KPI Cards ── */}
          <div className="grid-3" style={{ marginBottom: '28px' }}>
            <div className="card metric-card">
              <div className="metric-title">Total Projected Loss</div>
              <div className="metric-value" style={{ color: 'var(--accent-orange)' }}>
                ₹{(summary.total_projected_loss_inr || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div className="metric-delta delta-warn">Model estimated write-off</div>
            </div>
            <div className="card metric-card">
              <div className="metric-title">Critical Batches</div>
              <div className="metric-value" style={{ color: 'var(--accent-rose)' }}>
                {summary.critical_count || 0}
              </div>
              <div className="metric-delta delta-neg">Urgent action required</div>
            </div>
            <div className="card metric-card">
              <div className="metric-title">Under Surveillance</div>
              <div className="metric-value">
                {(summary.high_count || 0) + (summary.watch_count || 0)} Batches
              </div>
              <div className="metric-delta delta-info">High + Watch tier</div>
            </div>
          </div>

          {/* ── Warehouses at Risk ── */}
          <div style={{ marginBottom: '32px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700 }}>
                <i className="fa-solid fa-warehouse" style={{ marginRight: '8px', color: 'var(--accent-indigo)' }} />
                Warehouses at Risk
              </h3>
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                {warehouses.length} distribution center(s) · model-scored
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
              {warehouses.length === 0
                ? <div style={{ gridColumn: '1/-1', textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>No warehouse data available.</div>
                : warehouses.map(wh => <WarehouseCard key={wh.dc_id} wh={wh} />)
              }
            </div>
          </div>

          {/* ── Divider ── */}
          <div style={{ height: '1px', background: 'var(--border)', margin: '0 0 28px 0', opacity: 0.5 }} />

          {/* ── Tab Bar ── */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', flexWrap: 'wrap' }}>
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  padding: '9px 20px',
                  borderRadius: '9px',
                  border: activeTab === tab.id ? `1.5px solid ${tab.color}` : '1.5px solid var(--border)',
                  background: activeTab === tab.id ? `${tab.color}22` : 'var(--surface)',
                  color: activeTab === tab.id ? tab.color : 'var(--text-secondary)',
                  fontWeight: activeTab === tab.id ? 700 : 500,
                  fontSize: '13px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  transition: 'all 0.15s',
                }}
              >
                {tab.label}
                <span style={{
                  background: activeTab === tab.id ? tab.color : 'rgba(255,255,255,0.08)',
                  color: activeTab === tab.id ? '#fff' : 'var(--text-secondary)',
                  fontSize: '11px', fontWeight: 700, borderRadius: '20px', padding: '1px 8px',
                }}>
                  {tab.count}
                </span>
              </button>
            ))}
          </div>

          {/* ── Active Tab Content ── */}
          {activeTabData && (
            <div>
              {/* Suggestion banner — wires to Action Center */}
              <SuggestionBanner
                tier={activeTabData.tier}
                suggestion={activeTabData.suggestion}
                onNavigate={onNavigate}
              />

              {/* Inventory Table */}
              <div style={{ background: 'var(--surface)', borderRadius: '12px', border: '1px solid var(--border)', overflow: 'hidden' }}>
                <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontWeight: 600, fontSize: '14px' }}>
                    {activeTabData.label} — Categorised Inventory
                  </span>
                  <span style={{ fontSize: '12px', color: 'var(--text-secondary)', marginLeft: 'auto' }}>
                    {activeTabData.items.length} batch(es) · sorted by risk score ↓
                  </span>
                </div>
                <TierTable items={activeTabData.items} />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
