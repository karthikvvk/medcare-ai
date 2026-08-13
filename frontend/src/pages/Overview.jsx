import React, { useEffect, useState } from 'react';
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

export default function Overview({ skus, dcs }) {
  const [sumData, setSumData] = useState(null);
  const [invData, setInvData] = useState([]);
  const [recData, setRecData] = useState([]);
  const [expData, setExpData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getSummary(), getInventoryStatus(), getRecommendations(), getExpiryRisks()])
      .then(([s, inv, rec, exp]) => {
        setSumData(s);
        setInvData(inv);
        setRecData(rec);
        setExpData(exp);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading"><i className="fa-solid fa-circle-notch fa-spin" /> Loading overview...</div>;
  if (!sumData) return <div className="loading">Failed to load overview data.</div>;

  const totalSKUs = skus.length;
  const stockouts = sumData.counters?.critical_risks ?? 0;
  const transfers = sumData.counters?.transfers ?? 0;
  const replenishments = sumData.counters?.replenishment_orders ?? 0;
  const critExp = expData.filter(r => r.risk_level === 'CRITICAL' || r.risk_level === 'HIGH');
  const expCount = critExp.length;
  const expVal = critExp.reduce((sum, r) => sum + (r.remaining_quantity * r.unit_cost), 0);

  const criticalRecs = recData.filter(r => r.priority === 'CRITICAL');

  // Trend chart data
  const trendLabels = ['July 28','July 31','Aug 03','Aug 06','Aug 09','Aug 12','Aug 15 (Fc)','Aug 18 (Fc)','Aug 21 (Fc)'];
  const actualData = [1200,1340,1100,1420,1500,1610,null,null,null];
  const forecastData = [null,null,null,null,null,1610,1720,1790,1850];

  // Donut data
  let healthy=0, warning=0, low=0, critical=0;
  invData.forEach(i => {
    if (i.days_of_inventory < i.lead_time_days) critical++;
    else if (i.available_inventory < i.reorder_point) low++;
    else if (i.available_inventory < i.reorder_point * 1.2) warning++;
    else healthy++;
  });

  // DOI bar
  const dcMap = {};
  invData.forEach(i => {
    const n = i.dc_name;
    if (!dcMap[n]) dcMap[n] = { sum: 0, count: 0 };
    dcMap[n].sum += i.days_of_inventory;
    dcMap[n].count++;
  });
  const doiLabels = Object.keys(dcMap).map(l => l.replace(' DC',''));
  const doiData = Object.values(dcMap).map(v => v.sum / v.count);

  const chartOpts = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { labels: { color: legendColor() } } },
    scales: {
      x: { grid: { color: gridColor() }, ticks: { color: tickColor() } },
      y: { grid: { color: gridColor() }, ticks: { color: tickColor() } },
    },
  };

  return (
    <div className="page">
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
          <div className="metric-delta delta-warn"><i className="fa-solid fa-clock" /> Value: ${expVal.toLocaleString(undefined,{maximumFractionDigits:0})}</div>
        </div>
        <div className="card metric-card">
          <div className="metric-title">Stock Transfers</div>
          <div className="metric-value" style={{color:'var(--accent-sky)'}}>{transfers}</div>
          <div className="metric-delta delta-info"><i className="fa-solid fa-right-left" /> Rebalancing active</div>
        </div>
        <div className="card metric-card">
          <div className="metric-title">Replenishments</div>
          <div className="metric-value">{replenishments}</div>
          <div className="metric-delta delta-pos"><i className="fa-solid fa-truck" /> Supplier orders</div>
        </div>
      </div>

      <div className="grid-2-1">
        <div className="card">
          <div className="summary-box">
            <strong><i className="fa-solid fa-clipboard-list" /> MedCare Pharma Executive Summary:</strong><br />
            {sumData.summary}
          </div>
          <h2 className="section-title"><i className="fa-solid fa-chart-line" /> Daily Sales Trend &amp; sensing forecast</h2>
          <div className="chart-container">
            <Line data={{
              labels: trendLabels,
              datasets: [
                { label:'Historical Actual Sales', data:actualData, borderColor:'#6366f1', backgroundColor:'rgba(99,102,241,0.1)', borderWidth:3, fill:true, tension:0.3 },
                { label:'Sensing Demand Forecast', data:forecastData, borderColor:'#10b981', borderDash:[5,5], borderWidth:3, tension:0.3 },
              ]
            }} options={chartOpts} />
          </div>
        </div>
        <div className="card" style={{display:'flex',flexDirection:'column',gap:'20px'}}>
          <div>
            <h2 className="section-title"><i className="fa-solid fa-chart-pie" /> Network Stock Levels</h2>
            <div className="chart-donut-container">
              <Doughnut data={{
                labels:['Healthy Stock','Approaching ROP','Low Stock','Imminent Stockout'],
                datasets:[{data:[healthy,warning,low,critical],backgroundColor:['#10b981','#f59e0b','#f97316','#f43f5e'],borderColor:'#0e1117',borderWidth:2}]
              }} options={{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}}} />
            </div>
          </div>
          <div>
            <h2 className="section-title"><i className="fa-solid fa-warehouse" /> DOI by Distribution Center</h2>
            <div className="chart-donut-container" style={{height:'150px'}}>
              <Bar data={{
                labels:doiLabels,
                datasets:[{label:'Average DOI',data:doiData,backgroundColor:'rgba(99,102,241,0.45)',borderColor:'#6366f1',borderWidth:1.5,borderRadius:4}]
              }} options={{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{display:false},ticks:{color:tickColor(),font:{size:9}}},y:{grid:{color:gridColor()},ticks:{color:tickColor(),font:{size:9}}}}}} />
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="section-title" style={{color:'var(--accent-rose)'}}><i className="fa-solid fa-bell" /> Critical Priority Alerts</h2>
        <div className="table-container">
          <table>
            <thead>
              <tr><th>SKU</th><th>Distribution Center</th><th>Action Type</th><th>Quantity</th><th>Risk Rationale</th><th>Expected Impact</th></tr>
            </thead>
            <tbody>
              {criticalRecs.length === 0 ? (
                <tr><td colSpan={6} style={{textAlign:'center',color:'var(--text-secondary)'}}>
                  <i className="fa-solid fa-circle-check" style={{color:'var(--accent-emerald)'}} /> No critical priority alerts triggered.
                </td></tr>
              ) : criticalRecs.map(r => {
                const sku = skus.find(s => s.sku_id === r.sku_id);
                const dc = dcs.find(d => d.dc_id === r.dc_id);
                return (
                  <tr key={r.recommendation_id}>
                    <td><strong>{sku?.name || r.sku_id}</strong> <span style={{fontSize:'0.75rem',color:'var(--text-secondary)'}}>({r.sku_id})</span></td>
                    <td>{dc?.name || r.dc_id}</td>
                    <td><Badge label={r.action_type} /></td>
                    <td><strong>{parseInt(r.quantity)}</strong></td>
                    <td>{r.reason}</td>
                    <td style={{color:'var(--accent-emerald)'}}>{r.expected_impact}</td>
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
