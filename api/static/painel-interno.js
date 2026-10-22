/* Monitor de leitura: contratos públicos existentes e auditoria de importações. */
(function(root){
 'use strict';
 const el=(p,t,s)=>{const e=document.createElement(t);if(s!==undefined)e.textContent=s;p.appendChild(e);return e;};
 const D=root.PortalDados;
 const finito=n=>typeof n==='number'&&Number.isFinite(n);
 const valor=n=>finito(n)?String(n):'Não informado';
 const data=v=>D.data(v),idade=n=>finito(n)&&n>=0?n.toFixed(1)+' min':'Data ausente/inconsistente';
 const rotulos={NO_CRITERIO:'Dentro do critério declarado',ATRASADA:'Atrasada',SEM_DATA_VALIDA:'Sem data válida',COBERTURA_INCOMPLETA:'Cobertura incompleta',CONCLUIDO:'Concluída',PARCIAL:'Parcial',FALHA:'Falha',EM_EXECUCAO:'Sem término registrado'};
 function tabela(p,cols,rows){const wrap=el(p,'div');wrap.className='portal-tabela';const t=el(wrap,'table');el(t,'caption','Fotografia da consulta atual');const tr=el(el(t,'thead'),'tr');cols.forEach(c=>el(tr,'th',c).scope='col');const tb=el(t,'tbody');rows.forEach(row=>{const tr=el(tb,'tr');row.forEach(c=>el(tr,'td',c??'Não informado'));});}
 function aviso(p,s){const e=el(p,'p',s);e.setAttribute('role','status');return e;}
 function origem(p,url,quando){el(p,'p','Endpoint: '+url+' · Consulta: '+data(quando)+'.');}
 function botao(p,s,fn){const b=el(p,'button',s);b.type='button';b.onclick=fn;return b;}
 function erro(e){return e?.status===403?'Acesso negado para este perfil.':e?.status===429?'Limite de consultas atingido; aguarde antes de atualizar.':'Serviço indisponível nesta consulta; não significa ausência de falhas ou risco.';}
 async function render(p,ctx){
  if(root.PainelSessao.perfil()!=='ADMIN'){aviso(p,'Acesso interno exige perfil ADMIN.');return;}
  el(p,'p','Metadados técnicos de fontes públicas e registros da empresa autenticada. Consulta manual; não testa diretamente provedores externos nem dispara importações. Dados conhecidos não comprovam segurança da rodovia.');
  botao(p,'Atualizar painel interno',()=>ctx.recarregar());
  const nav=el(p,'nav');nav.setAttribute('aria-label','Áreas do painel interno');
  const areas={};for(const [id,nome]of [['fontes','Fontes e atualização'],['importacoes','Importações e falhas'],['servicos','Serviços e latência'],['qualidade','Métricas de qualidade']]){
   const a=el(p,'section');areas[id]=a;a.id='interno-'+id;el(a,'h4',nome);botao(nav,nome,()=>a.scrollIntoView({block:'start'}));
  }
  const caminhos=['/api/v1/operacional/fontes','/api/v1/indicadores/qualidade','/api/v1/dados-publicos/qualidade-precos',
   '/api/v1/alertas/precisao','/api/v1/logistica/observabilidade/metricas','/api/v1/health/liveness','/api/v1/health/readiness','/api/v1/infraestrutura/malha/importacoes','/api/v1/operacional/metricas-endpoints'];
  const carregando=aviso(p,'Consultando fontes, serviços e métricas…');
  const respostas=await Promise.allSettled(caminhos.map(url=>ctx.obter(url,{timeout:15000})));
  if(!ctx.atual())return;carregando.remove();const recebido=new Date().toISOString();
  const obter=i=>respostas[i].status==='fulfilled'?respostas[i].value:null;
  const falha=(area,i)=>aviso(area,erro(respostas[i].reason));
  const fontes=obter(0),q=obter(1),precos=obter(2),feedback=obter(3),metricas=obter(4),live=obter(5),ready=obter(6),malha=obter(7);
  origem(areas.fontes,caminhos[0],fontes?.consultado_em||recebido);
  if(Array.isArray(fontes?.fontes)){
   if(!fontes.fontes.length)aviso(areas.fontes,'Nenhuma fonte retornada; cobertura desconhecida.');
   else tabela(areas.fontes,['Fonte / natureza','Referência','Idade na consulta','Situação','Cobertura / limite'],fontes.fontes.map(f=>[
    f.nome+' · '+f.tipo,data(f.referencia_em),idade(f.idade_minutos),rotulos[f.status]||'Situação desconhecida',
    'Limite: '+valor(f.limite_minutos)+' min; '+(f.estacoes!==undefined?valor(f.com_leitura)+'/'+valor(f.estacoes)+' estações':f.segmentos!==undefined?valor(f.com_leitura)+'/'+valor(f.segmentos)+' segmentos':valor(f.registros)+' registros')]));
   const detalhes=el(areas.fontes,'details');el(detalhes,'summary','Critérios, validade e coleta por fonte');
   fontes.fontes.forEach(f=>el(detalhes,'p',f.nome+': '+f.criterio+(f.tipo==='DADOS_PUBLICOS'?' Registro mais recente: '+D.dataCalendario(f.data_registro_mais_recente)+'.':'')+' Coleta: '+data(f.ultima_coleta_em)+'. Validade mais curta: '+data(f.validade_mais_curta)+'.'));
   aviso(areas.fontes,fontes.aviso||'Cobertura não informada.');
   el(areas.fontes,'h5','Última tentativa por importador público');
   const tentativas=fontes.tentativas_dados_publicos;
   if(Array.isArray(tentativas)){
    if(!tentativas.length)aviso(areas.fontes,'Nenhuma tentativa de importação pública instrumentada foi registrada.');
    else tabela(areas.fontes,['Importador','Resultado da tentativa','Início','Término','Código de falha'],tentativas.map(t=>[
     t.fonte,rotulos[t.status]||'Estado desconhecido',data(t.iniciado_em),data(t.encerrado_em),t.motivo_codigo||'Não informado']));
    el(areas.fontes,'p','Uma tentativa com falha pode ocorrer após uma importação bem-sucedida. Sem término registrado não confirma que o processo ainda esteja em execução.');
   }else aviso(areas.fontes,'Resumo das tentativas indisponível nesta consulta.');
  }else falha(areas.fontes,0);
  origem(areas.servicos,caminhos[5]+' e '+caminhos[6],recebido);
  tabela(areas.servicos,['Serviço','Situação','Latência / interpretação'],[
   ['API / liveness',live?.status==='UP'?'Respondendo':live?'Resposta não reconhecida':erro(respostas[5].reason),'Não verifica provedores externos'],
   ['Banco, PostGIS e malha',ready?.status==='READY'?'Pronto':ready?'Resposta não reconhecida':erro(respostas[6].reason),valor(ready?.latencia_db_ms)+' ms; não comprova atualidade das fontes']]);
  for(const s of fontes?.integracoes||[])aviso(areas.servicos,s.nome+': '+s.status+'. '+s.motivo);
  origem(areas.servicos,caminhos[4],recebido);el(areas.servicos,'p','Métricas em memória, por empresa e processo da API, desde a inicialização ou último reset. Não são disponibilidade histórica de toda a infraestrutura.');
  if(metricas){tabela(areas.servicos,['Medida','Valor'],[['Requisições',valor(metricas.total_requisicoes)],['Erros HTTP',valor(metricas.total_erros)],['Taxa de erro (%)',metricas.total_requisicoes>0?valor(metricas.taxa_erro_pct):'Sem amostra'],['Latência média (ms)',metricas.total_requisicoes>0?valor(metricas.latencia_media_global_ms):'Sem amostra']]);
   const erros=metricas.erros_recentes||[];if(!erros.length)aviso(areas.servicos,'Nenhum erro no histórico recente em memória; isso não prova ausência de falhas anteriores.');
   else tabela(areas.servicos,['Rota / método','HTTP','Horário'],erros.map(e=>[e.metodo+' '+e.rota,e.status_code,finito(e.timestamp)?data(new Date(e.timestamp*1000).toISOString()):'Não informado']));
  }else falha(areas.servicos,4);
  el(areas.servicos,'h5','Histórico mensal por endpoint');
  const persistidas=obter(8);
  origem(areas.servicos,caminhos[8],recebido);
  if(Array.isArray(persistidas?.endpoints)){
   el(areas.servicos,'p','Período: '+persistidas.periodo+' · Fuso: '+persistidas.fuso_periodo+'. Erros incluem respostas HTTP 4xx e 5xx.');
   if(persistidas.endpoints.length)tabela(areas.servicos,['Método / rota','Respostas','Erros HTTP','Tempo médio (ms)','Maior tempo (ms)'],persistidas.endpoints.map(e=>[e.metodo+' '+e.rota_template,valor(e.requisicoes),valor(e.erros),valor(e.tempo_medio_ms),valor(e.tempo_max_ms)]));
   else aviso(areas.servicos,'Nenhuma medição persistida neste período. Isso não comprova ausência de falhas.');
   if(persistidas.truncado)aviso(areas.servicos,'Exibindo até 100 rotas; há outras rotas neste período.');
   el(areas.servicos,'p',persistidas.aviso||'Medição assíncrona; uma parada abrupta pode perder amostras recentes. Tempo de resposta não mede CPU ou custo.');
  }else aviso(areas.servicos,respostas[8].status==='rejected'?erro(respostas[8].reason):'Métricas persistidas indisponíveis nesta consulta.');
  origem(areas.qualidade,caminhos[1],recebido);
  if(q){tabela(areas.qualidade,['Indicador agregado','Valor'],[['Status declarado pela API',q.status_geral],['Verificações dentro de 48 h (%)',q.detalhamento_fontes?.length?valor(q.percentual_fontes_atualizadas_prazo):'Sem fontes'],...Object.entries(q.total_registros_base||{})]);el(areas.qualidade,'p','O percentual de prazo mede a última verificação das fontes externas cadastradas, não a idade de cada registro ou a precisão das previsões.');}else falha(areas.qualidade,1);
  origem(areas.qualidade,caminhos[2],recebido);
  if(precos){tabela(areas.qualidade,['Qualidade de preços','Valor'],[['Registros analisados',valor(precos.total_registros_analisados)],['Preços atípicos',precos.total_registros_analisados>0?valor(precos.alertas?.preco_atipico):'Sem amostra'],['Dados desatualizados',precos.total_registros_analisados>0?valor(precos.alertas?.dado_desatualizado):'Sem amostra']]);el(areas.qualidade,'p',precos.interpretacao||'Indicadores para revisão; não alteram preços originais.');}else falha(areas.qualidade,2);
  origem(areas.qualidade,caminhos[3],recebido);
  if(feedback){el(areas.qualidade,'p','Feedback da empresa: '+valor(feedback.total_eventos_analisados)+' evento(s). Estado declarado: '+feedback.status_calibracao+'. Não é validação independente.');if(feedback.total_eventos_analisados>0)tabela(areas.qualidade,['Métrica declarada','Valor'],Object.entries(feedback.metricas_precisao||{}));else aviso(areas.qualidade,'Amostra insuficiente; nenhum percentual validado.');}else falha(areas.qualidade,3);
  const imp=areas.importacoes;
  el(imp,'p','Auditoria persistente dos sincronizadores públicos e dos lotes desta empresa, desde a instrumentação. Falhas de validação HTTP anteriores à execução aparecem somente nas métricas recentes; validação local de arquivo não é importação no servidor.');
  const label=el(imp,'label','Situação da importação'),select=el(label,'select');
  for(const [v,n]of [['','Todas'],['FALHA','Falhas'],['PARCIAL','Parciais'],['EM_EXECUCAO','Sem término'],['CONCLUIDO','Concluídas']]){const o=el(select,'option',n);o.value=v;}
  const lista=el(imp,'div');let sequencia=0,offset=0;
  async function carregar(pos=0){const n=++sequencia;offset=pos;lista.replaceChildren();const st=aviso(lista,'Consultando histórico de importações…');
   try{const url='/api/v1/operacional/importacoes?limite=25&offset='+pos+(select.value?'&status='+encodeURIComponent(select.value):'');const d=await ctx.obter(url,{timeout:15000});if(!ctx.atual()||n!==sequencia)return;lista.replaceChildren();origem(lista,url,d.consultado_em);aviso(lista,d.aviso);
    if(!Array.isArray(d.items))throw Error();
    if(!d.items.length)aviso(lista,'Nenhuma tentativa registrada neste filtro. Isso não comprova ausência de falhas antes da instrumentação.');
    else tabela(lista,['Fonte','Início / fim','Situação','Registros / falhas','Diagnóstico seguro'],d.items.map(i=>[i.fonte,data(i.iniciado_em)+' / '+data(i.encerrado_em),rotulos[i.status]||'Desconhecida',valor(i.registros)+' / '+valor(i.falhas),i.motivo_codigo||'Sem código de falha']));
    if(pos>0)botao(lista,'Página anterior',()=>carregar(Math.max(0,pos-25)));if(d.proximo_offset!==null&&d.proximo_offset!==undefined)botao(lista,'Próxima página',()=>carregar(d.proximo_offset));
   }catch(e){if(ctx.atual()&&n===sequencia){lista.replaceChildren();aviso(lista,erro(e));botao(lista,'Tentar histórico novamente',()=>carregar(offset));}}
  }
  select.onchange=()=>carregar(0);botao(imp,'Atualizar histórico de importações',()=>carregar(0));await carregar();if(!ctx.atual())return;
  origem(imp,caminhos[7],recebido);
  if(Array.isArray(malha)){if(malha.length)tabela(imp,['Malha importada (últimas 100)','Data','Situação'],malha.map(i=>[i.fonte,data(i.criado_em),i.ativo?'Ativa':'Desativada']));else aviso(imp,'Nenhuma importação de malha registrada para esta empresa.');}else falha(imp,7);
  if(respostas.some(r=>r.status==='rejected'))aviso(p,'Consulta parcial: os resultados disponíveis foram preservados. Atualize para tentar novamente.');
 }
 root.PainelInterno={render};
 root.PortalOperacional.registrarSecao('interno','Painel operacional interno',render);
 const acesso=document.querySelector('[data-secao="interno"]');if(acesso){acesso.setAttribute('data-admin','');acesso.hidden=root.PainelSessao.perfil()!=='ADMIN';}
})(window);
