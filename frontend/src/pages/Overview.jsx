import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Line, Doughnut, Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, BarElement, ArcElement, Title, Tooltip, Legend, Filler
} from 'chart.js';
import { getSummary, getInventoryStatus, getRecommendations, getExpiryRisks } from '../api';
import Badge from '../components/Badge';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, ArcElement, Title, Tooltip, Legend, Filler);

const isLight = () => document.body.classList.contains('light-theme');
const gridColor = () => isLight() ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.05)';
const tickColor = () => isLight() ? '#475569' : '#94a3b8';
const legendColor = () => isLight() ? '#0f172a' : '#f8fafc';

export default function Overview({ skus, dcs, refreshKey }) {
  const [sumData, setSumData] = useState(null);
  const [invData, setInvData] = useState([]);
  const [recData, setRecData] = useState([]);
  const [expData, setExpData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [visibleCount, setVisibleCount] = useState(10);
  
  const observer = useRef(null);
  const lastElementRef = useCallback(node => {
    if (loading) return;
    if (observer.current) observer.current.disconnect();
    observer.current = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting) {
        setVisibleCount(prev => prev + 10);
      } 
    });
    if (node) observer.current.observe(node);
  }, [loading]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([getSummary(), getInventoryStatus(), getRecommendations(), getExpiryRisks()])
      .then(([s, inv, rec, exp]) => {
        setSumData(s);
        setInvData(Array.isArray(inv) ? inv : []);
        setRecData(Array.isArray(rec) ? rec : []);
        setExpData(Array.isArray(exp) ? exp : []);
        setLoading(false);
      })
      .catch(e => {
        setError(e.message);
        setLoading(false);
      });
  }, [refreshKey]);

  if (loading) return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:'12px', height:'300px', fontSize:'1.1rem', color:'var(--text-secondary)' }}>
      <i className="fa-solid fa-circle-notch fa-spin" style={{ color:'var(--accent-indigo)' }} />
      Loading overview data...
    </div>
  );
  
  if (error) return (
    <div className="card" style={{ padding:'40px', textAlign:'center' }}>
      <i className="fa-solid fa-triangle-exclamation" style={{ fontSize:'2rem', color:'var(--accent-rose)', marginBottom:'12px', display:'block' }} />
      <strong style={{ color:'var(--accent-rose)' }}>Failed to load overview data</strong>
      <p style={{ marginTop:'8px', color:'var(--text-secondary)', fontSize:'0.9rem' }}>{error}</p>
      <p style={{ marginTop:'8px', color:'var(--text-muted)', fontSize:'0.85rem' }}>Make sure the FastAPI backend is running on port 8000.</p>
    </div>
  );

  const totalSKUs = skus.length;
  const stockouts = sumData?.counters?.critical_risks ?? 0;
  const transfers = sumData?.counters?.transfers ?? 0;
  const replenishments = sumData?.counters?.replenishment_orders ?? 0;
  const critExp = expData.filter(r => r.risk_level === 'CRITICAL' || r.risk_level === 'HIGH');
  const expCount = critExp.length;
  const expVal = critExp.reduce((sum, r) => sum + ((r.remaining_quantity ?? 0) * (r.unit_cost ?? 25)), 0);
  const criticalRecs = recData.filter(r => r.priority === 'CRITICAL');
  const visibleRecs = criticalRecs.slice(0, visibleCount);

  // Trend chart — static demo data
  const trendLabels = ['Jul 28','Jul 31','Aug 03','Aug 06','Aug 09','Aug 12','Aug 15 (Fc)','Aug 18 (Fc)','Aug 21 (Fc)'];
  const actualData =   [1200, 1340, 1100, 1420, 1500, 1610, null, null, null];
  const forecastData = [null, null, null, null, null, 1610, 1720, 1790, 1850];

  // Donut — inventory health
  let healthy=0, warning=0, low=0, critical=0;
  invData.forEach(i => {
    if ((i.days_of_inventory ?? 999) < (i.lead_time_days ?? 5)) critical++;
    else if ((i.available_inventory ?? 0) < (i.reorder_point ?? 0)) low++;
    else if ((i.available_inventory ?? 0) < (i.reorder_point ?? 0) * 1.2) warning++;
    else healthy++;
  });

  // DOI bar per DC
  const dcMap = {};
  invData.forEach(i => {
    const n = i.dc_name ?? i.dc_id;
    if (!dcMap[n]) dcMap[n] = { sum: 0, count: 0 };
    dcMap[n].sum += (i.days_of_inventory ?? 0);
    dcMap[n].count++;
  });
  const doiLabels = Object.keys(dcMap).map(l => l.replace(' DC','').replace(' Distribution Center',''));
  const doiVals = Object.values(dcMap).map(v => v.count ? v.sum / v.count : 0);

  const sharedOpts = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { labels: { color: legendColor() } } },
    scales: {
      x: { grid: { color: gridColor() }, ticks: { color: tickColor() } },
      y: { 
        grid: { color: gridColor() }, 
        ticks: { color: tickColor() },
        title: {
          display: true,
          text: 'Units',
          color: tickColor(),
          font: { size: 11, weight: '600' }
        }
      },
    },
  };

  return (
    <div className="page">
      {/* KPI cards */}
      <div className="grid-5">
        <div className="card metric-card">
          <div className="metric-title">Active SKUs</div>
          <div className="metric-value">{totalSKUs}</div>
          <div className="metric-delta delta-info"><i className="fa-solid fa-circle" /> Live Network</div>
        </div>
        <div className="card metric-card">
          <div className="metric-title">Stock-out Risks</div>
          <div className="metric-value" style={{color:'var(--accent-rose)'}}>{stockouts}</div>
          <div className="metric-delta delta-neg"><i className="fa-solid fa-triangle-exclamation" /> Action Required</div>
        </div>
        <div className="card metric-card">
          <div className="metric-title">Expiry Warnings</div>
          <div className="metric-value" style={{color:'var(--accent-orange)'}}>{expCount}</div>
          <div className="metric-delta delta-warn"><i className="fa-solid fa-clock" /> ${expVal.toLocaleString(undefined,{maximumFractionDigits:0})} at risk</div>
        </div>
        <div className="card metric-card">
          <div className="metric-title">Stock Transfers</div>
          <div className="metric-value" style={{color:'var(--accent-sky)'}}>{transfers}</div>
          <div className="metric-delta delta-info"><i className="fa-solid fa-right-left" /> Rebalancing</div>
        </div>
        <div className="card metric-card">
          <div className="metric-title">Replenishments</div>
          <div className="metric-value">{replenishments}</div>
          <div className="metric-delta delta-pos"><i className="fa-solid fa-truck" /> Supplier orders</div>
        </div>
      </div>

      {/* Charts row */}
      <div className="grid-2-1">
        <div className="card">

          <h2 className="section-title"><i className="fa-solid fa-chart-line" /> Daily Sales Trend &amp; Demand Forecast</h2>
          <div className="chart-container">
            <Line data={{
              labels: trendLabels,
              datasets: [
                { label:'Historical Actuals', data:actualData, borderColor:'#6366f1', backgroundColor:'rgba(99,102,241,0.1)', borderWidth:3, fill:true, tension:0.3, spanGaps:true },
                { label:'Sensing Forecast', data:forecastData, borderColor:'#10b981', borderDash:[5,5], borderWidth:3, tension:0.3, spanGaps:true },
              ]
            }} options={sharedOpts} />
          </div>
        </div>
        <div className="card" style={{display:'flex',flexDirection:'column',gap:'20px'}}>
          <div>
            <h2 className="section-title"><i className="fa-solid fa-chart-pie" /> Network Stock Health</h2>
            <div className="chart-donut-container">
              <Doughnut data={{
                labels:['Healthy','Approaching ROP','Low Stock','Stockout Risk'],
                datasets:[{data:[healthy,warning,low,critical],backgroundColor:['#10b981','#f59e0b','#f97316','#f43f5e'],borderColor:'#0e1117',borderWidth:2}]
              }} options={{ responsive:true, maintainAspectRatio:false, plugins:{legend:{labels:{color:legendColor()}}} }} />
            </div>
          </div>
          <div>
            <h2 className="section-title"><i className="fa-solid fa-warehouse" /> Avg DOI by DC</h2>
            <div style={{height:'160px'}}>
              <Bar data={{
                labels: doiLabels,
                datasets:[{label:'Days of Inventory',data:doiVals,backgroundColor:'rgba(99,102,241,0.45)',borderColor:'#6366f1',borderWidth:1.5,borderRadius:4}]
              }} options={{
                responsive:true, maintainAspectRatio:false,
                plugins:{legend:{display:false}},
                scales:{
                  x:{grid:{display:false},ticks:{color:tickColor(),font:{size:9}}},
                  y:{
                    grid:{color:gridColor()},
                    ticks:{color:tickColor(),font:{size:9}},
                    title:{
                      display:true,
                      text:'Days',
                      color:tickColor(),
                      font:{size:10, weight:'600'}
                    }
                  }
                }
              }} />
            </div>
          </div>
        </div>
      </div>

      {/* Critical alerts table */}
      <div className="card">
        <h2 className="section-title" style={{color:'var(--accent-rose)'}}><i className="fa-solid fa-bell" /> Critical Priority Alerts</h2>
        <div className="table-container">
          <table>
            <thead>
              <tr><th>SKU</th><th>Distribution Center</th><th>Action</th><th>Quantity</th></tr>
            </thead>
            <tbody>
              {visibleRecs.length === 0 ? (
                <tr><td colSpan={5} style={{textAlign:'center', color:'var(--text-secondary)'}}>
                  <i className="fa-solid fa-circle-check" style={{color:'var(--accent-emerald)'}} /> No critical alerts today.
                </td></tr>
              ) : visibleRecs.map((r, index) => {
                const sku = skus.find(s => s.sku_id === r.sku_id);
                const dc = dcs.find(d => d.dc_id === r.dc_id);
                const isLast = index === visibleRecs.length - 1 && visibleRecs.length < criticalRecs.length;
                return (
                  <tr key={r.recommendation_id} ref={isLast ? lastElementRef : null}>
                    <td><strong>{sku?.name || r.sku_id}</strong> <span style={{fontSize:'0.75rem',color:'var(--text-secondary)'}}>({r.sku_id})</span></td>
                    <td>{dc?.name || r.dc_id}</td>
                    <td><Badge label={r.action_type} /></td>
                    <td><strong>{parseInt(r.quantity)}</strong></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
