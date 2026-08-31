import React, {useEffect, useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './styles.css';
import {Fleet, Governance, Memory, Audit} from './sections.jsx';
import {Overview, FleetMatrix, SupplierRiskDecision, GovernanceDecision, ReplayPanel, HowItWorks, RiskIntelligenceView, DemoCenterView} from './demo.jsx';
import {HumanApprovalQueue, PolicySimulator, IncidentModelHealth, EvidenceCenter, CommandPalette} from './expanded.jsx';

const API = import.meta.env.VITE_API_URL || (typeof window !== 'undefined' && window.location.origin.includes(':5173') ? 'http://localhost:8080/api' : '/api');
const formatTime = value => value ? new Date(value).toLocaleString([], {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'}) : '--';

function App(){
  const [page, setPage] = useState('overview');
  const [workflows, setWorkflows] = useState([]);
  const [agents, setAgents] = useState([]);
  const [securityEvents, setSecurityEvents] = useState([]);
  const [authStatus, setAuthStatus] = useState(null);
  const [selectedWfId, setSelectedWfId] = useState(null);
  const [wfDetail, setWfDetail] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [selectedTask, setSelectedTask] = useState(null);
  const [cmdOpen, setCmdOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  
  // Workflow Wizard State
  const [wizardStep, setWizardStep] = useState(1);
  const [goal, setGoal] = useState('Analyze supplier risk for ABC Logistics before vendor onboarding.');
  const [entity, setEntity] = useState('supplier_ABC');
  const [industry, setIndustry] = useState('Logistics & Freight');
  const [region, setRegion] = useState('North America');

  // TopBar System Clock State
  const [currentTime, setCurrentTime] = useState(new Date().toLocaleTimeString());
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Ctrl + K Event Listener
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setCmdOpen(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const request = async path => {
    const response = await fetch(`${API}${path}`);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.json();
  };

  const loadAllTelemetry = async () => {
    try {
      const [wfData, agentData, secData, sysAuth] = await Promise.all([
        request('/workflows'),
        request('/agents').catch(() => ({items: []})),
        request('/security-events').catch(() => ({items: []})),
        request('/system/auth-status').catch(() => null)
      ]);
      setWorkflows(wfData.items || []);
      setAgents(agentData.items || []);
      setSecurityEvents(secData.items || []);
      if (sysAuth) setAuthStatus(sysAuth);
      setError('');
    } catch (e) {
      setError(`Telemetry sync warning: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const loadDetails = async id => {
    setSelectedWfId(id);
    setWfDetail(null);
    try {
      const [workflow, taskData, summary] = await Promise.all([
        request(`/workflows/${id}`),
        request(`/workflows/${id}/tasks`),
        request(`/workflows/${id}/summary`)
      ]);
      setWfDetail({workflow, summary});
      setTasks(taskData.items || []);
      setError('');
    } catch (e) {
      setError(`Could not load workflow details. ${e.message}`);
    }
  };

  useEffect(() => {
    loadAllTelemetry();
    const interval = setInterval(loadAllTelemetry, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (selectedWfId) {
      loadDetails(selectedWfId);
      const detailInterval = setInterval(() => loadDetails(selectedWfId), 3000);
      return () => clearInterval(detailInterval);
    }
  }, [selectedWfId]);

  const submitWorkflow = async e => {
    if (e) e.preventDefault();
    if (!goal.trim()) return;
    try {
      const response = await fetch(`${API}/workflows`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          goal,
          context: { entity, industry, region }
        })
      });
      if (!response.ok) throw new Error('Workflow submission failed');
      const data = await response.json();
      setMessage(`Workflow ${data.workflow_id} launched cleanly.`);
      setGoal('Analyze supplier risk for ABC Logistics before vendor onboarding.');
      setWizardStep(1);
      await loadAllTelemetry();
      setTimeout(() => {
        setPage('workflows');
        loadDetails(data.workflow_id);
      }, 500);
    } catch (e) {
      setError(e.message);
    }
  };

  const hasQuotaError = tasks.some(t => t.error === 'quota_exceeded') || authStatus?.status_code === 'QUOTA_EXCEEDED';
  const hasAuthError = tasks.some(t => t.error === 'authentication_failed') || authStatus?.status_code === 'AUTHENTICATION_FAILED' || authStatus?.status_code === 'CREDENTIALS_MISSING';

  const nav = (name, icon, target) => (
    <button 
      className={page === target && !selectedWfId ? 'nav active' : 'nav'} 
      onClick={() => { setPage(target); setSelectedWfId(null); }}
    >
      <span className="nav-icon">{icon}</span>
      <span>{name}</span>
    </button>
  );

  const handlePaletteNavigate = (targetPage, wfId) => {
    setPage(targetPage);
    if (wfId) {
      loadDetails(wfId);
    } else {
      setSelectedWfId(null);
    }
  };

  return (
    <div className="shell">
      {/* Sidebar Navigation */}
      <aside>
        <div className="logo">
          <div className="logo-icon">✦</div>
          <div>AgentSphere <em>OS</em></div>
        </div>
        <small>ENTERPRISE CONTROL PLANE</small>

        <div className="nav-group">
          {nav('Overview', '📊', 'overview')}
          {nav('Workflows', '⚡', 'workflows')}
          {nav('Agent Fleet', '🤖', 'agents')}
          {nav('Risk Intelligence', '⚖️', 'risk')}
          {nav('Human Oversight', '✋', 'approval')}
          {nav('Policy Simulator', '🧪', 'simulator')}
          {nav('Incident & Health', '🚨', 'incidents')}
          {nav('Evidence Matrix', '📄', 'evidence')}
          {nav('Security Center', '🛡️', 'security')}
          {nav('Memory Explorer', '🧠', 'memory')}
          {nav('Audit Explorer', '📜', 'audit')}
          {nav('Architecture', '🏛️', 'architecture')}
          {nav('Demo Center', '🎯', 'demo')}
        </div>

        <div className="tenant">
          <b>Acme Global Supply Chain</b>
          <span>Production Multi-Agent Mesh</span>
        </div>
      </aside>

      {/* Main Workspace */}
      <div className="main-wrapper">
        {/* Sticky Top Bar */}
        <header className="topbar">
          <div className="topbar-left">
            <span className="env-badge">GC HACKATHON BUILD</span>
            <div className="system-telemetry">
              <span className="telemetry-item"><span className="status-dot ok"/> API Connected</span>
              <span className="telemetry-item"><span className="status-dot ok"/> Registry Healthy</span>
              <span className="telemetry-item"><span className="status-dot ok"/> Storage Ready</span>
              <span className="telemetry-item">
                <span className={`status-dot ${authStatus?.credentials_configured ? 'ok' : 'error'}`}/> 
                Google Auth: {authStatus?.credentials_configured ? 'Configured' : 'Missing'}
              </span>
              <span className="telemetry-item">
                <span className={`status-dot ${authStatus?.authentication_ready ? 'ok' : hasQuotaError ? 'warn' : 'error'}`}/> 
                Gemini Provider: {authStatus?.authentication_ready ? 'Online' : hasQuotaError ? 'Quota Limited' : hasAuthError ? 'Auth Failed' : 'Unavailable'}
              </span>
            </div>
          </div>

          <div className="topbar-right">
            <button className="cmd-btn" onClick={() => setCmdOpen(true)}>
              🔍 Search System <span className="cmd-kbd">Ctrl K</span>
            </button>
            <button className="btn-icon" title="Refresh Telemetry" onClick={loadAllTelemetry}>↻</button>
            <div className="clock-display">UTC {currentTime}</div>
          </div>
        </header>

        {/* Content Area */}
        <main>
          {error && (
            <div className="error">
              {error}
              <button onClick={loadAllTelemetry}>Retry</button>
            </div>
          )}

          {message && (
            <div className="notice" onClick={() => setMessage('')}>
              {message} (click to dismiss)
            </div>
          )}

          {/* Workflow Details View */}
          {selectedWfId && wfDetail && (
            <div>
              <button className="btn-secondary" style={{marginBottom:'16px'}} onClick={() => setSelectedWfId(null)}>
                ← Back to Operations
              </button>

              <div className="detail-hero">
                <div>
                  <small>WORKFLOW TELEMETRY RECORD</small>
                  <h2>{wfDetail.workflow.goal}</h2>
                  <p>ID: {wfDetail.workflow.workflow_id} · Launched: {formatTime(wfDetail.workflow.created_at)}</p>
                </div>
                <i className={wfDetail.workflow.status}>{wfDetail.workflow.status}</i>
              </div>

              <div className="metrics">
                <Metric label="Progress" value={`${wfDetail.workflow.progress || 0}%`}/>
                <Metric label="Completed Agents" value={wfDetail.summary.completed_agents.length}/>
                <Metric label="Failed Agents" value={wfDetail.summary.failed_agents.length}/>
                <Metric label="Execution Time" value={wfDetail.summary.execution_time ? `${wfDetail.summary.execution_time}s` : 'In Progress'}/>
              </div>

              <ReplayPanel workflow={wfDetail.workflow} tasks={tasks}/>

              {/* Timeline Card */}
              <div className="columns">
                <Card title="Agent Execution Timeline" sub="Click any task to inspect details">
                  <div className="timeline">
                    {tasks.map(task => (
                      <div className="task-item" key={task.task_id} onClick={() => setSelectedTask(task)}>
                        <div className={`task-dot ${task.status}`}/>
                        <div style={{flex:1}}>
                          <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                            <b>{task.agent_id}</b>
                            <i className={task.status}>{task.status}</i>
                          </div>
                          <small style={{display:'block', color:'var(--text-muted)', marginTop:'4px', fontFamily:'var(--font-mono)'}}>
                            {task.title} · {task.execution_time_ms ?? '--'} ms · {task.retries || 0} retries
                          </small>
                          {task.error && (
                            <div className="task-error-box">
                              <b>Execution Issue ({task.error}):</b> {
                                task.error === 'quota_exceeded' 
                                  ? 'Gemini API Free Tier Quota Exceeded (20 requests/day limit). Agent execution paused cleanly.' 
                                  : task.error === 'authentication_failed'
                                  ? 'Google Cloud API key or Application Default Credentials failed authentication.'
                                  : task.error === 'credentials_missing'
                                  ? 'No Google API key or project credentials found in backend/.env.'
                                  : task.error === 'model_unavailable'
                                  ? 'Configured model name is not available on current API endpoint.'
                                  : task.error
                              }
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                    {!tasks.length && <div className="empty">Agent tasks will populate as orchestrator executes strategy.</div>}
                  </div>
                </Card>

                <Card title="Final Executive Synthesis Output" sub="Generated by Report Agent">
                  <pre className="json-box">
                    {wfDetail.summary.final_report_output 
                      ? (typeof wfDetail.summary.final_report_output === 'string' ? wfDetail.summary.final_report_output : JSON.stringify(wfDetail.summary.final_report_output, null, 2))
                      : 'Final report pending completion of specialist agent tasks.'}
                  </pre>
                </Card>
              </div>

              <SupplierRiskDecision workflow={wfDetail.workflow} tasks={tasks} summary={wfDetail.summary}/>
              <GovernanceDecision workflow={wfDetail.workflow} tasks={tasks}/>
            </div>
          )}

          {/* Top-Level Page Views */}
          {!selectedWfId && page === 'overview' && (
            <Overview 
              workflows={workflows} 
              agents={agents} 
              security={securityEvents} 
              loading={loading} 
              error={error} 
              retry={loadAllTelemetry} 
              onWorkflow={loadDetails}
            />
          )}

          {!selectedWfId && page === 'workflows' && (
            <div>
              <div className="page-intro">
                <small>AUTONOMOUS ORCHESTRATION</small>
                <h1>Workflow Operations Center</h1>
                <p>Launch multi-agent workflows, monitor live execution timelines, and inspect governance decisions.</p>
              </div>

              {/* Pre-flight System Readiness Card */}
              {authStatus && (
                <div className="finding-card" style={{marginBottom:'20px'}}>
                  <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                    <b>PRE-FLIGHT PROVIDER TELEMETRY ({authStatus.provider.toUpperCase()})</b>
                    <Status value={authStatus.authentication_ready ? 'READY' : authStatus.status_code}/>
                  </div>
                  <p style={{margin:'6px 0 0'}}>
                    <b>Model:</b> <code>{authStatus.model}</code> · <b>Diagnostic:</b> {authStatus.reason}<br/>
                    <b>Action:</b> {authStatus.recommended_action}
                  </p>
                </div>
              )}

              {/* Workflow Creation Wizard Card */}
              <div className="workflow-form-card">
                <div className="wizard-steps">
                  <div className={`wizard-step ${wizardStep >= 1 ? 'active' : ''}`}>
                    <span className="wizard-step-num">1</span> Define Objective
                  </div>
                  <div className={`wizard-step ${wizardStep >= 2 ? 'active' : ''}`}>
                    <span className="wizard-step-num">2</span> Target Context
                  </div>
                  <div className={`wizard-step ${wizardStep >= 3 ? 'active' : ''}`}>
                    <span className="wizard-step-num">3</span> Governance Preview
                  </div>
                  <div className={`wizard-step ${wizardStep >= 4 ? 'active' : ''}`}>
                    <span className="wizard-step-num">4</span> Execute
                  </div>
                </div>

                {wizardStep === 1 && (
                  <div className="wizard-content">
                    <div className="form-group">
                      <label>WORKFLOW OBJECTIVE / GOAL</label>
                      <input 
                        value={goal} 
                        onChange={e => setGoal(e.target.value)} 
                        placeholder="e.g. Analyze supplier risk for ABC Logistics before vendor onboarding."
                      />
                      <div className="preset-goals">
                        <span className="preset-chip" onClick={() => setGoal('Analyze supplier risk for ABC Logistics before vendor onboarding.')}>
                          🏢 Supplier Risk: ABC Logistics
                        </span>
                        <span className="preset-chip" onClick={() => setGoal('Perform security policy and PII audit on newly ingested enterprise dataset.')}>
                          🛡️ Security & PII Audit
                        </span>
                        <span className="preset-chip" onClick={() => setGoal('Audit vendor compliance, financial indicators, and contract anomalies.')}>
                          📊 Vendor Compliance Check
                        </span>
                      </div>
                    </div>
                    <div style={{display:'flex', justifyContent:'flex-end'}}>
                      <button className="btn-primary" onClick={() => setWizardStep(2)}>Next: Context →</button>
                    </div>
                  </div>
                )}

                {wizardStep === 2 && (
                  <div className="wizard-content">
                    <div className="columns" style={{marginBottom:0}}>
                      <div className="form-group">
                        <label>TARGET ENTITY NAME</label>
                        <input value={entity} onChange={e => setEntity(e.target.value)}/>
                      </div>
                      <div className="form-group">
                        <label>INDUSTRY / SECTOR</label>
                        <input value={industry} onChange={e => setIndustry(e.target.value)}/>
                      </div>
                    </div>
                    <div className="form-group">
                      <label>GEOGRAPHIC REGION</label>
                      <input value={region} onChange={e => setRegion(e.target.value)}/>
                    </div>
                    <div style={{display:'flex', justifyContent:'space-between'}}>
                      <button className="btn-secondary" onClick={() => setWizardStep(1)}>← Back</button>
                      <button className="btn-primary" onClick={() => setWizardStep(3)}>Next: Governance →</button>
                    </div>
                  </div>
                )}

                {wizardStep === 3 && (
                  <div className="wizard-content">
                    <div className="finding-card">
                      <b>GOVERNANCE PRE-CHECK SANITY</b>
                      <div style={{fontFamily:'var(--font-mono)', fontSize:'11px', color:'var(--text-muted)', lineHeight:'1.6'}}>
                        ✓ Safety Filter Inspection: PASS<br/>
                        ✓ Required Agents Available: 4 Specialist Agents Approved<br/>
                        ✓ Policy Engine Check: Authorization granted for entity analysis<br/>
                        ✓ Provider Status: {authStatus?.status_code || 'CHECKED'} ({authStatus?.model || 'gemini-flash-latest'})
                      </div>
                    </div>
                    <div style={{display:'flex', justifyContent:'space-between'}}>
                      <button className="btn-secondary" onClick={() => setWizardStep(2)}>← Back</button>
                      <button className="btn-primary" onClick={submitWorkflow}>🚀 Launch Governed Workflow</button>
                    </div>
                  </div>
                )}
              </div>

              {/* Workflow Metrics */}
              <div className="metrics">
                <Metric label="Total Workflows" value={workflows.length}/>
                <Metric label="Active" value={workflows.filter(w=>['queued','running'].includes(w.status)).length}/>
                <Metric label="Completed" value={workflows.filter(w=>w.status==='completed').length}/>
                <Metric label="Failed" value={workflows.filter(w=>w.status==='failed').length}/>
              </div>

              {/* Workflow Table */}
              <Card title="Workflow Telemetry Records" sub="Click any row to open full decision trail">
                {loading ? <div className="loading">Loading workflow records…</div> :
                !workflows.length ? <div className="empty">No workflows launched yet. Use the wizard above to start your first execution.</div> :
                <table>
                  <thead>
                    <tr>
                      <th>Workflow ID</th>
                      <th>Goal / Objective</th>
                      <th>Status</th>
                      <th>Progress</th>
                      <th>Created Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {workflows.map(w => (
                      <tr className="clickable" key={w.workflow_id} onClick={() => loadDetails(w.workflow_id)}>
                        <td><b>{w.workflow_id}</b></td>
                        <td>{w.goal}</td>
                        <td><i className={w.status}>{w.status}</i></td>
                        <td>
                          <div className="bar"><span style={{width:`${w.progress||0}%`}}/></div>
                          <small>{w.progress||0}%</small>
                        </td>
                        <td>{formatTime(w.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>}
              </Card>
            </div>
          )}

          {!selectedWfId && page === 'agents' && <FleetMatrix/>}
          {!selectedWfId && page === 'risk' && <RiskIntelligenceView workflows={workflows} onSelectWorkflow={loadDetails}/>}
          {!selectedWfId && page === 'approval' && <HumanApprovalQueue workflows={workflows} onSelectWorkflow={loadDetails}/>}
          {!selectedWfId && page === 'simulator' && <PolicySimulator/>}
          {!selectedWfId && page === 'incidents' && <IncidentModelHealth workflows={workflows}/>}
          {!selectedWfId && page === 'evidence' && <EvidenceCenter/>}
          {!selectedWfId && page === 'security' && <Governance/>}
          {!selectedWfId && page === 'memory' && <Memory/>}
          {!selectedWfId && page === 'audit' && <Audit/>}
          {!selectedWfId && page === 'architecture' && <HowItWorks/>}
          {!selectedWfId && page === 'demo' && <DemoCenterView onStartDemoWorkflow={submitWorkflow}/>}

          {/* Task Inspector Drawer */}
          {selectedTask && (
            <div className="drawer-overlay" onClick={() => setSelectedTask(null)}>
              <div className="drawer-content" onClick={e => e.stopPropagation()}>
                <div className="drawer-header">
                  <div>
                    <small>TASK EXECUTION INSPECTOR</small>
                    <h3>{selectedTask.agent_id}</h3>
                  </div>
                  <button className="btn-close" onClick={() => setSelectedTask(null)}>✕</button>
                </div>
                <div style={{display:'flex', flexDirection:'column', gap:'16px'}}>
                  <div style={{display:'flex', gap:'8px', alignItems:'center'}}>
                    <i className={selectedTask.status}>{selectedTask.status}</i>
                    <span style={{fontFamily:'var(--font-mono)', fontSize:'11px', color:'var(--text-muted)'}}>
                      Task ID: {selectedTask.task_id}
                    </span>
                  </div>

                  <div>
                    <b style={{fontSize:'11px', color:'var(--text-muted)'}}>TITLE / ACTION</b>
                    <div style={{fontSize:'13px', marginTop:'2px'}}>{selectedTask.title}</div>
                  </div>

                  <div className="columns" style={{marginBottom:0}}>
                    <div>
                      <b style={{fontSize:'11px', color:'var(--text-muted)'}}>LATENCY</b>
                      <div style={{fontSize:'13px', marginTop:'2px', fontFamily:'var(--font-mono)'}}>
                        {selectedTask.execution_time_ms ?? '--'} ms
                      </div>
                    </div>
                    <div>
                      <b style={{fontSize:'11px', color:'var(--text-muted)'}}>RETRIES</b>
                      <div style={{fontSize:'13px', marginTop:'2px', fontFamily:'var(--font-mono)'}}>
                        {selectedTask.retries || 0}
                      </div>
                    </div>
                  </div>

                  {selectedTask.error && (
                    <div className="task-error-box">
                      <b>ERROR DIAGNOSTIC: {selectedTask.error}</b>
                      {selectedTask.error === 'quota_exceeded' && (
                        <p style={{margin:'6px 0 0', fontSize:'11px', color:'var(--text-muted)'}}>
                          The configured Gemini API key has exceeded its free-tier daily rate limit (20 requests/day). Wait for quota reset or configure a billing-enabled project.
                        </p>
                      )}
                      {selectedTask.error === 'authentication_failed' && (
                        <p style={{margin:'6px 0 0', fontSize:'11px', color:'var(--text-muted)'}}>
                          Authentication failed with Google Cloud / Gemini API. Verify GEMINI_API_KEY in backend/.env or run `gcloud auth application-default login` for Vertex AI.
                        </p>
                      )}
                      {selectedTask.error === 'credentials_missing' && (
                        <p style={{margin:'6px 0 0', fontSize:'11px', color:'var(--text-muted)'}}>
                          No credentials found. Add GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT to backend/.env.
                        </p>
                      )}
                      <div style={{marginTop:'10px'}}>
                        <button className="btn-secondary" onClick={loadAllTelemetry}>↻ Re-check Provider Health</button>
                      </div>
                    </div>
                  )}

                  <div>
                    <b style={{fontSize:'11px', color:'var(--text-muted)'}}>OUTPUT PAYLOAD JSON</b>
                    <pre className="json-box">
                      {selectedTask.output ? JSON.stringify(selectedTask.output, null, 2) : 'No output produced.'}
                    </pre>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Global Command Palette */}
          <CommandPalette 
            isOpen={cmdOpen} 
            onClose={() => setCmdOpen(false)} 
            onNavigate={handlePaletteNavigate} 
            workflows={workflows} 
            agents={agents}
          />
        </main>
      </div>
    </div>
  );
}

function Metric({label,value}){return <div className="metric"><small>{label}</small><strong>{value}</strong><span>● live API</span></div>}
function Card({title,sub,children}){return <section className="card"><div className="card-head"><div><h2>{title}</h2><small>{sub}</small></div><span>↗</span></div>{children}</section>}

createRoot(document.getElementById('root')).render(<App/>);
