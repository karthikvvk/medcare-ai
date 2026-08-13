import React, { useEffect, useState } from 'react';
import { getInventoryStatus } from '../api';
import Badge from '../components/Badge';

export default function Inventory({ dcs }) {
  const [data, setData] = useState([]);
  const [dcFilter, setDcFilter] = useState('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getInventoryStatus().then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const filtered = dcFilter === 'all' ? data : data.filter(i => i.dc_id === dcFilter);

  return (
    <div className="page card">
      <h2 className="section-title"><i className="fa-solid fa-boxes-stacked" /> Distribution Center Inventory Status</h2>
      <div className="filter-row">
        <div className="filter-group">
          <label>Filter by DC:</label>
          <select value={dcFilter} onChange={e => setDcFilter(e.target.value)}>
            <option value="all">-- All Distribution Centers --</option>
            {dcs.map(d => <option key={d.dc_id} value={d.dc_id}>{d.name}</option>)}
          </select>
        </div>
      </div>
      {loading ? (
        <div className="loading"><i className="fa-solid fa-circle-notch fa-spin" /> Loading inventory...</div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>SKU ID</th><th>Medication Name</th><th>Distribution Center</th>
                <th>Physical Stock</th><th>Available Stock</th><th>In-Transit</th>
                <th>Safety Stock</th><th>Reorder Point</th><th>DOI</th><th>Value</th><th>Criticality</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan={11} style={{textAlign:'center',color:'var(--text-secondary)'}}>No inventory snapshots matched filter.</td></tr>
              ) : filtered.map((i, idx) => {
                const isCrit = i.days_of_inventory < i.lead_time_days;
                const isLow = i.available_inventory < i.reorder_point;
                let rowStyle = {};
                if (isCrit) rowStyle = {backgroundColor:'rgba(244,63,94,0.05)'};
                else if (isLow) rowStyle = {backgroundColor:'rgba(249,115,22,0.05)'};
                return (
                  <tr key={idx} style={rowStyle}>
                    <td><strong>{i.sku_id}</strong></td>
                    <td>{i.sku_name}</td>
                    <td>{i.dc_name}</td>
                    <td>{parseInt(i.closing_inventory)}</td>
                    <td><strong>{parseInt(i.available_inventory)}</strong></td>
                    <td>{parseInt(i.incoming_inventory)}</td>
                    <td>{parseInt(i.safety_stock)}</td>
                    <td>{parseInt(i.reorder_point)}</td>
                    <td style={{color: isCrit ? 'var(--accent-rose)' : 'inherit'}}><strong>{i.days_of_inventory.toFixed(1)}</strong> days</td>
                    <td>${i.value?.toLocaleString(undefined,{minimumFractionDigits:2})}</td>
                    <td><Badge label={i.criticality} /></td>
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
