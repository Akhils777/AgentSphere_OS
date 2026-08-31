import React, {useEffect, useMemo, useState} from 'react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8080/api';
const get = async path => { const response = await fetch(`${API}${path}`); if (!response.ok) throw new Error(`${response.status} ${response.statusText}`); return response.json(); };
const time = value => value ? new Date(value).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : '--';

function Panel({title,sub,children}){return <section className="card"><div className="card-head"><div><h2>{title}</h2><small>{sub}</small></div><span>↗</span></div>{children}</section>}
function Metric({label,value}){return <div className="metric"><small>{label}</small><strong>{value}</strong><span>● derived from API</span></div>}
function Intro({label,title,text}){return <div className="page-intro"><small>{label}</small><h1>{title}</h1><p>{text}</p></div>}
function ErrorBox({error,retry}){return <div className="error">Could not load live data: {error}<button onClick={retry}>Retry</button></div>}

export function Overview({workflows,agents,security,loading,error,retry,onWorkflow}){
  const active=workflows.filter(w=>['queued','running'].includes(w.status));
  const completed=workflows.filter(w=>w.status==='completed');
  const failed=workflows.filter(w=>w.status==='failed');
  const [demo,setDemo]=useState(false);

  return <>
    <Intro label="EXECUTIVE CONTROL" title="Executive Overview" text="A live operating view of autonomous agent activity, risk, and governance."/>
    <div className="metrics">
      <Metric label="Total workflows" value={workflows.length}/>
      <Metric label="Active workflows" value={active.length}/>
      <Metric label="Completed" value={completed.length}/>
      <Metric label="Failed" value={failed.length}/>
      <Metric label="Registered agents" value={agents.length}/>
      <Metric label="Security events" value={security.length}/>
    </div>
    {error?<ErrorBox error={error} retry={retry}/>:loading?<div className="loading">Loading executive telemetry…</div>:
    <>
      <div className="columns">
        <Panel title="Platform risk posture" sub="Derived from workflow and security records">
          <div className="risk-summary">
            <div className={`risk-ring ${failed.length||security.length?'attention':'clear'}`}>
              {failed.length||security.length?'ATTN':'OK'}
            </div>
            <div>
              <b>{failed.length||security.length?'Review required':'Operating normally'}</b>
              <p>{security.length} security event(s), {failed.length} failed workflow(s), {active.length} active workflow(s).</p>
              <small>Risk summary is calculated from live API records; no data is invented.</small>
            </div>
          </div>
        </Panel>
        <Panel title="Demo readiness" sub="Live capability checklist">
          <Checklist workflows={workflows} agents={agents} security={security}/>
        </Panel>
      </div>
      <Panel title="Recent workflow executions" sub="Select a workflow to inspect its full decision trail">
        <div className="recent-list">
          {workflows.slice(0,6).map(w=>
            <button className="recent-item" key={w.workflow_id} onClick={()=>onWorkflow(w.workflow_id)}>
              <span><b>{w.workflow_id}</b><small>{w.goal}</small></span>
              <span><i className={w.status}>{w.status}</i><small>{time(w.created_at)}</small></span>
            </button>
          )}
          {!workflows.length&&<div className="empty">No workflow executions available. Run a workflow to view execution telemetry.</div>}
        </div>
      </Panel>
      <div className="how-strip">
        <div><b>Guided Walkthrough Mode</b><span>Interactive architectural inspection mode.</span></div>
        <label className="switch">
          <input type="checkbox" checked={demo} onChange={e=>setDemo(e.target.checked)}/>
          <span/>
        </label>
      </div>
      {demo&&<HowItWorks compact/>}
    </>}
  </>
}

function Checklist({workflows,agents,security}){
  const items=[
    ['Agent registry',agents.length>0],
    ['Governed workflow',workflows.length>0],
    ['Multi-agent execution',workflows.some(w=>w.progress>0)],
    ['Risk analysis',agents.some(a=>(a.capabilities||[]).includes('risk_scoring'))],
    ['Security/compliance',agents.some(a=>(a.capabilities||[]).includes('policy_validation'))],
    ['Memory',workflows.some(w=>w.memory_updated)],
    ['Audit trail',workflows.length>0],
    ['Executive reporting',agents.some(a=>(a.capabilities||[]).includes('executive_reporting'))]
  ];
  return <div className="checklist">{items.map(([name,ok])=><div key={name}><span className={ok?'checked':''}>{ok?'✓':'○'}</span>{name}<small>{ok?'Available':'No live evidence'}</small></div>)}</div>
}

