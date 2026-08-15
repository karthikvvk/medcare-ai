import React, { useState, useEffect, useCallback, useRef } from 'react';
import Badge from '../components/Badge';
import { useToast } from '../components/Toast';
import {
  getLiveScenarioStatus,
  simulateLiveScenario,
  resetLiveScenario,
  analyzeLiveScenario,
  commitLiveScenarioRecommendations,
  checkOllamaStatus,
  pullOllamaModel,
  setLiveScenarioMode,
  getLiveNewsHeadlines,
  extractScenarioFromNews
} from '../api';

const SEVERITIES = ['Critical', 'High', 'Medium', 'Low'];
const REGIONS = ['Chennai', 'Bangalore', 'Hyderabad', 'Mumbai', 'Delhi', 'Kolkata', 'Pune', 'Ahmedabad'];
const EVENTS = [
  'Flood',
  'Cyclone',
  'Heavy Rainfall Warning',
  'Heatwave Alert',
  'Dengue Outbreak',
  'Flu / Seasonal Disease Spurt',
  'Viral Disease Outbreak',
  'Water Contamination Emergency'
];

const PRIORITY_CONFIG = {
  CRITICAL: { color: 'var(--accent-rose)',   dot: '#f43f5e', bg: 'rgba(244,63,94,0.08)',  label: '🔴 Critical'  },
  HIGH:     { color: 'var(--accent-orange)', dot: '#f97316', bg: 'rgba(249,115,22,0.08)', label: '🟠 High'      },
  MEDIUM:   { color: 'var(--accent-yellow)', dot: '#f59e0b', bg: 'rgba(245,158,11,0.08)', label: '🟡 Medium'    },
  LOW:      { color: 'var(--accent-indigo)', dot: '#6366f1', bg: 'rgba(99,102,241,0.04)', label: '🟢 Low'       },
};

