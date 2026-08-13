import React, { useState, useEffect } from 'react';
import { getSKUs, getDCs, getInventoryStatus, getExpiryRisks, getRecommendations, getSummary } from '../api';

const TABLES = {
  skus: { label: 'SKUs Master', fetcher: getSKUs },
  distribution_centers: { label: 'Distribution Centers', fetcher: getDCs },
  inventory_snapshots: { label: 'Inventory Snapshots', fetcher: getInventoryStatus },
  batches: { label: 'Batches', fetcher: getExpiryRisks },
  recommendations: { label: 'Recommendations', fetcher: getRecommendations },
};

export default function Explorer() {
  const [table, setTable] = useState('skus');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    TABLES[table].fetcher().then(d => {
      setData(Array.isArray(d) ? d : [d]);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [table]);

  const keys = data.length > 0 ? Object.keys(data[0]) : [];

  const handleDownload = () => {
    if (!data.length) return;
    let csv = keys.join(',') + '\n';
    data.forEach(row => {
      csv += keys.map(k => JSON.stringify(row[k])).join(',') + '\n';
    });
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `medcare_${table}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="page card">
      <h2 className="section-title"><i className="fa-solid fa-database" /> Database Table Explorer</h2>
      
      <div className="filter-row">
        <div className="filter-group">
          <label>Select Table:</label>
          <select value={table} onChange={e => setTable(e.target.value)}>
            {Object.entries(TABLES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </div>
        <div className="filter-group" style={{justifyContent:'flex-end'}}>
          <button className="btn btn-secondary" onClick={handleDownload}><i className="fa-solid fa-download" /> Download table CSV</button>
        </div>
      </div>

      <div className="table-container" style={{maxHeight:'480px', overflowY:'auto'}}>
        <table>
          <thead>
            <tr>{keys.map(k => <th key={k}>{k}</th>)}</tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={keys.length || 1} style={{textAlign:'center'}}><i className="fa-solid fa-circle-notch fa-spin" /> Querying table data...</td></tr>
            ) : data.length === 0 ? (
              <tr><td colSpan={keys.length || 1} style={{textAlign:'center',color:'var(--text-secondary)'}}>Table is empty.</td></tr>
            ) : data.slice(0, 100).map((row, idx) => (
              <tr key={idx}>
                {keys.map(k => {
                  let v = row[k];
                  if (typeof v === 'number') v = v.toFixed(2);
                  return <td key={k}>{v}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
