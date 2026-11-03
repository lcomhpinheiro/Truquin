'use strict';
const $ = id => document.getElementById(id);
const suitSymbol = {Clubs:'♣',Hearts:'♥',Spades:'♠',Diamonds:'♦'};
const ranks = ['4','5','6','7','Q','J','K','A','2','3'];
const names = {lobby:'Aguardando',playing:'Em jogo',trick_end:'Fim da vaza',hand_end:'Fim da mão',finished:'Fim de partida',eleven:'Mão de onze'};
let session = null, state = null, capacity = 4, busy = false, pollBusy = false, lastRender = '', toastTimer;
let prevScore = null, prevHandNo = 0, prevPendingKey = '', dealTimer, victoryShown = false;
// A partida acaba com as cartas ainda na mesa: a tela final espera um pouco
// para todo mundo ver o lance que decidiu.
const VICTORY_DELAY = 2800;
let prevPhase = '', victoryTimer = 0, victoryReady = false;
let chatScope = 'room', chatOpen = false, chatSeen = 0, chatKey = '';
try { session = JSON.parse(sessionStorage.getItem('truco-session')); $('nickname').value = localStorage.getItem('truco-name') || ''; } catch {}
function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 4200); }
function node(tag, cls, text) { const el = document.createElement(tag); if (cls) el.className = cls; if (text !== undefined) el.textContent = text; return el; }
function cardURL(c) { if (!c || c.blind || c.covered) return '/assets/Backs/back_0.png'; const value = {A:1,J:11,Q:12,K:13}[c.rank] || Number(c.rank); return `/assets/${c.suit}/${c.suit}_card_${String(value).padStart(2,'0')}.png`; }
function cardImage(c) { const img = node('img'); img.src = cardURL(c); img.alt = !c || c.blind || c.covered ? 'Carta fechada' : `${c.rank} ${suitSymbol[c.suit]}`; img.draggable = false; return img; }
async function api(path, data) { const response = await fetch('/api/' + path, data ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)} : {cache:'no-store'}); const result = await response.json(); if (!response.ok) throw new Error(result.error || 'Não foi possível concluir.'); return result; }
function nickname() { const name = $('nickname').value.trim(); if (!name) { $('nickname').focus(); throw new Error('Digite seu apelido para puxar uma cadeira.'); } try { localStorage.setItem('truco-name', name); } catch {} return name; }
async function enter(kind, room) { if (busy) return; busy = true; try { const name = nickname(); const result = await api(kind, kind === 'create' ? {name, room_name:$('room-name').value, capacity, cut_enabled:true} : {name,room}); session = result; sessionStorage.setItem('truco-session',JSON.stringify(session)); lastRender=''; history.replaceState(null,'', '/?mesa=' + result.room); await poll(); } catch (e) { toast(e.message); } finally { busy=false; } }
async function action(actionName, extra = {}) { if (busy || !session) return; busy = true; document.body.classList.add('is-sending');$('game').setAttribute('aria-busy','true'); try { const result = await api('action',{...session,action:actionName,...extra}); state = result; render(result); } catch (e) { toast(e.message); } finally { busy=false;document.body.classList.remove('is-sending');$('game').setAttribute('aria-busy','false'); } }
function setTab(create) { $('create-form').hidden = !create; $('join-form').hidden = create; $('create-tab').classList.toggle('selected',create); $('join-tab').classList.toggle('selected',!create); $('create-tab').setAttribute('aria-selected',String(create)); $('join-tab').setAttribute('aria-selected',String(!create)); }
$('create-tab').onclick = () => setTab(true); $('join-tab').onclick = () => setTab(false);
document.querySelectorAll('.mode').forEach(el => el.onclick = () => { capacity=Number(el.dataset.capacity); document.querySelectorAll('.mode').forEach(b => b.classList.toggle('selected',b===el)); });
$('create-form').onsubmit = e => { e.preventDefault(); enter('create'); };
$('join-form').onsubmit = e => { e.preventDefault(); enter('join',$('room-code').value.trim().toUpperCase()); };
$('start').onclick = () => action('start'); $('fill-bots').onclick = () => action('bots'); $('raise').onclick = () => action('raise');
$('accept').onclick = () => action('respond',{answer:'accept'}); $('run').onclick = () => action('respond',{answer:'run'}); $('reraise').onclick = () => action('respond',{answer:'raise'}); $('rematch').onclick = () => action('rematch');
$('leave').onclick = async () => { if(busy)return;busy=true;try { await api('action',{...session,action:'leave'});session=null;state=null;lastRender='';sessionStorage.removeItem('truco-session');history.replaceState(null,'','/');$('game').hidden=true;$('home').hidden=false;document.body.classList.remove('at-table','shouting');prevScore=null;prevHandNo=0;prevPendingKey='';victoryShown=false;confetti($('confetti'),false);chatOpen=false;$('chat-dock').hidden=true;chatSeen=0;chatKey='';clearTimeout(victoryTimer);victoryTimer=0;victoryReady=false;prevPhase='';toast('Você saiu da mesa.');rooms(); } catch(e) {toast(e.message);} finally {busy=false;} };
$('rules-open').onclick = $('credits-open').onclick = () => $('rules').showModal(); $('rules-close').onclick = () => $('rules').close();
$('rules').onclick = e => { if(e.target===$('rules')) { const rect=$('rules').getBoundingClientRect(); if(e.clientX<rect.left||e.clientX>rect.right||e.clientY<rect.top||e.clientY>rect.bottom) $('rules').close(); } };
async function copyInvite() { const link = `${location.origin}/?mesa=${session.room}`; try { await navigator.clipboard.writeText(link); toast('Convite copiado! Envie para a turma na mesma rede.'); } catch { const box = node('textarea');box.value=link;box.style.position='fixed';box.style.left='-9999px';document.body.append(box);box.select();const ok=document.execCommand('copy');box.remove();toast(ok?'Convite copiado!':`Convite: ${link}`); } }
$('invite').onclick=$('copy-link').onclick=copyInvite;
$('refresh').onclick=rooms;
async function rooms() { if(session) return; try { const data = await api('rooms'); $('rooms-count').textContent=data.rooms.length; const container=$('rooms');container.replaceChildren(); if(!data.rooms.length) container.append(node('div','empty-state','Ainda não tem mesa aberta. Que tal puxar a primeira?')); for(const r of data.rooms) { const item=node('div','room-item'),text=node('div');text.append(node('strong','',r.name),node('small','',`${r.capacity===4?'DUPLAS':'DUELO'} · ${r.players}/${r.capacity} jogadores · ${r.code}`));const button=node('button','secondary','Entrar →');button.onclick=()=>enter('join',r.code);item.append(text,button);container.append(item); } } catch { toast('Sem conexão com o servidor. Verifique se o Python está rodando.'); } }
function seatPosition(i, s) { const relative = (i - s.seat + s.capacity) % s.capacity; return s.capacity === 2 ? ['bottom','top'][relative] : ['bottom','left','top','right'][relative]; }
function shoutWord(value) { return value === 3 ? 'TRUCO!' : value === 6 ? 'SEIS!' : value === 9 ? 'NOVE!' : 'DOZE!'; }
function replay(el, cls) { el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); }
function setCards(box, cards) { const key = cards.map(c => (c && c.id) || 'x').join(','); if (box.dataset.key === key) return; box.dataset.key = key;
  box.replaceChildren(...cards.map((c, i) => { const img = cardImage(c); img.style.setProperty('--i', String(i)); return img; })); }
