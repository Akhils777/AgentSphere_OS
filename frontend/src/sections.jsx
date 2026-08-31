import React, {useEffect, useMemo, useState} from 'react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8080/api';
const request = async path => { const response = await fetch(`${API}${path}`); if (!response.ok) throw new Error(`${response.status} ${response.statusText}`); return response.json(); };
const format = value => value ? new Date(value).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : '--';
const Status = ({value}) => <i className={String(value||'unknown').toLowerCase()}>{value || 'unknown'}</i>;
const Loading = () => <div className="loading">Loading live records…</div>;
const ErrorState = ({message,retry}) => <div className="error">{message}<button onClick={retry}>Retry</button></div>;
const Empty = ({children}) => <div className="empty">{children}</div>;
function Card({title,sub,children}){return <section className="card"><div className="card-head"><div><h2>{title}</h2><small>{sub}</small></div><span>↗</span></div>{children}</section>}

export function Fleet(){
  const [data,setData]=useState(null), [error,setError]=useState(''), [selectedAgent, setSelectedAgent]=useState(null);
  const load=()=>request('/agents').then(setData).catch(e=>setError(e.message));
  useEffect(()=>{load()},[]);
  const agents=data?.items||[];

  return <>
    <PageIntro label="GOVERNED INVENTORY" title="Agent Fleet" text="Discover approved agents, capabilities, tools, and access boundaries."/>
    <div className="metrics">
      <Metric label="Total agents" value={agents.length}/>
      <Metric label="Approved" value={agents.filter(a=>a.status==='approved').length}/>
      <Metric label="Enabled" value={agents.filter(a=>a.enabled!==false).length}/>
      <Metric label="Roles represented" value={new Set(agents.map(a=>a.role)).size||'N/A'}/>
    </div>
    <Card title="Registered agent fleet" sub="Click an agent card to inspect governance details">
      {error?<ErrorState message={error} retry={load}/>:!data?<Loading/>:!agents.length?<Empty>No registered agents found.</Empty>:
      <div className="fleet-grid">
        {agents.map(agent=>
          <article className="agent-card" key={agent.agent_id} onClick={()=>setSelectedAgent(agent)}>
            <div className="agent-card-top"><span className="agent-symbol">✦</span><Status value={agent.status}/></div>
            <h3>{agent.name}</h3>
            <code>{agent.agent_id}</code>
            <p>{agent.description}</p>
            <div className="agent-meta">
              <span>Owner <b>{agent.owner}</b></span>
              <span>Version <b>v{agent.version||'1.0'}</b></span>
              <span>Role <b>{agent.role||'specialist'}</b></span>
            </div>
            <div className="tag-row">{(agent.capabilities||[]).map(x=><span key={x}>{x}</span>)}</div>
            <small className="agent-access">Tools: {(agent.tools||[]).join(', ')||'None'}<br/>Permissions: {Object.entries(agent.permissions||{}).filter(([,v])=>v).map(([k])=>k).join(', ')||'None'}</small>
          </article>
        )}
      </div>}
    </Card>

    {selectedAgent && (
      <div className="drawer-overlay" onClick={()=>setSelectedAgent(null)}>
        <div className="drawer-content" onClick={e=>e.stopPropagation()}>
          <div className="drawer-header">
            <div>
              <small>{selectedAgent.agent_id}</small>
              <h3>{selectedAgent.name}</h3>
            </div>
            <button className="btn-close" onClick={()=>setSelectedAgent(null)}>✕</button>
          </div>
          <div style={{display:'flex', flexDirection:'column', gap:'16px'}}>
            <div style={{display:'flex', gap:'8px', alignItems:'center'}}>
              <Status value={selectedAgent.status}/>
              <span style={{fontFamily:'var(--font-mono)', fontSize:'11px', color:'var(--text-muted)'}}>Role: {selectedAgent.role||'specialist'}</span>
            </div>
            <div>
              <b style={{fontSize:'12px', color:'var(--text-muted)'}}>DESCRIPTION</b>
              <p style={{fontSize:'13px', lineHeight:'1.5', margin:'4px 0'}}>{selectedAgent.description}</p>
            </div>
            <div className="columns" style={{marginBottom:0}}>
              <div>
                <b style={{fontSize:'11px', color:'var(--text-muted)'}}>OWNER</b>
                <div style={{fontSize:'13px', marginTop:'2px'}}>{selectedAgent.owner}</div>
              </div>
              <div>
                <b style={{fontSize:'11px', color:'var(--text-muted)'}}>VERSION</b>
                <div style={{fontSize:'13px', marginTop:'2px'}}>v{selectedAgent.version||'1.0'}</div>
              </div>
            </div>
            <div>
              <b style={{fontSize:'11px', color:'var(--text-muted)'}}>CAPABILITIES</b>
              <div className="tag-row">{(selectedAgent.capabilities||[]).map(c=><span key={c}>{c}</span>)}</div>
            </div>
            <div>
              <b style={{fontSize:'11px', color:'var(--text-muted)'}}>TOOLS ASSIGNED</b>
              <div className="tag-row">{(selectedAgent.tools||[]).map(t=><span key={t}>{t}</span>)}</div>
            </div>
            <div>
              <b style={{fontSize:'11px', color:'var(--text-muted)'}}>SECURITY PERMISSIONS</b>
              <pre className="json-box">{JSON.stringify(selectedAgent.permissions||{}, null, 2)}</pre>
            </div>
          </div>
        </div>
      </div>
    )}
  </>
}

