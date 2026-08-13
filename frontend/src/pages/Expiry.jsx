import React, { useEffect, useState } from 'react';
import { getExpiryRisks } from '../api';
import Badge from '../components/Badge';

export default function Expiry() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getExpiryRisks().then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const totalWastage = data.reduce((s, r) => s + (r.simulated_waste * r.unit_cost), 0);
  const criticalWastage = data.filter(r => r.risk_level === 'CRITICAL').reduce((s, r) => s + (r.simulated_waste * r.unit_cost), 0);
  const warningBatches = data.filter(r => r.risk_level === 'HIGH' || r.risk_level === 'WATCH').length;

  return (
    <div className="page card">
      <h2 className="section-title"><i className="fa-solid fa-hourglass-half" /> Batch Expiry Management</h2>
      <div className="grid-3">
        <div className="card metric-card">
          <div className="metric-title">Expiry Value at Risk</div>
          <div className="metric-value" style={{color:'var(--accent-orange)'}}>
            ${totalWastage.toLocaleString(undefined,{minimumFractionDigits:2})}
          </div>
          <div className="metric-delta delta-warn">FEFO simulated waste</div>
        </div>
        <div className="card metric-card">
          <div className="metric-title">Critical Wastage (&lt;30d)</div>
          <div className="metric-value" style={{color:'var(--accent-rose)'}}>
            ${criticalWastage.toLocaleString(undefined,{minimumFractionDigits:2})}
          </div>
          <div className="metric-delta delta-neg">Urgent Action Required</div>
        </div>
        <div className="card metric-card">
          <div className="metric-title">Potential Batches in Warning</div>
          <div className="metric-value">{warningBatches} Batches</div>
          <div className="metric-delta delta-info">Monitored for transfers</div>
        </div>
      </div>
      {loading ? (
        <div className="loading"><i className="fa-solid fa-circle-notch fa-spin" /> Loading expiry data...</div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Batch ID</th><th>SKU</th><th>Medication Name</th><th>DC Location</th>
                <th>Batch Stock</th><th>Expiry Date</th><th>Days Remaining</th>
                <th>Projected Wastage</th><th>Risk Level</th><th>System Rationale</th>
              </tr>
            </thead>
            <tbody>
              {data.length === 0 ? (
                <tr><td colSpan={10} style={{textAlign:'center',color:'var(--text-secondary)'}}>No active batches found.</td></tr>
              ) : data.map((r, idx) => {
                let rowStyle = {};
                if (r.risk_level === 'CRITICAL') rowStyle = {backgroundColor:'rgba(244,63,94,0.05)'};
                else if (r.risk_level === 'HIGH') rowStyle = {backgroundColor:'rgba(249,115,22,0.05)'};
                else if (r.risk_level === 'WATCH') rowStyle = {backgroundColor:'rgba(245,158,11,0.05)'};
                return (
                  <tr key={idx} style={rowStyle}>
                    <td><strong>{r.batch_id}</strong></td>
                    <td>{r.sku_id}</td>
                    <td>{r.sku_name}</td>
                    <td>{r.dc_name}</td>
                    <td>{parseInt(r.remaining_quantity)}</td>
                    <td>{r.expiry_date}</td>
                    <td><strong>{r.days_to_expiry}</strong> days</td>
                    <td><strong>{parseInt(r.simulated_waste)}</strong> units</td>
                    <td><Badge label={r.risk_level} /></td>
                    <td>{r.reason}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
