import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import { ToastProvider, useToast } from './components/Toast';
import Overview from './pages/Overview';
import Forecast from './pages/Forecast';
import Inventory from './pages/Inventory';
import Expiry from './pages/Expiry';
import Replenishments from './pages/Replenishments';
import Transfers from './pages/Transfers';
import Actions from './pages/Actions';
import Simulation from './pages/Simulation';
import Explorer from './pages/Explorer';
import { getSKUs, getDCs, generateForecasts, getRecommendations, DATE } from './api';

function AppContent() {
  const [activePage, setActivePage] = useState('overview');
  const [theme, setTheme] = useState('dark');
  const [skus, setSkus] = useState([]);
  const [dcs, setDcs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0); // force page re-mount on refresh
  const showToast = useToast();

  useEffect(() => {
    // Apply saved theme on mount
    const saved = localStorage.getItem('medcare-theme') || 'dark';
    setTheme(saved);
    document.body.className = saved === 'light' ? 'light-theme' : '';

    Promise.all([getSKUs(), getDCs()])
      .then(([s, d]) => {
        setSkus(s);
        setDcs(d);
        setLoading(false);
      })
      .catch(() => {
        showToast('Failed to load master data. Is the backend running?', 'critical');
        setLoading(false);
      });
  }, [showToast]);

  const toggleTheme = useCallback(() => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    localStorage.setItem('medcare-theme', nextTheme);
    document.body.className = nextTheme === 'light' ? 'light-theme' : '';
  }, [theme]);

  const handleRefreshPrediction = useCallback(async () => {
    showToast('Running prediction models on demand...', 'info');
    try {
      await generateForecasts(DATE);
      await getRecommendations(DATE, true);
      showToast('Prediction and recommendations updated!', 'success');
      // Force all page components to re-fetch by remounting
      setRefreshKey(k => k + 1);
    } catch (e) {
      showToast(`Error running prediction: ${e.message}`, 'critical');
    }
  }, [showToast]);

  const pageProps = { skus, dcs, refreshKey };

  let PageComponent;
  switch (activePage) {
    case 'overview':    PageComponent = <Overview    {...pageProps} />; break;
    case 'forecast':    PageComponent = <Forecast    {...pageProps} />; break;
    case 'inventory':   PageComponent = <Inventory   {...pageProps} />; break;
    case 'expiry':      PageComponent = <Expiry      {...pageProps} />; break;
    case 'replenish':   PageComponent = <Replenishments {...pageProps} />; break;
    case 'transfers':   PageComponent = <Transfers   {...pageProps} />; break;
    case 'actions':     PageComponent = <Actions     {...pageProps} />; break;
    case 'simulation':  PageComponent = <Simulation  {...pageProps} />; break;
    case 'explorer':    PageComponent = <Explorer    {...pageProps} />; break;
    default:            PageComponent = <Overview    {...pageProps} />;
  }

  return (
    <div className="app-container">
      <Sidebar activePage={activePage} onNavigate={setActivePage} />
      <main className="main-content">
        <Header
          activePage={activePage}
          theme={theme}
          onToggleTheme={toggleTheme}
          onRefreshPrediction={handleRefreshPrediction}
        />
        <div className="page-container">
          {loading ? (
            <div className="loading" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px', height: '300px', fontSize: '1.2rem', color: 'var(--text-secondary)' }}>
              <i className="fa-solid fa-circle-notch fa-spin" style={{ color: 'var(--accent-indigo)' }} />
              Loading MedCare Control Tower...
            </div>
          ) : PageComponent}
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <AppContent />
    </ToastProvider>
  );
}