export default function LiveScenario() {
  const showToast = useToast();
  
  // App States
  const [activeMode, setActiveMode] = useState('NEWS');
  const [activeScenario, setActiveScenario] = useState(null);
  const [ollamaStatus, setOllamaStatus] = useState(null);
  const [newsList, setNewsList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [extractingNews, setExtractingNews] = useState(false);
  const [analysisResults, setAnalysisResults] = useState(null);
  const [committing, setCommitting] = useState(false);
  const [pullingModel, setPullingModel] = useState(false);
  
  // Region-wise tab state
  const [selectedRegion, setSelectedRegion] = useState(null);

  // Simulator Inputs
  const [simEvent, setSimEvent] = useState(EVENTS[0]);
  const [simRegion, setSimRegion] = useState(REGIONS[0]);
  const [simArea, setSimArea] = useState('Velachery');
  const [simSeverity, setSimSeverity] = useState(SEVERITIES[1]); // High

  const intervalRef = useRef(null);

  // Initial load
  const loadStatus = useCallback(async () => {
    try {
      const data = await getLiveScenarioStatus();
      setActiveScenario(data.active_scenario);
      setOllamaStatus(data.ollama_status);
      setActiveMode(data.mode || 'NEWS');

      const news = await getLiveNewsHeadlines();
      setNewsList(news);

      if (data.ollama_status?.pull_status?.status === 'downloading') {
        startPollingOllamaStatus();
      }
    } catch (err) {
      showToast('Error loading live scenario dashboard data.', 'critical');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    loadStatus();
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [loadStatus]);

  const startPollingOllamaStatus = () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setPullingModel(true);
    
    intervalRef.current = setInterval(async () => {
      try {
        const data = await checkOllamaStatus();
        setOllamaStatus(data);
        const pullStatus = data.pull_status;
        if (!pullStatus || pullStatus.status === 'success' || pullStatus.status === 'error') {
          clearInterval(intervalRef.current);
          setPullingModel(false);
          if (pullStatus?.status === 'success') {
            showToast('Ollama model downloaded successfully!', 'success');
            loadStatus();
          } else if (pullStatus?.status === 'error') {
            showToast(`Ollama pull error: ${pullStatus.message}`, 'critical');
          }
        }
      } catch (err) {
        clearInterval(intervalRef.current);
        setPullingModel(false);
      }
    }, 2000);
  };

  const handleModeChange = async (mode) => {
    setLoading(true);
    try {
      await setLiveScenarioMode(mode);
      showToast(`Switched operational mode to ${mode}.`, 'success');
      
      if (mode === 'NEWS') {
        setExtractingNews(true);
        try {
          const extracted = await extractScenarioFromNews();
          setActiveScenario(extracted);
          showToast(`AI successfully parsed news: Detected ${extracted.event} in ${extracted.region}.`, 'success');
        } catch (e) {
          showToast('Failed to auto-extract scenario from news.', 'warning');
        } finally {
          setExtractingNews(false);
        }
      } else if (mode === 'AUTO') {
        await resetLiveScenario();
      }
      
      setAnalysisResults(null);
      loadStatus();
    } catch (err) {
      showToast('Failed to change operational mode.', 'critical');
      setLoading(false);
    }
  };

  const handleFetchAndParseNews = async () => {
    setExtractingNews(true);
    setAnalysisResults(null);
    try {
      const news = await getLiveNewsHeadlines();
      setNewsList(news);
      showToast('Fetched fresh Google News RSS headlines.', 'info');
      
      const extracted = await extractScenarioFromNews();
      setActiveScenario(extracted);
      
      showToast(`AI successfully parsed news: Detected ${extracted.event} in ${extracted.region}.`, 'success');
      loadStatus();
    } catch (err) {
      showToast('Failed to extract scenario from news. Using fallback.', 'warning');
      loadStatus();
    } finally {
      setExtractingNews(false);
    }
  };

  const handleApplySimulation = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await simulateLiveScenario({
        event: simEvent,
        region: simRegion,
        area: simArea,
        severity: simSeverity
      });
      showToast('Live scenario simulation activated.', 'success');
      loadStatus();
      setAnalysisResults(null);
    } catch (err) {
      showToast('Failed to apply simulation config.', 'critical');
      setLoading(false);
    }
  };

  const handlePullModel = async () => {
    try {
      await pullOllamaModel();
      showToast('Model download started in background. Polling progress...', 'info');
      startPollingOllamaStatus();
    } catch (err) {
      showToast('Failed to initiate model pull request.', 'critical');
    }
  };

  const handleRunAnalysis = async () => {
    setAnalyzing(true);
    try {
      const results = await analyzeLiveScenario();
      setAnalysisResults(results);
      // Initialize selected region to the active scenario's region
      const primaryReg = results.active_scenario?.region || 'Chennai';
      setSelectedRegion(primaryReg);
      showToast(`AI analysis completed successfully in ${results.analysis_mode} mode!`, 'success');
    } catch (err) {
      showToast('Live scenario analysis failed. Check server logs.', 'critical');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleCommitRecommendations = async () => {
    setCommitting(true);
    try {
      const res = await commitLiveScenarioRecommendations();
      showToast(res.message, 'success');
      setAnalysisResults(null);
    } catch (err) {
      showToast('Failed to commit emergency recommendations.', 'critical');
    } finally {
      setCommitting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '300px', fontSize: '1.2rem', color: 'var(--text-secondary)' }}>
        <i className="fa-solid fa-circle-notch fa-spin" style={{ color: 'var(--accent-indigo)', marginRight: '10px' }} />
        Analyzing environment...
      </div>
    );
  }

  const isOllamaHealthy = ollamaStatus?.is_connected;
  const isModelReady = ollamaStatus?.is_model_available;
  const targetModelName = ollamaStatus?.target_model || 'llama3.2';
  const pullProgress = ollamaStatus?.pull_status;
  const primaryRegion = activeScenario?.region || 'Chennai';

  return (
    <div className="live-scenario-page" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      
      {/* OLLAMA STATUS BANNER */}
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 24px', borderLeft: `4px solid ${isOllamaHealthy ? (isModelReady ? 'var(--accent-emerald)' : 'var(--accent-amber)') : 'var(--accent-rose)'}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <i className={`fa-solid ${isOllamaHealthy ? 'fa-network-wired' : 'fa-triangle-exclamation'}`} style={{ fontSize: '24px', color: isOllamaHealthy ? (isModelReady ? 'var(--accent-emerald)' : 'var(--accent-amber)') : 'var(--accent-rose)' }} />
          <div>
            <h4 style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
              Ollama Local AI Engine: {isOllamaHealthy ? 'Connected' : 'Offline'}
            </h4>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              {isOllamaHealthy 
                ? (isModelReady 
                    ? `Model "${targetModelName}" is active for News Extraction and Live forecasting.` 
                    : `Ollama is connected, but model "${targetModelName}" is not pulled.`)
                : `Run 'ollama serve' on your system. Using deterministic clinical fallback metrics.`
              }
            </p>
          </div>
        </div>
        
        {isOllamaHealthy && !isModelReady && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px' }}>
            {pullingModel ? (
              <div style={{ minWidth: '180px' }}>
                <div style={{ fontSize: '11px', display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span>Downloading...</span>
                  <span>{pullProgress?.progress || 0}%</span>
                </div>
                <div style={{ height: '6px', background: 'rgba(255,255,255,0.08)', borderRadius: '99px', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${pullProgress?.progress || 0}%`, background: 'var(--accent-amber)', borderRadius: '99px', transition: 'width 0.4s ease' }} />
                </div>
                <div style={{ fontSize: '9px', color: 'var(--text-muted)', marginTop: '2px', textAlign: 'right' }}>
                  {pullProgress?.message}
                </div>
              </div>
            ) : (
              <button className="btn btn-secondary" onClick={handlePullModel}>
                <i className="fa-solid fa-cloud-arrow-down" style={{ marginRight: '6px' }} />
                Pull {targetModelName}
              </button>
            )}
          </div>
        )}
      </div>

      {/* MODE SEGMENT CONTROLS */}
      <div style={{ display: 'flex', gap: '8px', background: 'rgba(255,255,255,0.02)', padding: '6px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.04)', alignSelf: 'flex-start' }}>
        <button className={`btn ${activeMode === 'NEWS' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => handleModeChange('NEWS')} style={{ padding: '8px 16px', fontSize: '0.85rem' }}>
          <i className="fa-solid fa-newspaper" style={{ marginRight: '6px' }} />
          Live News Feed
        </button>
        <button className={`btn ${activeMode === 'SIMULATED' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => handleModeChange('SIMULATED')} style={{ padding: '8px 16px', fontSize: '0.85rem' }}>
          <i className="fa-solid fa-flask" style={{ marginRight: '6px' }} />
          Disaster Simulator
        </button>
        <button className={`btn ${activeMode === 'AUTO' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => handleModeChange('AUTO')} style={{ padding: '8px 16px', fontSize: '0.85rem' }}>
          <i className="fa-solid fa-calendar-days" style={{ marginRight: '6px' }} />
          Seasonal Calendar
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '24px' }}>
        
        {/* LEFT COLUMN: ACTIVE SCENARIO PANEL */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          
          <div className="card" style={{ padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
              <div>
                <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--accent-indigo)', fontWeight: 600 }}>
                  Active Environmental Scenario
                </span>
                <h3 style={{ fontSize: '1.4rem', fontWeight: 600, marginTop: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {extractingNews && <i className="fa-solid fa-circle-notch fa-spin" style={{ color: 'var(--accent-indigo)', fontSize: '1.1rem' }} />}
                  {activeScenario?.event}
                </h3>
              </div>
              <Badge 
                content={activeMode === 'NEWS' ? 'LIVE NEWS FEED' : (activeMode === 'SIMULATED' ? 'SIMULATION' : 'SEASONAL AUTOPILOT')} 
                color={activeMode === 'NEWS' ? 'emerald' : (activeMode === 'SIMULATED' ? 'orange' : 'indigo')} 
              />
            </div>

            {activeMode === 'NEWS' && activeScenario?.rationale && (
              <div style={{ background: 'rgba(6,182,212,0.04)', padding: '12px 16px', borderRadius: '8px', border: '1px solid rgba(6,182,212,0.12)', color: 'var(--text-primary)', fontSize: '0.85rem', marginBottom: '20px', lineHeight: 1.4 }}>
                <strong>AI Headline extraction context:</strong> {activeScenario.rationale}
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '12px 16px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.03)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Region/Area</span>
                <div style={{ fontWeight: 600, marginTop: '2px' }}>{activeScenario?.area}, {activeScenario?.region}</div>
              </div>
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '12px 16px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.03)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Temperature</span>
                <div style={{ fontWeight: 600, marginTop: '2px' }}>{activeScenario?.temperature}°C</div>
              </div>
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '12px 16px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.03)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Precipitation</span>
                <div style={{ fontWeight: 600, marginTop: '2px' }}>{activeScenario?.rainfall} mm</div>
              </div>
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '12px 16px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.03)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Scenario Mode</span>
                <div style={{ fontWeight: 600, marginTop: '2px', fontSize: '0.85rem' }}>{activeScenario?.season}</div>
              </div>
            </div>

            <div style={{ marginTop: '20px' }}>
              <h5 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '8px', fontWeight: 600 }}>
                Primary Health Threat Vector Checklist:
              </h5>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {activeScenario?.possible_diseases?.map((dis, idx) => (
                  <span key={idx} style={{ padding: '6px 12px', background: 'rgba(244,63,94,0.05)', border: '1px solid rgba(244,63,94,0.12)', color: 'var(--accent-rose)', borderRadius: '99px', fontSize: '0.75rem', fontWeight: 500 }}>
                    ⚠️ {dis}
                  </span>
                ))}
              </div>
            </div>

            <div style={{ marginTop: '24px', paddingTop: '20px', borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', gap: '12px' }}>
              <button className="btn btn-primary" onClick={handleRunAnalysis} disabled={analyzing || extractingNews}>
                {analyzing ? (
                  <>
                    <i className="fa-solid fa-circle-notch fa-spin" style={{ marginRight: '8px' }} />
                    Generating AI Predictions...
                  </>
                ) : (
                  <>
                    <i className="fa-solid fa-brain" style={{ marginRight: '8px' }} />
                    Run AI Surge Analysis
                  </>
                )}
              </button>
              {activeMode === 'NEWS' && (
                <button className="btn btn-secondary" onClick={handleFetchAndParseNews} disabled={extractingNews}>
                  <i className="fa-solid fa-sync" style={{ marginRight: '6px' }} />
                  Fetch & Analyze News
                </button>
              )}
            </div>
          </div>

        </div>

        {/* RIGHT COLUMN: SIMULATOR OR LIVE NEWS HEADLINES PANEL */}
        <div>
          {activeMode === 'NEWS' ? (
            <div className="card" style={{ padding: '20px', height: '100%', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <i className="fa-solid fa-newspaper" style={{ color: 'var(--accent-indigo)' }} />
                  Trending Headlines
                </h3>
                <button onClick={handleFetchAndParseNews} disabled={extractingNews} style={{ background: 'none', border: 'none', color: 'var(--accent-indigo)', fontSize: '0.8rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <i className="fa-solid fa-arrows-rotate" /> Refresh
                </button>
              </div>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Real-time headlines from Google News RSS relating to climate, infection alerts, and epidemics in India.
              </p>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', overflowY: 'auto', maxHeight: '310px', paddingRight: '4px' }}>
                {newsList.map((news, idx) => (
                  <div key={idx} style={{ padding: '10px', background: 'rgba(255,255,255,0.01)', border: '1px solid rgba(255,255,255,0.04)', borderRadius: '6px', fontSize: '0.8rem' }}>
                    <a href={news.link} target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'none', color: 'var(--text-primary)', fontWeight: 500, display: 'block', marginBottom: '4px' }}>
                      {news.title}
                    </a>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                      <i className="fa-regular fa-clock" style={{ marginRight: '4px' }} />
                      {news.pub_date}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : activeMode === 'SIMULATED' ? (
            <div className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <i className="fa-solid fa-flask" style={{ color: 'var(--accent-indigo)' }} />
                Disaster Simulator
              </h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Manually simulate an upcoming anomaly to analyze shortages and direct medical stocks before critical impacts.
              </p>

              <form onSubmit={handleApplySimulation} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Anomalous Event</label>
                  <select value={simEvent} onChange={e => setSimEvent(e.target.value)} style={{ padding: '8px', borderRadius: '6px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--text-primary)' }}>
                    {EVENTS.map((e, idx) => (
                      <option key={idx} value={e} style={{ background: 'var(--bg-main)' }}>{e}</option>
                    ))}
                  </select>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Target Region</label>
                  <select value={simRegion} onChange={e => setSimRegion(e.target.value)} style={{ padding: '8px', borderRadius: '6px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--text-primary)' }}>
                    {REGIONS.map((r, idx) => (
                      <option key={idx} value={r} style={{ background: 'var(--bg-main)' }}>{r}</option>
                    ))}
                  </select>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Specific Area</label>
                  <input type="text" value={simArea} onChange={e => setSimArea(e.target.value)} placeholder="e.g. Velachery" style={{ padding: '8px', borderRadius: '6px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--text-primary)' }} />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Threat Severity Level</label>
                  <select value={simSeverity} onChange={e => setSimSeverity(e.target.value)} style={{ padding: '8px', borderRadius: '6px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--text-primary)' }}>
                    {SEVERITIES.map((s, idx) => (
                      <option key={idx} value={s} style={{ background: 'var(--bg-main)' }}>{s}</option>
                    ))}
                  </select>
                </div>

                <button type="submit" className="btn btn-primary" style={{ marginTop: '8px', background: 'var(--accent-orange)' }}>
                  Apply Simulation Settings
                </button>
              </form>
            </div>
          ) : (
            <div className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <i className="fa-solid fa-circle-info" style={{ color: 'var(--accent-indigo)' }} />
                Calendar Autopilot
              </h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                Seasonal autopilot mode tracks the calendar date and dynamically detects recurring regional environmental threats:
              </p>
              <ul style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <li><strong>Jun - Sep (Monsoon)</strong>: Wet weather, flash floods, waterborne diseases and Dengue risk in Chennai/Bangalore.</li>
                <li><strong>Apr - May (Summer)</strong>: Severe heatwaves, sunstrokes, dehydration formulas in Delhi/North India.</li>
                <li><strong>Nov - Jan (Winter)</strong>: Influenza, flu peaks, bronchitis and respiratory issues in Mumbai.</li>
              </ul>
            </div>
          )}
        </div>

      </div>

      {/* ANALYSIS RESULTS PANEL */}
      {analysisResults && (
        <div className="card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--accent-indigo)', fontWeight: 600 }}>
                Analysis Intelligence Report ({analysisResults.model_used})
              </span>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginTop: '2px' }}>
                Proactive Surge Impact Assessment
              </h3>
            </div>
            
            <button className="btn btn-primary" onClick={handleCommitRecommendations} disabled={committing} style={{ background: 'var(--accent-emerald)' }}>
              {committing ? (
                <>
                  <i className="fa-solid fa-circle-notch fa-spin" style={{ marginRight: '8px' }} />
                  Saving...
                </>
              ) : (
                <>
                  <i className="fa-solid fa-check-double" style={{ marginRight: '8px' }} />
                  Commit Recommendations to System
                </>
              )}
            </button>
          </div>

          {/* RISK CLASSIFIER MATRIX */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
            {analysisResults.health_risks?.slice(0, 3).map((risk, idx) => (
              <div key={idx} style={{ padding: '16px', background: 'rgba(255,255,255,0.01)', border: '1px solid rgba(255,255,255,0.04)', borderRadius: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-primary)' }}>{risk.risk_name}</span>
                  <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '4px', background: risk.probability.toLowerCase() === 'high' ? 'rgba(244,63,94,0.1)' : 'rgba(245,158,11,0.1)', color: risk.probability.toLowerCase() === 'high' ? 'var(--accent-rose)' : 'var(--accent-amber)', fontWeight: 600 }}>
                    {risk.probability} Risk
                  </span>
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>{risk.description}</p>
              </div>
            ))}
          </div>

          {/* REGION / DC TAB SELECTOR */}
          <div style={{ marginTop: '10px' }}>
            <h5 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '10px', fontWeight: 600 }}>
              Select Distribution Center to View Specific Impact:
            </h5>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', background: 'rgba(255,255,255,0.01)', padding: '8px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.04)' }}>
              {analysisResults.region_recommendations && Object.keys(analysisResults.region_recommendations).map(reg => {
                const recs = analysisResults.region_recommendations[reg];
                const shortageCount = recs.filter(r => r.shortage > 0).length;
                const isPrimary = reg.toLowerCase() === primaryRegion.toLowerCase();
                return (
                  <button
                    key={reg}
                    className={`btn ${selectedRegion === reg ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => setSelectedRegion(reg)}
                    style={{ padding: '8px 14px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '6px' }}
                  >
                    {isPrimary && <i className="fa-solid fa-star" style={{ color: 'var(--accent-amber)' }} />}
                    {reg} DC
                    {shortageCount > 0 && (
                      <span style={{ background: 'var(--accent-rose)', color: '#fff', fontSize: '10px', padding: '2px 6px', borderRadius: '99px', fontWeight: 'bold' }}>
                        {shortageCount}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* SURGE QUANTITIES TABLE */}
          {selectedRegion && analysisResults.region_recommendations?.[selectedRegion] && (
            <div className="table-container" style={{ margin: 0 }}>
              <table>
                <thead>
                  <tr>
                    <th>SKU Code</th>
                    <th>Product Category</th>
                    <th>DC Current Inventory</th>
                    <th>Predicted Demand Surge</th>
                    <th>7-day Projected Demand</th>
                    <th>Projected Shortage</th>
                    <th>System Action Priority</th>
                    <th>Emergency Logistics Action</th>
                  </tr>
                </thead>
                <tbody>
                  {analysisResults.region_recommendations[selectedRegion].map((item, idx) => {
                    const hasShortage = item.shortage > 0;
                    const priority = item.priority || 'LOW';
                    const priorityColor = PRIORITY_CONFIG[priority]?.color || 'var(--text-secondary)';
                    const priorityBg = PRIORITY_CONFIG[priority]?.bg || 'rgba(255,255,255,0.02)';
                    const priorityLabel = PRIORITY_CONFIG[priority]?.label || 'Low';

                    return (
                      <tr key={idx} style={{ opacity: hasShortage ? 1 : 0.65 }}>
                        <td>
                          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{item.sku_name}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{item.sku_id}</div>
                        </td>
                        <td>
                          <span style={{ fontSize: '0.8rem', background: 'rgba(255,255,255,0.03)', padding: '2px 8px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                            {item.category}
                          </span>
                        </td>
                        <td>{item.current_stock.toFixed(0)} units</td>
                        <td style={{ color: hasShortage ? 'var(--accent-rose)' : 'inherit', fontWeight: hasShortage ? 600 : 'normal' }}>
                          +{item.demand_increase_pct.toFixed(0)}%
                        </td>
                        <td>{item.predicted_demand.toFixed(0)} units</td>
                        <td style={{ color: hasShortage ? 'var(--accent-rose)' : 'inherit', fontWeight: hasShortage ? 600 : 'normal' }}>
                          {hasShortage ? `${item.shortage.toFixed(0)} units` : '0 (Safe)'}
                        </td>
                        <td>
                          <span style={{ padding: '4px 10px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600, color: priorityColor, background: priorityBg }}>
                            {priorityLabel}
                          </span>
                        </td>
                        <td>
                          <div style={{ fontSize: '0.8rem', fontWeight: 500, color: hasShortage ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                            {hasShortage ? (
                              <>
                                <i className={`fa-solid ${item.source_dc_id ? 'fa-right-left' : 'fa-truck-ramp-box'}`} style={{ color: 'var(--accent-indigo)', marginRight: '6px' }} />
                                {item.recommended_action}
                              </>
                            ) : (
                              <span style={{ color: 'var(--text-muted)' }}>✓ Supply Adequate</span>
                            )}
                          </div>
                          {hasShortage && (
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px', maxWidth: '300px' }}>
                              {item.rationale}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
