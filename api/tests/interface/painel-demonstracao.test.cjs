const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const {parseHTML}=require('linkedom');
async function ambiente({demo=true,perfil='ADMIN',tenant='demo_corp',falha=false}={}){
 const {window}=parseHTML('<html><body><div class="map-legend"></div><p class="portal-aviso" hidden></p><dialog id="portal-operacional"></dialog><section></section></body></html>');
 const {document}=window,chamadas=[],sources={},layers=[];let ativo=true;
 const referencia=JSON.parse(fs.readFileSync(path.join(__dirname,'../../../dados/demonstracao/evento-historico.json'),'utf8'));
 window.PortalDados={moeda:n=>n==null?'Não informado':String(n)};
 window.PainelSessao={empresa:()=>tenant,perfil:()=>perfil,request:async(url,o)=>{chamadas.push({url,o});if(url.endsWith('/estado')){if(falha)throw Error('offline');return{json:async()=>({demo_isolada:demo,aviso:'AMBIENTE DE DEMONSTRAÇÃO'})};}
 return{json:async()=>({id_operacao:'DEMO',aviso:'Dados sintéticos',comparativo_rotas:{rota_original_km:null},financeiro:null,rota_original:null,rota_alternativa:null})};}};
 const map={getSource:id=>sources[id],loaded:()=>true,addSource:(id,s)=>sources[id]={setData:d=>sources[id].data=d},addLayer:l=>layers.push(l),fitBounds:()=>{}};
 document.querySelector('dialog').close=()=>{};
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../../static/painel-demonstracao.js'),'utf8'),vm.createContext({window,document,map,console}));
 await new Promise(r=>setImmediate(r));
 const p=document.querySelector('section'),ctx={atual:()=>ativo,obter:async()=>referencia,tabela:(p,c,r)=>{const e=document.createElement('pre');e.textContent=JSON.stringify(r);p.appendChild(e);}};
 await window.PainelDemonstracao.render(p,ctx);
 const botao=s=>[...p.querySelectorAll('button')].find(b=>b.textContent.includes(s));
 return{window,document,p,chamadas,botao,sources,layers,encerrar:()=>ativo=false};
}
test('ambiente operacional bloqueia preparação e reprodução',async()=>{const a=await ambiente({demo:false});assert(a.p.textContent.includes('bloqueado'));assert.equal(a.p.querySelectorAll('button').length,0);assert(a.document.getElementById('demo-faixa').hidden);});
test('estado indisponível não habilita o exercício e mostra aviso',async()=>{const a=await ambiente({falha:true});assert(a.p.textContent.includes('bloqueado'));assert(a.document.getElementById('demo-faixa').textContent.includes('Não foi possível verificar'));});
test('VIEWER consulta modelo mas não prepara; origem e incógnitas são visíveis',async()=>{const a=await ambiente({perfil:'VIEWER'});assert(a.botao('Preparar').disabled);assert(!a.botao('2. Simular').disabled);for(const s of ['pesquisa pública','não foi identificado','sintética','zero'])assert(a.p.textContent.includes(s),s);assert(!a.document.querySelector('.portal-aviso').hidden);});
test('outra empresa não prepara nem reproduz o cenário reservado',async()=>{const a=await ambiente({tenant:'outra'});assert(a.botao('Preparar').disabled);assert(a.botao('2. Simular').disabled);});
test('ausência de rota permanece desconhecida e mapa usa somente camadas próprias',async()=>{const a=await ambiente();await a.botao('2. Simular').onclick();assert(a.p.textContent.includes('Sem rota disponível'));assert(a.p.textContent.includes('Economia comprovada: indisponível'));await a.botao('Ver exercício').onclick();assert.deepEqual(a.layers.map(l=>l.id),['demo34-original','demo34-alternativa']);a.window.PainelDemonstracao.limparMapa();assert.equal(a.sources['demo34-original'].data.features.length,0);});
test('tela encerrada não dispara nova ação',async()=>{const a=await ambiente();a.encerrar();await a.botao('Preparar').onclick();assert(!a.chamadas.some(c=>c.url.endsWith('/preparar')));});
