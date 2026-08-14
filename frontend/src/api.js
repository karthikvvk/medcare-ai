// MedCare AI — Centralized API layer
const API_BASE = '/api';

async function apiFetch(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

export const DATE = '2026-08-12';

export const getSKUs = () => apiFetch(`${API_BASE}/dashboard/skus`);
export const getDCs = () => apiFetch(`${API_BASE}/dashboard/distribution-centers`);
// Summary uses date_str (not date) as query param
export const getSummary = (date = DATE) => apiFetch(`${API_BASE}/dashboard/summary?date_str=${date}`);
export const getModelMetrics = () => apiFetch(`${API_BASE}/dashboard/model-metrics`);
export const getInventoryStatus = (date = DATE) => apiFetch(`${API_BASE}/inventory/status?date_str=${date}`);
export const getRecommendations = (date = DATE, regenerate = false) =>
  apiFetch(`${API_BASE}/recommendations?date_str=${date}&regenerate=${regenerate}`);
export const getExpiryRisks = (date = DATE) => apiFetch(`${API_BASE}/inventory/expiry-risks?date_str=${date}`);
export const getExpiryPredictions = (date = DATE) => apiFetch(`${API_BASE}/inventory/expiry-predictions?date_str=${date}`);
export const getTransfers = () => apiFetch(`${API_BASE}/recommendations/transfers`);
export const getForecastComparison = (predDate, skuId, dcId) =>
  apiFetch(`${API_BASE}/forecast/historical-comparison?prediction_date=${predDate}&sku_id=${skuId}&dc_id=${dcId}`);
// POST - generate forecasts on demand
export const generateForecasts = (date = DATE) =>
  apiFetch(`${API_BASE}/forecast/generate?prediction_date=${date}`, { method: 'POST' });
// POST - update recommendation status
export const updateRecStatus = (recId, status) =>
  apiFetch(`${API_BASE}/recommendations/${recId}/status?status=${status}`, { method: 'POST' });
// POST - run simulation
export const runSimulation = (date, body) =>
  apiFetch(`${API_BASE}/recommendations/simulate?date_str=${date}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

// Surge Management
export const getSurgeSummary = () => apiFetch(`${API_BASE}/surge/summary`);
export const getSurgePredictions = (riskLevel = null) =>
  apiFetch(`${API_BASE}/surge/predictions${riskLevel ? `?risk_level=${riskLevel}` : ''}`);
export const getSurgeTopProducts = () => apiFetch(`${API_BASE}/surge/top-products`);
