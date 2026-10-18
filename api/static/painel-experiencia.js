/* Organização visual progressiva. Não calcula rotas, custos ou risco. */
(function(root){
 'use strict';
 const U=root.FluxoPainel,D=root.PortalDados;
 let usuario=null,geracao=0,versaoLista=0,chaveLista='',historico=new Map();
 const rail=document.createElement('aside');rail.id='ux-navegacao';rail.hidden=true;
 document.querySelector('header').before(rail);
 const marca=U.el(rail,'strong','SPRain');marca.className='ux-marca';
 const menu=U.el(rail,'button','Menu');menu.type='button';menu.id='ux-menu';menu.setAttribute('aria-controls','ux-menu-conteudo');
 const nav=U.el(rail,'nav');nav.id='ux-menu-conteudo';nav.setAttribute('aria-label','Navegação principal');
 U.el(nav,'p','OPERAÇÃO').className='ux-grupo';
 const abas=document.querySelector('.nav-tabs');nav.appendChild(abas);
 for(const[id,label]of [['tab-urbano','Operações'],['tab-frota','Frota'],['tab-corredor','Corredor de referência']])document.getElementById(id).textContent=label;
 const links=[];
 function link(label,id){
  const b=U.el(nav,'button',label);b.type='button';b.dataset.destino=id;
  b.onclick=()=>{root.PortalOperacional.navegar(id);marcar(id);recolher();};links.push(b);return b;
 }
 link('Corredores e recorrências','corredores');link('Relatórios e exportações','relatorios');
 U.el(nav,'p','CONFIGURAÇÃO E AJUDA').className='ux-grupo';
 link('Configurar primeiro cliente','onboarding');link('Acesso e configurações','configuracao');
 link('Demonstração','demonstracao');const interno=link('Painel operacional interno','interno');
 const empresa=U.el(nav,'p','');empresa.className='ux-empresa';
 const pequeno=root.matchMedia('(max-width: 900px)');
 function recolher(){if(pequeno.matches){nav.hidden=true;menu.setAttribute('aria-expanded','false');}}
 function ajustar(){nav.hidden=pequeno.matches;menu.setAttribute('aria-expanded',String(!nav.hidden));root.dispatchEvent(new root.Event('resize'));}
 menu.onclick=()=>{nav.hidden=!nav.hidden;menu.setAttribute('aria-expanded',String(!nav.hidden));};
 rail.addEventListener('keydown',e=>{if(e.key==='Escape'&&pequeno.matches){recolher();menu.focus();}});
 pequeno.addEventListener('change',ajustar);ajustar();
 abas.addEventListener('click',recolher);
 function marcar(id){links.forEach(b=>b.setAttribute('aria-current',b.dataset.destino===id?'page':'false'));if(id)abas.querySelectorAll('button').forEach(b=>b.setAttribute('aria-current','false'));}
 function aba(tipo){marcar(null);for(const[id,valor]of [['tab-urbano','URBANO'],['tab-frota','FROTA'],['tab-corredor','CORREDOR']])document.getElementById(id).setAttribute('aria-current',tipo===valor?'page':'false');}
 document.getElementById('portal-operacional').addEventListener('close',()=>{if(!document.getElementById('portal-operacional').open){const id=abas.querySelector('.active')?.id;aba(id==='tab-frota'?'FROTA':id==='tab-corredor'?'CORREDOR':'URBANO');}});
 const principal=document.querySelector('.workspace');principal.id='ux-conteudo';
 const pular=U.el(rail,'a','Ir para as operações');pular.href='#urbano-panel';pular.className='ux-pular';
 document.getElementById('urbano-panel').tabIndex=-1;
 const chamada=document.createElement('section');chamada.className='ux-atencao';chamada.setAttribute('aria-label','Acompanhamento das operações');
 document.querySelector('#urbano-panel .control-bar').before(chamada);
 U.el(chamada,'h1','Operações');
 const indicador=U.status(chamada,'Carregando operações…');
 const orientacao=U.el(chamada,'details');U.el(orientacao,'summary','Como acompanhar as viagens');
 U.el(orientacao,'p','Selecione uma viagem, confira fontes e compare as opções antes de registrar a decisão. O filtro usa a existência de decisões no histórico; decisões passadas precisam ser conferidas no cenário atual.');
 const kpis=U.el(chamada,'details');kpis.className='ux-kpis';U.el(kpis,'summary','Indicadores e impacto potencial');kpis.appendChild(document.querySelector('.kpi-grid'));
 for(const b of document.querySelectorAll('.top-controls button'))if(b.textContent==='Corredores e recorrências')b.hidden=true;
 const pendentes=U.el(document.querySelector('.filter-pills'),'button','Sem decisão no histórico');pendentes.id='flt-PENDENTE';pendentes.type='button';pendentes.className='filter-pill';pendentes.onclick=()=>root.definirFiltro('PENDENTE');
 const atualizarDecisoes=U.el(chamada,'button','Atualizar decisões');atualizarDecisoes.type='button';atualizarDecisoes.className='btn-top';atualizarDecisoes.onclick=()=>{chaveLista='';root.renderizarTabela();};
 const controles=document.querySelector('#urbano-panel .control-row');
 const simulacao=document.createElement('details');simulacao.className='ux-simulacao';U.el(simulacao,'summary','Simular cenário de chuva');
 controles.before(simulacao);simulacao.appendChild(controles);
 U.el(simulacao,'p','Altera o cenário calculado. A chuva escolhida não é uma observação meteorológica nem uma previsão.');
 // Camadas e legenda permanecem no mapa, recolhíveis para deixar a rota visível.
 const legenda=document.querySelector('.map-legend'),camadas=document.createElement('details');
 U.el(camadas,'summary','Legenda e camadas do mapa');while(legenda.firstChild)camadas.appendChild(legenda.firstChild);legenda.appendChild(camadas);
 const comparacao=document.createElement('section');comparacao.className='ux-comparacao';comparacao.setAttribute('aria-label','Resumo comparativo da viagem');
 document.querySelector('.route-compare').after(comparacao);
 function selecionar(op){
  comparacao.replaceChildren();const versao=++geracao;
  const f=op.infraestrutura?.financeiro||{};
  const temAlternativa=op.validacao_rota?.rota_alternativa_disponivel===true
   && op.geometrias?.rota_alternativa_geojson?.features?.some(x=>['LineString','MultiLineString'].includes(x.geometry?.type)&&x.geometry.coordinates?.length);
  U.el(comparacao,'h3','Compare os custos da viagem');
  const tabela=U.el(comparacao,'table');U.el(tabela,'caption','Estimativas com parcelas conhecidas da consulta atual');
  const cab=U.el(U.el(tabela,'thead'),'tr');for(const s of ['Parcela','Original','Alternativa'])U.el(cab,'th',s).scope='col';
  const body=U.el(tabela,'tbody');
  function linha(nome,a,b){const tr=U.el(body,'tr');U.el(tr,'th',nome).scope='row';U.el(tr,'td',D.moeda(a));U.el(tr,'td',D.moeda(temAlternativa?b:null));}
  linha('Custo estimado',f.custo_original_conhecido_brl,f.custo_alternativa_conhecido_brl);
  const infra=op.infraestrutura||{};
  linha('Pedágios conhecidos',infra.original?.pedagios?.subtotal_conhecido_reais,infra.alternativa?.pedagios?.subtotal_conhecido_reais);
  U.el(comparacao,'p','Tarifas pendentes nas duas rotas: '+(typeof f.tarifas_pendentes_comparacao==='number'?f.tarifas_pendentes_comparacao:'Não informado')+'.');
  U.el(comparacao,'p',temAlternativa?'Diferença de custo (alternativa − original): '+D.moeda(f.custo_desvio_brl):'Sem alternativa com geometria disponível; a comparação de desvio não está disponível.');
  U.el(comparacao,'p','Cobertura parcial: valores ausentes não são zero. Menor custo não confirma passagem nem comprova economia realizada.');
  const espera=U.el(comparacao,'details');U.el(espera,'summary','Comparar um cenário de espera');
  U.el(espera,'p','Novo exercício financeiro com o motor da API. Não substitui a fotografia da decisão. O risco após esperar precisa de nova avaliação.');
  const form=U.el(espera,'form');form.onsubmit=e=>e.preventDefault();
  const minutos=U.campo(form,'tempo_espera_min','Tempo de espera informado (min)','number','',{min:0,step:'any',required:''});
  const chuva=U.campo(form,'chuva_espera','Chuva simulada para comparar a espera (mm/h)','number',op.contexto_consulta?.precipitacao_mm,{min:0,max:250,step:'any',required:''});
  const resultado=U.status(espera,'Informe o tempo e confira as premissas antes de calcular.'),saida=U.el(espera,'div');
  U.botao(form,'Calcular cenário de espera',async()=>{
   if(!form.reportValidity())return;resultado.textContent='Calculando com a API…';
   const p=f.premissas||{},parametros={tempo_espera_min:Number(minutos.value)};
   for(const[a,b]of [['custo_por_km','custo_por_km'],['custo_por_km_sem_combustivel','custo_por_km_sem_combustivel'],['consumo_km_l','consumo_km_l'],['preco_combustivel_litro','preco_diesel_litro'],['custo_hora_motorista','custo_hora_motorista'],['custo_operacional_veiculo_hora','custo_hora_veiculo'],['custo_atraso_hora','multa_por_hora_atraso']])if(typeof p[a]==='number')parametros[b]=p[a];
   if(parametros.custo_por_km!==undefined)delete parametros.custo_por_km_sem_combustivel;
   if(typeof f.janela_disponivel_min==='number'&&f.janela_disponivel_min>=1)parametros.janela_limite_min=f.janela_disponivel_min;
   try{
    const r=await root.PainelSessao.request('/api/v1/logistica/decisao-economica',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
     ...op.coordenadas,id_veiculo:op.id_veiculo,dimensoes:infra.dimensoes,tenant_id:usuario.tenant_id,precipitacao_mm:Number(chuva.value),parametros})});
    const resposta=await r.json();if(versao!==geracao)return;
    const d=resposta.decisao;
    if(!d?.tradeoff?.aguardar||typeof d.tradeoff.aguardar.custo_aguardar_brl!=='number')throw Error('Não foi possível ler o cálculo da espera. Tente novamente.');
    saida.replaceChildren();resultado.textContent='Cenário calculado. Confira os valores e as premissas abaixo.';const t=d.tradeoff;
    U.el(saida,'p','Custo estimado original: '+D.moeda(t?.rota_direta?.custo_total_estimado_brl)+'. Alternativa: '+D.moeda(t?.rota_alternativa?.custo_total_estimado_brl)+'. Aguardar: '+D.moeda(t?.aguardar?.custo_aguardar_brl)+'.');
    U.el(saida,'p',(t?.aguardar?.aviso||'Tempo de espera não calculado.')+' '+(d.aviso||''));
    const prem=U.el(saida,'details');U.el(prem,'summary','Premissas aplicadas neste exercício');U.el(prem,'pre',JSON.stringify(d.premissas_aplicadas,null,2));
   }catch(e){if(versao===geracao)resultado.textContent=U.erro(e);}
  },{escrita:true,valido:()=>versao===geracao});
  if(!root.PainelSessao.podeEscrever())form.querySelectorAll('input').forEach(i=>i.disabled=true);
  const titulo=document.getElementById('modal-acao');
  titulo.setAttribute('aria-label','Recomendação retornada: '+op.acao_recomendada);
 }
 function resumo(lista,decisoes){
  if(!usuario)return;
  for(const id of Object.keys(decisoes))if(decisoes[id])historico.set(id,true);
  const pend=lista.filter(o=>historico.get(o.id_operacao)===false).length,criticos=lista.filter(o=>o.nivel_risco==='CRITICO').length;
  const faltam=lista.some(o=>!historico.has(o.id_operacao));
  indicador.textContent=lista.length?lista.length+' viagens · '+criticos+' críticas · '+(faltam?'conferindo histórico de decisões':pend+' sem decisão no histórico'):'Nenhuma viagem retornada. Cadastre uma viagem ou importe as rotas do cliente.';
  const ids=lista.map(o=>o.id_operacao).sort(),chave=JSON.stringify(ids);
  if(!ids.length||chave===chaveLista)return;chaveLista=chave;
  const versao=++versaoLista;atualizarDecisoes.disabled=true;
  root.PainelSessao.request('/api/v1/painel/acompanhamento',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operacoes:ids.slice(0,500)})})
   .then(r=>r.json()).then(d=>{if(versao!==versaoLista)return;for(const op of d.items)historico.set(op.id_operacao,op.possui_decisao);root.renderizarTabela();})
   .catch(e=>{if(versao===versaoLista&&!e?.silencioso)indicador.textContent='Histórico de decisões indisponível. As viagens continuam disponíveis; use Atualizar decisões para tentar novamente.';})
   .finally(()=>{if(versao===versaoLista)atualizarDecisoes.disabled=false;});
 }
 function limpar(){geracao++;versaoLista++;chaveLista='';historico.clear();usuario=null;rail.hidden=true;document.body.classList.remove('ux-pronta');comparacao.replaceChildren();indicador.textContent='Carregando operações…';empresa.textContent='';}
 function sessao(user){usuario=user;rail.hidden=false;empresa.textContent='Empresa: '+user.tenant_id;interno.hidden=user.role!=='ADMIN';document.body.classList.add('ux-pronta');ajustar();}
 root.PainelExperiencia={sessao,limpar,selecionar,resumo,semDecisao:id=>historico.has(id)?!historico.get(id):null,aba};
})(window);
