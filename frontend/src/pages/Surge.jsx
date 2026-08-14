import React, { useState, useEffect, useCallback } from 'react';
import { Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { getSurgeSummary, getSurgePredictions, getSurgeTopProducts } from '../api';
import Badge from '../components/Badge';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

/* ─────────────────────────────────────────────
   Helpers
───────────────────────────────────────────── */
const isLight = () => document.body.classList.contains('light-theme');
const gridColor   = () => isLight() ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.04)';
const tickColor   = () => isLight() ? '#475569' : '#94a3b8';
const legendColor = () => isLight() ? '#0f172a' : '#f8fafc';

const RISK_CONFIG = {
  CRITICAL: { color: 'var(--accent-rose)',   dot: '#f43f5e', bg: 'rgba(244,63,94,0.08)',  label: '🔴 Critical'  },
  HIGH:     { color: 'var(--accent-orange)', dot: '#f97316', bg: 'rgba(249,115,22,0.08)', label: '🟠 High'      },
  MEDIUM:   { color: 'var(--accent-yellow)', dot: '#f59e0b', bg: 'rgba(245,158,11,0.08)', label: '🟡 Medium'    },
  LOW:      { color: 'var(--accent-indigo)', dot: '#6366f1', bg: 'rgba(99,102,241,0.04)', label: '🟢 Low'       },
};

function fmt(n, digits = 1) {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return Number(n).toFixed(digits);
}

/* ─────────────────────────────────────────────
   Probability Progress Bar Cell
───────────────────────────────────────────── */
function ProbBar({ value, riskLevel }) {
  const dot = RISK_CONFIG[riskLevel]?.dot || '#6366f1';
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: '110px' }}>
      <div style={{ flex: 1, height: '5px', background: 'rgba(255,255,255,0.08)', borderRadius: '99px', overflow: 'hidden' }}>
        <div style={{
          height: '100%', width: `${pct}%`,
          background: dot, borderRadius: '99px',
          transition: 'width 0.6s ease',
        }} />
      </div>
      <span style={{ fontSize: '11px', fontWeight: 700, color: dot, minWidth: '36px' }}>
        {fmt(value, 1)}%
      </span>
    </div>
  );
}

