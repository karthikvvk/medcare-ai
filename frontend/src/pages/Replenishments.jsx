import React, { useEffect, useState } from 'react';
import { getRecommendations } from '../api';
import Badge from '../components/Badge';

export default function Replenishments({ skus, dcs }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getRecommendations().then(d => {
      setData(d.filter(r => r.action_type === 'REPLENISH'));
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const totalValue = data.reduce((sum, r) => {
    const sku = skus.find(s => s.sku_id === r.sku_id);
    return sum + (r.quantity * (sku ? sku.unit_cost : 25));
  }, 0);

  return (
    <div className="page card">
      <h2 className="section-title"><i className="fa-solid fa-truck-ramp-box" /> Replenishment Order Planning</h2>
      
      <div className="grid-3" style={{gridTemplateColumns:'1fr 1fr', marginBottom:'24px'}}>
        <div className="card metric-card">
          <div className="metric-title">Total Orders Recommended</div>
          <div className="metric-value">{data.length} orders</div>
        </div>
        <div className="card metric-card">
          <div className="metric-title">Projected Spend Value</div>
          <div className="metric-value" style={{color:'var(--accent-emerald)'}}>
            ${totalValue.toLocaleString(undefined, {minimumFractionDigits:2})}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="loading"><i className="fa-solid fa-circle-notch fa-spin" /> Loading replenishments...</div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>SKU ID</th><th>Medication Name</th><th>DC Target</th>
                <th>Recommended Qty</th><th>Unit Price</th><th>Purchase Spend</th>
                <th>Priority Escalation</th><th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {data.length === 0 ? (
                <tr><td colSpan={8} style={{textAlign:'center',color:'var(--text-secondary)'}}><i className="fa-solid fa-check" style={{color:'var(--accent-emerald)'}} /> No replenishment orders recommended. Available stock comfortably covers safety bounds.</td></tr>
              ) : data.map((r, idx) => {
                const sku = skus.find(s => s.sku_id === r.sku_id);
                const dc = dcs.find(d => d.dc_id === r.dc_id);
                const price = sku ? sku.unit_cost : 25.0;
                return (
                  <tr key={idx}>
                    <td><strong>{r.sku_id}</strong></td>
                    <td>{sku ? sku.name : 'Unknown'}</td>
                    <td>{dc ? dc.name : r.dc_id}</td>
                    <td><strong>{parseInt(r.quantity)}</strong> units</td>
                    <td>${price.toFixed(2)}</td>
                    <td><strong>${(price * r.quantity).toLocaleString(undefined, {minimumFractionDigits:2})}</strong></td>
                    <td><Badge label={r.priority} /></td>
                    <td>{(r.confidence * 100).toFixed(0)}%</td>
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
