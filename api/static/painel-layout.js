/* Apresentação do painel real: os nós, dados e ações existentes são reutilizados. */
(function(root){
 'use strict';
 const U=root.FluxoPainel,D=root.PortalDados,E=root.PainelExperiencia;
 const rail=document.getElementById('ux-navegacao'),antigo=document.getElementById('ux-menu-conteudo');
 antigo.hidden=true;antigo.removeAttribute('aria-label');antigo.id='ux-atalhos-anteriores';
 const nav=U.el(rail,'nav');nav.id='ux-menu-conteudo';nav.setAttribute('aria-label','Navegação principal');
 const principais=[];let operacaoAtual=null;
 function marcar(destino){principais.forEach(b=>destino===b.dataset.area?b.setAttribute('aria-current','page'):b.removeAttribute('aria-current'));}
 function recolher(){if(root.matchMedia('(max-width:900px)').matches){nav.hidden=true;document.getElementById('ux-menu').setAttribute('aria-expanded','false');}}
 for(const [id,area]of [['tab-urbano','URBANO'],['tab-frota','FROTA']]){const b=document.getElementById(id);b.dataset.area=area;nav.appendChild(b);principais.push(b);b.addEventListener('click',recolher);}
 for(const[label,area]of [['Corredores','corredores'],['Relatórios','relatorios'],['Configurações','configuracao']]){
  const b=U.el(nav,'button',label);b.type='button';b.dataset.area=area;b.onclick=()=>{root.PortalOperacional.navegar(area);recolher();};principais.push(b);
 }
 const rodape=U.el(rail,'div');rodape.className='ux-rodape';
 const primeiro=antigo.querySelector('[data-destino="onboarding"]');rodape.appendChild(primeiro);
 const central=document.querySelector('.top-controls [aria-haspopup="dialog"]');rodape.appendChild(central);
 const empresa=antigo.querySelector('.ux-empresa');rodape.appendChild(empresa);
 const menu=document.getElementById('ux-menu');menu.onclick=()=>{nav.hidden=!nav.hidden;menu.setAttribute('aria-expanded',String(!nav.hidden));};
 function ajustar(){antigo.hidden=true;nav.hidden=root.matchMedia('(max-width:900px)').matches;menu.setAttribute('aria-expanded',String(!nav.hidden));root.dispatchEvent(new root.Event('resize'));}
 root.matchMedia('(max-width:900px)').addEventListener('change',ajustar);
 rail.addEventListener('keydown',e=>{if(e.key==='Escape'){recolher();menu.focus();}});

 const cab=U.el(document.body,'section');cab.className='ux-cabecalho-pagina';cab.hidden=true;
 document.querySelector('.workspace').before(cab);
 const titulos=U.el(cab,'div'),titulo=U.el(titulos,'h1','Operações'),subtitulo=U.el(titulos,'p','Acompanhe as viagens e confira onde é preciso agir.');
 const acoes=U.el(cab,'div');acoes.className='ux-acoes-pagina';
 const despacho=document.querySelector('[data-acao="abrirModalDespacho"]')||Array.from(document.querySelectorAll('.top-controls button')).find(b=>b.textContent.includes('Despachar'));
 if(despacho)acoes.appendChild(despacho);
 const ferramentas=U.el(acoes,'details');ferramentas.className='ux-ferramentas';U.el(ferramentas,'summary','Cenário e indicadores');
 const chamada=document.querySelector('.ux-atencao'),indicador=chamada.querySelector('[role="status"]');chamada.querySelector('h1').hidden=true;
 const resumo=U.el(document.body,'section');resumo.className='ux-visao-geral';resumo.hidden=true;cab.after(resumo);
 resumo.appendChild(indicador);const atualizar=chamada.querySelector('button');if(atualizar)resumo.appendChild(atualizar);
 for(const detalhe of chamada.querySelectorAll('details'))ferramentas.appendChild(detalhe);
 ferramentas.appendChild(document.querySelector('.ux-simulacao'));
 const exportar=Array.from(document.querySelectorAll('.top-controls button')).find(b=>b.textContent.includes('Exportar CSV'));if(exportar)ferramentas.appendChild(exportar);
 chamada.hidden=true;
 const empresaHeader=document.querySelector('.brand-title');empresaHeader.textContent='Central de operações';
 const linhaRota=U.el(document.getElementById('map-container'),'article');linhaRota.id='ux-rota-resumo';linhaRota.hidden=true;linhaRota.setAttribute('aria-label','Viagem selecionada');
 const codigo=U.el(linhaRota,'p');codigo.className='ux-sobretitulo';
 const nome=U.el(linhaRota,'h2'),mensagem=U.el(linhaRota,'p');mensagem.setAttribute('role','status');
 const base=U.el(linhaRota,'div');base.className='ux-rota-acoes';const natureza=U.el(base,'p');
 const comparar=U.el(base,'button','Comparar rotas');comparar.type='button';comparar.className='ux-primario';comparar.disabled=true;
 const dialog=U.el(document.body,'dialog');dialog.id='ux-comparar';dialog.setAttribute('aria-label','Comparação e decisão da viagem');
 const status=U.status(dialog,'');status.className='ux-carga-comparacao';
 const inspector=document.getElementById('inspector');dialog.appendChild(inspector);
 inspector.querySelector('.insp-header button').onclick=()=>dialog.close();
 comparar.onclick=()=>{if(comparar.disabled||!operacaoAtual)return;
  if(!Array.from(inspector.querySelectorAll('summary')).some(s=>s.textContent==='Postos, historico e atualizacao dos dados'))root.DadosViagem.exibir([operacaoAtual.geometrias?.rota_original_geojson,operacaoAtual.geometrias?.rota_alternativa_geojson]);ferramentas.open=false;dialog.showModal();dialog.scrollTop=0;};
 dialog.addEventListener('close',()=>{if(root.PainelSessao.perfil()&&comparar.isConnected)comparar.focus();});
 // O mesmo conteúdo de comparação é exibido em janela própria, sem cobrir o mapa permanentemente.
 const anteriorSelecionar=E.selecionar;
 E.selecionar=op=>{operacaoAtual=op;anteriorSelecionar(op);linhaRota.hidden=false;comparar.disabled=false;inspector.hidden=false;status.textContent='';dialog.removeAttribute('aria-busy');
  codigo.textContent=op.id_operacao+' · '+(op.id_veiculo||'Caminhão não informado');
  nome.textContent=op.coordenadas?.origem_nome&&op.coordenadas?.destino_nome?op.coordenadas.origem_nome+' → '+op.coordenadas.destino_nome:'Confira a viagem selecionada';
  mensagem.textContent=op.justificativa||'Justificativa não informada. Confira fontes e restrições antes de decidir.';
  const c=op.contexto_consulta||{};natureza.textContent='Natureza: '+(c.natureza||'Não informada')+' · Cálculo: '+D.data(c.calculo_gerado_em);
 };
 function limparSelecao(){operacaoAtual=null;comparar.disabled=true;linhaRota.hidden=true;codigo.textContent='';nome.textContent='';mensagem.textContent='';natureza.textContent='';status.textContent='';}
 function carregando(id){linhaRota.hidden=false;comparar.disabled=true;codigo.textContent=id;nome.textContent='Consultando viagem…';mensagem.textContent='Carregando a rota, as fontes e a comparação de custos.';natureza.textContent='';if(dialog.open){inspector.hidden=true;status.textContent='Atualizando a comparação…';dialog.setAttribute('aria-busy','true');}}
 function erro(){inspector.hidden=true;comparar.disabled=true;linhaRota.hidden=false;nome.textContent='Consulta indisponível';mensagem.textContent='Selecione a viagem novamente para tentar. Os dados da consulta anterior não são usados.';natureza.textContent='';status.textContent=mensagem.textContent;dialog.removeAttribute('aria-busy');}
 const anteriorAba=E.aba;
 E.aba=tipo=>{concluirMapa();anteriorAba(tipo);marcar(tipo==='CORREDOR'?'corredores':tipo);const urbano=tipo==='URBANO';titulo.textContent=urbano?'Operações':tipo==='FROTA'?'Frota':'Corredor de referência';subtitulo.textContent=urbano?'Acompanhe as viagens e confira onde é preciso agir.':tipo==='FROTA'?'Cadastre medidas e custos dos veículos da empresa.':'Consulte o cenário regional e suas limitações.';resumo.hidden=!urbano;ferramentas.hidden=!urbano;cab.dataset.area=tipo;document.body.dataset.area=tipo;root.dispatchEvent(new root.Event('resize'));};
 E.secao=id=>{if(dialog.open)dialog.close();marcar(id==='corredores'||id==='importacao'?'corredores':id==='relatorios'||id==='consultas'?'relatorios':'configuracao');};
 const anteriorSessao=E.sessao,anteriorLimpar=E.limpar;
 E.sessao=user=>{anteriorSessao(user);cab.hidden=false;resumo.hidden=false;E.aba('URBANO');ajustar();};
 E.limpar=()=>{document.body.classList.remove('ux-escolhendo-mapa');dialog.close();limparSelecao();ferramentas.open=false;cab.hidden=true;resumo.hidden=true;anteriorLimpar();};
 // As ferramentas secundárias continuam disponíveis no mesmo registro de seções e com as mesmas permissões.
 const portal=document.getElementById('portal-operacional'),navPortal=portal.querySelector('nav');
 const navegacao=U.el(portal,'details');navegacao.className='ux-ferramentas-central';U.el(navegacao,'summary','Navegar entre ferramentas');navPortal.before(navegacao);navegacao.appendChild(navPortal);
 navPortal.addEventListener('click',e=>{if(e.target.closest('button'))navegacao.open=false;});
 portal.addEventListener('close',()=>{navegacao.open=false;const id=document.querySelector('.nav-tab.active')?.id;E.aba(id==='tab-frota'?'FROTA':id==='tab-corredor'?'CORREDOR':'URBANO');});
 const voltarFrota=U.el(document.getElementById('map-container'),'button','Concluir escolha no mapa');voltarFrota.id='ux-voltar-frota';voltarFrota.type='button';
 function concluirMapa(){root.CadastroInfra.cancelarEscolha?.();document.body.classList.remove('ux-escolhendo-mapa');root.dispatchEvent(new root.Event('resize'));}
 voltarFrota.onclick=concluirMapa;
 root.PainelLayout={carregando,erro,limparSelecao,escolherMapa:()=>{document.body.classList.add('ux-escolhendo-mapa');root.dispatchEvent(new root.Event('resize'));document.getElementById('map-container').scrollIntoView({block:'nearest'});},concluirMapa};
 ajustar();
})(window);
