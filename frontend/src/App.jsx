import React, { useState, useEffect } from 'react';
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
  const showToast = useToast();

  useEffect(() => {
    Promise.all([getSKUs(), getDCs()])
      .then(([s, d]) => {
        setSkus(s);
        setDcs(d);
        setLoading(false);
      })
      .catch(e => {
        showToast('Failed to load master data', 'critical');
        setLoading(false);
      });
  }, [showToast]);

  const toggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    document.body.className = nextTheme + '-theme';
  };

  const handleRefreshPrediction = async () => {
    showToast("Running prediction models on demand...", "info");
    try {
      await generateForecasts();
      await getRecommendations(DATE, true);
      showToast("Prediction and recommendations updated successfully!", "success");
      // trigger rerender
      setActivePage(p => p); 
    } catch (e) {
      showToast("Error running prediction.", "critical");
    }
  };

  let PageComponent;
  switch (activePage) {
    case 'overview': PageComponent = <Overview skus={skus} dcs={dcs} />; break;
    case 'forecast': PageComponent = <Forecast skus={skus} dcs={dcs} />; break;
    case 'inventory': PageComponent = <Inventory dcs={dcs} />; break;
    case 'expiry': PageComponent = <Expiry />; break;
    case 'replenish': PageComponent = <Replenishments skus={skus} dcs={dcs} />; break;
    case 'transfers': PageComponent = <Transfers skus={skus} dcs={dcs} />; break;
    case 'actions': PageComponent = <Actions skus={skus} dcs={dcs} />; break;
    case 'simulation': PageComponent = <Simulation skus={skus} dcs={dcs} />; break;
    case 'explorer': PageComponent = <Explorer />; break;
    default: PageComponent = <Overview skus={skus} dcs={dcs} />;
  }

  return (
    <div className="app-container">
      <Sidebar activePage={activePage} onNavigate={setActivePage} />
      <main className="main-content">
        <Header activePage={activePage} theme={theme} onToggleTheme={toggleTheme} onRefreshPrediction={handleRefreshPrediction} />
        <div className="page-container">
          {loading ? <div className="loading"><i className="fa-solid fa-circle-notch fa-spin" /> Loading Core Engine...</div> : PageComponent}
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
