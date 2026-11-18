import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  ArrowUpRight,
  BriefcaseBusiness,
  Building2,
  CheckCircle2,
  FileText,
  LogOut,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  Upload,
  Users,
} from 'lucide-react';
import './style.css';

const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';

async function request(path, accessToken, options = {}) {
  const headers = { ...(options.headers || {}) };

  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${API}${path}`, {
    ...options,
    headers,
  });
  const data = await response.json().catch(() => ({
    detail: 'Unexpected response from the API.',
  }));

  if (!response.ok) {
    throw new Error(data.detail || 'Request failed.');
  }
  return data;
}

const req = request;

function App() {
  const [session, S] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('rn'));
    } catch {
      return null;
    }
  });
  const [mode, M] = useState('login');
  const [role, R] = useState('applicant');
  const [name, N] = useState('');
  const [email, E] = useState('');
  const [password, P] = useState('');
  const [tab, T] = useState('overview');
  const [jobs, J] = useState([]);
  const [apps, A] = useState([]);
  const [err, Er] = useState('');
  const [msg, Msg] = useState('');
  const [busy, B] = useState(false);
  const [form, F] = useState({
    title: '',
    company: '',
    location: '',
    description: '',
    required_skills: '',
  });
  const [jobid, JI] = useState('');
  const [file, FI] = useState(null);
  const [detail, D] = useState(null);
  const [query, Q] = useState('');
  const [analysisProgress, AP] = useState(null);

  const user = session?.user;
  const token = session?.access_token;

  function flash(message) {
    Msg(message);
    setTimeout(() => Msg(''), 3000);
  }

  async function refresh() {
    if (!token) return;

    try {
      const [jobList, applicationList] = await Promise.all([
        request('/jobs', token),
        request('/applications', token),
      ]);
      J(jobList);
      A(applicationList);
    } catch (error) {
      Er(error.message);
    }
  }

  useEffect(() => {
    if (token) refresh();
  }, [token]);

  async function auth(event) {
    event.preventDefault();
    B(true);
    Er('');

    try {
      const payload = mode === 'login'
        ? { email, password }
        : { name, email, password, role };
      const response = await request(
        `/auth/${mode === 'login' ? 'login' : 'register'}`,
        null,
        { method: 'POST', body: JSON.stringify(payload) },
      );
      localStorage.setItem('rn', JSON.stringify(response));
      S(response);
      flash('Signed in successfully');
    } catch (error) {
      Er(error.message);
    } finally {
      B(false);
    }
  }

  function logout() {
    localStorage.removeItem('rn');
    S(null);
    T('overview');
    J([]);
    A([]);
  }

  async function createJob(event) {
    event.preventDefault();
    B(true);

    try {
      const requiredSkills = form.required_skills
        .split(',')
        .map((skill) => skill.trim())
        .filter(Boolean);
      await request('/jobs', token, {
        method: 'POST',
        body: JSON.stringify({ ...form, required_skills: requiredSkills }),
      });
      F({
        title: '',
        company: '',
        location: '',
        description: '',
        required_skills: '',
      });
      await refresh();
      T('jobs');
      flash('Job description published');
    } catch (error) {
      Er(error.message);
    } finally {
      B(false);
    }
  }

  async function upload(event) {
    event.preventDefault();
    if (!file || !jobid) {
      Er('Select a job and resume file');
      return;
    }

    B(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      await request(`/applications?job_id=${jobid}`, token, {
        method: 'POST',
        body: formData,
      });
      await refresh();
      T('applications');
      FI(null);
      flash('Resume parsed and uploaded');
    } catch (error) {
      Er(error.message);
    } finally {
      B(false);
    }
  }

  async function analyze(applicationId) {
    B(true);
    Er('');

    const labels = [
      'Read resume and job requirements',
      'Run rule-based skill extraction',
      'Run ML phrase classification',
      'Resolve aliases and normalize skills',
      'Calculate semantic relevance',
      'Aggregate hybrid score and recommendations',
    ];
    AP({
      id: applicationId,
      active: 0,
      steps: labels.map((label, index) => ({
        label,
        status: index === 0 ? 'active' : 'pending',
      })),
    });

    let finishProgress;
    const completion = new Promise((resolve) => {
      finishProgress = resolve;
    });
    const progressAnimation = (async () => {
      for (let index = 0; index < labels.length - 1; index += 1) {
        AP((previous) => ({
          ...previous,
          active: index,
          steps: labels.map((label, stepIndex) => ({
            label,
            status: stepIndex < index
              ? 'complete'
              : stepIndex === index ? 'active' : 'pending',
          })),
        }));
        await new Promise((resolve) => setTimeout(resolve, 650));
      }

      AP((previous) => ({
        ...previous,
        active: labels.length - 1,
        steps: labels.map((label, index) => ({
          label,
          status: index < labels.length - 1 ? 'complete' : 'active',
        })),
      }));
      await completion;
      AP((previous) => ({
        ...previous,
        active: labels.length,
        steps: labels.map((label) => ({ label, status: 'complete' })),
      }));
    })();

    try {
      const response = await request(
        `/applications/${applicationId}/analyze`,
        token,
        { method: 'POST' },
      );
      finishProgress();
      await progressAnimation;
      D(response);
      await refresh();
      flash('Three-model analysis completed');
    } catch (error) {
      finishProgress();
      await progressAnimation;
      Er(error.message);
    } finally {
      AP(null);
      B(false);
    }
  }

  async function openDetail(applicationId) {
    try {
      const response = await request(`/applications/${applicationId}`, token);
      D({
        parsed: response.parsed,
        result: response.result,
        application_id: applicationId,
        job_title: response.job_title,
        company: response.company,
        filename: response.filename,
      });
    } catch (error) {
      Er(error.message);
    }
  }

    if(!session)return <div className="auth"><section className="hero"><div className="brand"><i><Sparkles/></i> Resume<span>_NER</span></div><div><small>HYBRID TALENT INTELLIGENCE</small><h1>Make every resume <em>count.</em></h1><p>Structured resume intelligence, normalized skills, and explainable job alignment — built for recruiters and applicants.</p><div className="steps"><span>01&nbsp; Extract</span><span>02&nbsp; Normalize</span><span>03&nbsp; Match</span></div></div><small className="foot">BUILT FOR CLARITY · DESIGNED FOR PEOPLE</small></section><section className="authside"><form className="authcard" onSubmit={auth}><i className="icon"><ShieldCheck/></i><h2>{mode==='login'?'Welcome back':'Create your workspace'}</h2><p>{mode==='login'?'Sign in to continue to your talent workspace.':'Choose your account type to get started.'}</p>{err&&<div className="error">{err}</div>}{mode==='register'&&<><label>Full name<input required value={name} onChange={e=>N(e.target.value)}/></label><label>Account type<select value={role} onChange={e=>R(e.target.value)}><option value="applicant">Applicant</option><option value="recruiter">Recruiter</option></select></label></>}<label>Email address<input type="email" required value={email} onChange={e=>E(e.target.value)} placeholder="you@example.com"/></label><label>Password<input type="password" required minLength="8" value={password} onChange={e=>P(e.target.value)} placeholder="At least 8 characters"/></label><button className="primary widebtn" disabled={busy}>{busy?'Please wait…':mode==='login'?'Sign in →':'Create account →'}</button><p className="switch">{mode==='login'?'New here?':'Already registered?'} <button type="button" onClick={()=>{M(mode==='login'?'register':'login');Er('')}}>{mode==='login'?'Create account':'Sign in'}</button></p></form></section></div>;
let nav=user.role==='recruiter'?[['overview','Overview',Activity],['jobs','Job descriptions',BriefcaseBusiness],['applications','Applications',Users],['evaluation','ML Evaluation',Target]]:[['overview','Overview',Activity],['jobs','Explore jobs',BriefcaseBusiness],['upload','Upload resume',Upload],['applications','My applications',FileText]];
return <div className="layout"><aside><div className="brand"><i><Sparkles/></i> Resume<span>_NER</span></div><small className="label">WORKSPACE</small><div className="user"><b>{user.name}</b><small>{user.role} account</small></div><nav>{nav.map(([k,l,I])=><button className={tab===k?'active':''} key={k} onClick={()=>T(k)}><I size={17}/>{l}</button>)}</nav><div className="bottom"><p><ShieldCheck size={16}/> Local prototype workspace</p><button onClick={logout}><LogOut size={16}/> Sign out</button></div></aside><main><header><div><small>WORKSPACE / {tab.toUpperCase()}</small><h1>{tab==='overview'?'Overview':tab==='jobs'?(user.role==='recruiter'?'Job descriptions':'Explore opportunities'):tab==='upload'?'Submit your resume':tab==='evaluation'?'ML Model Evaluation':'Applications'}</h1></div><div className="connected">● API connected <b>{user.name.slice(0,1).toUpperCase()}</b></div></header>{err&&<div className="error">{err}<button onClick={()=>Er('')}>Dismiss</button></div>}{msg&&<div className="success"><CheckCircle2 size={16}/>{msg}</div>}
{tab==='overview'&&<><section className="banner"><div><small>YOUR TALENT WORKSPACE</small><h2>{user.role==='recruiter'?'Find alignment, not just keywords.':'Show your skills with clarity.'}</h2><p>{user.role==='recruiter'?'Publish a real job description, review candidate evidence, and run explainable analysis.':'Explore recruiter-listed opportunities, submit your resume, and review alignment.'}</p><button onClick={()=>T(user.role==='recruiter'?'jobs':'upload')}>{user.role==='recruiter'?'Create a job description':'Upload a resume'} <ArrowUpRight size={16}/></button></div><div className="target"><Target size={60}/></div></section><h3>Workspace snapshot</h3><div className="stats"><Stat icon={BriefcaseBusiness} n={user.role==='recruiter'?jobs.filter(j=>j.recruiter_id===user.id).length:jobs.length} t={user.role==='recruiter'?'Your job descriptions':'Open opportunities'}/><Stat icon={FileText} n={apps.length} t="Applications"/><Stat icon={Sparkles} n={apps.filter(a=>a.status==='analyzed').length} t="Analyzed"/></div><h3>{user.role==='recruiter'?'Recent applications':'Recent job descriptions'}</h3>{user.role==='recruiter'?<AppTable apps={apps.slice(0,5)} analyze={analyze} detail={openDetail} busy={busy}/>:<div className="cards">{jobs.slice(0,4).map(j=><JobCard key={j.id} j={j} apply={()=>{JI(String(j.id));T('upload')}}/>)}{!jobs.length&&<Empty text="No job descriptions have been published yet."/>}</div>}</>}
{tab==='jobs'&&<><div className="tools"><div className="search"><Search size={16}/><input value={query} onChange={e=>Q(e.target.value)} placeholder="Search roles, companies, locations"/></div>{user.role==='recruiter'&&<button className="primary" onClick={()=>T('create')}>＋ Create job</button>}</div>{user.role==='recruiter'&&<JobForm form={form} set={F} submit={createJob} busy={busy}/>}<div className="cards">{jobs.filter(j=>(j.title+j.company+j.location).toLowerCase().includes(query.toLowerCase())).map(j=><JobCard key={j.id} j={j} apply={()=>{JI(String(j.id));T('upload')}} recruiter={user.role==='recruiter'}/>)}</div></>}
{tab==='create'&&<JobForm form={form} set={F} submit={createJob} busy={busy}/>}
{tab==='upload'&&<div className="two"><form className="panel" onSubmit={upload}><i className="icon"><Upload/></i><h2>Upload your resume</h2><p>Select a recruiter-listed job and upload a resume.</p><label>Target job<select required value={jobid} onChange={e=>JI(e.target.value)}><option value="">Select a job description</option>{jobs.map(j=><option key={j.id} value={j.id}>{j.title} · {j.company}</option>)}</select></label><label className="drop"><Upload size={26}/><b>{file?file.name:'Choose a resume file'}</b><small>PDF, DOCX, TXT · up to 12 MB</small><input type="file" accept=".pdf,.docx,.txt" onChange={e=>FI(e.target.files?.[0]||null)}/></label><button className="primary widebtn" disabled={busy||!file||!jobid}>{busy?'Processing…':'Upload and parse resume'}</button></form><div className="panel"><small className="purple">PROCESSING PIPELINE</small><h2>From document to evidence</h2>{['Extract text from the document','Recognize entities and normalize skill aliases','Recruiter runs JD alignment analysis','Review score, gaps, recommendations and JSON'].map((x,i)=><div className="step" key={x}><b>0{i+1}</b><span>{x}</span><CheckCircle2 size={16}/></div>)}<p className="muted">Scanned/image-only PDFs need OCR. Files remain in the local backend.</p></div></div>}
{tab==='applications'&&<><h3>{apps.length} application{apps.length===1?'':'s'}</h3><AppTable apps={apps} analyze={analyze} detail={openDetail} busy={busy}/></>}
{analysisProgress&&<div className="overlay progress-overlay"><div className="report progress-report"><div className="progress-orb"><Sparkles size={24}/></div><small className="purple">LIVE ANALYSIS PIPELINE</small><h2>Comparing three models</h2><p className="muted">The recruiter workflow is extracting evidence, resolving skills, and building the comparison report.</p><div className="live-steps">{analysisProgress.steps.map((step,i)=><div className={'live-step '+step.status} key={step.label}><span className="live-step-number">{step.status==='complete'?<CheckCircle2 size={15}/>:String(i+1).padStart(2,'0')}</span><div><b>{step.label}</b><small>{step.status==='complete'?'Completed':step.status==='active'?'Processing now…':'Waiting'}</small></div><span className="step-state">{step.status==='active'?'●':step.status==='complete'?'✓':'·'}</span></div>)}</div><div className="progress-track"><i style={{width:Math.round((analysisProgress.active/analysisProgress.steps.length)*100)+'%'}}/></div><p className="muted">Please keep this page open while the analysis runs.</p></div></div>}{detail&&<div className="overlay" onClick={()=>D(null)}><div className="report" onClick={e=>e.stopPropagation()}><button className="close" onClick={()=>D(null)}>×</button><small className="purple">ANALYSIS REPORT</small><h2>{detail.job_title||'Resume analysis'}</h2><p className="muted">{detail.company||''} · {detail.filename||''}</p>{detail.result?.score!==undefined?<><div className="score"><strong>{detail.result.score}</strong><span>/ 100<br/>Hybrid ATS readiness estimate</span></div><h3 className="report-section-title">Three-model score comparison</h3><div className="model-comparison">{Object.entries(detail.result.model_comparison||{}).map(([key,model])=><div className={'model-card '+key} key={key}><div className="model-card-top"><span>{model.name}</span><b>{model.score}<small>/100</small></b></div><div className="bar"><i style={{width:model.score+'%'}}/></div><p>{model.contribution}</p><small>{model.formula}</small><div className="model-match">{(model.matched_skills||[]).length} required skills matched</div></div>)}</div><h3 className="report-section-title">Processing trace · component attribution</h3><div className="trace-list">{(detail.result.process_trace||[]).map((step,i)=><div className="trace-item" key={step.stage}><span className="trace-check"><CheckCircle2 size={15}/></span><div><b>{String(i+1).padStart(2,'0')} · {step.stage}</b><small>{step.component}</small><p>{step.detail}</p></div></div>)}</div><div className="metrics">{Object.entries(detail.result.breakdown||{}).map(([k,v])=><div key={k}><span>{k.replaceAll('_',' ')}</span><b>{v}%</b><div className="bar"><i style={{width:v+'%'}}/></div></div>)}</div><div className="twocol"><div><h4>✓ Matched skills</h4><Chips xs={detail.result.matched_skills}/></div><div><h4>! Skills to evidence</h4><Chips xs={detail.result.missing_skills}/></div></div><details className="component-details"><summary>Which component produced which skills?</summary><h4>Rule-based output</h4><Chips xs={detail.result.component_outputs?.rule_based_skills}/><h4>ML-based output</h4><Chips xs={detail.result.component_outputs?.ml_based_skills}/><h4>Resolved hybrid skill set</h4><Chips xs={detail.result.component_outputs?.resolved_hybrid_skills}/><h4>ML phrase evidence</h4>{(detail.result.component_outputs?.ml_phrase_evidence||[]).slice(0,12).map((x,i)=><p className="evidence-row" key={i}><b>{Math.round(x.confidence*100)}%</b> {x.phrase} <span>→ {(x.skills||[]).join(', ')}</span></p>)}</details><h4>Recommendations</h4><ul>{(detail.result.recommendations||[]).map(x=><li key={x}>{x}</li>)}</ul><details><summary>Structured extracted profile (JSON)</summary><pre>{JSON.stringify(detail.parsed,null,2)}</pre></details><p className="muted">{detail.result.caveat}</p></>:<p>Analysis has not run yet. Close and click Run analysis on the application.</p>}</div></div>}
{tab==='evaluation'&&user.role==='recruiter'&&<EvaluationPanel token={token}/>}
<footer>Resume_NER · Hybrid resume intelligence <span>Scores are advisory · Human review required</span></footer></main></div>}
function Stat({icon:I,n,t}){return <div className="stat"><i><I size={19}/></i><strong>{n}</strong><span>{t}</span></div>}
function JobCard({j,apply,recruiter}){return <article className="job"><div className="jobhead"><i><Building2 size={20}/></i><small>JOB DESCRIPTION</small></div><h3>{j.title}</h3><p>{j.company} {j.location&&'· '+j.location}</p><div className="desc">{j.description}</div><Chips xs={j.required_skills}/>{!recruiter&&<button className="linkbtn" onClick={apply}>Apply with resume ↗</button>}</article>}
function Chips({xs=[]}){return <div className="chips">{(xs||[]).map(x=><span key={x}>{x}</span>)}</div>}
function Empty({text}){return <div className="empty"><FileText/><p>{text}</p></div>}
function JobForm({form,set,submit,busy}){return <form className="panel jobform" onSubmit={submit}><h2>Publish a job description</h2><p className="muted">Use a real JD; no sample job descriptions are generated.</p><div className="grid"><label>Job title<input required minLength="3" value={form.title} onChange={e=>set({...form,title:e.target.value})}/></label><label>Company<input required value={form.company} onChange={e=>set({...form,company:e.target.value})}/></label><label className="fullrow">Location<input value={form.location} onChange={e=>set({...form,location:e.target.value})} placeholder="City · Hybrid / Remote"/></label><label className="fullrow">Full job description<textarea required minLength="50" rows="7" value={form.description} onChange={e=>set({...form,description:e.target.value})} placeholder="Paste responsibilities, qualifications, required and preferred skills…"/></label><label className="fullrow">Explicit required skills (comma-separated)<input value={form.required_skills} onChange={e=>set({...form,required_skills:e.target.value})} placeholder="Python, SQL, NLP"/></label></div><button className="primary" disabled={busy}>{busy?'Publishing…':'Publish job description'}</button></form>}
function AppTable({apps,analyze,detail,busy}){if(!apps.length)return <Empty text="Applications appear after an applicant uploads a resume for a listed role."/>;return <div className="tablewrap"><table><thead><tr><th>Applicant / Resume</th><th>Job</th><th>Status</th><th>Score</th><th>Actions</th></tr></thead><tbody>{apps.map(a=><tr key={a.id}><td><b>{a.applicant_name||a.filename}</b><small>{a.applicant_email||a.filename}</small></td><td>{a.job_title}<small>{a.company}</small></td><td><span className={'tag '+(a.status==='analyzed'?'done':'wait')}>{a.status==='analyzed'?'Analyzed':'Awaiting analysis'}</span></td><td><b>{a.result?.score!==undefined?a.result.score+'/100':'—'}</b></td><td>{a.status==='analyzed'?<button className="secondary" onClick={()=>detail(a.id)}>View report</button>:<button className="primary tiny" disabled={busy} onClick={()=>analyze(a.id)}>✧ Run analysis</button>}</td></tr>)}</tbody></table></div>}

function EvaluationPanel({token}){
 const [report,setReport]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState('');
 useEffect(()=>{let cancelled=false;setLoading(true);setError('');req('/model-evaluation',token).then(data=>{if(!cancelled)setReport(data)}).catch(e=>{if(!cancelled)setError(e.message||'Could not load the evaluation report')}).finally(()=>{if(!cancelled)setLoading(false)});return()=>{cancelled=true}},[token]);
 if(loading)return <section className="panel"><h2>ML benchmark evaluation</h2><p className="muted">Loading saved evaluation report…</p></section>;
 if(error)return <section className="panel"><h2>ML benchmark evaluation</h2><p className="error">{error}</p><p className="muted">The saved report should be at backend/reports/ml_benchmark_evaluation.json.</p></section>;
 const metrics=report.metrics||report.results||report;
 const accuracy=metrics.accuracy??report.accuracy;
 const macroF1=metrics.macro_f1??metrics.macro_f1_score??report.macro_f1??report.macro_f1_score;
 const skill=report.classification_report?.SKILL||report.classification_report?.skill||metrics.classification_report?.SKILL||{};
 const matrixFromReport=()=>{
  const supplied=report.confusion_matrix||report.confusionMatrix||metrics.confusion_matrix||metrics.confusionMatrix;
  if(Array.isArray(supplied)&&supplied.length>=2&&Array.isArray(supplied[0])&&Array.isArray(supplied[1]))return supplied;
  // Compatibility fallback for older saved reports that include class support/recall but omit the matrix.
  const cr=report.classification_report||metrics.classification_report||{};
  const other=cr.OTHER||cr.other||{}, skillClass=cr.SKILL||cr.skill||{};
  const roundedCorrect=(cls)=>Number.isFinite(Number(cls.support))&&Number.isFinite(Number(cls.recall))?Math.round(Number(cls.support)*Number(cls.recall)):null;
  const otherCorrect=roundedCorrect(other), skillCorrect=roundedCorrect(skillClass);
  if(otherCorrect!==null&&skillCorrect!==null&&Number.isFinite(Number(other.support))&&Number.isFinite(Number(skillClass.support))){
   return [[otherCorrect,Math.max(0,Number(other.support)-otherCorrect)],[Math.max(0,Number(skillClass.support)-skillCorrect),skillCorrect]];
  }
  return [];
 };
 const matrix=matrixFromReport();
 const nTest=report.test_examples??report.test_size??report.dataset?.test_examples??report.dataset?.test_size;
 const nTrain=report.train_examples??report.train_size??report.dataset?.train_examples??report.dataset?.train_size;
 const nTotal=report.total_examples??report.dataset_size??report.dataset?.total_examples??report.dataset?.size;
 const misclassified=report.misclassified_examples||report.misclassifications||report.errors||[];
 const limitations=report.limitations||report.notes||['This is a small phrase-classification benchmark, not an end-to-end evaluation of resume extraction.','Results do not establish performance on unseen real-world resumes.'];
 const pct=v=>v===undefined||v===null?'—':`${(Number(v)<=1?Number(v)*100:Number(v)).toFixed(1)}%`;
 const metricCard=(label,value,sub)=><div className="stat" key={label}><span>{label}</span><strong>{value}</strong>{sub&&<small className="muted">{sub}</small>}</div>;
 return <div className="evaluation-page" style={{display:'grid',gap:20}}>
  <section className="banner"><div><small>MODEL VALIDATION</small><h2>ML phrase-classifier evaluation</h2><p>Held-out benchmark results for the TF-IDF character n-gram and Logistic Regression phrase classifier. This is a phrase-level test, not a full resume-level NER score.</p></div></section>
  <div className="stats">{metricCard('Test accuracy',pct(accuracy),'Held-out test split')}{metricCard('Macro F1',pct(macroF1),'Average across both classes')}{metricCard('SKILL precision',pct(skill.precision??report.skill_precision),'Predicted skills that were correct')}{metricCard('SKILL recall',pct(skill.recall??report.skill_recall),'Benchmark skills detected')}</div>
  <section className="panel"><h2>Evaluation setup</h2><div className="stats">{metricCard('Total examples',nTotal??(Number(nTrain||0)+Number(nTest||0)||'—'),'Labeled phrase benchmark')}{metricCard('Training examples',nTrain??'—','Used to fit evaluation model')}{metricCard('Test examples',nTest??'—','Held out from training')}</div><p className="muted">Split: {report.split_strategy||report.split||'Stratified train/test split'}{report.random_state!==undefined?` · random_state=${report.random_state}`:''}{report.test_size_fraction!==undefined?` · test fraction=${report.test_size_fraction}`:''}</p>{report.generated_at&&<p className="muted">Generated: {report.generated_at}</p>}</section>
  <section className="panel"><h2>Confusion matrix</h2><p className="muted">Rows are actual labels; columns are predicted labels. Label order: OTHER, SKILL.</p>{Array.isArray(matrix)&&matrix.length>=2?<div className="tablewrap"><table><thead><tr><th>Actual \ Predicted</th><th>OTHER</th><th>SKILL</th></tr></thead><tbody>{['OTHER','SKILL'].map((label,i)=><tr key={label}><th>{label}</th><td>{matrix[i]?.[0]??'—'}</td><td>{matrix[i]?.[1]??'—'}</td></tr>)}</tbody></table></div>:<p className="muted">Confusion matrix is not present in the saved report.</p>}</section>
  <section className="panel"><h2>Misclassified benchmark phrases</h2>{misclassified.length?<div className="tablewrap"><table><thead><tr><th>Phrase</th><th>Actual</th><th>Predicted</th></tr></thead><tbody>{misclassified.map((item,i)=><tr key={i}><td>{typeof item==='string'?item:(item.phrase??item.text??item.input??'—')}</td><td>{item.actual??item.true_label??item.y_true??'—'}</td><td>{item.predicted??item.predicted_label??item.y_pred??'—'}</td></tr>)}</tbody></table></div>:<p className="muted">No misclassified examples were included in this report.</p>}</section>
  <section className="panel"><h2>Limitations and responsible interpretation</h2><ul>{(Array.isArray(limitations)?limitations:[String(limitations)]).map((item,i)=><li key={i}>{typeof item==='string'?item:JSON.stringify(item)}</li>)}</ul><p className="muted">Use these results as a small benchmark sanity check only. Recruiters must review resume evidence; the score is not a hiring decision.</p></section>
 </div>;
}

createRoot(document.getElementById('root')).render(<App/>);