function confetti(box, on) { box.replaceChildren(); if (!on) return; const colors = ['#e6bd65','#83b9d0','#d87960','#8fd6a8','#fff3cf'];
  for (let i = 0; i < 30; i++) { const bit = node('i'); bit.style.setProperty('--x', `${Math.random() * 100}%`);
   bit.style.setProperty('--d', `${(Math.random() * 2.4).toFixed(2)}s`); bit.style.setProperty('--r', `${Math.round(Math.random() * 540)}deg`);
   bit.style.setProperty('--w', `${6 + Math.round(Math.random() * 7)}px`); bit.style.background = colors[i % colors.length]; box.append(bit); } }
function render(s) {
 const signature=JSON.stringify(s);if(signature===lastRender)return;lastRender=signature;
 $('home').hidden=true;$('game').hidden=false;document.body.classList.add('at-table');
 $('game-title').textContent=s.name;$('game-mode').textContent=s.capacity===4?' / DUPLAS':' / DUELO';$('invite-code').textContent=s.code;
 $('score-blue').textContent=String(s.score[0]).padStart(2,'0');$('score-coral').textContent=String(s.score[1]).padStart(2,'0');
 ['score-blue','score-coral'].forEach((id,team)=>{if(prevScore&&prevScore[team]!==s.score[team])replay($(id),'bump');});
 prevScore=s.score.slice();
 const pendingKey=s.pending?`${s.hand_no}:${s.pending.team}:${s.pending.value}:${s.pending.seat}`:'';
 if(pendingKey&&pendingKey!==prevPendingKey)replay(document.body,'shouting');else if(!pendingKey)document.body.classList.remove('shouting');
 prevPendingKey=pendingKey;
 $('hand-number').textContent=s.hand_no?`MÃO ${String(s.hand_no).padStart(2,'0')}`:'AGUARDANDO';
 const seats=$('seats');seats.replaceChildren();
 for(let i=0;i<s.capacity;i++) { const position=seatPosition(i,s);const p=s.players[i];const active=s.phase==='playing'&&!s.pending&&s.turn===i;const seat=node('div',`seat seat-${position} team-${i%2}${active?' active':''}${p?'':' empty'}`);seat.append(node('div','avatar',p?p.name.slice(0,1).toUpperCase():'+'));seat.append(node('div','seat-name',p?`${p.name}${i===s.seat?' (você)':''}`:'Lugar livre'));seat.append(node('div','seat-note',p?(p.bot?'BOT':!p.online?'DESCONECTADO':active?'NA VEZ':i%2===s.seat%2?'SUA EQUIPE':'ADVERSÁRIO'):'AGUARDANDO'));const backs=node('div','seat-cards');if(p&&i!==s.seat)for(let n=0;n<p.count;n++)backs.append(cardImage(null));seat.append(backs);if(s.pending&&s.pending.seat===i)seat.append(node('div','seat-shout',shoutWord(s.pending.value)));seats.append(seat); }
 $('vira-box').hidden=!s.vira;
 if(s.vira) { if($('vira').dataset.card!==`${s.hand_no}:${s.vira.id}`){$('vira').replaceChildren(cardImage(s.vira));$('vira').dataset.card=`${s.hand_no}:${s.vira.id}`;}$('manilha').textContent=`MANILHA: ${ranks[(ranks.indexOf(s.vira.rank)+1)%10]}`; }
 $('table-stake').textContent=s.hand_no?`VALE ${s.stake} ${s.stake===1?'PONTO':'PONTOS'}`:'RESERVE SEU LUGAR';
 const table=$('table-cards');const previousCards=new Set([...table.children].map(el=>el.dataset.play));table.replaceChildren();s.table.forEach(p=>{const wrap=node('div','played-wrap');wrap.dataset.play=JSON.stringify(p);wrap.dataset.from=seatPosition(p.seat,s);if(previousCards.has(wrap.dataset.play))wrap.classList.add('settled');if(s.trick_winner===p.seat&&['trick_end','hand_end','finished'].includes(s.phase))wrap.classList.add('winner');wrap.append(cardImage(p.card),node('small','',s.players[p.seat].name));table.append(wrap);});
 const settled=['trick_end','hand_end','finished'].includes(s.phase)&&s.trick_winner!==null&&s.trick_winner!==undefined;
 table.classList.toggle('resolved',settled);table.parentElement.classList.toggle('resolved',settled);
 document.querySelector('.table-logo').hidden=s.table.length>0;
 const dots=$('trick-dots');dots.replaceChildren();if(s.hand_no)for(let i=0;i<3;i++)dots.append(node('div',`trick-dot${i<s.results.length&&s.results[i]!==null?' won-'+s.results[i]:''}`,i<s.results.length?(s.results[i]===null?'=':s.results[i]===s.seat%2?'✓':'×'):String(i+1)));
 const yourTurn=s.phase==='playing'&&!s.pending&&s.turn===s.seat;
 const ran=(s.pending&&s.pending.ran)||[],iRan=ran.includes(s.seat);
 const canRespond=s.phase==='eleven'?s.eleven===s.seat%2:!!s.pending&&s.pending.team!==s.seat%2&&!iRan;
 let status='';
 if(s.phase==='lobby')status=s.players.length<s.capacity?`Aguardando a turma · ${s.players.length} de ${s.capacity} lugares ocupados.`:(s.host?'Mesa completa. Pode começar a resenha!':'Mesa completa. Aguardando o anfitrião começar.');
 else if(s.phase==='eleven')status=canRespond?'Mão de onze! Olhe as cartas e decida: jogar por 3 ou correr.':'A equipe com onze está decidindo se joga.';
 else if(s.pending)status=`${s.pending.value===3?'TRUCO!':s.pending.value+' PONTOS!'} ${canRespond?'Sua equipe aceita o desafio?':'Aguardando a resposta dos adversários…'}`;
 else if(s.phase==='playing')status=yourTurn?(s.iron?'Mão de ferro: escolha uma carta às cegas.':'Sua vez! Escolha uma carta ou peça aumento.'):`É a vez de ${s.players[s.turn].name}.`;
 else if(s.phase==='trick_end')status=`${s.results.at(-1)===null?'A vaza empatou.':'Equipe '+(s.results.at(-1)===0?'Azul':'Coral')+' levou a vaza.'} Próxima em ${s.next_in}s…`;
 else if(s.phase==='hand_end')status=`${s.log.at(-1)} Nova mão em ${s.next_in}s…`;
 else if(s.phase==='finished')status=`${s.winner===s.seat%2?'Sua equipe venceu!':'A equipe adversária levou essa.'} Placar final: ${s.score[0]} × ${s.score[1]}.`;
 const preparing=['shuffling','cut','cutting'].includes(s.phase);
 $('cut-scene').hidden=!preparing;
 $('cut-scene').dataset.phase=s.phase;
 const myCut=s.phase==='cut'&&s.cutter===s.seat;
 $('cut-button').hidden=!myCut;
 $('cut-slider').hidden=!myCut;
 $('cut-title').textContent=s.phase==='shuffling'?'Embaralhando…':s.phase==='cutting'?'Corte feito!':myCut?'É sua vez de cortar':`${s.players[s.cutter]?.name} vai cortar`;
 $('cut-hint').textContent=s.phase==='cut'?`${myCut?'Escolha a altura do corte e toque em Cortar.':'Aguardando o corte.'} Automático em ${s.next_in}s.`:s.phase==='cutting'?`Corte em ${s.cut_position} cartas · distribuindo…`:'Misturando as 40 cartas para a próxima mão.';
 if(preparing) status='Prepare o blefe. Uma nova mão vai começar.';
 $('status').textContent=status;
 $('lobby-actions').hidden=!(s.phase==='lobby'&&s.host);$('fill-bots').hidden=s.players.length===s.capacity;$('start').disabled=s.players.length!==s.capacity;
 const challenge=!!s.pending||s.phase==='eleven';
 $('challenge-overlay').hidden=!challenge;
 $('challenge-title').textContent=s.phase==='eleven'?'MÃO DE ONZE':s.pending?.value===3?'TRUCO!':s.pending?`VALE ${s.pending.value}!`:'';
 $('challenge-overlay').dataset.level=s.pending?.value||'eleven';
 $('challenge-kicker').textContent=s.pending?`${s.players[s.pending.seat]?.name||'A outra equipe'} pediu`.toUpperCase():'DESAFIO NA MESA';
 $('challenge-detail').textContent=s.phase==='eleven'?'A decisão vale a partida.':`Equipe ${s.pending?.team===0?'Azul':'Coral'} pediu ${s.pending?.value||3} pontos.`;
 $('challenge-cost').textContent=canRespond?`Aceitar: vale ${s.phase==='eleven'?3:s.pending.value}. Correr: adversários ganham ${s.phase==='eleven'?1:s.stake}.`:'Sua equipe lançou o desafio.';
 const showCards=challenge&&!!s.vira;
 $('challenge-cards').hidden=!showCards;
 if(showCards){
  setCards($('cc-vira'),[s.vira]);
  $('cc-manilha').textContent=`MANILHA ${ranks[(ranks.indexOf(s.vira.rank)+1)%10]}`;
  setCards($('cc-hand'),s.hand);
  $('cc-partner-group').hidden=!s.partner.length;
  if(s.partner.length)setCards($('cc-partner'),s.partner);
 }
 const waiting=s.pending?[...Array(s.capacity).keys()].filter(i=>i%2!==s.pending.team&&!ran.includes(i)):[];
 const missing=waiting.map(i=>i===s.seat?'você':s.players[i].name).join(' e ');
 $('challenge-ran').hidden=!(s.pending&&ran.length);
 if(s.pending&&ran.length)$('challenge-ran').textContent=(iRan?'Você quis correr.':`${ran.map(i=>s.players[i].name).join(' e ')} quis correr.`)+(missing?` Falta ${missing} decidir.`:'');
 $('challenge-wait').textContent=iRan?'Esperando a decisão do seu parceiro…':'Aguardando a resposta da outra equipe…';
 $('challenge-wait').hidden=canRespond;
 $('run').textContent=`Correr · ceder ${s.phase==='eleven'?1:s.stake}`;
 $('response-actions').hidden=!canRespond;$('accept').textContent=s.phase==='eleven'?'Jogar por 3':`Aceitar · ${s.pending?.value||s.stake} pontos`;$('reraise').hidden=s.phase==='eleven'||!s.pending||s.pending.value===12;
 if(s.pending&&s.pending.value<12)$('reraise').textContent='Pedir '+[3,6,9,12][[3,6,9,12].indexOf(s.pending.value)+1];
 $('play-actions').hidden=!yourTurn;$('raise').hidden=!s.can_raise;$('raise').textContent=s.stake===1?'TRUCO!':'PEDIR '+[1,3,6,9,12][[1,3,6,9,12].indexOf(s.stake)+1];
 $('covered').disabled=!s.results.length||!yourTurn;if(!s.results.length)$('covered').checked=false;
 $('rematch').hidden=!(s.phase==='finished'&&s.host);
 const over=s.phase==='finished',won=over&&s.winner===s.seat%2;
 if(!over){clearTimeout(victoryTimer);victoryTimer=0;victoryReady=false;}
 else if(!victoryReady&&!victoryTimer){
  if(prevPhase&&prevPhase!=='finished')victoryTimer=setTimeout(()=>{victoryTimer=0;victoryReady=true;if(state&&state.phase==='finished'){lastRender='';render(state);}},VICTORY_DELAY);
  else victoryReady=true;
 }
 const showVictory=over&&victoryReady;
 $('victory-overlay').hidden=!showVictory;
 $('victory-overlay').classList.toggle('lost',showVictory&&!won);
 if(showVictory){
  $('victory-kicker').textContent=`FIM DE PARTIDA · ${s.capacity===4?'DUPLAS':'DUELO'}`;
  $('victory-medal').textContent=won?'♣':'♠';
  $('victory-title').textContent=won?'VITÓRIA!':'NÃO FOI DESSA VEZ.';
  $('victory-team').textContent=`Equipe ${s.winner===0?'Azul':'Coral'} levou a partida.`;
  $('victory-blue').textContent=String(s.score[0]).padStart(2,'0');$('victory-coral').textContent=String(s.score[1]).padStart(2,'0');
  $('vs-blue').className=`vs-team ${s.winner===0?'won':'lost'}`;$('vs-coral').className=`vs-team ${s.winner===1?'won':'lost'}`;
  $('victory-summary').textContent=`${s.hand_no} ${s.hand_no===1?'mão disputada':'mãos disputadas'} nesta mesa.`;
  $('victory-wait').hidden=s.host;
  if(!victoryShown){victoryShown=true;confetti($('confetti'),won);}
 } else if(victoryShown){victoryShown=false;confetti($('confetti'),false);}
 prevPhase=s.phase;
 $('hand-hint').textContent=s.phase==='lobby'?'Esperando a partida começar.':s.iron?'Cartas às cegas · mão de ferro':yourTurn?'Clique em uma carta para jogar.':'Só você pode ver estas cartas.';
 const hand=$('hand');
 if(!s.hand_no)prevHandNo=0;
 if(s.hand.length&&prevHandNo!==s.hand_no){prevHandNo=s.hand_no;hand.classList.add('dealing');clearTimeout(dealTimer);dealTimer=setTimeout(()=>hand.classList.remove('dealing'),950);}
 hand.replaceChildren();s.hand.forEach((c,index)=>{const b=node('button','card-button');b.style.setProperty('--i',String(index));b.append(cardImage(c));b.disabled=!yourTurn;b.setAttribute('aria-label',c.blind?'Jogar carta às cegas':`Jogar ${c.rank} ${suitSymbol[c.suit]}`);if(s.vira&&c.rank===ranks[(ranks.indexOf(s.vira.rank)+1)%10])b.classList.add('is-manilha');b.onclick=()=>action('play',{card:c.id,covered:$('covered').checked});hand.append(b);});
 $('partner-area').hidden=!s.partner.length;$('partner-hand').replaceChildren(...s.partner.map(cardImage));
 $('history').replaceChildren(...s.log.slice().reverse().map(msg=>node('li','',msg)));
 renderChat(s);
}