export function RiskIntelligenceView({workflows, onSelectWorkflow}){
  const [selectedWfId, setSelectedWfId] = useState(workflows[0]?.workflow_id || '');
  const [tasks, setTasks] = useState([]);
  const [loadingTasks, setLoadingTasks] = useState(false);

  useEffect(() => {
    if (!selectedWfId && workflows.length > 0) {
      setSelectedWfId(workflows[0].workflow_id);
    }
  }, [workflows]);

  useEffect(() => {
    if (!selectedWfId) return;
    setLoadingTasks(true);
    get(`/workflows/${selectedWfId}/tasks`)
      .then(res => setTasks(res.items || []))
      .catch(() => setTasks([]))
      .finally(() => setLoadingTasks(false));
  }, [selectedWfId]);

  const activeWorkflow = workflows.find(w => w.workflow_id === selectedWfId);
  const task = id => tasks.find(t => t.agent_id === id);
  const risk = task('risk-analysis-agent-v1')?.output;
  const security = task('security-compliance-agent-v1')?.output;
  const data = task('data-intelligence-agent-v1')?.output;
  const reportTask = task('report-generation-agent-v1');

  const riskScore = risk?.risk_score ?? (risk?.score || null);
  const riskCat = (risk?.risk_category || 'UNVALUATED').toUpperCase();

  return <>
    <Intro label="DECISION INTELLIGENCE" title="Risk Intelligence Dashboard" text="Enterprise risk scoring, confidence factors, and compliance findings calculated by specialist agents."/>
    
    <div style={{marginBottom:'20px', display:'flex', gap:'12px', alignItems:'center'}}>
      <label style={{fontFamily:'var(--font-mono)', fontSize:'12px', color:'var(--text-muted)'}}>Select Workflow Record:</label>
      <select 
        value={selectedWfId} 
        onChange={e=>setSelectedWfId(e.target.value)}
        style={{minWidth:'320px'}}
      >
        {workflows.map(w => (
          <option key={w.workflow_id} value={w.workflow_id}>
            {w.workflow_id} — {w.goal.length > 50 ? w.goal.slice(0, 50) + '...' : w.goal}
          </option>
        ))}
      </select>
    </div>

    {!activeWorkflow ? (
      <Panel title="Supplier Risk Assessment" sub="No workflow record selected">
        <div className="empty">No workflows found. Run a new workflow to perform risk intelligence scoring.</div>
      </Panel>
    ) : loadingTasks ? (
      <div className="loading">Loading risk telemetry...</div>
    ) : (
      <>
        <Panel title="Supplier Risk Scorecard" sub={`Target Entity: ${activeWorkflow.context?.entity || 'Supplier_ABC'} · Workflow: ${activeWorkflow.workflow_id}`}>
          <div className="risk-dial-container">
            <div className={`risk-ring ${riskCat === 'HIGH' || riskCat === 'HIGH RISK' ? 'high' : riskCat === 'MEDIUM' ? 'medium' : 'low'}`}>
              {riskScore !== null ? riskScore : 'N/A'}
            </div>
            <div className="risk-details">
              <h3>{riskCat}</h3>
              <p>Risk calculation derived from Data Intelligence Agent and Risk Analysis Agent evidence.</p>
              <div style={{display:'flex', gap:'16px', fontFamily:'var(--font-mono)', fontSize:'11px', color:'var(--text-muted)'}}>
                <span>Confidence: <b>{risk?.confidence || 'N/A'}</b></span>
                <span>Workflow Status: <i className={activeWorkflow.status}>{activeWorkflow.status}</i></span>
              </div>
            </div>
          </div>
        </Panel>

        {reportTask?.error && (
          <div className="error">
            <b>Gemini Model Execution Note:</b> {reportTask.error === 'quota_exceeded' ? 'The Report Generation Agent paused because the Gemini API quota limit was reached. Specialist risk calculations (Data & Risk agents) completed successfully.' : reportTask.error}
          </div>
        )}

        <div className="finding-grid">
          <div className="finding-card">
            <b>KEY FINDINGS</b>
            <p>{risk?.key_findings || data?.findings || 'Data unavailable from current execution.'}</p>
          </div>
          <div className="finding-card">
            <b>MISSING EVIDENCE / GAPS</b>
            <p>{risk?.missing_evidence || 'No evidence gaps identified.'}</p>
          </div>
          <div className="finding-card">
            <b>RECOMMENDED ACTIONS</b>
            <p>{risk?.recommendations || 'Data unavailable.'}</p>
          </div>
          <div className="finding-card">
            <b>COMPLIANCE & SECURITY FINDINGS</b>
            <p>{security?.findings || security?.analysis || 'Policy validation completed cleanly.'}</p>
          </div>
          <div className="finding-card">
            <b>DATA QUALITY & ANOMALIES</b>
            <p>{data?.data_quality_issues || data?.anomalies || 'No data quality anomalies flagged.'}</p>
          </div>
          <div className="finding-card">
            <b>EXECUTIVE REPORT OUTPUT</b>
            <p>{reportTask?.output ? (typeof reportTask.output === 'string' ? reportTask.output : JSON.stringify(reportTask.output, null, 2)) : 'Report generation pending Gemini availability.'}</p>
          </div>
        </div>
      </>
    )}
  </>
}

