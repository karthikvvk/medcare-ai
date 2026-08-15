import React, { useState } from 'react';
import { runSimulation, DATE } from '../api';
import { useToast } from '../components/Toast';
import Badge from '../components/Badge';

export default function Simulation({ skus, dcs }) {
  const [demand, setDemand] = useState(0);
  const [promo, setPromo] = useState(0);
  const [lt, setLt] = useState(0);
  const [inv, setInv] = useState(0);
  const [results, setResults] = useState(null);
  const showToast = useToast();

  const handleRun = async () => {
    showToast("Executing stress test simulation...", "info");
    try {
      const data = await runSimulation(DATE, {
        demand_increase_pct: demand,
        promotion_impact_pct: promo,
        supplier_lead_time_days_offset: lt,
        inventory_reduction_pct: inv,
        seasonality_multiplier: 1.0
      });
      setResults(data);
      showToast("What-If simulation recalculations executed successfully!", "success");
    } catch (e) {
      showToast("Failed to run What-If simulation.", "critical");
    }
  };

  return (
    <div className="page card">
      <h2 className="section-title"><i className="fa-solid fa-flask" /> What-If Simulation Studio</h2>
      
      <div className="sim-controls">
        <Slider id="sim-demand" label="Regional Demand Increase" val={demand} setVal={setDemand} min={0} max={50} step={5} unit="%" prefix="+" />
        <Slider id="sim-promo" label="Promotion Impact Factor" val={promo} setVal={setPromo} min={0} max={50} step={5} unit="%" prefix="+" />
        <Slider id="sim-lt" label="Supplier Lead Time Offset" val={lt} setVal={setLt} min={-5} max={5} step={1} unit=" days" prefix={lt >= 0 ? '+' : ''} />
        <Slider id="sim-inv" label="Available Stock Reduction" val={inv} setVal={setInv} min={0} max={50} step={5} unit="%" prefix="-" />
      </div>

      <div style={{display:'flex', justifyContent:'center', marginBottom:'32px'}}>
        <button className="btn btn-primary" style={{fontSize:'0.95rem', padding:'10px 24px'}} onClick={handleRun}>
          <i className="fa-solid fa-calculator" /> Run What-If Scenario Calculation
        </button>
      </div>

      {results && (
        <div>
          <h2 className="section-title"><i className="fa-solid fa-chart-bar" /> Simulated Impact Comparison</h2>
          <div className="grid-3" style={{gridTemplateColumns:'repeat(auto-fit,minmax(240px,1fr))'}}>
            <div className="card metric-card">
              <div className="metric-title">Stock-out Risk Events</div>
              <div className="metric-value">{results.simulated_stockout_events} DCs</div>
              <div className="metric-delta">
                {results.simulated_stockout_events - results.original_stockout_events >= 0 
                  ? <span className="delta-neg"><i className="fa-solid fa-arrow-up" /> +{results.simulated_stockout_events - results.original_stockout_events} events</span>
                  : <span className="delta-pos"><i className="fa-solid fa-arrow-down" /> {results.simulated_stockout_events - results.original_stockout_events} events</span>
                }
              </div>
            </div>
            <div className="card metric-card">
              <div className="metric-title">Replenishments Required</div>
              <div className="metric-value">+{results.additional_replenishment_units.toLocaleString()} units</div>
              <div className="metric-delta"><span className="delta-neg"><i className="fa-solid fa-plus" /> Additional reorders required</span></div>
            </div>
            <div className="card metric-card">
              <div className="metric-title">Additional Purchasing Spend</div>
              <div className="metric-value">${(results.additional_replenishment_units * 25.0).toLocaleString(undefined, {maximumFractionDigits:2})}</div>
              <div className="metric-delta"><span className="delta-neg"><i className="fa-solid fa-arrow-up-right" /> Extra spend allocated</span></div>
            </div>
          </div>

          <div className="card" style={{marginTop:'24px'}}>
            <h2 className="section-title"><i className="fa-solid fa-list-check" /> Detailed Facility Risk Changes</h2>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>SKU</th><th>Distribution Center</th><th>Orig. Stockout Risk</th>
                    <th>Sim. Stockout Risk</th><th>Orig. Order Qty</th><th>Sim. Order Qty</th><th>Simulated Risk Variance Description</th>
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    const changed = results.details.filter(d => d.original_stockout_risk !== d.simulated_stockout_risk || d.original_replenish_qty !== d.simulated_replenish_qty);
                    if (changed.length === 0) return <tr><td colSpan={7} style={{textAlign:'center',color:'var(--text-secondary)'}}>No Stockout risk status changes or ordering qty variations occurred under these stress parameters.</td></tr>;
                    return changed.map((d, idx) => {
                      const sku = skus.find(s => s.sku_id === d.sku_id);
                      const dc = dcs.find(x => x.dc_id === d.dc_id);
                      return (
                        <tr key={idx}>
                          <td><strong>{sku ? sku.name : d.sku_id}</strong> <span style={{fontSize:'0.75rem',color:'var(--text-secondary)'}}>({d.sku_id})</span></td>
                          <td>{dc ? dc.name : d.dc_id}</td>
                          <td><Badge label={d.original_stockout_risk} /></td>
                          <td><Badge label={d.simulated_stockout_risk} /></td>
                          <td>{parseInt(d.original_replenish_qty)}</td>
                          <td style={{color:'var(--accent-emerald)'}}><strong>{parseInt(d.simulated_replenish_qty)}</strong></td>
                          <td>{d.reason}</td>
                        </tr>
                      );
                    });
                  })()}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Slider({ id, label, val, setVal, min, max, step, unit, prefix }) {
  return (
    <div className="slider-group">
      <div className="slider-header">
        <label htmlFor={id}>{label}:</label>
        <span className="slider-val">{prefix}{Math.abs(val)}{unit}</span>
      </div>
      <input type="range" id={id} min={min} max={max} step={step} value={val} onChange={e => setVal(Number(e.target.value))} />
    </div>
  );
}