function renderChat(s) {
 const all=s.chat||[];
 $('chat-tab-team').hidden=s.capacity!==4;
 if(s.capacity!==4&&chatScope==='team')chatScope='room';
 const msgs=all.filter(m=>m.scope===chatScope);
 const key=`${chatScope}|${s.seat}|${msgs.map(m=>m.id).join(',')}`;
 if(key!==chatKey){
  chatKey=key;const log=$('chat-log');
  const atBottom=log.scrollHeight-log.scrollTop-log.clientHeight<40;
  log.replaceChildren(...(msgs.length?msgs.map(m=>{
   const li=node('li',`team-${m.team}${m.seat===s.seat?' mine':''}${m.scope==='team'?' is-team':''}`);
   li.append(node('b','',m.seat===s.seat?'Você':m.name),document.createTextNode(m.text));return li;
  }):[node('li','chat-empty',chatScope==='team'?'Conversa reservada à sua dupla. Os adversários não leem.':'Ninguém falou ainda. Quebra o gelo!')]));
  if(atBottom)log.scrollTop=log.scrollHeight;
 }
 const last=all.length?all[all.length-1].id:0;
 if(chatOpen)chatSeen=last;
 const unread=all.filter(m=>m.id>chatSeen&&m.seat!==s.seat).length;
 $('chat-badge').hidden=!unread||chatOpen;$('chat-badge').textContent=String(unread);
}
async function poll() { if(!session||pollBusy)return;pollBusy=true;const activeSession=session;try{const s=await api(`state?room=${encodeURIComponent(activeSession.room)}&token=${encodeURIComponent(activeSession.token)}`);if(session!==activeSession)return;state=s;render(s);$('connection').lastChild.textContent=' CONECTADO';$('connection').querySelector('i').style.background='#588b5a';}catch(e){$('connection').lastChild.textContent=' RECONECTANDO';$('connection').querySelector('i').style.background='#d87960';if(e.message.includes('Mesa não encontrada')||e.message.includes('sessão não pertence')) {session=null;sessionStorage.removeItem('truco-session');$('game').hidden=true;$('home').hidden=false;document.body.classList.remove('at-table');toast(e.message);}}finally{pollBusy=false;}}
const invited=new URLSearchParams(location.search).get('mesa');if(invited&&!session){$('room-code').value=invited.toUpperCase();setTab(false);}
if(session)poll();else rooms();
setInterval(()=>{if(session)poll();},700);setInterval(()=>{if(!session)rooms();},6000);

