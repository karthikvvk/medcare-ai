import React, { useEffect, useState } from 'react';
import { getRecommendations, updateRecStatus, getInventoryStatus, getForecastComparison, DATE } from '../api';
import Badge from '../components/Badge';
import { Line } from 'react-chartjs-2';
import { useToast } from '../components/Toast';

const isLight = () => document.body.classList.contains('light-theme');
const gridColor = () => isLight() ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.04)';
const tickColor = () => isLight() ? '#475569' : '#94a3b8';
const legendColor = () => isLight() ? '#0f172a' : '#f8fafc';

export default function Actions({ skus, dcs, initialPriority = 'CRITICAL' }) {
  const [recs, setRecs] = useState([]);
  const [priority, setPriority] = useState(initialPriority);
  const [loading, setLoading] = useState(true);
  const [drilldown, setDrilldown] = useState(null);
  const showToast = useToast();

  const loadData = () => {
    setLoading(true);
    getRecommendations().then(d => {
      setRecs(d.filter(r => r.action_type !== 'NO_ACTION'));
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, []);

  if (drilldown) return <ActionDetail rec={drilldown} skus={skus} dcs={dcs} onBack={() => setDrilldown(null)} onStatusUpdate={loadData} />;

  const filtered = recs.filter(r => r.priority === priority);

  return (
    <div className="page card">
      <h2 className="section-title"><i className="fa-solid fa-shield-halved" /> Action Command Center</h2>
      
      <div className="tabs-container" style={{display:'flex', gap:'12px', marginBottom:'24px'}}>
        {['CRITICAL','HIGH','MEDIUM','LOW'].map(p => (
          <button key={p} className={`btn btn-secondary ${priority === p ? 'active-tab' : ''}`} onClick={() => setPriority(p)}>
            {p} ({recs.filter(r => r.priority === p).length})
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading"><i className="fa-solid fa-circle-notch fa-spin" /> Loading actions...</div>
      ) : (
        <div id="actions-list" style={{display:'flex', flexDirection:'column', gap:'16px'}}>
          {filtered.length === 0 ? (
            <div className="card" style={{textAlign:'center', padding:'32px', color:'var(--text-secondary)'}}>
              <i className="fa-solid fa-circle-check" style={{fontSize:'2rem', color:'var(--accent-emerald)', marginBottom:'12px'}} /><br />
              No pending actions in the {priority} escalation pool today.
            </div>
          ) : filtered.map(r => {
            const sku = skus.find(s => s.sku_id === r.sku_id);
            const dc = dcs.find(d => d.dc_id === r.dc_id);
            const borderColor = priority === 'CRITICAL' ? 'var(--accent-rose)' : (priority === 'HIGH' ? 'var(--accent-orange)' : 'var(--accent-amber)');
            return (
              <div key={r.recommendation_id} className="card" style={{borderLeft: `4px solid ${borderColor}`}}>
                <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', flexWrap:'wrap', gap:'12px', marginBottom:'12px'}}>
                  <div>
                    <Badge label={r.action_type} />
                    <strong style={{fontSize:'1.1rem', marginLeft:'8px'}}>{sku ? sku.name : r.sku_id} ({r.sku_id})</strong> at <strong>{dc ? dc.name : r.dc_id}</strong>
                  </div>
                  <div style={{marginLeft:'auto', fontSize:'0.85rem', color:'var(--text-secondary)'}}>
                    Status: <strong style={{color:'var(--accent-indigo)'}}>{r.status}</strong>
                  </div>
                </div>
                
                <div className="explain-panel">
                  <strong>Dynamic Explanation / Optimization Reason:</strong>
                  <p style={{marginTop:'6px', color:'var(--text-primary)'}}>{r.reason}</p>
                  <p style={{color:'var(--accent-emerald)', marginTop:'6px', fontWeight:600}}><i className="fa-solid fa-shield" /> Target Impact: {r.expected_impact}</p>
                </div>
                
                <div className="btn-group">
                  <button className="btn btn-primary" onClick={() => setDrilldown(r)}><i className="fa-solid fa-magnifying-glass-chart" /> Review Details &amp; Forecast Chart</button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ActionDetail({ rec, skus, dcs, onBack, onStatusUpdate }) {
  const showToast = useToast();
  const [invStatus, setInvStatus] = useState(null);
  const [chartData, setChartData] = useState(null);

  useEffect(() => {
    getInventoryStatus().then(d => {
      const s = d.find(i => i.sku_id === rec.sku_id && i.dc_id === rec.dc_id);
      setInvStatus(s || { closing_inventory:0, available_inventory:0, safety_stock:0, reorder_point:0 });
    });
    getForecastComparison(DATE, rec.sku_id, rec.dc_id).then(data => {
      const actuals = data.actuals || [];
      const forecasts = data.forecasts || [];
      const labels = actuals.map(a => a.date.replace('2026-', ''));
      const actualValues = actuals.map(a => a.actual);
      const forecastValues = new Array(actuals.length).fill(null);
      if (actuals.length) forecastValues[actuals.length - 1] = actualValues[actualValues.length - 1];
      forecasts.forEach(f => { labels.push(f.forecast_date.replace('2026-', '')); forecastValues.push(f.forecast); });
      setChartData({ labels, actualValues, forecastValues });
    });
  }, [rec]);

  const handleUpdate = async (status) => {
    try {
      await updateRecStatus(rec.recommendation_id, status);
      showToast(`Recommendation successfully ${status === 'APPROVED' ? 'Approved' : 'Rejected'}!`, 'success');
      onStatusUpdate();
      onBack();
    } catch (e) {
      showToast(`Failed to update status: ${e.message}`, 'critical');
    }
  };

  const sku = skus.find(s => s.sku_id === rec.sku_id);
  
  return (
    <div className="page animate-fade-in">
      <div style={{marginBottom:'20px'}}>
        <a href="#" onClick={e => { e.preventDefault(); onBack(); }} style={{color:'var(--accent-indigo)', textDecoration:'none', fontWeight:600, display:'inline-flex', alignItems:'center', gap:'8px'}}>
          <i className="fa-solid fa-arrow-left" /> Back to Escalations List
        </a>
      </div>

      <div className="grid-2-1">
        <div className="card" style={{display:'flex', flexDirection:'column', gap:'20px'}}>
          <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start'}}>
            <div>
              <Badge label={rec.priority} />
              <h2 style={{fontFamily:'Outfit', fontSize:'1.5rem', marginTop:'8px', color:'var(--text-primary)'}}>{sku?.name || rec.sku_id}</h2>
              <span style={{fontSize:'0.85rem', color:'var(--text-secondary)'}}>SKU Reference: {rec.sku_id}</span>
            </div>
            <div style={{textAlign:'right'}}>
              <Badge label={rec.action_type} />
              <h3 style={{fontFamily:'Outfit', fontSize:'1.3rem', marginTop:'8px', color:'var(--accent-indigo)'}}>Qty: {parseInt(rec.quantity)} units</h3>
            </div>
          </div>

          <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:'16px', background:'rgba(0,0,0,0.15)', padding:'16px', borderRadius:'8px', border:'1px solid var(--border-glass)'}}>
            <div>
              <span style={{fontSize:'0.8rem', color:'var(--text-secondary)'}}>Physical Stock:</span>
              <strong style={{display:'block', fontSize:'1.1rem', color:'var(--text-primary)'}}>{invStatus ? parseInt(invStatus.closing_inventory) : '-'} units</strong>
            </div>
            <div>
              <span style={{fontSize:'0.8rem', color:'var(--text-secondary)'}}>Available Stock:</span>
              <strong style={{display:'block', fontSize:'1.1rem', color:'var(--text-primary)'}}>{invStatus ? parseInt(invStatus.available_inventory) : '-'} units</strong>
            </div>
            <div>
              <span style={{fontSize:'0.8rem', color:'var(--text-secondary)'}}>Safety Stock Level:</span>
              <strong style={{display:'block', fontSize:'1.1rem', color:'var(--text-primary)'}}>{invStatus ? parseInt(invStatus.safety_stock) : '-'} units</strong>
            </div>
            <div>
              <span style={{fontSize:'0.8rem', color:'var(--text-secondary)'}}>Reorder Point (ROP):</span>
              <strong style={{display:'block', fontSize:'1.1rem', color:'var(--text-primary)'}}>{invStatus ? parseInt(invStatus.reorder_point) : '-'} units</strong>
            </div>
          </div>

          <div className="explain-panel" style={{marginTop:0}}>
            <strong>Escalation Explanation:</strong>
            <p style={{marginTop:'6px', color:'var(--text-primary)', lineHeight:1.5}}>{rec.reason}</p>
            <p style={{color:'var(--accent-emerald)', marginTop:'10px', fontWeight:600, display:'flex', alignItems:'center', gap:'6px'}}>
              <i className="fa-solid fa-shield-halved" /> Estimated Saved Valuation: {rec.expected_impact}
            </p>
          </div>

          <div style={{display:'flex', gap:'12px', marginTop:'8px'}}>
            <button className="btn btn-primary" style={{flexGrow:1, padding:'12px'}} onClick={() => handleUpdate('APPROVED')}>
              <i className="fa-solid fa-circle-check" /> Approve &amp; Deploy
            </button>
            <button className="btn btn-secondary" style={{flexGrow:1, padding:'12px', borderColor:'var(--accent-rose)', color:'var(--accent-rose)'}} onClick={() => handleUpdate('REJECTED')}>
              <i className="fa-solid fa-circle-xmark" /> Reject Action
            </button>
          </div>
        </div>

        <div className="card" style={{display:'flex', flexDirection:'column', gap:'20px'}}>
          <h2 className="section-title" style={{marginBottom:0}}><i className="fa-solid fa-chart-line" /> Demand Sensing Forecast</h2>
          <div className="chart-container" style={{height:'320px'}}>
            {chartData ? (
              <Line data={{
                labels: chartData.labels,
                datasets: [
                  { label:'Observed Demand', data:chartData.actualValues, borderColor:'#06b6d4', borderWidth:2.5, fill:false },
                  { label:'Sensed Demand Forecast', data:chartData.forecastValues, borderColor:'#8b5cf6', borderDash:[4,4], borderWidth:2.5, fill:false },
                ]
              }} options={{
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { labels: { color: legendColor() } } },
                scales: {
                  x: { grid: { color: gridColor() }, ticks: { color: tickColor() } },
                  y: { grid: { color: gridColor() }, ticks: { color: tickColor() } },
                }
              }} />
            ) : <div className="loading"><i className="fa-solid fa-circle-notch fa-spin" /> Loading forecast...</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
