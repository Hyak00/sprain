const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const {parseHTML}=require('linkedom');
async function ambiente({perfil='ADMIN',handler}={}){
 const {window}=parseHTML('<html><body><button data-secao="interno"></button><section id="conteudo"></section></body></html>');const {document}=window;let ativo=true;const chamadas=[];
 Object.defineProperty(window.HTMLSelectElement.prototype,'value',{configurable:true,get(){return this.querySelector('option[selected]')?.value||this.querySelector('option')?.value||'';},set(v){this.querySelectorAll('option').forEach(o=>o.toggleAttribute('selected',o.value===v));}});
 window.PainelSessao={perfil:()=>perfil};window.PortalDados={data:v=>v||'Não informado',dataCalendario:v=>v||'Não informada'};window.PortalOperacional={registrarSecao:()=>{}};
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../../static/painel-interno.js'),'utf8'),vm.createContext({window,document,console,Date}));
 const ctx={atual:()=>ativo,recarregar:()=>{},obter:async(url,o)=>{chamadas.push({url,o});const h=handler?await handler(url,o):undefined;if(h!==undefined)return h;
  if(url.includes('/operacional/fontes'))return{consultado_em:'2026-10-17T12:00:00Z',fontes:[{nome:'Fonte <script>ruim</script>',tipo:'OBSERVACAO',idade_minutos:null,status:'SEM_DATA_VALIDA',limite_minutos:30,criterio:'Não é SLA',registros:0}],tentativas_dados_publicos:[{fonte:'DADOS_PUBLICOS/anp',status:'FALHA',iniciado_em:'2026-10-17T12:00:00Z',encerrado_em:'2026-10-17T12:01:00Z',motivo_codigo:'EXECUCAO_INTERROMPIDA'}],integracoes:[]};
  if(url.includes('/operacional/importacoes'))return{items:[],proximo_offset:null,aviso:'Histórico instrumentado'};
  if(url.includes('/operacional/metricas-endpoints'))return{periodo:'2026-10',fuso_periodo:'America/Sao_Paulo',endpoints:[],truncado:false};
  if(url.includes('/health/liveness'))return{status:'UP'};if(url.includes('/health/readiness'))return{status:'READY',latencia_db_ms:0};
  if(url.includes('malha/importacoes'))return[];if(url.includes('indicadores'))return{status_geral:'ATENCAO_FONTES',detalhamento_fontes:[],total_registros_base:{trechos:0}};
  if(url.includes('qualidade-precos'))return{total_registros_analisados:0,alertas:{preco_atipico:0,dado_desatualizado:0}};
  if(url.includes('precisao'))return{total_eventos_analisados:0,status_calibracao:'AMOSTRA_INSUFICIENTE'};
  return{total_requisicoes:0,total_erros:0,erros_recentes:[]};}};
 const p=document.getElementById('conteudo'),botao=s=>[...p.querySelectorAll('button')].find(b=>b.textContent===s);
 return{p,document,window,ctx,chamadas,botao,encerrar:()=>ativo=false,render:()=>window.PainelInterno.render(p,ctx)};
}
test('painel exige ADMIN antes de consultar qualquer endpoint',async()=>{const a=await ambiente({perfil:'VIEWER'});await a.render();assert.equal(a.chamadas.length,0);assert(a.p.textContent.includes('exige perfil ADMIN'));assert(a.document.querySelector('[data-admin]').hidden);});

test('métricas persistidas preservam zero, período, limites e texto sem interpretar HTML',async()=>{
 const a=await ambiente({handler:url=>url.includes('/metricas-endpoints')?{periodo:'2026-10',fuso_periodo:'America/Sao_Paulo',endpoints:[{metodo:'GET',rota_template:'/<img src=x>',requisicoes:4,erros:0,tempo_medio_ms:0,tempo_max_ms:12}],truncado:true,aviso:'Gravação assíncrona'}:undefined});
 await a.render();const area=a.document.querySelector('#interno-servicos');assert(area.textContent.includes('2026-10'));assert(area.textContent.includes('GET /<img src=x>'));assert.equal(area.querySelectorAll('img').length,0);assert(area.textContent.includes('há outras rotas'));assert([...area.querySelectorAll('td')].some(n=>n.textContent==='0'));assert(area.textContent.includes('Gravação assíncrona'));
});

test('falha das métricas persistidas conserva serviços e fontes disponíveis',async()=>{
 const a=await ambiente({handler:url=>{if(url.includes('/metricas-endpoints'))throw Error('offline');}});await a.render();assert(a.p.textContent.includes('Consulta parcial'));assert(a.p.textContent.includes('Respondendo'));assert(a.p.textContent.includes('Fonte <script>'));assert(a.document.querySelector('#interno-servicos').textContent.includes('Serviço indisponível'));
});
test('fontes sem data e amostra vazia não viram dados atuais ou precisão de zero',async()=>{const a=await ambiente();await a.render();for(const s of ['Data ausente/inconsistente','Sem data válida','Amostra insuficiente','Sem amostra','Nenhuma tentativa registrada'])assert(a.p.textContent.includes(s),s);assert.equal(a.document.querySelectorAll('script').length,0);assert(a.p.textContent.includes('<script>ruim</script>'));assert(a.chamadas.every(c=>!c.o?.method));});
test('falha recente do importador aparece ao lado da fonte sem apagar o último sucesso',async()=>{const a=await ambiente();await a.render();assert(a.p.textContent.includes('DADOS_PUBLICOS/anp'));assert(a.p.textContent.includes('Falha'));assert(a.p.textContent.includes('Uma tentativa com falha pode ocorrer após uma importação bem-sucedida.'));});
test('falha parcial conserva fontes e métricas e oferece tentativa do histórico',async()=>{const a=await ambiente({handler:url=>{if(url.includes('readiness')||url.includes('/operacional/importacoes'))throw Error('offline');}});await a.render();assert(a.p.textContent.includes('Fonte <script>'));assert(a.p.textContent.includes('Consulta parcial'));assert(a.botao('Tentar histórico novamente'));assert(a.p.textContent.includes('Serviço indisponível'));});
test('filtro de falhas e paginação consultam endpoint sem gravar',async()=>{const a=await ambiente({handler:url=>url.includes('/operacional/importacoes')?{items:[],proximo_offset:url.includes('offset=0')?25:null}:undefined});await a.render();await a.botao('Próxima página').onclick();assert(a.chamadas.some(c=>c.url.includes('offset=25')));const select=a.p.querySelector('select');select.value='FALHA';await select.onchange();assert(a.chamadas.at(-1).url.includes('offset=0&status=FALHA'));});
test('resposta após logout não preenche a tela anterior',async()=>{let liberar;const a=await ambiente({handler:url=>url.includes('/operacional/fontes')?new Promise(r=>liberar=r):undefined});const pendente=a.render();await new Promise(r=>setImmediate(r));a.encerrar();liberar({fontes:[{nome:'DADO ANTIGO'}]});await pendente;assert(!a.p.textContent.includes('DADO ANTIGO'));});
test('filtro novo descarta resultado atrasado do filtro anterior',async()=>{let liberar,contagem=0;const a=await ambiente({handler:url=>{if(url.includes('/operacional/importacoes')&&++contagem===2)return new Promise(r=>liberar=r);}});await a.render();const sel=a.p.querySelector('select');sel.value='FALHA';const antigo=sel.onchange();await new Promise(r=>setImmediate(r));sel.value='CONCLUIDO';await sel.onchange();liberar({items:[{fonte:'FALHA ANTIGA'}],proximo_offset:null});await antigo;assert(!a.p.textContent.includes('FALHA ANTIGA'));});
