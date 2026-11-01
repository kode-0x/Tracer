import React, { useState, useEffect } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  HelpCircle,
  Play,
  RotateCcw,
  Activity,
  Server,
  Database,
  ArrowRight,
  ShieldAlert,
  Terminal,
  Clock,
  Layers,
  ChevronRight,
  Info,
  CheckCircle2,
  FileText
} from 'lucide-react';

const API_BASE = '/api';

export default function App() {
  const [scenarios, setScenarios] = useState([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState(null);
  const [currentScenarioData, setCurrentScenarioData] = useState(null);
  const [loadingScenarios, setLoadingScenarios] = useState(true);
  const [loadingInvestigation, setLoadingInvestigation] = useState(false);
  const [error, setError] = useState(null);

  // Investigation State
  const [investigationResult, setInvestigationResult] = useState(null);
  const [activeStepIndex, setActiveStepIndex] = useState(-1);
  const [autoPlaying, setAutoPlaying] = useState(false);
  const [showRawReport, setShowRawReport] = useState(false);

  // Load scenarios on mount
  useEffect(() => {
    fetchScenarios();
  }, []);

  // When scenario changes, fetch its full details and reset investigation
  useEffect(() => {
    if (selectedScenarioId) {
      fetchScenarioDetails(selectedScenarioId);
    }
  }, [selectedScenarioId]);

  // Auto-play step-through timer
  useEffect(() => {
    let timer;
    if (autoPlaying && investigationResult) {
      if (activeStepIndex < investigationResult.investigation_steps.length - 1) {
        timer = setTimeout(() => {
          setActiveStepIndex(prev => prev + 1);
        }, 1100);
      } else {
        setAutoPlaying(false);
      }
    }
    return () => clearTimeout(timer);
  }, [autoPlaying, activeStepIndex, investigationResult]);

  const fetchScenarios = async () => {
    try {
      setLoadingScenarios(true);
      setError(null);
      const res = await fetch(`${API_BASE}/scenarios`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to fetch scenarios`);
      const data = await res.json();
      setScenarios(data.scenarios || []);
      if (data.scenarios && data.scenarios.length > 0) {
        setSelectedScenarioId(data.scenarios[0].incident_id);
      }
    } catch (err) {
      setError(`Cannot connect to Tracer backend server: ${err.message}. Ensure backend is running.`);
    } finally {
      setLoadingScenarios(false);
    }
  };

  const fetchScenarioDetails = async (id) => {
    try {
      setInvestigationResult(null);
      setActiveStepIndex(-1);
      setAutoPlaying(false);
      const res = await fetch(`${API_BASE}/scenarios/${id}`);
      if (!res.ok) throw new Error(`Failed to load incident ${id}`);
      const data = await res.json();
      setCurrentScenarioData(data);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleStartInvestigation = async (stepMode = false) => {
    if (!selectedScenarioId) return;
    try {
      setLoadingInvestigation(true);
      setError(null);
      const res = await fetch(`${API_BASE}/investigate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: selectedScenarioId })
      });
      if (!res.ok) throw new Error(`Investigation failed: HTTP ${res.status}`);
      const data = await res.json();
      setInvestigationResult(data);

      if (stepMode) {
        setActiveStepIndex(0);
        setAutoPlaying(false);
      } else {
        // Fast animated progression
        setActiveStepIndex(0);
        setAutoPlaying(true);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingInvestigation(false);
    }
  };

  const handleReset = () => {
    setInvestigationResult(null);
    setActiveStepIndex(-1);
    setAutoPlaying(false);
  };

  // Compute displayed evaluations based on current step
  const getDisplayedEvaluations = () => {
    if (!investigationResult) {
      // Baseline before investigation
      if (!currentScenarioData) return [];
      return currentScenarioData.hypotheses.map(h => ({
        ...h,
        status: 'unresolved',
        supporting_evidence: [],
        contradicting_evidence: []
      }));
    }

    if (activeStepIndex === -1) {
      return investigationResult.final_evaluations;
    }

    const currentStep = investigationResult.investigation_steps[activeStepIndex];
    if (currentStep && currentStep.evaluations_after_step) {
      return currentStep.evaluations_after_step;
    }

    return investigationResult.final_evaluations;
  };

  const displayedSteps = investigationResult
    ? (activeStepIndex >= 0
      ? investigationResult.investigation_steps.slice(0, activeStepIndex + 1)
      : investigationResult.investigation_steps)
    : [];

  const isInvestigationFinished = investigationResult && (
    activeStepIndex === -1 || activeStepIndex === investigationResult.investigation_steps.length - 1
  );

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Top Banner & Header */}
      <header style={{
        borderBottom: '1px solid var(--border-subtle)',
        background: 'rgba(10, 13, 20, 0.95)',
        backdropFilter: 'blur(8px)',
        position: 'sticky',
        top: 0,
        zIndex: 50,
        padding: '12px 24px'
      }}>
        <div style={{ maxWidth: 1400, margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              background: 'linear-gradient(135deg, #6366f1, #3b82f6)',
              padding: '8px 12px',
              borderRadius: 8,
              fontWeight: 800,
              fontSize: '1.1rem',
              letterSpacing: '0.05em',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              boxShadow: '0 4px 12px rgba(99, 102, 241, 0.35)'
            }}>
              <Activity size={20} color="#fff" />
              Tracer
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>Autonomous RCA & Diagnostic Engine</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Information-Gain Triage • Ground-Truth Independent
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div className="simulated-pill">
              Simulated Telemetry Environment
            </div>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: '0.8rem',
              padding: '4px 10px',
              borderRadius: 6,
              background: error ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
              border: `1px solid ${error ? 'rgba(239, 68, 68, 0.3)' : 'rgba(16, 185, 129, 0.3)'}`,
              color: error ? '#f87171' : '#34d399'
            }}>
              <span style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                backgroundColor: error ? '#ef4444' : '#10b981'
              }}></span>
              {error ? 'API Offline' : 'Engine Connected'}
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main style={{ maxWidth: 1400, margin: '0 auto', padding: '24px 20px', flex: 1, width: '100%' }}>

        {/* Error Alert */}
        {error && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.12)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            color: '#fca5a5',
            padding: '12px 16px',
            borderRadius: 8,
            marginBottom: 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <AlertTriangle size={18} />
              <span>{error}</span>
            </div>
            <button
              onClick={fetchScenarios}
              style={{
                background: '#ef4444',
                color: '#fff',
                border: 'none',
                padding: '4px 12px',
                borderRadius: 4,
                cursor: 'pointer',
                fontSize: '0.8rem',
                fontWeight: 600
              }}
            >
              Retry
            </button>
          </div>
        )}

        {/* Section 1: Scenario Selector */}
        <section style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <h2 style={{ fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Layers size={16} /> Select Incident Scenario
            </h2>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-faint)' }}>
              Choose a scenario to investigate with autonomous probe triage
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12 }}>
            {scenarios.map((sc) => {
              const isSelected = sc.incident_id === selectedScenarioId;
              const sevColor = sc.severity === 'CRITICAL' ? '#ef4444' : sc.severity === 'HIGH' ? '#f97316' : '#eab308';
              return (
                <div
                  key={sc.incident_id}
                  onClick={() => setSelectedScenarioId(sc.incident_id)}
                  className={isSelected ? 'glass-panel-elevated' : 'glass-panel'}
                  style={{
                    padding: '14px 16px',
                    cursor: 'pointer',
                    transition: 'all 0.18s ease',
                    position: 'relative',
                    borderColor: isSelected ? 'var(--accent-indigo)' : 'var(--border-subtle)',
                    boxShadow: isSelected ? '0 0 16px rgba(99, 102, 241, 0.25)' : 'none'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{
                      fontFamily: 'JetBrains Mono',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      color: isSelected ? 'var(--accent-cyan)' : 'var(--text-muted)'
                    }}>
                      {sc.incident_id}
                    </span>
                    <span style={{
                      fontSize: '0.68rem',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: 4,
                      backgroundColor: `${sevColor}22`,
                      color: sevColor,
                      border: `1px solid ${sevColor}55`
                    }}>
                      {sc.severity}
                    </span>
                  </div>
                  <div style={{ fontWeight: 600, fontSize: '0.92rem', marginBottom: 4 }}>
                    {sc.title}
                  </div>
                  <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Server size={12} /> {sc.service}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Section 2: Active Incident Overview & Action Bar */}
        {currentScenarioData && (
          <section className="glass-panel" style={{ padding: 20, marginBottom: 24 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
              <div style={{ flex: '1 1 500px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                  <span style={{
                    fontFamily: 'JetBrains Mono',
                    fontSize: '0.85rem',
                    background: '#1e293b',
                    padding: '3px 8px',
                    borderRadius: 4,
                    color: 'var(--accent-cyan)',
                    fontWeight: 700
                  }}>
                    {currentScenarioData.incident_id}
                  </span>
                  <h1 style={{ fontSize: '1.35rem', fontWeight: 800 }}>
                    {currentScenarioData.title}
                  </h1>
                </div>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem', marginBottom: 14 }}>
                  {currentScenarioData.description}
                </p>

                {/* Initial Observed Evidence */}
                {currentScenarioData.evidence && currentScenarioData.evidence.length > 0 && (
                  <div>
                    <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-faint)', fontWeight: 700, marginBottom: 6 }}>
                      Initial Contextual Observations ({currentScenarioData.evidence.length})
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {currentScenarioData.evidence.map(ev => (
                        <div key={ev.id} style={{
                          display: 'flex',
                          alignItems: 'baseline',
                          gap: 8,
                          fontSize: '0.82rem',
                          background: 'rgba(30, 41, 59, 0.4)',
                          padding: '6px 10px',
                          borderRadius: 6,
                          borderLeft: '3px solid var(--accent-blue)'
                        }}>
                          <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.75rem', color: 'var(--accent-blue)', fontWeight: 600 }}>
                            [{ev.source}]
                          </span>
                          <span>{ev.observation}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minWidth: 260 }}>
                <button
                  onClick={() => handleStartInvestigation(false)}
                  disabled={loadingInvestigation}
                  style={{
                    background: 'linear-gradient(135deg, #4f46e5, #3b82f6)',
                    color: '#fff',
                    border: 'none',
                    padding: '12px 20px',
                    borderRadius: 8,
                    fontWeight: 700,
                    fontSize: '0.95rem',
                    cursor: loadingInvestigation ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    boxShadow: '0 4px 14px rgba(79, 70, 229, 0.4)',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <Play size={18} fill="#fff" />
                  {loadingInvestigation ? 'Triaging Incident...' : 'Start Investigation'}
                </button>

                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    onClick={() => {
                      if (!investigationResult) {
                        handleStartInvestigation(true);
                      } else if (activeStepIndex < investigationResult.investigation_steps.length - 1) {
                        setActiveStepIndex(prev => prev + 1);
                      }
                    }}
                    disabled={loadingInvestigation || (investigationResult && isInvestigationFinished)}
                    style={{
                      flex: 1,
                      background: 'rgba(30, 41, 59, 0.8)',
                      border: '1px solid var(--border-subtle)',
                      color: 'var(--text-main)',
                      padding: '8px 12px',
                      borderRadius: 6,
                      fontSize: '0.82rem',
                      fontWeight: 600,
                      cursor: (loadingInvestigation || (investigationResult && isInvestigationFinished)) ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 6
                    }}
                  >
                    <ChevronRight size={16} />
                    {investigationResult ? 'Next Step' : 'Step-by-Step'}
                  </button>

                  {investigationResult && (
                    <button
                      onClick={handleReset}
                      style={{
                        background: 'rgba(30, 41, 59, 0.8)',
                        border: '1px solid var(--border-subtle)',
                        color: 'var(--text-muted)',
                        padding: '8px 12px',
                        borderRadius: 6,
                        fontSize: '0.82rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 4
                      }}
                      title="Reset investigation"
                    >
                      <RotateCcw size={14} /> Reset
                    </button>
                  )}
                </div>

                {/* Progress bar if investigation running / completed */}
                {investigationResult && (
                  <div style={{ marginTop: 4 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.74rem', color: 'var(--text-muted)', marginBottom: 4 }}>
                      <span>Investigation Progress</span>
                      <span>
                        {displayedSteps.length} executed (of {investigationResult.total_checks_available ?? investigationResult.investigation_steps.length} available checks)
                      </span>
                    </div>
                    <div style={{ height: 6, background: '#1e293b', borderRadius: 9999, overflow: 'hidden' }}>
                      <div style={{
                        height: '100%',
                        width: `${Math.min(100, (displayedSteps.length / (investigationResult.total_checks_available || investigationResult.investigation_steps.length || 1)) * 100)}%`,
                        background: isInvestigationFinished ? '#10b981' : 'linear-gradient(90deg, #6366f1, #3b82f6)',
                        transition: 'width 0.3s ease'
                      }}></div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </section>
        )}

        {/* Section 3: Dual-Column Live Dashboard */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))', gap: 24, marginBottom: 24 }}>

          {/* Left Column: Live Diagnostic Timeline */}
          <div className="glass-panel" style={{ padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Clock size={18} color="var(--accent-blue)" />
                <h3 style={{ fontSize: '1rem', fontWeight: 700 }}>Autonomous Diagnostic Timeline</h3>
              </div>
              <span className="simulated-pill">Simulated Probes</span>
            </div>

            {displayedSteps.length === 0 ? (
              <div style={{
                padding: '40px 20px',
                textAlign: 'center',
                color: 'var(--text-muted)',
                background: 'rgba(15, 23, 42, 0.4)',
                borderRadius: 8,
                border: '1px dashed var(--border-subtle)'
              }}>
                <Activity size={32} style={{ margin: '0 auto 12px', opacity: 0.4 }} />
                <div style={{ fontWeight: 600, fontSize: '0.95rem', marginBottom: 4 }}>
                  No Diagnostic Checks Executed Yet
                </div>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-faint)' }}>
                  Click "Start Investigation" to begin selecting and evaluating diagnostic probes.
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {displayedSteps.map((step, idx) => {
                  const isSuccess = step.result === 'healthy' || step.result === 'valid' || step.result === 'pass';
                  const isAnomaly = step.result === 'unhealthy' || step.result === 'invalid' || step.result === 'fail';
                  const badgeColor = isAnomaly ? '#ef4444' : isSuccess ? '#10b981' : '#f59e0b';

                  return (
                    <div
                      key={step.step}
                      style={{
                        background: 'rgba(24, 34, 56, 0.7)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 8,
                        padding: 14,
                        position: 'relative'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{
                            background: 'rgba(99, 102, 241, 0.2)',
                            color: 'var(--accent-cyan)',
                            fontFamily: 'JetBrains Mono',
                            fontSize: '0.72rem',
                            fontWeight: 700,
                            padding: '2px 6px',
                            borderRadius: 4
                          }}>
                            STEP {step.step}
                          </span>
                          <span style={{ fontWeight: 700, fontSize: '0.92rem' }}>
                            {step.check_name}
                          </span>
                        </div>

                        <span style={{
                          fontFamily: 'JetBrains Mono',
                          fontSize: '0.75rem',
                          fontWeight: 700,
                          padding: '3px 8px',
                          borderRadius: 4,
                          backgroundColor: `${badgeColor}22`,
                          color: badgeColor,
                          border: `1px solid ${badgeColor}55`
                        }}>
                          {step.result}
                        </span>
                      </div>

                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 8 }}>
                        {step.description}
                      </div>

                      {/* Explainability Callout */}
                      <div style={{
                        background: 'rgba(15, 23, 42, 0.7)',
                        borderLeft: '3px solid var(--accent-indigo)',
                        padding: '6px 10px',
                        borderRadius: '0 6px 6px 0',
                        fontSize: '0.76rem',
                        color: '#cbd5e1'
                      }}>
                        <span style={{ color: 'var(--accent-indigo)', fontWeight: 700 }}>Why this check? </span>
                        {step.selection_reason}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Right Column: Competing Hypotheses Board */}
          <div className="glass-panel" style={{ padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <ShieldAlert size={18} color="var(--accent-indigo)" />
                <h3 style={{ fontSize: '1rem', fontWeight: 700 }}>Competing Hypotheses Evaluation</h3>
              </div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Real-time Evidence Triage
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {getDisplayedEvaluations().map(hyp => {
                const status = hyp.status || 'unresolved';
                const statusStyles = {
                  supported: { bg: 'rgba(16, 185, 129, 0.15)', text: '#34d399', border: 'rgba(16, 185, 129, 0.4)', icon: CheckCircle },
                  contradicted: { bg: 'rgba(239, 68, 68, 0.15)', text: '#f87171', border: 'rgba(239, 68, 68, 0.4)', icon: XCircle },
                  mixed: { bg: 'rgba(245, 158, 11, 0.15)', text: '#fbbf24', border: 'rgba(245, 158, 11, 0.4)', icon: AlertTriangle },
                  unresolved: { bg: 'rgba(100, 116, 139, 0.15)', text: '#94a3b8', border: 'rgba(100, 116, 139, 0.4)', icon: HelpCircle }
                }[status];

                const IconComponent = statusStyles.icon;

                return (
                  <div
                    key={hyp.id}
                    style={{
                      background: 'rgba(24, 34, 56, 0.7)',
                      border: `1px solid ${status === 'supported' ? 'rgba(16, 185, 129, 0.5)' : 'var(--border-subtle)'}`,
                      borderRadius: 8,
                      padding: 14,
                      boxShadow: status === 'supported' ? '0 0 12px rgba(16, 185, 129, 0.15)' : 'none'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{
                          fontFamily: 'JetBrains Mono',
                          fontSize: '0.75rem',
                          fontWeight: 700,
                          color: 'var(--text-muted)'
                        }}>
                          {hyp.id}
                        </span>
                        <span style={{ fontWeight: 700, fontSize: '0.94rem' }}>
                          {hyp.name}
                        </span>
                      </div>

                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        padding: '2px 8px',
                        borderRadius: 4,
                        backgroundColor: statusStyles.bg,
                        color: statusStyles.text,
                        border: `1px solid ${statusStyles.border}`
                      }}>
                        <IconComponent size={12} />
                        {status}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 10 }}>
                      {hyp.description}
                    </div>

                    {/* Evidence points */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {hyp.supporting_evidence && hyp.supporting_evidence.map((ev, i) => (
                        <div key={i} style={{ fontSize: '0.75rem', color: '#6ee7b7', display: 'flex', alignItems: 'baseline', gap: 6 }}>
                          <span style={{ color: '#10b981' }}>+</span>
                          <span>{ev}</span>
                        </div>
                      ))}

                      {hyp.contradicting_evidence && hyp.contradicting_evidence.map((ev, i) => (
                        <div key={i} style={{ fontSize: '0.75rem', color: '#fca5a5', display: 'flex', alignItems: 'baseline', gap: 6 }}>
                          <span style={{ color: '#ef4444' }}>-</span>
                          <span>{ev}</span>
                        </div>
                      ))}

                      {(!hyp.supporting_evidence || hyp.supporting_evidence.length === 0) &&
                        (!hyp.contradicting_evidence || hyp.contradicting_evidence.length === 0) && (
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-faint)', fontStyle: 'italic' }}>
                            No direct evidence signals observed yet.
                          </div>
                        )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Section 4: Final Root-Cause Assessment & Action Plan Card */}
        {investigationResult && isInvestigationFinished && (
          <section className="glass-panel-elevated" style={{ padding: 24, marginBottom: 24, borderLeft: '4px solid #10b981' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <CheckCircle2 size={24} color="#10b981" />
                <h3 style={{ fontSize: '1.2rem', fontWeight: 800 }}>Investigation Conclusion & Root Cause</h3>
              </div>
              <button
                onClick={() => setShowRawReport(!showRawReport)}
                style={{
                  background: 'rgba(30, 41, 59, 0.7)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-muted)',
                  padding: '6px 12px',
                  borderRadius: 6,
                  fontSize: '0.78rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6
                }}
              >
                <FileText size={14} />
                {showRawReport ? 'Hide Terminal Report' : 'View Full Terminal Report'}
              </button>
            </div>

            {investigationResult.leading_hypothesis ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 20 }}>
                {/* Leading Hypothesis Box */}
                <div style={{
                  background: investigationResult.leading_hypothesis.is_decisive ? 'rgba(16, 185, 129, 0.08)' : 'rgba(245, 158, 11, 0.08)',
                  border: `1px solid ${investigationResult.leading_hypothesis.is_decisive ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
                  borderRadius: 8,
                  padding: 16
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{
                      fontSize: '0.75rem',
                      textTransform: 'uppercase',
                      color: investigationResult.leading_hypothesis.is_decisive ? '#34d399' : '#fbbf24',
                      fontWeight: 800,
                      letterSpacing: '0.06em'
                    }}>
                      {investigationResult.leading_hypothesis.is_decisive ? 'Confirmed Leading Root Cause' : 'Probable Root Cause (Incomplete Triage)'}
                    </span>
                    <span style={{
                      fontSize: '0.7rem',
                      padding: '2px 6px',
                      borderRadius: 4,
                      fontWeight: 700,
                      background: investigationResult.leading_hypothesis.is_decisive ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                      color: investigationResult.leading_hypothesis.is_decisive ? '#10b981' : '#f59e0b'
                    }}>
                      {investigationResult.leading_hypothesis.is_decisive ? 'Decisive' : 'Alternatives Unresolved'}
                    </span>
                  </div>
                  <div style={{ fontSize: '1.15rem', fontWeight: 800, marginBottom: 6 }}>
                    {investigationResult.leading_hypothesis.id} — {investigationResult.leading_hypothesis.name}
                  </div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: 10 }}>
                    {investigationResult.leading_hypothesis.description}
                  </div>
                  <div style={{ fontSize: '0.76rem', color: '#fbbf24', background: 'rgba(245, 158, 11, 0.1)', padding: '6px 10px', borderRadius: 4 }}>
                    {investigationResult.leading_hypothesis.is_decisive
                      ? 'Confidence Note: Supported by simulated diagnostic telemetry; all alternatives contradicted.'
                      : `Confidence Note: Leading candidate supported; unresolved alternatives: ${(investigationResult.leading_hypothesis.unresolved_alternatives || []).join(', ')}.`}
                  </div>
                </div>

                {/* Remediation Action Box */}
                <div style={{ background: 'rgba(59, 130, 246, 0.08)', border: '1px solid rgba(59, 130, 246, 0.25)', borderRadius: 8, padding: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--accent-blue)', fontWeight: 800, letterSpacing: '0.06em' }}>
                      Recommended Next Action
                    </span>
                    {investigationResult.leading_hypothesis.remediation_safety && (
                      <span style={{
                        fontSize: '0.68rem',
                        fontWeight: 800,
                        padding: '2px 8px',
                        borderRadius: 4,
                        background: investigationResult.leading_hypothesis.remediation_safety.tier === 'OPERATOR_REVIEW_REQUIRED'
                          ? 'rgba(239, 68, 68, 0.2)'
                          : 'rgba(59, 130, 246, 0.2)',
                        color: investigationResult.leading_hypothesis.remediation_safety.tier === 'OPERATOR_REVIEW_REQUIRED'
                          ? '#f87171'
                          : '#60a5fa',
                        border: `1px solid ${investigationResult.leading_hypothesis.remediation_safety.tier === 'OPERATOR_REVIEW_REQUIRED' ? 'rgba(239, 68, 68, 0.4)' : 'rgba(59, 130, 246, 0.4)'}`
                      }}>
                        {investigationResult.leading_hypothesis.remediation_safety.badge}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '0.92rem', color: 'var(--text-main)', lineHeight: 1.6, marginBottom: 10 }}>
                    {investigationResult.leading_hypothesis.recommended_action || "Investigate component telemetry and remediate."}
                  </div>
                  {investigationResult.leading_hypothesis.remediation_safety && (
                    <div style={{
                      fontSize: '0.75rem',
                      color: investigationResult.leading_hypothesis.remediation_safety.tier === 'OPERATOR_REVIEW_REQUIRED' ? '#fca5a5' : '#93c5fd',
                      background: 'rgba(15, 23, 42, 0.5)',
                      padding: '6px 10px',
                      borderRadius: 4,
                      marginBottom: 8
                    }}>
                      Safety Protocol: {investigationResult.leading_hypothesis.remediation_safety.warning}
                    </div>
                  )}
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-faint)' }}>
                    Rationale: {investigationResult.stopping_reason}
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.25)', borderRadius: 8, padding: 16 }}>
                <div style={{ fontSize: '0.8rem', textTransform: 'uppercase', color: '#fbbf24', fontWeight: 800, letterSpacing: '0.06em', marginBottom: 6 }}>
                  Outcome: Ambiguous / Inconclusive Event
                </div>
                <div style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: 6 }}>
                  Telemetry snapshot across checked probes returned healthy or non-discriminating signals.
                </div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 10 }}>
                  Recommended Action: Transient or intermittent disturbance suspected. Enable fine-grained distributed tracing and monitor for recurrence.
                </div>
                <div style={{ fontSize: '0.76rem', color: 'var(--text-faint)' }}>
                  Rationale: {investigationResult.stopping_reason}
                </div>
              </div>
            )}

            {/* Expandable Terminal Report */}
            {showRawReport && (
              <div style={{ marginTop: 20 }}>
                <pre style={{
                  background: '#020617',
                  border: '1px solid #1e293b',
                  borderRadius: 8,
                  padding: 16,
                  color: '#94a3b8',
                  fontSize: '0.8rem',
                  overflowX: 'auto',
                  lineHeight: 1.45
                }}>
                  {investigationResult.report}
                </pre>
              </div>
            )}
          </section>
        )}

      </main>

      {/* Footer */}
      <footer style={{
        borderTop: '1px solid var(--border-subtle)',
        padding: '16px 24px',
        textAlign: 'center',
        fontSize: '0.78rem',
        color: 'var(--text-faint)',
        background: 'rgba(10, 13, 20, 0.95)'
      }}>
        Tracer • Autonomous Root Cause Analysis • Operates ground-truth independent
      </footer>
    </div>
  );
}