$('table-info').onclick=()=>$('table-drawer').showModal();
$('drawer-close').onclick=()=>$('table-drawer').close();
$('fullscreen').onclick=async()=>{
 try {
  if(document.fullscreenElement) await document.exitFullscreen();
  else if(document.documentElement.requestFullscreen) await document.documentElement.requestFullscreen();
  else toast('A mesa já ocupa toda a área disponível. Este navegador não oferece tela cheia.');
 } catch {toast('Não foi possível ocultar as barras do navegador. A mesa continua expandida.');}
};
document.addEventListener('fullscreenchange',()=>{$('fullscreen').textContent=document.fullscreenElement?'⛶ Sair da tela cheia':'⛶ Tela cheia';});

$('victory-leave').onclick=()=>$('leave').click();
function setChatScope(scope){chatScope=scope;chatKey='';
 for(const [id,name] of [['chat-tab-room','room'],['chat-tab-team','team']]){$(id).classList.toggle('selected',scope===name);$(id).setAttribute('aria-selected',String(scope===name));}
 $('chat-dock').classList.toggle('team-mode',scope==='team');
 $('chat-input').placeholder=scope==='team'?'Só o seu parceiro lê…':'Falar na mesa…';
 if(state)renderChat(state);}
$('chat-tab-room').onclick=()=>setChatScope('room');$('chat-tab-team').onclick=()=>setChatScope('team');
$('chat-open').onclick=()=>{chatOpen=!chatOpen;$('chat-dock').hidden=!chatOpen;if(chatOpen){if(state)renderChat(state);$('chat-log').scrollTop=$('chat-log').scrollHeight;$('chat-input').focus();}};
$('chat-close').onclick=()=>{chatOpen=false;$('chat-dock').hidden=true;};
$('chat-form').onsubmit=async e=>{e.preventDefault();const text=$('chat-input').value.trim();if(!text||!session)return;
 $('chat-input').value='';
 try{const result=await api('action',{...session,action:'chat',text,scope:chatScope});state=result;render(result);$('chat-log').scrollTop=$('chat-log').scrollHeight;}
 catch(err){toast(err.message);$('chat-input').value=text;}};
$('table-rules').onclick=()=>{$('table-drawer').close();$('rules').showModal();};

$('cut-button').onclick=()=>action('cut',{position:Number($('cut-slider').value)});
$('cut-slider').oninput=()=>{$('cut-button').textContent=`Cortar em ${$('cut-slider').value} cartas ✂`;};