/* ─────────────────────────────────────────────
   KPI Card
───────────────────────────────────────────── */
function KpiCard({ icon, title, value, sub, color }) {
  return (
    <div className="card metric-card">
      <div className="metric-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <i className={`fa-solid ${icon}`} style={{ color: color || 'var(--accent-indigo)' }} />
        {title}
      </div>
      <div className="metric-value" style={{ color: color || 'inherit' }}>{value}</div>
      <div className="metric-delta delta-info" style={{ color: 'var(--text-secondary)' }}>{sub}</div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Detail Table
───────────────────────────────────────────── */
function SurgeTable({ items }) {
  if (!items || items.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)', fontSize: '14px' }}>
        <i className="fa-solid fa-circle-check" style={{ fontSize: '28px', color: '#22c55e', marginBottom: '12px', display: 'block' }} />
        No surge alerts in this category.
      </div>
    );
  }

  const rowBg = {
    CRITICAL: 'rgba(244,63,94,0.04)',
    HIGH:     'rgba(249,115,22,0.04)',
    MEDIUM:   'rgba(245,158,11,0.04)',
    LOW:      'transparent',
  };

  return (
    <div className="table-container" style={{ marginTop: 0 }}>
      <table>
        <thead>
          <tr>
            <th>SKU</th>
            <th>Product</th>
            <th>DC</th>
            <th>Current Demand</th>
            <th>Baseline Demand</th>
            <th>Forecast 3d</th>
            <th>Demand Δ%</th>
            <th>Surge Probability</th>
            <th>Status</th>
            <th>Risk Level</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r, i) => (
            <tr key={i} style={{ backgroundColor: rowBg[r.risk_level] || 'transparent' }}>
              <td><strong>{r.sku_id}</strong></td>
              <td>{r.product_name}</td>
              <td>
                <span style={{ fontFamily: 'monospace', fontSize: '12px', background: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: '6px' }}>
                  {r.dc_id}
                </span>
              </td>
              <td>{fmt(r.current_demand, 0)} units</td>
              <td>{fmt(r.baseline_demand, 1)} units</td>
              <td>
                <span style={{ color: r.forecast_demand > r.baseline_demand ? '#10b981' : 'inherit' }}>
                  {fmt(r.forecast_demand, 1)} units
                </span>
              </td>
              <td>
                <span style={{
                  color: r.demand_increase_pct > 0 ? '#10b981' : r.demand_increase_pct < -20 ? '#f43f5e' : 'var(--text-secondary)',
                  fontWeight: 600,
                }}>
                  {r.demand_increase_pct > 0 ? '+' : ''}{fmt(r.demand_increase_pct, 1)}%
                </span>
              </td>
              <td><ProbBar value={r.surge_probability} riskLevel={r.risk_level} /></td>
              <td>
                <span style={{
                  fontSize: '11px', fontWeight: 700, padding: '3px 10px', borderRadius: '20px',
                  background: r.surge_status === 'SURGE' ? 'rgba(244,63,94,0.15)' : 'rgba(34,197,94,0.12)',
                  color: r.surge_status === 'SURGE' ? '#f43f5e' : '#22c55e',
                }}>
                  {r.surge_status === 'SURGE' ? '⚡ SURGE' : '✓ STABLE'}
                </span>
              </td>
              <td><Badge label={r.risk_level} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Main Surge Page
───────────────────────────────────────────── */
export default function Surge({ refreshKey }) {
  const [summary, setSummary]       = useState(null);
  const [topProducts, setTopProducts] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [activeTab, setActiveTab]   = useState('CRITICAL');
  const [loading, setLoading]       = useState(true);
  const [tabLoading, setTabLoading] = useState(false);

  /* ── Initial data load ── */
  const load = useCallback(() => {
    setLoading(true);
    Promise.all([getSurgeSummary(), getSurgeTopProducts()])
      .then(([s, top]) => {
        setSummary(s);
        setTopProducts(top || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load, refreshKey]);

  /* ── Tab data load ── */
  useEffect(() => {
    setTabLoading(true);
    getSurgePredictions(activeTab)
      .then(rows => { setPredictions(rows || []); setTabLoading(false); })
      .catch(() => setTabLoading(false));
  }, [activeTab]);

  /* ── Bar chart data ── */
  const chartData = {
    labels: topProducts.map(p => `${p.sku || p.sku_id} · ${p.dc || p.dc_id}`),
    datasets: [
      {
        label: 'Surge Risk Score',
        data: topProducts.map(p => p.surge_risk_score),
        backgroundColor: topProducts.map(p => {
          const c = RISK_CONFIG[p.risk_level];
          return c ? c.dot + 'cc' : '#6366f1cc';
        }),
        borderColor: topProducts.map(p => RISK_CONFIG[p.risk_level]?.dot || '#6366f1'),
        borderWidth: 1.5,
        borderRadius: 6,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: legendColor() } },
      tooltip: {
        callbacks: {
          label: ctx => {
            const p = topProducts[ctx.dataIndex];
            return [
              ` Risk Score: ${ctx.parsed.y}`,
              ` Product: ${p.product_name}`,
              ` Surge Prob: ${p.surge_probability}%`,
              ` Status: ${p.surge_status}`,
            ];
          },
        },
      },
    },
    scales: {
      x: {
        grid: { color: gridColor() },
        ticks: { color: tickColor(), maxRotation: 35, minRotation: 20, font: { size: 11 } },
      },
      y: {
        grid: { color: gridColor() },
        ticks: { color: tickColor() },
        min: 0,
        max: 100,
        title: { display: true, text: 'Surge Risk Score (0–100)', color: tickColor() },
      },
    },
  };

  /* ── Tabs config ── */
  const tabs = [
    { id: 'CRITICAL', ...RISK_CONFIG.CRITICAL, count: summary?.critical_count || 0 },
    { id: 'HIGH',     ...RISK_CONFIG.HIGH,     count: summary?.high_count    || 0 },
    { id: 'MEDIUM',   ...RISK_CONFIG.MEDIUM,   count: summary?.medium_count  || 0 },
    { id: 'LOW',      ...RISK_CONFIG.LOW,      count: summary?.low_count     || 0 },
  ];

  return (
    <div className="page card">
      {/* ── Header row ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h2 className="section-title" style={{ margin: 0 }}>
          <i className="fa-solid fa-bolt" style={{ color: '#f59e0b' }} /> Demand Surge Detection
        </h2>
        <button
          id="surge-refresh-btn"
          className="btn btn-secondary"
          onClick={load}
          disabled={loading}
          style={{ fontSize: '13px', padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '8px' }}
        >
          <i className={`fa-solid fa-arrows-rotate ${loading ? 'fa-spin' : ''}`} />
          {loading ? 'Running...' : 'Refresh Model'}
        </button>
      </div>

      {loading ? (
        <div className="loading">
          <i className="fa-solid fa-circle-notch fa-spin" /> Loading Surge Detection Model...
        </div>
      ) : (
        <>
          {/* ── KPI Cards ── */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
              gap: '16px',
              marginBottom: '32px',
            }}
          >
            <KpiCard
              icon="fa-bolt"
              title="Total Surge Alerts"
              value={summary?.surge_count ?? '—'}
              sub={`of ${summary?.total_records ?? 0} scored records`}
              color="#f59e0b"
            />
            <KpiCard
              icon="fa-circle-exclamation"
              title="Critical Alerts"
              value={summary?.critical_count ?? '—'}
              sub="Surge probability ≥ 80%"
              color="#f43f5e"
            />
            <KpiCard
              icon="fa-triangle-exclamation"
              title="High Alerts"
              value={summary?.high_count ?? '—'}
              sub="Surge probability 60–79%"
              color="#f97316"
            />
            <KpiCard
              icon="fa-gauge-high"
              title="Avg Surge Probability"
              value={`${fmt(summary?.avg_surge_probability)}%`}
              sub="Across all scored SKU × DC"
              color="#6366f1"
            />
          </div>

          {/* ── Bar Chart: Top 10 ── */}
          <div style={{ marginBottom: '32px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700 }}>
                <i className="fa-solid fa-ranking-star" style={{ marginRight: '8px', color: 'var(--accent-indigo)' }} />
                Top 10 Highest Surge-Risk Products
              </h3>
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                Ranked by XGBoost surge risk score · colour = risk level
              </span>
            </div>
            <div style={{ height: '300px', background: 'var(--surface)', borderRadius: '12px', border: '1px solid var(--border)', padding: '16px' }}>
              {topProducts.length > 0 ? (
                <Bar data={chartData} options={chartOptions} />
              ) : (
                <div className="loading"><i className="fa-solid fa-circle-notch fa-spin" /> Loading chart...</div>
              )}
            </div>

            {/* ── Top 10 Product Cards ── */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '12px', marginTop: '20px' }}>
              {topProducts.map((p, idx) => {
                const rc = RISK_CONFIG[p.risk_level] || RISK_CONFIG.LOW;
                return (
                  <div
                    key={idx}
                    style={{
                      border: `1.5px solid ${rc.dot}`,
                      borderRadius: '12px',
                      background: rc.bg,
                      padding: '14px 16px',
                      transition: 'transform 0.15s, box-shadow 0.15s',
                      position: 'relative',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-3px)'; e.currentTarget.style.boxShadow = `0 8px 24px ${rc.dot}33`; }}
                    onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; }}
                  >
                    {/* rank badge */}
                    <span style={{
                      position: 'absolute', top: '10px', left: '12px',
                      fontSize: '10px', fontWeight: 800, color: rc.dot,
                      background: rc.dot + '22', padding: '2px 8px', borderRadius: '99px',
                    }}>
                      #{idx + 1}
                    </span>
                    {/* risk level badge */}
                    <span style={{
                      position: 'absolute', top: '10px', right: '12px',
                      fontSize: '10px', fontWeight: 700, color: '#fff',
                      background: rc.dot, padding: '2px 8px', borderRadius: '99px',
                    }}>
                      {p.risk_level}
                    </span>

                    <div style={{ marginTop: '24px', fontWeight: 700, fontSize: '13px', marginBottom: '2px' }}>
                      {p.product_name}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '10px' }}>
                      {p.sku || p.sku_id} · {p.dc || p.dc_id}
                    </div>

                    {/* Probability bar */}
                    <div style={{ marginBottom: '8px' }}>
                      <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '3px' }}>
                        Surge Probability
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{ flex: 1, height: '5px', background: 'rgba(255,255,255,0.08)', borderRadius: '99px', overflow: 'hidden' }}>
                          <div style={{
                            height: '100%',
                            width: `${Math.min(100, p.surge_probability || 0)}%`,
                            background: rc.dot, borderRadius: '99px', transition: 'width 0.8s ease',
                          }} />
                        </div>
                        <span style={{ fontSize: '12px', fontWeight: 700, color: rc.dot }}>{fmt(p.surge_probability)}%</span>
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                      {[
                        { label: 'Current Demand',  val: `${fmt(p.current_demand, 0)} units` },
                        { label: 'Baseline Demand', val: `${fmt(p.baseline_demand, 0)} units` },
                        { label: 'Risk Score',       val: `${fmt(p.surge_risk_score)} / 100` },
                        { label: 'Status',           val: p.surge_status === 'SURGE' ? '⚡ SURGE' : '✓ STABLE' },
                      ].map(s => (
                        <div key={s.label} style={{ background: 'rgba(255,255,255,0.04)', borderRadius: '6px', padding: '5px 8px' }}>
                          <div style={{ fontSize: '9px', color: 'var(--text-secondary)', marginBottom: '1px' }}>{s.label}</div>
                          <div style={{ fontSize: '12px', fontWeight: 700 }}>{s.val}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ── Divider ── */}
          <div style={{ height: '1px', background: 'var(--border)', margin: '0 0 28px 0', opacity: 0.5 }} />

          {/* ── Risk Tab Bar ── */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  padding: '9px 20px',
                  borderRadius: '9px',
                  border: activeTab === tab.id ? `1.5px solid ${tab.dot}` : '1.5px solid var(--border)',
                  background: activeTab === tab.id ? tab.bg : 'var(--surface)',
                  color: activeTab === tab.id ? tab.dot : 'var(--text-secondary)',
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
                  background: activeTab === tab.id ? tab.dot : 'rgba(255,255,255,0.08)',
                  color: activeTab === tab.id ? '#fff' : 'var(--text-secondary)',
                  fontSize: '11px', fontWeight: 700, borderRadius: '20px', padding: '1px 8px',
                }}>
                  {tab.count}
                </span>
              </button>
            ))}
          </div>

          {/* ── Tab Detail Table ── */}
          <div style={{ background: 'var(--surface)', borderRadius: '12px', border: '1px solid var(--border)', overflow: 'hidden' }}>
            <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontWeight: 600, fontSize: '14px' }}>
                {RISK_CONFIG[activeTab]?.label} — Surge Predictions
              </span>
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)', marginLeft: 'auto' }}>
                {tabLoading ? 'Loading...' : `${predictions.length} record(s) · sorted by surge probability ↓`}
              </span>
            </div>
            {tabLoading ? (
              <div className="loading" style={{ padding: '40px' }}>
                <i className="fa-solid fa-circle-notch fa-spin" /> Filtering predictions...
              </div>
            ) : (
              <SurgeTable items={predictions} />
            )}
          </div>
        </>
      )}
    </div>
  );
}