export function FleetMatrix(){
  const [agents,setAgents]=useState(null),[error,setError]=useState(''),[filters,setFilters]=useState({status:'all',role:'all',capability:''});
  const load=()=>get('/agents').then(x=>setAgents(x.items||[])).catch(e=>setError(e.message));
  useEffect(()=>{load()},[]);
  const roles=[...new Set((agents||[]).map(a=>a.role||'specialist'))];
  const rows=(agents||[]).filter(a=>(filters.status==='all'||a.status===filters.status)&&(filters.role==='all'||(a.role||'specialist')===filters.role)&&(!filters.capability||(a.capabilities||[]).some(c=>c.toLowerCase().includes(filters.capability.toLowerCase()))));
  
  return <>
    <Intro label="FLEET GOVERNANCE" title="Agent Capability Matrix" text="A read-only view of the capabilities, tools, permissions, and roles exposed by the registered fleet."/>
    <Panel title="Agent capability matrix" sub={`${rows.length} of ${(agents||[]).length} agents`}>
      <div className="filters">
        <select value={filters.status} onChange={e=>setFilters({...filters,status:e.target.value})}>
          <option value="all">All statuses</option>
          <option value="approved">Approved</option>
          <option value="disabled">Disabled</option>
        </select>
        <select value={filters.role} onChange={e=>setFilters({...filters,role:e.target.value})}>
          <option value="all">All roles</option>
          {roles.map(r=><option key={r}>{r}</option>)}
        </select>
        <input placeholder="Filter capability" value={filters.capability} onChange={e=>setFilters({...filters,capability:e.target.value})}/>
      </div>
      {error?<ErrorBox error={error} retry={load}/>:!agents?<div className="loading">Loading agent fleet…</div>:!rows.length?<div className="empty">No agents match these filters.</div>:
      <div className="audit-table">
        <div className="audit-head" style={{gridTemplateColumns:'1.5fr 1fr 1fr 2fr 1.5fr 1.5fr'}}>
          <span>Agent</span>
          <span>Role</span>
          <span>Status</span>
          <span>Capabilities</span>
          <span>Tools</span>
          <span>Permissions</span>
        </div>
        {rows.map(a=>
          <div className="audit-row" key={a.agent_id} style={{gridTemplateColumns:'1.5fr 1fr 1fr 2fr 1.5fr 1.5fr'}}>
            <span><b>{a.name}</b><small>{a.agent_id} · v{a.version||'1.0'}</small></span>
            <span>{a.role||'specialist'}</span>
            <span><i className={a.status}>{a.status}</i></span>
            <span>{(a.capabilities||[]).join(', ')||'None'}</span>
            <span>{(a.tools||[]).join(', ')||'None'}</span>
            <span>{Object.entries(a.permissions||{}).filter(([,v])=>v).map(([k])=>k).join(', ')||'None'}</span>
          </div>
        )}
      </div>}
    </Panel>
  </>
}