export function Governance(){
  const [state,setState]=useState(null), [error,setError]=useState('');
  const load=()=>Promise.all([request('/security-events'),request('/audit-logs')]).then(([security,audit])=>setState({security:security.items||[],audit:audit.items||[]})).catch(e=>setError(e.message));
  useEffect(()=>{load()},[]);
  if(error)return <><PageIntro label="CONTROL PLANE" title="Security & Governance" text="Policy, safety, and authorization activity across the fleet."/><ErrorState message={error} retry={load}/></>;
  if(!state)return <Loading/>;
  const blocks=state.security;
  const authorized=state.audit.filter(x=>x.status==='success').length;
  const failed=state.audit.filter(x=>x.status==='failed').length;

  return <>
    <PageIntro label="CONTROL PLANE" title="Security & Governance" text="Policy, safety, and authorization activity across the fleet."/>
    <div className="metrics">
      <Metric label="Security events" value={blocks.length}/>
      <Metric label="Blocked requests" value={blocks.filter(x=>x.status==='blocked').length}/>
      <Metric label="Authorized actions" value={authorized}/>
      <Metric label="Failed actions" value={failed}/>
    </div>
    <div className="governance-flow">
      {['User request','Safety inspection','Gateway authorization','Agent execution','Audit log'].map((x,i)=>
        <React.Fragment key={x}>
          <div><span>0{i+1}</span><b>{x}</b></div>
          {i<4&&<strong>↓</strong>}
        </React.Fragment>
      )}
    </div>
    <Card title="Recent security events" sub="Blocked actions recorded by the gateway and safety layer">
      {!blocks.length?<Empty>No security events recorded.</Empty>:
      <div className="event-table">
        {blocks.slice(0,12).map((event,i)=>
          <div className="event-row" key={event.event_id||event.id||i}>
            <Status value="BLOCKED"/>
            <div>
              <b>{event.reason||event.action||'Policy violation'}</b>
              <small>Agent: {event.agent||'gateway'} · Resource: {event.resource||'--'} · {format(event.timestamp)}</small>
            </div>
          </div>
        )}
      </div>}
    </Card>
    <Card title="Authorization activity" sub="Successful and failed agent actions from audit logs">
      {!state.audit.length?<Empty>No authorization activity recorded.</Empty>:
      <div className="event-table">
        {state.audit.slice(0,12).map((event,i)=>
          <div className="event-row" key={event.id||i}>
            <Status value={event.status==='success'?'AUTHORIZED':event.status}/>
            <div>
              <b>{event.action}</b>
              <small>{event.agent} · Workflow {event.workflow_id} · {format(event.timestamp)}</small>
            </div>
          </div>
        )}
      </div>}
    </Card>
  </>
}

export function Memory(){
  const [data,setData]=useState(null), [error,setError]=useState(''), [search,setSearch]=useState('');
  const load=()=>request('/memories').then(setData).catch(e=>setError(e.message));
  useEffect(()=>{load()},[]);

  const filteredMemories = useMemo(() => {
    const items = data?.items || [];
    if (!search.trim()) return items;
    return items.filter(m => 
      (m.entity||'').toLowerCase().includes(search.toLowerCase()) ||
      (m.previous_analysis||'').toLowerCase().includes(search.toLowerCase())
    );
  }, [data, search]);

  return <>
    <PageIntro label="LONG-TERM CONTEXT" title="Memory Explorer" text="Persistent entity context recalled across governed workflows."/>
    {error?<ErrorState message={error} retry={load}/>:!data?<Loading/>:
    <>
      <div style={{marginBottom:'16px', display:'flex', gap:'12px'}}>
        <input 
          placeholder="Search memory entities or analysis text..." 
          value={search} 
          onChange={e=>setSearch(e.target.value)} 
          style={{maxWidth:'400px', width:'100%'}}
        />
      </div>
      {!filteredMemories.length?<Empty>No persisted memories match your filter. Complete a workflow to create entity context.</Empty>:
      <div className="memory-grid">
        {filteredMemories.map(memory=>
          <Card key={memory.entity} title={memory.entity} sub={`Updated ${format(memory.last_updated)}`}>
            <div className="memory-body">
              <b>Previous analysis</b>
              <p>{memory.previous_analysis||'No analysis recorded.'}</p>
              <b>Previous decisions</b>
              <ul>{(memory.previous_decisions||[]).map((x,i)=><li key={i}>{x}</li>)}</ul>
              <small style={{display:'block', marginTop:'10px'}}>Workflow ID: {memory.workflow_id||'--'}</small>
            </div>
          </Card>
        )}
      </div>}
    </>}
  </>
}

