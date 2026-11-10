import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

const ROSTER = [
  {id: 'luna', name: 'Luna', model: 'gpt-6-luna', score: 0},
  {id: 'terra', name: 'Terra', model: 'gpt-6.1-terra', score: 0},
  {id: 'sonnet', name: 'Sonnet', model: 'anthropic/claude-sonnet-5.5', score: 0},
  {id: 'haiku', name: 'Haiku', model: 'anthropic/claude-haiku-5.5', score: 0},
];
const STEPS = ['DRAW', 'GUESS', 'SCORE'];
const PHASE_STEP = {awaiting_clue:0, creating_clue:0, checking_clue:0, rendering:0, guessing:1, judging:1, ready_to_reveal:1, reveal:2, complete:2};
const ACTIVE = ['creating_clue', 'checking_clue', 'rendering', 'guessing', 'judging'];
function Mark({kind='eye', className=''}) {
  const paths = {
    eye: <><path d="M3 18c8-10 18-10 26 0-8 10-18 10-26 0Z"/><circle cx="16" cy="18" r="3.5" fill="currentColor" stroke="none"/><path d="M5 8 2 5M11 5l-1-4M21 5l1-4M27 8l3-3"/></>,
    luna: <path d="M27 18.2A11.5 11.5 0 0 1 13.8 5 11.5 11.5 0 1 0 27 18.2Z" fill="currentColor" stroke="none"/>,
    terra: <><path d="m2 27 10-15 7 10M12 27l9-22 10 22"/></>,
    muse: <path d="M16 2c1 11 3 13 14 14-11 1-13 3-14 14C15 19 13 17 2 16 13 15 15 13 16 2Z" fill="currentColor" stroke="none"/>,
    sonnet: <><path d="M6 24 16 5l10 19M10 17h12"/><path d="M5 28h22"/></>,
    haiku: <><path d="M5 10c7-5 15-5 22 0M7 16c6-3 12-3 18 0M10 23h12"/></>,
    check: <path d="m7 16 6 6L26 9"/>,
    arrow: <path d="M5 16h22M19 8l8 8-8 8"/>,
    close: <path d="m8 8 16 16M24 8 8 24"/>,
  };
  return <svg className={className} width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[kind] || paths.eye}</svg>;
}
async function api(path, body, token) {
  const headers = body === undefined ? {} : {'Content-Type': 'application/json'};
  if(token) headers.Authorization='Bearer '+token;
  const response = await fetch(path, {method: body === undefined ? 'GET' : 'POST', headers, body: body === undefined ? undefined : JSON.stringify(body)});
  const json = await response.json();
  if (!response.ok) throw new Error(typeof json.error === 'string' ? json.error : 'The game could not complete this action.');
  return json;
}
const LINK_GAME = new URLSearchParams(window.location.search).get('game');
const SEAT_TOKEN = new URLSearchParams(window.location.hash.slice(1)).get('seat');
function App() {
  const [game,setGame]=useState(null),[loaded,setLoaded]=useState(false),[health,setHealth]=useState(null);
  const [hostToken,setHostToken]=useState(()=>localStorage.getItem('sight-unseen-host-token')||'');
  const [setup,setSetup]=useState(false),[seats,setSeats]=useState(ROSTER.map(p=>({...p,type:'ai'})));
  const [customGoals,setCustomGoals]=useState(''),[goalDraft,setGoalDraft]=useState(''),[stageView,setStageView]=useState(null);
  const [roundCount,setRoundCount]=useState('full'),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [help,setHelp]=useState(false),[zoom,setZoom]=useState(false),[selected,setSelected]=useState(null);
  const [clue,setClue]=useState(''),[guess,setGuess]=useState(''),[copied,setCopied]=useState('');
  const dialogRef=useRef(null),oldRound=useRef(''),autoReveal=useRef(''),hydratedPrompt=useRef('');
  const token=SEAT_TOKEN||hostToken;
  const inLobby=setup||!game;
  const isHost=game?.hostView ?? !SEAT_TOKEN;
  const viewer=game?.viewer;
  const players=inLobby?seats:game.players;
  const live=game?.rounds?.at(-1);
  const round=inLobby?null:selected===null?live:game.rounds.find(r=>r.number===selected)||live;
  const past=round&&round!==live;
  const phase=inLobby?'idle':past?'reveal':game.phase;
  const actualStep=PHASE_STEP[phase]??-1;
  const step=stageView??actualStep;
  const revealed=!!round?.answer;
  const describer=players.find(p=>p.id===(round?.describerId||round?.drawerId));
  const isDescriber=viewer?.playerId===describer?.id;
  const submitted=round?.submittedPlayerIds||[];
  const joined=viewer&&submitted.includes(viewer.playerId);
  const nameOf=id=>players.find(p=>p.id===id)?.name||id;
  const roundsWanted=roundCount==='full'?seats.length:Number(roundCount);
  const drawing=round?.drawing;
  const drawingSeconds=Math.max(0,Math.ceil(drawing?.secondsRemaining??60));
  const drawingBusy=['checking_clue','rendering','creating_clue'].includes(phase);
  const phaseStarted=Date.parse(round?.timings?.[phase]||'');
  const phaseElapsed=Number.isFinite(phaseStarted)?Math.max(0,Math.floor((Date.now()-phaseStarted)/1000)):0;
  const canEditDrawing=phase==='awaiting_clue'&&!busy;
  const visibleAttempts=round?.promptAttempts||[];
  const guesses=Array.isArray(round?.guesses)?round.guesses:[];
  const difficultyNames={1:'Warm-up',2:'Getting trickier',3:'Hard',4:'Deep cut'};
  const difficulty=round?.difficulty||1;
  const highest=Math.max(...players.map(p=>p.score||0));
  const winners=players.filter(p=>p.score===highest).map(p=>p.name);
  const winnerText=winners.length>1?`${winners.join(', ')} share the win.`:`${winners[0]} takes the win.`;
  const statusText={awaiting_clue:`Waiting for ${describer?.name}’s prompt`,creating_clue:`${describer?.name} is writing a prompt`,checking_clue:'Muse Ember is checking the prompt',rendering:'Muse Ember is drawing the scene',guessing:'Everyone makes their guess',judging:'Checking the locked guesses',ready_to_reveal:'The scores are ready',reveal:'The secret is out',complete:'Match complete',error:'This round stopped',cancelled:'Match stopped',idle:'Make room for a little mystery'}[phase]||phase;

  useEffect(()=>{
    let active=true;
    async function poll(){
      try{const data=await api(LINK_GAME?`/api/games/${LINK_GAME}`:'/api/games/latest',undefined,token);if(active){setGame(data.game);setLoaded(true);}}
      catch(e){if(active){setError(e.message);setLoaded(true);}}
    }
    poll();api('/api/health').then(setHealth).catch(()=>{});
    const timer=setInterval(poll,1200);return()=>{active=false;clearInterval(timer);};
  },[token]);
  useEffect(()=>{
    const key=game?`${game.id}-${game.roundIndex}`:'';
    if(key!==oldRound.current){oldRound.current=key;setClue('');setGuess('');setSelected(null);setStageView(null);setGoalDraft('');setZoom(false);setError('');}
  },[game?.id,game?.roundIndex]);
  useEffect(()=>{
    const latestPrompt=viewer?.playerId===live?.drawerId?live?.promptAttempts?.at(-1)?.clue:undefined;
    const roundKey=game?`${game.id}-${game.roundIndex}`:'';
    if(latestPrompt&&hydratedPrompt.current!==roundKey){
      hydratedPrompt.current=roundKey;
      setClue(current=>current||latestPrompt);
    }
  },[game?.id,game?.roundIndex,live?.promptAttempts,viewer?.playerId]);
  useEffect(()=>{setStageView(null);},[actualStep]);
  async function action(kind,body={}){
    setBusy(true);setError('');
    try{
      const isStarting=kind==='start'||kind==='demo';
      const startBody={
        rounds:kind==='demo'?3:roundsWanted,
        players:seats.map(({id,type,name})=>({id,type,name})),
        ...(kind==='demo'?{demoRoute:true}:{customGoals:customGoals.split('\n').map(s=>s.trim()).slice(0,roundsWanted)}),
      };
      const response=await api(isStarting?'/api/games':`/api/games/${game.id}/${kind}`,isStarting?startBody:body,token);
      if(response.hostToken){localStorage.setItem('sight-unseen-host-token',response.hostToken);setHostToken(response.hostToken);}
      setGame(response.game);setSelected(null);if(isStarting){setSetup(false);setStageView(null);}
      if(kind==='goal'){setClue('');setGoalDraft('');}
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  useEffect(()=>{
    if(game?.phase==='ready_to_reveal'&&isHost&&!inLobby){
      const key=`${game.id}-${game.roundIndex}`;
      if(autoReveal.current!==key){autoReveal.current=key;action('reveal');}
    }
  },[game?.phase,game?.id,game?.roundIndex,isHost,inLobby]);
  useEffect(()=>{
    if(!help&&!zoom)return;
    const restore=document.activeElement;dialogRef.current?.focus();
    const onKey=e=>{
      if(e.key==='Escape'){setHelp(false);setZoom(false);}
      if(e.key==='Tab'){
        const nodes=[...dialogRef.current.querySelectorAll('button:not(:disabled),a[href],input')];const first=nodes[0],last=nodes.at(-1);
        if(e.shiftKey&&(document.activeElement===first||document.activeElement===dialogRef.current)){e.preventDefault();last?.focus();}
        else if(!e.shiftKey&&(document.activeElement===last||document.activeElement===dialogRef.current)){e.preventDefault();first?.focus();}
      }
    };
    document.addEventListener('keydown',onKey);return()=>{document.removeEventListener('keydown',onKey);restore?.focus?.();};
  },[help,zoom]);

  function configure(id,values){setSeats(old=>old.map(p=>p.id===id?{...p,...values}:p));}
  function addPerson(){let i=1;while(seats.some(p=>p.id===`person-${i}`))i++;setSeats(old=>[...old,{id:`person-${i}`,name:`Player ${old.length+1}`,type:'human',score:0}]);}
  const stageTitle=inLobby?'A place. A prompt. A wild guess.':phase==='complete'?winnerText:step===2?'Did you see it?':step===1?'What place do you see?':isDescriber?'Describe it. Don’t name it.':'A picture starts with a prompt.';
  return <div className="shell">
    <header className="topbar"><a href="/" className="brand" aria-label="Pass the Ember home"><Mark/>Pass the Ember</a><span className="topmeta">California <span>·</span> Norway <span>·</span> Nepal</span><button className="text-button" onClick={()=>setHelp(true)}>How to play</button></header>
    <div className="layout">
      <main>
        <section className="intro"><h1>{stageTitle}</h1><p>{inLobby?'People and AI play. Muse Ember draws and checks the prompt.':phase==='complete'?'Different minds. A shared eye for places.':`Round ${round?.number||1} of ${game.totalRounds} · ${difficultyNames[difficulty]||`Level ${difficulty}`}`}</p></section>
        <nav className="stages" role="tablist" aria-label="Game stages">{STEPS.map((name,i)=><button type="button" role="tab" key={name} id={`stage-tab-${i}`} aria-controls="stage-panel" aria-selected={step===i} className={`${step===i?'current':''} ${i<actualStep?'done':''}`} onClick={()=>setStageView(i)}><span className="stage-number">0{i+1}</span><span>{name}</span>{i<actualStep&&<Mark kind="check"/>}</button>)}</nav>
        {viewer&&!inLobby&&<div className={`player-banner ${viewer.playerId}`}><Mark kind={viewer.playerId}/><span>Playing as <strong>{viewer.name}</strong></span><span className="banner-role">{isDescriber?'Describer':'Guesser'}</span></div>}
        {inLobby?<section className="lobby scene-enter"><h2>Who’s at the table?</h2><p>Choose your players. Muse Ember is always the artist and prompt judge.</p><div className="seat-setup">{seats.map((seat,i)=><div className="setup-row" key={seat.id}><div className={`mini-avatar ${seat.id}`}><Mark kind={seat.id}/></div><label htmlFor={`seat-${seat.id}`}>Seat {i+1}</label><select id={`seat-${seat.id}`} value={seat.type} onChange={e=>configure(seat.id,{type:e.target.value,name:e.target.value==='ai'?(ROSTER.find(p=>p.id===seat.id)?.name||seat.name):`Player ${i+1}`})}>{ROSTER.some(p=>p.id===seat.id)&&<option value="ai">{ROSTER.find(p=>p.id===seat.id).name} · AI</option>}<option value="human">Person</option></select>{seat.type==='human'?<input aria-label={`Name for seat ${i+1}`} value={seat.name} maxLength="24" onChange={e=>configure(seat.id,{name:e.target.value})}/>:<span className="setup-model">{seat.model}</span>}<button className="remove-seat" aria-label={`Remove seat ${i+1}`} disabled={seats.length<=2} onClick={()=>setSeats(old=>old.filter(p=>p.id!==seat.id))}><Mark kind="close"/></button></div>)}</div><div className="lobby-bottom"><button className="text-button" disabled={seats.length>=6} onClick={addPerson}>+ Add a person</button><label>Length <select aria-label="Match length" value={roundCount} onChange={e=>setRoundCount(e.target.value)}><option value="full">Full match · {seats.length} rounds</option><option value="1">Quick round · 1</option><option value="8">Long match · 8 rounds</option></select></label></div><details className="custom-goals"><summary>Choose your own drawing goals</summary><label htmlFor="custom-goals">One secret subject per line, in round order</label><textarea id="custom-goals" rows="3" maxLength="1000" value={customGoals} onChange={e=>setCustomGoals(e.target.value)} placeholder={"Golden Gate Bridge\nBoudhanath Stupa\na red panda"}/><p>Use the name of a place or subject. Blank rounds use surprise landmarks.</p></details><p className="lobby-note">Private links for people. Fresh pictures every round. The places get harder as you go.</p><button className="primary" disabled={busy||!loaded||seats.some(s=>!s.name.trim())||health?.openrouterConfigured===false} onClick={()=>action('start')}>{busy?'Starting…':'Start match'}<Mark kind="arrow"/></button><button className="secondary competition-demo" disabled={busy||!loaded||seats.some(s=>!s.name.trim())||health?.openrouterConfigured===false} onClick={()=>action('demo')}>Competition demo<Mark kind="arrow"/></button><p className="demo-route-note">3 rounds · San Francisco → Norway → Nepal · increasingly difficult</p></section>:<div className="scene-enter" id="stage-panel" role="tabpanel" aria-labelledby={`stage-tab-${Math.max(0,step)}`} key={`${round?.number}-${step}`}>
          {isHost&&game.invitations?.length>0&&!['complete','cancelled','error'].includes(phase)&&<details className="invite-panel"><summary>Private player links <span>{game.invitations.length} {game.invitations.length===1?'person':'people'}</span></summary><div className="invite-list">{game.invitations.map(inv=>{const url=`${location.origin}/?game=${game.id}#seat=${inv.token}`;return <div className="invite-row" key={inv.playerId}><strong>{inv.name}</strong><input aria-label={`Private link for ${inv.name}`} readOnly value={url} onFocus={e=>e.target.select()}/><button className="secondary" onClick={async()=>{try{await navigator.clipboard.writeText(url);setCopied(inv.playerId);}catch{setError('Select the private link and copy it.');}}}>{copied===inv.playerId?'Copied':'Copy'}</button><a href={url} target="_blank" rel="noopener noreferrer">Play as this person</a></div>})}</div></details>}
          {step===2?(revealed?<section className="reveal-panel score-stage"><div className="answer-heading"><div><span className="field-label">The landmark was</span><h2>{round.answer}</h2><p className="place-origin">{[round.region,round.country].filter(Boolean).join(', ')}</p></div>{round.imageUrl&&<button className="answer-thumb" onClick={()=>setZoom(true)} aria-label="Enlarge landmark drawing"><img src={round.imageUrl} alt={`Muse Ember’s drawing of ${round.answer}`}/></button>}</div><div className="score-verdict">The guesses</div><div className="guess-results">{guesses.map(g=><div className={`guess-result ${g.correct?'correct':'missed'}`} key={g.playerId}><div className={`mini-avatar ${g.playerId}`}><Mark kind={g.playerId}/></div><div><strong>{nameOf(g.playerId)}</strong><span>{g.guess}</span>{(g.explanation||g.reason)&&<details className="guess-explanation"><summary>Why this guess?</summary><p>{g.explanation||g.reason}</p></details>}</div><b>{g.correct?'+2':'0'}<small>points</small></b></div>)}</div><div className="describer-award"><span>Prompt by <strong>{describer?.name}</strong></span><strong>+{round.awards?.[describer?.id]||0} points</strong></div><details className="clue"><summary>Read the prompt</summary><blockquote>“{round.clue}”</blockquote></details></section>:<section className="locked-stage"><Mark kind="muse"/><h2>The score is still a secret.</h2><p>It appears after everyone has locked a guess.</p><button className="secondary" onClick={()=>setStageView(actualStep)}>Back to the live stage</button></section>):step===0&&viewer&&isDescriber&&game.privateAssignment?<section className="drawing-workspace">
            <div className="draw-topline"><div><span className="field-label">YOUR DRAWING TURN</span><h2>Make the picture recognizable.</h2></div><div className={`draw-clock ${drawingSeconds<=10?'urgent':''}`} aria-label={`${drawingSeconds} seconds of drawing time remaining`}><strong>{String(Math.floor(drawingSeconds/60)).padStart(2,'0')}:{String(drawingSeconds%60).padStart(2,'0')}</strong><span>{drawing?.paused?'Paused while Muse works':'Drawing time'}</span></div></div>
            <div className="draw-work-grid"><div className="draw-preview scene-card"><div className="scene-heading"><strong>{round?.imageUrl?'Your current drawing':'Your canvas'}</strong><span className={drawingBusy?'working':''}>{drawingBusy&&<i/>}{drawingBusy?statusText:round?.imageUrl?'Revise it or send it to the guessers':'Waiting for your first prompt'}</span></div><div className="scene">{round?.imageUrl?<><button className="image-button" onClick={()=>setZoom(true)} aria-label="Enlarge landmark drawing"><img src={round.imageUrl} alt="Your current landmark drawing"/></button>{drawingBusy&&<div className="drawing-overlay"><div className="button-spinner"/>{statusText}</div>}</>:<div className="waiting-scene"><div className="sketch-orbit"><Mark kind="muse"/></div><h2>{drawingBusy?statusText:'Your words become the picture.'}</h2><p>Describe the shape, color, materials and surroundings. You can improve the drawing before time runs out.</p>{drawingBusy&&<div className="loading-line"><span/></div>}</div>}</div></div>
            <div className="private-turn"><div className="private-label"><Mark kind="eye"/>Only you can see the goal</div><h2>{game.privateAssignment.name}</h2>{canEditDrawing&&game.privateAssignment.canChangeGoal&&<details className="change-goal"><summary>Use a different drawing goal</summary><label htmlFor="custom-goal">Name the place or subject</label><div><input id="custom-goal" maxLength="120" value={goalDraft} onChange={e=>setGoalDraft(e.target.value)} placeholder="e.g. a red panda"/><button className="secondary" disabled={!goalDraft.trim()||busy} onClick={()=>action('goal',{goal:goalDraft.trim()})}>Use this goal</button></div></details>}<p>Describe what we would see. No names, locations, trivia or written labels.</p>{game.privateFeedback&&<div className="clue-feedback" role="alert"><strong>Prompt needs a revision</strong><p>{typeof game.privateFeedback==='string'?game.privateFeedback:game.privateFeedback.reason}</p><span>{round?.imageUrl?'Your last accepted drawing is kept.':'Revise the prompt and try again.'}</span></div>}<form onSubmit={e=>{e.preventDefault();action('clue',{clue:clue.trim()});}}><label htmlFor="human-clue">Your prompt to Muse Ember</label><textarea id="human-clue" rows="7" placeholder="Picture a place with…" value={clue} maxLength="1600" onChange={e=>setClue(e.target.value)} disabled={!canEditDrawing}/><button className="primary" disabled={!canEditDrawing||!clue.trim()}>{drawingBusy?statusText:round?.imageUrl?'Revise the drawing':'Draw my prompt'}<Mark kind="arrow"/></button></form>{drawing?.canFinish&&<button className="secondary finish-drawing" disabled={busy||drawingBusy} onClick={()=>action('finish-drawing')}>Done drawing · let them guess<Mark kind="arrow"/></button>}<p className="timer-help">You have 60 seconds to write and revise. The clock pauses while Muse Ember checks and draws.</p></div></div>
          </section>:<>
          {step===0&&actualStep===0&&drawing&&<div className="public-draw-progress"><div><strong>{drawingBusy?statusText:`${describer?.name} is refining the drawing`}</strong><p>{drawing.paused?'The editing clock is paused while Muse Ember works.':'One minute to describe, see the result and improve it.'}</p></div><div className="draw-clock"><strong>{String(Math.floor(drawingSeconds/60)).padStart(2,'0')}:{String(drawingSeconds%60).padStart(2,'0')}</strong><span>Drawing time</span></div></div>}{step===0&&actualStep>0&&<section className="prompt-review"><h2>The drawing prompt</h2>{round?.clue?<blockquote>“{round.clue}”</blockquote>:<p>Read the submitted prompts and Muse Ember’s feedback in Drawing prompt checks below.</p>}</section>}<section className="scene-card"><div className="scene-heading"><strong>{step===1?'The picture is your only clue':'The drawing room'}</strong><span className={ACTIVE.includes(phase)?'working':''}>{ACTIVE.includes(phase)&&<i/>}{statusText}</span></div><div className="scene">{round?.imageUrl?<button className="image-button" onClick={()=>setZoom(true)} aria-label="Enlarge landmark drawing"><img src={round.imageUrl} alt="Mystery landmark drawing"/><span className="image-enlarge">View full picture<Mark kind="arrow"/></span></button>:<div className="waiting-scene"><div className="sketch-orbit"><Mark kind="muse"/></div><h2>{statusText}</h2><p>{phase==='rendering'?'A few words are becoming a place.':phase==='checking_clue'?'Muse Ember keeps names and giveaways out of the picture.':phase==='awaiting_clue'?`${describer?.name} has a private landmark to describe.`:phase==='error'||phase==='cancelled'?game.error||'Start a new match when you’re ready.':`${describer?.name} gets the secret. Everyone else gets the picture.`}</p>{ACTIVE.includes(phase)&&<div className="loading-line"><span/></div>}</div>}</div></section>
          {step===0&&describer?.type!=='human'&&visibleAttempts.length>0&&<section className="model-prompt-panel"><div className="model-prompt-heading"><span className={`mini-avatar ${describer?.id}`}><Mark kind={describer?.id}/></span><div><h2>{describer?.name}’s submitted prompt</h2><p>Actual model output · attempt {visibleAttempts.length}</p></div><span className={`verdict ${visibleAttempts.at(-1).verdict?.verdict}`}>{visibleAttempts.at(-1).verdict?.verdict==='allow'?'Approved for drawing':'Needs revision'}</span></div><p className="model-prompt-text">{visibleAttempts.at(-1).clue}</p></section>}
          {step===1&&viewer&&!isDescriber?<section className="spectator human-guess"><label htmlFor="human-guess">Your guess</label><form onSubmit={e=>{e.preventDefault();action('guess',{guess:guess.trim()});}}><input id="human-guess" placeholder="Name the place" maxLength="200" autoComplete="off" value={guess} onChange={e=>setGuess(e.target.value)} disabled={joined||busy||phase!=='guessing'}/><button className="primary" disabled={joined||busy||!guess.trim()||phase!=='guessing'}>{joined?'Guess locked':'Lock my guess'}</button></form><p>{joined?'Locked in. Scores appear once everyone has answered.':'One answer. Your guess stays private until the score.'}</p></section>:step===1?<div className="guess-wait"><strong>{phase==='judging'?'Checking the locked guesses…':`${submitted.length} of ${players.length-1} guesses locked`}</strong><p>{isDescriber?'Your prompt is in play. Let’s see if they get it.':'The next stage appears when everyone has answered.'}</p></div>:null}
          </>}
          {drawing&&<section className="drawing-insights" aria-label="Drawing prompt checks">
            <div className="insights-heading"><h2>Drawing prompt checks</h2><span>{drawing.attempts?.length||0} prompt {drawing.attempts?.length===1?'attempt':'attempts'}</span></div>
            <div className="insights-scroll" tabIndex="0" aria-label="Drawing activity and prompt attempts">
              <div className="insight-status"><span className={`status-dot ${drawingBusy?'busy':''}`}/><strong>{statusText}{drawingBusy&&<small className="phase-elapsed">{phaseElapsed}s elapsed</small>}</strong><p>{phase==='checking_clue'?'Muse Ember checks for names, location giveaways and written labels.':phase==='rendering'?'The approved description is becoming a 3D picture. The editing clock is paused.':phase==='awaiting_clue'?'The describer can submit a new visual description or improve the current drawing.':'The final picture is locked. Guesses are based on the image alone.'}</p></div>
              <div className="attempt-cards">{drawing.attempts?.map((attempt,index)=>{
                const detail=visibleAttempts?.[index];
                const pending=index===drawing.attempts.length-1&&attempt.status==='allow'&&drawingBusy;
                const verdictLabel=attempt.verdict==='allow'?'Prompt approved':attempt.verdict==='block'?'Prompt blocked':attempt.verdict==='revise'?'Prompt needs revision':attempt.status||'Checking';
                const duration=pending?`${phase==='rendering'?'Drawing':'Checking'}… ${phaseElapsed}s`:attempt.status==='render_failed'?'Drawing failed':attempt.seconds>0?`${Number(attempt.seconds).toFixed(1)}s`:'Checking…';
                return <article className={`attempt-card ${attempt.verdict}`} key={index}>
                  <header><strong>Drawing prompt {attempt.number||index+1}</strong><span className={`verdict ${attempt.verdict}`}>{verdictLabel}</span><small>{duration}</small></header>
                  {detail?<><div className="attempt-clue"><span>Submitted prompt</span><p>{detail.clue||detail.prompt}</p></div><div className="attempt-feedback"><strong>Muse Ember’s check</strong><p>{detail.verdict?.reason||detail.reason||'The prompt passed the check.'}</p></div></>:<p className="attempt-sealed">Waiting for the submitted prompt and check result.</p>}
                </article>;
              })}</div>
              {phase==='checking_clue'&&viewer&&isDescriber&&clue&&<article className="attempt-card pending"><header><strong>Checking submitted prompt</strong><small>{phaseElapsed}s elapsed</small></header><div className="attempt-clue"><p>{clue}</p></div><p className="attempt-sealed">Muse Ember is checking this description.</p></article>}
              {!drawing.attempts?.length&&phase!=='checking_clue'&&<p className="attempt-sealed">The first prompt check will appear here.</p>}
            </div>
            <p className="insight-privacy">Muse Ember checks drawing prompts. Guesses are marked correct or incorrect at SCORE.</p>
          </section>}

          {(phase==='reveal'||phase==='complete')&&<div className="actions">{past?<button className="primary" onClick={()=>setSelected(null)}>Back to current round<Mark kind="arrow"/></button>:isHost?<button className="primary" disabled={busy} onClick={()=>phase==='complete'?setSetup(true):action('next')}>{phase==='complete'?'Play again':game.rounds.length>=game.totalRounds?'Finish match':'Next round'}<Mark kind="arrow"/></button>:<p className="waiting-host">{phase==='complete'?'Thanks for playing.':'The host will start the next round.'}</p>}</div>}
          {['error','cancelled'].includes(phase)&&isHost&&<div className="actions"><button className="primary" onClick={()=>setSetup(true)}>New match<Mark kind="arrow"/></button></div>}
          {phase==='ready_to_reveal'&&isHost&&error&&<button className="primary" onClick={()=>action('reveal')}>Show scores</button>}
          {game.rounds.some(r=>r.answer)&&<nav className="round-history" aria-label="Round history">{game.rounds.filter(r=>r.answer).map(r=><button key={r.number} className={r===round?'selected':''} onClick={()=>setSelected(r.number)}><span>Round {r.number}</span>{r.answer}</button>)}</nav>}
        </div>}
        {error&&<p className="error" role="alert">{error}</p>}
      </main>
      <aside className="sidebar"><section className="muse-host"><div className="avatar muse"><Mark kind="muse"/></div><div><h2>Muse Ember</h2><p>Artist & prompt judge</p><p className="model-name">meta/muse-ember</p></div></section><h2 className="table-title">The players</h2><div className="players">{players.map(p=>{const role=inLobby?(p.type==='human'?'Ready to play':'Ready to play'):phase==='complete'?(p.score===highest?'Winner':'Good game'):p.id===describer?.id?'Describer':submitted.includes(p.id)?'Guess locked':'Guesser';return <div className={`player ${p.id} ${p.id===describer?.id?'is-drawer':''}`} key={p.id}><div className={`avatar ${p.id}`}><Mark kind={p.id}/></div><div className="player-name"><h3>{p.name}{viewer?.playerId===p.id&&<small className="you">you</small>}</h3><p>{role} · {p.type==='human'?'Person':'AI'}</p>{p.type!=='human'&&<p className="model-name">{p.model}</p>}</div><strong className="score">{p.score||0}</strong></div>})}</div><section className="round-note"><h3>{inLobby?'A little harder every time.':phase==='complete'?'Well played.':'One rule to remember.'}</h3><p>{inLobby?'From familiar silhouettes to deep cuts across California, Norway and Nepal.':'Describe the place. Never name it. Let the picture do the talking.'}</p></section>{!inLobby&&<details className="activity-details"><summary>Round activity</summary><div className="activity">{game.events.slice(-5).map((e,i)=><p key={`${e.at}-${i}`}><span className="dot muse"/>{e.message}</p>)}</div></details>}{!inLobby&&<div className="cost-note"><span>API cost this match</span><strong>${(game.cost?.openrouterUsd||0).toFixed(4)}</strong><small>Codex subscription usage is separate.</small></div>}{isHost&&!inLobby&&!['complete','cancelled','error'].includes(phase)&&<button className="text-button quiet stop-match" disabled={busy} onClick={()=>action('cancel')}>End match</button>}</aside>
    </div>
    <footer><p>2 points for a correct guess. 2 for a recognizable prompt.</p><p className="footer-note">Muse Ember checks the prompts and draws the scenes. One prompt, everyone else guesses.</p></footer>
    {(help||zoom)&&<div className="modal-backdrop" onClick={()=>{setHelp(false);setZoom(false);}}><section className={`modal ${zoom?'picture-modal':''}`} ref={dialogRef} role="dialog" aria-modal="true" aria-label={zoom?'Full landmark picture':'How to play'} tabIndex="-1" onClick={e=>e.stopPropagation()}><button className="close" aria-label="Close dialog" onClick={()=>{setHelp(false);setZoom(false);}}><Mark kind="close"/></button>{zoom?<img src={round?.imageUrl} alt={revealed?round.answer:'Mystery landmark'}/>:<><Mark className="help-eye"/><h2>Draw. Guess. Score.</h2><ol><li><strong>DRAW.</strong> One player receives a secret place and writes a visual prompt without naming it. Muse Ember checks the prompt and draws it. You have 60 seconds to revise; the clock pauses while the model works.</li><li><strong>GUESS.</strong> Everyone else sees only the picture and locks in one answer. Other players’ guesses stay hidden until SCORE.</li><li><strong>SCORE.</strong> The answer is revealed and guesses are matched to the landmark. Correct guesses earn 2 points; the describer earns 2 if anyone gets it.</li></ol><p className="help-note">Muse Ember is always the artist and prompt judge. Players can be people or AI. Each new round brings a harder place. People join using their own private links; the host starts the next round.</p><button className="primary" onClick={()=>setHelp(false)}>Let’s play<Mark kind="arrow"/></button></>}</section></div>}
  </div>;
}
createRoot(document.getElementById('root')).render(<App/>);
