import React, { useEffect, useState } from 'react';
import { getRecommendations, updateRecStatus, getInventoryStatus, getForecastComparison, DATE } from '../api';
import Badge from '../components/Badge';
import { Line } from 'react-chartjs-2';
import { useToast } from '../components/Toast';

const isLight = () => document.body.classList.contains('light-theme');
const gridColor = () => isLight() ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.04)';
const tickColor = () => isLight() ? '#475569' : '#94a3b8';
const legendColor = () => isLight() ? '#0f172a' : '#f8fafc';

export default function Actions({ 
  skus, 
  dcs, 
  initialPriority = 'CRITICAL', 
  filterSku = null, 
  fromPage = null, 
  expiryItem = null, 
  onNavigate,
  markBatchResolved 
}) {
  const [recs, setRecs] = useState([]);
  const [priority, setPriority] = useState(initialPriority);
  const [loading, setLoading] = useState(true);
  const [drilldown, setDrilldown] = useState(null);
  const showToast = useToast();

  const loadData = () => {
    setLoading(true);
    getRecommendations().then(d => {
      const activeRecs = d.filter(r => r.action_type !== 'NO_ACTION' && r.status !== 'APPROVED' && r.status !== 'REJECTED');
      setRecs(activeRecs);
      setLoading(false);
      
      // Auto drill-down if a filterSku or expiryItem is provided
      if (filterSku || expiryItem) {
        let matchingRec = activeRecs.find(r => r.sku_id === (filterSku || expiryItem?.sku_id));
        if (!matchingRec && expiryItem) {
          matchingRec = {
            recommendation_id: `REC-EXP-${expiryItem.batch_id || expiryItem.sku_id}`,
            sku_id: expiryItem.sku_id,
            dc_id: expiryItem.dc_id || (dcs[0]?.dc_id ?? 'DC001'),
            action_type: expiryItem.recommended_action || (expiryItem.days_to_expiry < 30 ? 'EXPEDITE_FEFO' : 'REDUCE_ORDER'),
            priority: expiryItem.expiry_risk === 'WATCH' ? 'HIGH' : (expiryItem.expiry_risk || 'CRITICAL'),
            quantity: expiryItem.expected_writeoff_quantity || expiryItem.available_quantity || 100,
            reason: `Expiry Action Protocol for Batch [${expiryItem.batch_id || ''}]. ${expiryItem.available_quantity?.toLocaleString() || 0} units at ${expiryItem.dc_name || expiryItem.dc_id} expiring in ${expiryItem.days_to_expiry} days (${expiryItem.expiry_date}). AI model recommends immediate FEFO prioritized redistribution or markdown to mitigate projected write-off loss.`,
            expected_impact: `Avoid projected loss of ₹${(expiryItem.projected_loss_inr || ((expiryItem.expected_writeoff_quantity || expiryItem.available_quantity || 0) * (expiryItem.unit_cost || 25))).toLocaleString(undefined, {maximumFractionDigits:0})}.`,
            confidence: expiryItem.expiry_risk_score || 0.95,
            status: 'PENDING',
            isExpirySuggestion: true,
            batch_id: expiryItem.batch_id
          };
        } else if (matchingRec && expiryItem?.batch_id) {
          matchingRec = { ...matchingRec, batch_id: expiryItem.batch_id, isExpirySuggestion: true };
        }
        if (matchingRec) {
          setDrilldown(matchingRec);
        }
      }
    }).catch(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, [filterSku, expiryItem]);

  if (drilldown) {
    return (
      <ActionDetail 
        rec={drilldown} 
        skus={skus} 
        dcs={dcs} 
        onBack={() => { setDrilldown(null); }} 
        onStatusUpdate={loadData}
        fromPage={fromPage}
        onNavigate={onNavigate}
        markBatchResolved={markBatchResolved}
      />
    );
  }

  const filtered = recs.filter(r => r.priority === priority);

  return (
    <div className="page card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2 className="section-title" style={{ margin: 0 }}>
          <i className="fa-solid fa-shield-halved" /> Action Command Center
        </h2>
        <button 
          className="btn btn-secondary" 
          onClick={() => {
            setLoading(true);
            getRecommendations(DATE, true).then(d => {
              const activeRecs = d.filter(r => r.action_type !== 'NO_ACTION' && r.status !== 'APPROVED' && r.status !== 'REJECTED');
              setRecs(activeRecs);
              setLoading(false);
              showToast('Action recommendations regenerated!', 'success');
            }).catch(() => {
              setLoading(false);
              showToast('Failed to regenerate actions.', 'critical');
            });
          }} 
          disabled={loading}
          style={{ fontSize: '13px', padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '8px' }}
        >
          <i className={`fa-solid fa-arrows-rotate ${loading ? 'fa-spin' : ''}`} /> 
          {loading ? 'Running...' : 'Refresh Prediction'}
        </button>
      </div>
      
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

function ActionDetail({ rec, skus, dcs, onBack, onStatusUpdate, fromPage, onNavigate, markBatchResolved }) {
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
      if (rec.recommendation_id && !rec.recommendation_id.startsWith('REC-EXP-')) {
        await updateRecStatus(rec.recommendation_id, status);
      }
      if (rec.batch_id && markBatchResolved) {
        markBatchResolved(rec.batch_id);
      }
      showToast(`Recommendation successfully ${status === 'APPROVED' ? 'Approved' : 'Rejected'}!`, 'success');
      onStatusUpdate();
      if (fromPage === 'expiry' && onNavigate) {
        onNavigate('expiry');
      } else {
        onBack();
      }
    } catch (e) {
      showToast(`Failed to update status: ${e.message}`, 'critical');
    }
  };

  const sku = skus.find(s => s.sku_id === rec.sku_id);
  const dc = dcs.find(d => d.dc_id === rec.dc_id);
  
  return (
    <div className="page animate-fade-in">
      <div style={{marginBottom:'20px'}}>
        <a 
          href="#" 
          onClick={e => { 
            e.preventDefault(); 
            if (fromPage === 'expiry' && onNavigate) {
              onNavigate('expiry');
            } else {
              onBack(); 
            }
          }} 
          style={{color:'var(--accent-indigo)', textDecoration:'none', fontWeight:600, display:'inline-flex', alignItems:'center', gap:'8px'}}
        >
          <i className="fa-solid fa-arrow-left" /> {fromPage === 'expiry' ? 'Back to Expiry Management' : 'Back to Escalations List'}
        </a>
      </div>

      <div className="grid-2-1">
        <div className="card" style={{display:'flex', flexDirection:'column', gap:'20px'}}>
          <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start'}}>
            <div>
              <Badge label={rec.priority} />
              <h2 style={{fontFamily:'Outfit', fontSize:'1.5rem', marginTop:'8px', color:'var(--text-primary)'}}>{sku?.name || rec.sku_id}</h2>
              <span style={{fontSize:'0.85rem', color:'var(--text-secondary)'}}>
                SKU Reference: {rec.sku_id} {rec.batch_id ? `· Batch: ${rec.batch_id}` : ''} {dc ? `· DC: ${dc.name}` : ''}
              </span>
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
              <i className="fa-solid fa-shield-halved" /> Estimated Impact: {rec.expected_impact}
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

        <div className="card" style={{display:'flex', flexDirection:'column', gap:'16px'}}>
          <h3 className="section-title" style={{margin:0, fontSize:'1.05rem'}}>
            <i className="fa-solid fa-chart-line" /> Demand &amp; Allocation Forecast
          </h3>
          <div className="chart-container" style={{height:'260px'}}>
            {chartData ? (
              <Line 
                data={{
                  labels: chartData.labels,
                  datasets: [
                    { label: 'Historical Actuals', data: chartData.actualValues, borderColor: '#6366f1', backgroundColor: 'rgba(99,102,241,0.1)', fill: true, borderWidth: 2, tension: 0.3, spanGaps: true },
                    { label: 'Sensing Forecast', data: chartData.forecastValues, borderColor: '#10b981', borderDash: [4, 4], borderWidth: 2, tension: 0.3, spanGaps: true },
                  ]
                }} 
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: { legend: { labels: { color: legendColor() } } },
                  scales: {
                    x: { grid: { color: gridColor() }, ticks: { color: tickColor() } },
                    y: { 
                      grid: { color: gridColor() }, 
                      ticks: { color: tickColor() },
                      title: { display: true, text: 'Units', color: tickColor(), font: { size: 10, weight: '600' } }
                    }
                  }
                }}
              />
            ) : (
              <div className="loading"><i className="fa-solid fa-circle-notch fa-spin" /> Loading projection...</div>
            )}
          </div>
          <div style={{background:'rgba(255,255,255,0.03)', borderRadius:'8px', padding:'12px', fontSize:'0.85rem', color:'var(--text-secondary)'}}>
            <i className="fa-solid fa-circle-info" style={{color:'var(--accent-indigo)', marginRight:'6px'}} />
            Action approval triggers immediate inventory re-balancing and updates the ERP procurement queue.
          </div>
        </div>
      </div>
    </div>
  );
}