export function Audit(){
  const [data,setData]=useState(null), [error,setError]=useState(''), [filters,setFilters]=useState({status:'all',agent:'',workflow:''}), [selectedEvent, setSelectedEvent]=useState(null);
  const load=()=>request('/audit-logs').then(setData).catch(e=>setError(e.message));
  useEffect(()=>{load()},[]);

  const items=useMemo(()=>{
    const all=data?.items||[];
    return all.filter(x=>(filters.status==='all'||x.status===filters.status)&&( !filters.agent || (x.agent||'').toLowerCase().includes(filters.agent.toLowerCase()))&&(!filters.workflow||(x.workflow_id||'').toLowerCase().includes(filters.workflow.toLowerCase())))
  },[data,filters]);

  const exportJSON = () => {
    const jsonStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(items, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", jsonStr);
    downloadAnchor.setAttribute("download", `audit-logs-${new Date().toISOString().slice(0,10)}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return <>
    <PageIntro label="DECISION EVIDENCE" title="Audit Explorer" text="Searchable execution history for every agent action."/>
    {error?<ErrorState message={error} retry={load}/>:!data?<Loading/>:
    <Card title="Audit timeline" sub={`${items.length} records matching current filters`}>
      <div className="filters" style={{alignItems:'center'}}>
        <select value={filters.status} onChange={e=>setFilters({...filters,status:e.target.value})}>
          <option value="all">All statuses</option>
          <option value="success">Success</option>
          <option value="failed">Failed</option>
          <option value="blocked">Blocked</option>
        </select>
        <input placeholder="Filter agent" value={filters.agent} onChange={e=>setFilters({...filters,agent:e.target.value})}/>
        <input placeholder="Filter workflow ID" value={filters.workflow} onChange={e=>setFilters({...filters,workflow:e.target.value})}/>
        <button className="btn-secondary" onClick={exportJSON} style={{marginLeft:'auto', whiteSpace:'nowrap'}}>
          Export JSON ↗
        </button>
      </div>
      {!items.length?<Empty>No audit records match these filters.</Empty>:
      <div className="audit-table">
        <div className="audit-head">
          <span>Timestamp</span>
          <span>Agent / Action</span>
          <span>Status</span>
          <span>Workflow</span>
          <span>Resources</span>
        </div>
        {items.map((event,i)=>
          <div className="audit-row clickable" key={event.id||i} onClick={()=>setSelectedEvent(event)}>
            <span>{format(event.timestamp)}</span>
            <span><b>{event.agent}</b><small>{event.action}</small></span>
            <Status value={event.status}/>
            <span>{event.workflow_id||'--'}</span>
            <span>{(event.tools_used||[]).join(', ')||'--'}</span>
          </div>
        )}
      </div>}
    </Card>}

    {selectedEvent && (
      <div className="drawer-overlay" onClick={()=>setSelectedEvent(null)}>
        <div className="drawer-content" onClick={e=>e.stopPropagation()}>
          <div className="drawer-header">
            <div>
              <small>AUDIT RECORD INSPECTOR</small>
              <h3>{selectedEvent.action || 'Audit Event'}</h3>
            </div>
            <button className="btn-close" onClick={()=>setSelectedEvent(null)}>✕</button>
          </div>
          <div style={{display:'flex', flexDirection:'column', gap:'16px'}}>
            <div style={{display:'flex', gap:'8px', alignItems:'center'}}>
              <Status value={selectedEvent.status}/>
              <span style={{fontFamily:'var(--font-mono)', fontSize:'11px', color:'var(--text-muted)'}}>Agent: {selectedEvent.agent}</span>
            </div>
            <div>
              <b style={{fontSize:'11px', color:'var(--text-muted)'}}>TIMESTAMP</b>
              <div style={{fontSize:'13px', marginTop:'2px', fontFamily:'var(--font-mono)'}}>{format(selectedEvent.timestamp)}</div>
            </div>
            <div>
              <b style={{fontSize:'11px', color:'var(--text-muted)'}}>WORKFLOW ID</b>
              <div style={{fontSize:'13px', marginTop:'2px', fontFamily:'var(--font-mono)'}}>{selectedEvent.workflow_id||'--'}</div>
            </div>
            <div>
              <b style={{fontSize:'11px', color:'var(--text-muted)'}}>RESOURCES / TOOLS USED</b>
              <div className="tag-row">{(selectedEvent.tools_used||[]).map(t=><span key={t}>{t}</span>)}</div>
            </div>
            <div>
              <b style={{fontSize:'11px', color:'var(--text-muted)'}}>FULL JSON EVIDENCE</b>
              <pre className="json-box">{JSON.stringify(selectedEvent, null, 2)}</pre>
            </div>
          </div>
        </div>
      </div>
    )}
  </>
}

function PageIntro({label,title,text}){return <div className="page-intro"><small>{label}</small><h1>{title}</h1><p>{text}</p></div>}
function Metric({label,value}){return <div className="metric"><small>{label}</small><strong>{value}</strong><span>● live API</span></div>}
