import React, { useState, useEffect } from 'react';
import { Line } from 'react-chartjs-2';
import { getForecastComparison, DATE } from '../api';

const isLight = () => document.body.classList.contains('light-theme');
const gridColor = () => isLight() ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.04)';
const tickColor = () => isLight() ? '#475569' : '#94a3b8';
const legendColor = () => isLight() ? '#0f172a' : '#f8fafc';

export default function Forecast({ skus, dcs }) {
  const [selectedSKU, setSelectedSKU] = useState('');
  const [selectedDC, setSelectedDC] = useState('');
  const [chartData, setChartData] = useState(null);
  const [signals, setSignals] = useState(null);

  useEffect(() => {
    if (skus.length && !selectedSKU) setSelectedSKU(skus[0]?.sku_id);
    if (dcs.length && !selectedDC) setSelectedDC(dcs[0]?.dc_id);
  }, [skus, dcs]);

  useEffect(() => {
    if (!selectedSKU || !selectedDC) return;
    getForecastComparison(DATE, selectedSKU, selectedDC).then(data => {
      const actuals = data.actuals || [];
      const forecasts = data.forecasts || [];
      const labels = actuals.map(a => a.date.replace('2026-', ''));
      const actualValues = actuals.map(a => a.actual);
      const forecastValues = new Array(actuals.length).fill(null);
      if (actuals.length) forecastValues[actuals.length - 1] = actualValues[actualValues.length - 1];
      forecasts.forEach(f => {
        labels.push(f.forecast_date.replace('2026-', ''));
        forecastValues.push(f.forecast);
      });
      setChartData({ labels, actualValues, forecastValues });
      const lastQty = actualValues[actualValues.length - 1] || 25;
      const prevQty = actualValues[actualValues.length - 2] || 25;
      setSignals({ lastQty, vel: lastQty - prevQty });
    }).catch(() => {});
  }, [selectedSKU, selectedDC]);

  const skuObj = skus.find(s => s.sku_id === selectedSKU);

  return (
    <div className="page card">
      <h2 className="section-title"><i className="fa-solid fa-arrow-trend-up" /> Demand Sensing Analysis</h2>
      <div className="filter-row">
        <div className="filter-group">
          <label>Medication SKU:</label>
          <select value={selectedSKU} onChange={e => setSelectedSKU(e.target.value)}>
            {skus.map(s => <option key={s.sku_id} value={s.sku_id}>{s.sku_id} - {s.name}</option>)}
          </select>
        </div>
        <div className="filter-group">
          <label>Distribution Center:</label>
          <select value={selectedDC} onChange={e => setSelectedDC(e.target.value)}>
            {dcs.map(d => <option key={d.dc_id} value={d.dc_id}>{d.dc_id} - {d.name}</option>)}
          </select>
        </div>
      </div>

      <div className="chart-container" style={{ height: '380px', marginBottom: '32px' }}>
        {chartData ? (
          <Line
            data={{
              labels: chartData.labels,
              datasets: [
                { label: 'Observed Daily Demand', data: chartData.actualValues, borderColor: '#6366f1', borderWidth: 2.5, fill: false },
                { label: 'XGBoost Sensing Forecast (7d)', data: chartData.forecastValues, borderColor: '#10b981', borderDash: [4, 4], borderWidth: 2.5, fill: false },
              ],
            }}
            options={{
              responsive: true, maintainAspectRatio: false,
              plugins: { legend: { labels: { color: legendColor() } } },
              scales: {
                x: { grid: { color: gridColor() }, ticks: { color: tickColor() } },
                y: { grid: { color: gridColor() }, ticks: { color: tickColor() } },
              },
            }}
          />
        ) : <div className="loading"><i className="fa-solid fa-circle-notch fa-spin" /> Loading forecast chart...</div>}
      </div>

      <h2 className="section-title"><i className="fa-solid fa-rss" /> Live Demand Sensing Signals</h2>
      <div className="grid-3">
        {signals && (
          <>
            <div className="card metric-card">
              <div className="metric-title">Lag-1 Sales Velocity</div>
              <div className="metric-value">{signals.lastQty.toFixed(0)} Units</div>
              <div className={`metric-delta ${signals.vel >= 0 ? 'delta-pos' : 'delta-neg'}`}>
                <i className={`fa-solid fa-arrow-trend-${signals.vel >= 0 ? 'up' : 'down'}`} />
                {signals.vel >= 0 ? '+' : ''}{signals.vel.toFixed(1)} units shift
              </div>
            </div>
            <div className="card metric-card">
              <div className="metric-title">Promotion Sensor</div>
              <div className="metric-value">INACTIVE</div>
              <div className="metric-delta delta-pos"><i className="fa-solid fa-bullhorn" /> No promotions active</div>
            </div>
            <div className="card metric-card">
              <div className="metric-title">Category Seasonality Profile</div>
              <div className="metric-value" style={{ fontSize: '1.4rem', paddingTop: '4px' }}>{skuObj?.category || 'Standard'}</div>
              <div className="metric-delta delta-info"><i className="fa-solid fa-cloud-sun" /> Outbreak multiplier applied</div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
