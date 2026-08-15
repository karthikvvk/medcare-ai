import React, { useEffect, useState } from 'react';
import { getTransfers } from '../api';
import Badge from '../components/Badge';

export default function Transfers({ skus, dcs }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTransfers().then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const totalQty = data.reduce((sum, t) => sum + t.quantity, 0);

  return (
    <div className="page card">
      <h2 className="section-title"><i className="fa-solid fa-right-left" /> Inter-DC Stock Rebalancing</h2>
      
      <div className="grid-3" style={{gridTemplateColumns:'1fr 1fr', marginBottom:'24px'}}>
        <div className="card metric-card">
          <div className="metric-title">Transfer Operations Recommended</div>
          <div className="metric-value">{data.length} transfers</div>
        </div>
        <div className="card metric-card">
          <div className="metric-title">Total Rebalanced Quantity</div>
          <div className="metric-value" style={{color:'var(--accent-sky)'}}>{parseInt(totalQty)} units</div>
        </div>
      </div>

      {loading ? (
        <div className="loading"><i className="fa-solid fa-circle-notch fa-spin" /> Loading transfers...</div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Transfer ID</th><th>SKU ID</th><th>Medication Name</th>
                <th>Source DC</th><th>Destination DC</th><th>Batch ID Ref</th>
                <th>Transfer Qty</th><th>Transit Time</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.length === 0 ? (
                <tr><td colSpan={9} style={{textAlign:'center',color:'var(--text-secondary)'}}><i className="fa-solid fa-check" style={{color:'var(--accent-emerald)'}} /> No inter-DC stock rebalancing transfers required today.</td></tr>
              ) : data.map((t, idx) => {
                const sku = skus.find(s => s.sku_id === t.sku_id);
                const src = dcs.find(d => d.dc_id === t.source_dc_id);
                const dest = dcs.find(d => d.dc_id === t.destination_dc_id);
                return (
                  <tr key={idx}>
                    <td><strong>{t.transfer_id}</strong></td>
                    <td>{t.sku_id}</td>
                    <td>{sku ? sku.name : 'Unknown'}</td>
                    <td style={{color:'var(--accent-orange)'}}>{src ? src.name : t.source_dc_id}</td>
                    <td style={{color:'var(--accent-emerald)'}}>{dest ? dest.name : t.destination_dc_id}</td>
                    <td><code>{t.batch_id}</code></td>
                    <td><strong>{parseInt(t.quantity)}</strong> units</td>
                    <td><i className="fa-solid fa-clock" /> {t.transit_days} days</td>
                    <td><Badge label={t.status} /></td>
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