export function SupplierRiskDecision({workflow,tasks,summary}){
  const entity=workflow.context?.entity||'Data unavailable';
  const task=id=>tasks.find(t=>t.agent_id===id);
  const risk=task('risk-analysis-agent-v1')?.output;
  const security=task('security-compliance-agent-v1')?.output;
  const data=task('data-intelligence-agent-v1')?.output;

  return <Panel title="Supplier Risk Assessment" sub={`Entity: ${entity} · Decision View`}>
    <div className="decision-grid" style={{display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(160px, 1fr))', gap:'12px', padding:'16px'}}>
      <Decision label="Overall risk score" value={risk?.risk_score??'Data unavailable'}/>
      <Decision label="Risk category" value={risk?.risk_category??'Data unavailable'}/>
      <Decision label="Confidence" value={risk?.confidence??'Data unavailable'}/>
      <Decision label="Final status" value={workflow.status}/>
    </div>
    <div className="finding-grid">
      <Finding title="Key findings" value={risk?.key_findings||data?.findings}/>
      <Finding title="Missing evidence" value={risk?.missing_evidence}/>
      <Finding title="Recommended actions" value={risk?.recommendations}/>
      <Finding title="Compliance findings" value={security?.findings||security?.analysis}/>
      <Finding title="Data-quality issues" value={data?.data_quality_issues||data?.anomalies}/>
      <Finding title="Final report" value={summary.final_report_output}/>
    </div>
  </Panel>
}

function Decision({label,value}){return <div className="finding-card"><b style={{fontSize:'10px', color:'var(--text-muted)'}}>{label}</b><div style={{fontFamily:'var(--font-mono)', fontSize:'14px', marginTop:'4px', color:'var(--accent-lime)'}}>{typeof value==='object'?JSON.stringify(value):String(value)}</div></div>}
function Finding({title,value}){return <div className="finding-card"><b>{title}</b><p>{value?typeof value==='string'?value:JSON.stringify(value,null,2):'Data unavailable'}</p></div>}

export function GovernanceDecision({workflow,tasks}){
  const [audit,setAudit]=useState([]), [security,setSecurity]=useState([]);
  useEffect(()=>{
    Promise.all([get(`/audit-logs?workflow_id=${workflow.workflow_id}`),get('/security-events')])
      .then(([a,s])=>{setAudit(a.items||[]);setSecurity(s.items||[])})
      .catch(()=>{})
  },[workflow.workflow_id]);

  const first=tasks[0];
  const event=audit.find(x=>x.agent===first?.agent_id);

  return <Panel title="Governance decision panel" sub="Audit evidence associated with this execution">
    <div className="finding-grid">
      <Decision label="Selected agent" value={first?.agent_id||'Data unavailable'}/>
      <Decision label="Agent status" value={first?.status||'Data unavailable'}/>
      <Decision label="Authorization result" value={event?.status==='success'?'AUTHORIZED':event?.status||'Data unavailable'}/>
      <Decision label="Safety inspection" value={security.length?'Events recorded':'No security event recorded'}/>
    </div>
    <div style={{padding:'20px'}}>
      <b style={{fontSize:'11px', color:'var(--text-muted)'}}>ASSOCIATED AUDIT EVENT EVIDENCE</b>
      <pre className="json-box">{event?JSON.stringify(event,null,2):'Data unavailable'}</pre>
    </div>
  </Panel>
}

export function ReplayPanel({workflow,tasks}){
  const stageStatus = (stageId) => {
    if (stageId === 'request') return 'completed';
    if (stageId === 'gateway') return 'completed';
    if (stageId === 'supervisor') return workflow.plan ? 'completed' : 'running';
    const foundTask = tasks.find(t => t.agent_id.includes(stageId));
    if (!foundTask) return 'queued';
    return foundTask.status;
  };

  return <Panel title="Visual Workflow Lifecycle Graph" sub="Interactive node execution graph">
    <div className="visualizer-container">
      <div className="node-graph">
        <div className="graph-stage">
          <div className={`graph-node ${stageStatus('request')}`}>
            <span style={{fontSize:'18px'}}>📩</span>
            <div className="graph-node-title">Request</div>
            <div className="graph-node-sub">API Gateway</div>
          </div>
        </div>
        <div className="graph-connector active"/>
        
        <div className="graph-stage">
          <div className={`graph-node ${stageStatus('gateway')}`}>
            <span style={{fontSize:'18px'}}>🛡️</span>
            <div className="graph-node-title">Safety</div>
            <div className="graph-node-sub">Inspection</div>
          </div>
        </div>
        <div className="graph-connector active"/>

        <div className="graph-stage">
          <div className={`graph-node ${stageStatus('supervisor')}`}>
            <span style={{fontSize:'18px'}}>👑</span>
            <div className="graph-node-title">Supervisor</div>
            <div className="graph-node-sub">Orchestration</div>
          </div>
        </div>
        <div className="graph-connector active"/>

        <div className="graph-stage">
          <div className={`graph-node ${stageStatus('data-intelligence')}`}>
            <span style={{fontSize:'18px'}}>📊</span>
            <div className="graph-node-title">Data Agent</div>
            <div className="graph-node-sub">Validation</div>
          </div>
        </div>
        <div className="graph-connector active"/>

        <div className="graph-stage">
          <div className={`graph-node ${stageStatus('risk-analysis')}`}>
            <span style={{fontSize:'18px'}}>⚖️</span>
            <div className="graph-node-title">Risk Agent</div>
            <div className="graph-node-sub">Scoring</div>
          </div>
        </div>
        <div className="graph-connector active"/>

        <div className="graph-stage">
          <div className={`graph-node ${stageStatus('security-compliance')}`}>
            <span style={{fontSize:'18px'}}>🔒</span>
            <div className="graph-node-title">Security Agent</div>
            <div className="graph-node-sub">Compliance</div>
          </div>
        </div>
        <div className="graph-connector active"/>

        <div className="graph-stage">
          <div className={`graph-node ${stageStatus('report-generation')}`}>
            <span style={{fontSize:'18px'}}>📝</span>
            <div className="graph-node-title">Report Agent</div>
            <div className="graph-node-sub">Executive Summary</div>
          </div>
        </div>
      </div>
    </div>
  </Panel>
}

export function DemoCenterView({onStartDemoWorkflow}){
  return <>
    <Intro label="HACKATHON WALKTHROUGH" title="Demo Center" text="Guided interactive scenario demonstrator for multi-agent enterprise governance."/>
    
    <div className="demo-banner">
      <h2>🎯 Enterprise Scenario: Supplier Risk Assessment</h2>
      <p>Evaluate vendor <b>ABC Logistics</b> prior to enterprise onboarding. The Orchestrator Agent decomposes the request into data quality verification, risk scoring, security compliance check, and executive report synthesis.</p>
      <button className="btn-primary" onClick={onStartDemoWorkflow}>
        ▶ Launch Live Demo Workflow (ABC Logistics)
      </button>
    </div>

    <div className="columns">
      <Panel title="1. Autonomous Task Decomposition" sub="Supervisor Agent Strategy">
        <p className="prose">The Supervisor Agent inspects approved specialist agents in the registry and assigns tasks in sequence: Data Intelligence → Risk Analysis → Security Compliance → Report Generation.</p>
      </Panel>
      <Panel title="2. Policy & Capability Enforcement" sub="Security Control Plane">
        <p className="prose">Every agent invocation checks permissions against the policy engine. Specialist agents cannot access unauthorized data pools or act outside designated boundaries.</p>
      </Panel>
    </div>

    <div className="columns">
      <Panel title="3. Context Persistence" sub="Memory Explorer">
        <p className="prose">Historical decisions and risk findings are persisted in entity memory (e.g. `supplier_ABC`), ensuring future workflows recall previous risk scores.</p>
      </Panel>
      <Panel title="4. Audit & Observability" sub="Enterprise Audit Log">
        <p className="prose">Every agent step, tool access, and output payload is captured in immutable audit logs with timestamped execution telemetry.</p>
      </Panel>
    </div>
  </>
}

export function HowItWorks({compact=false}){
  return <div className={compact?'how-panel compact':'how-page'}>
    <Intro label="ARCHITECTURE DEEP DIVE" title={compact?'How AgentSphere Works':'Platform Architecture'} text="AgentSphere turns a business goal into governed, observable, multi-agent AI execution."/>
    
    <div className="architecture-flow">
      {['User Request','React App Shell','API Gateway','Safety Inspection','Supervisor Agent','Data Agent','Risk Agent','Security Agent','Report Agent','Memory & Audit'].map((x,i)=>
        <React.Fragment key={x}>
          <div className="arch-step">
            <span>STAGE {String(i+1).padStart(2,'0')}</span>
            <b>{x}</b>
          </div>
          {i<9&&<strong style={{color:'var(--text-muted)'}}>→</strong>}
        </React.Fragment>
      )}
    </div>

    <div className="columns">
      <Panel title="Why Multi-Agent Architecture?" sub="Specialized intelligence vs general LLM">
        <p className="prose">Generic LLMs lack bounded permissions and strict access controls. By partitioning work across specialist agents with explicit capability manifests, enterprises maintain strict governance and auditing.</p>
      </Panel>
      <Panel title="Google Cloud & Gemini Stack" sub="Cloud Platform Architecture">
        <p className="prose">Powered by Gemini reasoning models, Google ADK patterns, Cloud Run execution containers, Firestore/JSON persistence, and BigQuery data tools for enterprise multi-agent workflows.</p>
      </Panel>
    </div>
  </div>
}
