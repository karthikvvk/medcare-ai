import React, { useState, useEffect, useCallback, useRef } from 'react';
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
import Surge from './pages/Surge';
import { getSKUs, getDCs, generateForecasts, getRecommendations, DATE } from './api';

function AppContent() {
  const [activePage, setActivePage] = useState('overview');
  const [theme, setTheme] = useState('dark');
  const [skus, setSkus] = useState([]);
  const [dcs, setDcs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0); // force page re-mount on refresh
  const [actionPriority, setActionPriority] = useState('CRITICAL'); // deep-link priority for Action Center
  const [actionFilterSku, setActionFilterSku] = useState(null); // deep-link specific SKU
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

  // Navigate to a page, optionally pre-setting the Action Center priority filter
  const navigateTo = useCallback((page, opts = {}) => {
    if (opts.actionPriority) setActionPriority(opts.actionPriority);
    if (opts.filterSku !== undefined) setActionFilterSku(opts.filterSku);
    setActivePage(page);
  }, []);

  const pageProps = { skus, dcs, refreshKey, onNavigate: navigateTo };

  let PageComponent;
  switch (activePage) {
    case 'overview':    PageComponent = <Overview    {...pageProps} />; break;
    case 'forecast':    PageComponent = <Forecast    {...pageProps} />; break;
    case 'inventory':   PageComponent = <Inventory   {...pageProps} />; break;
    case 'expiry':      PageComponent = <Expiry      {...pageProps} />; break;
    case 'replenish':   PageComponent = <Replenishments {...pageProps} />; break;
    case 'transfers':   PageComponent = <Transfers   {...pageProps} />; break;
    case 'actions':     PageComponent = <Actions     {...pageProps} initialPriority={actionPriority} filterSku={actionFilterSku} />; break;
    case 'simulation':  PageComponent = <Simulation  {...pageProps} />; break;
    case 'explorer':    PageComponent = <Explorer    {...pageProps} />; break;
    case 'surge':       PageComponent = <Surge       {...pageProps} />; break;
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
