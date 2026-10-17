/* Central complementar. Usa os contratos existentes; não cria cadastros fictícios. */
(function(root){
    'use strict';
    const D=root.PortalDados, PDF=root.PortalPDF;
    const dialog=document.createElement('dialog');dialog.id='portal-operacional';dialog.setAttribute('aria-labelledby','portal-titulo');
    const cab=document.createElement('div');cab.className='portal-cab';
    const titulo=document.createElement('h2');titulo.id='portal-titulo';titulo.textContent='Central de trabalho';cab.appendChild(titulo);
    const fechar=document.createElement('button');fechar.type='button';fechar.textContent='Fechar';cab.appendChild(fechar);dialog.appendChild(cab);
    const aviso=document.createElement('p');aviso.className='portal-aviso';aviso.textContent='ACESSO DE DEMONSTRAÇÃO · Os resultados não comprovam viagens ou economia reais.';dialog.appendChild(aviso);
    const nav=document.createElement('nav');nav.setAttribute('aria-label','Seções da central');dialog.appendChild(nav);
    const conteudo=document.createElement('section');conteudo.id='portal-conteudo';conteudo.tabIndex=-1;dialog.appendChild(conteudo);document.body.appendChild(dialog);
    const abrir=document.createElement('button');abrir.type='button';abrir.className='btn-action-top';abrir.textContent='Central de trabalho';abrir.setAttribute('aria-haspopup','dialog');document.querySelector('.top-controls').prepend(abrir);
    let usuario=null,versao=0,controle,selecionada=null,secao='relatorios',inicio=0,primeiro=null;
    const urls=new Set();let importarPendente=false;
    function el(parent,tag,valor){const n=document.createElement(tag);if(valor!==undefined)n.textContent=valor;parent.appendChild(n);return n;}
    function botao(parent,texto,acao){const b=el(parent,'button',texto);b.type='button';b.onclick=async()=>{try{await acao();}catch(e){if(usuario&&!e?.silencioso)mensagem(parent,textoErro(e));}};return b;}
    function mensagem(parent,texto){const p=el(parent,'p',texto);p.setAttribute('role','status');return p;}
    function tabela(parent,colunas,linhas){const wrap=el(parent,'div');wrap.className='portal-tabela';const t=el(wrap,'table');
        el(t,'caption','Dados retornados na consulta atual');const hr=el(el(t,'thead'),'tr');colunas.forEach(c=>el(hr,'th',c).scope='col');
        const tb=el(t,'tbody');linhas.forEach(l=>{const tr=el(tb,'tr');l.forEach(v=>el(tr,'td',v??'Não informado'));});return t;}
    function textoErro(e){return e?.name==='ErroPainel'?e.message:'Não foi possível concluir. Atualize a consulta e tente novamente.';}
    function atual(v){return v===versao&&usuario!==null;}
    async function obter(path,v,options={}){const r=await root.PainelSessao.request(path,{...options,signal:controle.signal});const d=await r.json();if(!atual(v))throw Object.assign(new Error(),{silencioso:true});return d;}
    function download(nome,dados,tipo){
        if(!usuario||!root.PainelSessao.perfil())return;
        const blob=new Blob([dados],{type:tipo}),url=URL.createObjectURL(blob);urls.add(url);
        const a=document.createElement('a');a.href=url;a.download=nome;document.body.appendChild(a);a.click();a.remove();
        setTimeout(()=>{URL.revokeObjectURL(url);urls.delete(url);},1000);
    }
    function nome(s){return String(s||'consulta').replace(/[^a-zA-Z0-9_.-]/g,'_').slice(0,100);}
    function encerrar(){dialog.close();abrir.focus();}
    fechar.onclick=encerrar;abrir.onclick=()=>{if(!usuario)return;dialog.showModal();render(secao);};
    dialog.addEventListener('close',()=>{if(dialog.open)return;versao++;controle?.abort();conteudo.replaceChildren();});
    async function render(aba){
        if(!usuario)return;secao=aba;const v=++versao;controle?.abort();controle=new AbortController();conteudo.replaceChildren();dialog.scrollTop=0;
        nav.querySelectorAll('button').forEach(b=>b.setAttribute('aria-current',String(b.dataset.secao===aba)));
        el(conteudo,'h3',rotulos[aba]);const carregando=mensagem(conteudo,'Carregando…');
        try {await telas[aba](conteudo,v);if(atual(v))carregando.remove();}
        catch(e){if(atual(v)&&!e?.silencioso){carregando.textContent=textoErro(e);botao(conteudo,'Tentar novamente',()=>render(aba));}}
    }
    const rotulos={relatorios:'Relatórios e exportações',qualidade:'Qualidade e serviços',importacao:'Importar rotas',configuracao:'Acesso e configurações',demonstracao:'Demonstração',ajuda:'Primeiros passos'};
    const telas={relatorios,qualidade,importacao,configuracao,demonstracao,ajuda};
    for(const [id,label]of Object.entries(rotulos)){const b=botao(nav,label,()=>render(id));b.dataset.secao=id;}
    async function relatorios(p,v){
        if(root.RelatoriosPainel)return root.RelatoriosPainel.render(p,{atual:()=>atual(v),obter:(path,options)=>obter(path,v,options),download,nome,tabela,usuario:()=>usuario});
        el(p,'p','Exportações geradas no seu computador, com os dados disponíveis para a empresa autenticada. Compartilhe os arquivos apenas com pessoas autorizadas.');
        const resultados=await Promise.allSettled([obter('/api/v1/logistica/operacoes',v),obter('/api/v1/logistica/relatorios/sumario-executivo',v)]);if(!atual(v))return;
        const [operacoes,sumario]=resultados.map(r=>r.status==='fulfilled'?r.value:null);
        const piloto=el(p,'article');el(piloto,'h4','Relatório do piloto');
        if(sumario?.kpis){
            const k=sumario.kpis, linhas=['SPRain | Relatório do piloto','Empresa: '+usuario.tenant_id,'Consulta recebida em: '+D.data(new Date().toISOString()),
                'Escopo: retrato das últimas recomendações disponíveis; não é filtro de período nem comprovação de execução.',
                'Operações: '+k.total_operacoes,'Rotas em risco de alagamento: '+k.rotas_em_risco_alagamento,'Rotas recalculadas: '+k.rotas_recalculadas_com_sucesso,
                'Prejuízo estimado potencial evitado: '+D.moeda(k.prejuizo_estimado_evitado_brl),
                'Economia comprovada: não disponível.','Custo observado: não disponível.','Custo estimado agregado comparável: não fornecido neste endpoint.',
                'Limitações: cobertura parcial de tarifas e restrições; dados de planejamento não comprovam economia realizada.',
                'Fonte: /api/v1/logistica/relatorios/sumario-executivo.','Período declarado pela API: '+sumario.periodo];
            tabela(piloto,['Indicador','Resultado'],[['Operações',k.total_operacoes],['Em risco',k.rotas_em_risco_alagamento],['Recalculadas',k.rotas_recalculadas_com_sucesso],['Impacto potencial estimado',D.moeda(k.prejuizo_estimado_evitado_brl)],['Economia comprovada','Não disponível'],['Custo observado','Não disponível']]);
            botao(piloto,'Baixar PDF do piloto',()=>download('piloto.pdf',PDF.gerar(linhas),'application/pdf'));
            botao(piloto,'Baixar dados do resumo (JSON)',()=>download('piloto.json',JSON.stringify({natureza:'PLANEJAMENTO_NAO_COMPROVADO',recebido_em:new Date().toISOString(),...sumario},null,2),'application/json'));
        }else mensagem(piloto,'Resumo indisponível. Não há base para declarar economia ou operações protegidas.');
        el(p,'h4','Consulta e decisão individual');
        if(!Array.isArray(operacoes)){mensagem(p,'Lista de operações indisponível.');return;}
        if(!operacoes.length){mensagem(p,'Nenhuma operação cadastrada para esta empresa.');return;}
        const label=el(p,'label','Operação '),select=el(label,'select');select.id='portal-operacao';
        operacoes.forEach(o=>{const option=el(select,'option',o.id_operacao+' · '+(o.origem_nome||'Origem')+' → '+(o.destino_nome||'Destino'));option.value=o.id_operacao;});
        if(selecionada&&operacoes.some(o=>o.id_operacao===selecionada.id_operacao))select.value=selecionada.id_operacao;
        const area=el(p,'div');let leitura=0;
        const carregar=botao(p,'Carregar consulta e decisões',async()=>{
            const l=++leitura;carregar.disabled=true;area.replaceChildren();const st=mensagem(area,'Consultando operação e histórico…');
            try{
                const id=select.value,base='/api/v1/logistica/operacoes/'+encodeURIComponent(id);
                const dados=await Promise.allSettled([obter('/api/v1/painel/consultas',v,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id_operacao:id})}),obter(base+'/decisoes',v)]);
                if(!atual(v)||l!==leitura)return;
                const op=dados[0].status==='fulfilled'?dados[0].value.explicacao:null,hist=dados[1].status==='fulfilled'?dados[1].value:null;
                if(!op||op.id_operacao!==id)throw Error('Consulta indisponível');
                const horario=new Date().toISOString(),linhas=D.linhasDecisao(op,hist,usuario.tenant_id,horario);
                area.replaceChildren();el(area,'h4',id+' · '+op.acao_recomendada);el(area,'p',op.justificativa||'Justificativa não informada.');
                el(area,'p','Consulta recebida em '+D.data(horario)+'. O histórico não fornece autoria individual nem a fotografia de cada decisão antiga.');
                botao(area,'Baixar PDF da consulta e decisões',()=>download(nome(id)+'.pdf',PDF.gerar(linhas),'application/pdf'));
                botao(area,'Baixar consulta integral (JSON)',()=>download(nome(id)+'.json',JSON.stringify({empresa:usuario.tenant_id,consulta_recebida_em:horario,operacao:op,decisoes:hist},null,2),'application/json'));
                botao(area,'Baixar consulta (CSV)',()=>download(nome(id)+'-consulta.csv',D.csv([['empresa','operacao','consulta_recebida_em','recomendacao','custo_desvio_estimado_brl','impacto_potencial_brl'],[usuario.tenant_id,id,horario,op.acao_recomendada,op.infraestrutura?.financeiro?.custo_desvio_brl,op.infraestrutura?.financeiro?.prejuizo_potencial_evitado_brl]]),'text/csv;charset=utf-8'));
                botao(area,'Baixar relatório compartilhável (HTML)',()=>{
                    const doc=document.implementation.createHTMLDocument('SPRain · '+id);doc.documentElement.lang='pt-BR';
                    const meta=doc.createElement('meta');meta.setAttribute('http-equiv','Content-Security-Policy');meta.content="default-src 'none'; style-src 'unsafe-inline'";doc.head.appendChild(meta);
                    const style=doc.createElement('style');style.textContent='body{max-width:900px;margin:32px auto;padding:16px;font:16px/1.5 sans-serif}pre{white-space:pre-wrap;overflow-wrap:anywhere}';doc.head.appendChild(style);
                    const pre=doc.createElement('pre');pre.textContent=linhas.join('\n');doc.body.appendChild(pre);download(nome(id)+'.html','<!doctype html>'+doc.documentElement.outerHTML,'text/html;charset=utf-8');
                });
                if(Array.isArray(hist)){
                    tabela(area,['Decisão','Motivo','Registro'],hist.map(d=>[d.decisao,d.motivo_gestor,D.data(d.registrado_em)]));
                    if(!hist.length)mensagem(area,'Nenhuma decisão retornada.');
                    botao(area,'Baixar decisões (CSV)',()=>download(nome(id)+'-decisoes.csv',D.csv([['id_decisao','operacao','decisao','motivo','registrado_em','autoria_individual'],...hist.map(d=>[d.id_decisao,id,d.decisao,d.motivo_gestor,d.registrado_em,'Não fornecida'])]),'text/csv;charset=utf-8'));
                }else mensagem(area,'Histórico indisponível; o relatório sinaliza essa ausência. Atualize para tentar novamente.');
                if(!primeiro)primeiro=Date.now();
            }catch(e){if(atual(v)&&l===leitura)st.textContent=textoErro(e);}
            finally{if(atual(v)&&l===leitura)carregar.disabled=false;}
        });
        select.onchange=()=>{leitura++;area.replaceChildren();carregar.disabled=false;};
        el(p,'p','As consultas são guardadas no servidor e podem ser abertas na seção Histórico de consultas. Os arquivos acima representam a consulta carregada e as decisões retornadas. Exportação administrativa integral continua fora deste relatório.');
    }
    async function qualidade(p,v){
        el(p,'p','Atualização manual. Os indicadores de fontes são públicos/globais; feedback e métricas operacionais são da empresa autenticada. O critério de 48 horas é o adotado pelo endpoint, não a frequência homologada de cada fonte.');
        botao(p,'Atualizar qualidade e serviços',()=>render('qualidade'));
        const caminhos=['/api/v1/indicadores/qualidade','/api/v1/dados-publicos/fontes','/api/v1/health/liveness','/api/v1/health/readiness','/api/v1/alertas/precisao'];
        if(root.PainelSessao.podeEscrever())caminhos.push('/api/v1/logistica/observabilidade/metricas');
        const respostas=await Promise.allSettled(caminhos.map(c=>obter(c,v)));if(!atual(v))return;
        const dados=respostas.map(r=>r.status==='fulfilled'?r.value:null),[q,f,live,ready,precisao,metricas]=dados;
        el(p,'p','Consulta recebida em '+D.data(new Date().toISOString())+'. Uma falha de serviço ou fonte não significa ausência de risco.');
        tabela(p,['Serviço','Situação'],[['API',live?.status||'Indisponível'],['Banco / malha',ready?.status||'Indisponível'],['Latência do banco (ms)',ready?.latencia_db_ms],['Critério agregado da API',q?.status_geral||'Indisponível']]);
        el(p,'h4','Fontes e idade dos dados');
        if(Array.isArray(f?.fontes)&&f.fontes.length)tabela(p,['Fonte','Última importação bem-sucedida','Idade','Registros'],f.fontes.map(s=>{
            const tempo=Date.parse(s.ultimo_sucesso_em),horas=(Date.now()-tempo)/3600000;
            return [s.nome,D.data(s.ultimo_sucesso_em),!Number.isFinite(horas)||horas<0?'Data ausente/inconsistente':horas.toFixed(1)+' h',s.registros_importados];
        }));else mensagem(p,Array.isArray(f?.fontes)?'Nenhuma fonte cadastrada/importada foi retornada.':'Consulta de fontes indisponível.');
        el(p,'p','Histórico de tentativas e falhas de importação: não fornecido pelos endpoints atuais. Último sucesso não comprova ausência de falhas posteriores.');
        if(q){const detalhes=el(p,'details');el(detalhes,'summary','Classificação de prazo declarada pela API');el(detalhes,'pre',JSON.stringify(q,null,2));}
        el(p,'h4','Qualidade a partir do feedback da empresa');
        if(precisao){el(p,'p','Amostra: '+precisao.total_eventos_analisados+' evento(s) avaliados. Não representa homologação independente.');
            if(precisao.total_eventos_analisados>0)tabela(p,['Indicador da API','Valor'],Object.entries(precisao.metricas_precisao||{}));else mensagem(p,'Amostra insuficiente; não há percentual de precisão validado a apresentar.');
        }else mensagem(p,'Indicadores de feedback indisponíveis.');
        if(metricas){const d=el(p,'details');el(d,'summary','Métricas operacionais da empresa');el(d,'pre',JSON.stringify(metricas,null,2));}
        if(respostas.some(r=>r.status==='rejected'))mensagem(p,'Consulta parcial: um ou mais serviços não responderam. Os dados disponíveis foram mantidos e cada ausência foi indicada.');
    }
    function importacao(p,v){
        el(p,'p','Importe JSON de até 1 MB e 100 operações, com coordenadas, janela com fuso e premissas opcionais. A validação local não garante cobertura da malha: o backend avalia cada rota. O lote não é atômico; podem ocorrer gravações parciais.');
        botao(p,'Baixar modelo JSON',()=>download('modelo-operacoes.json',JSON.stringify([{id_operacao:'PREENCHA_ID',id_veiculo:null,origem_nome:'PREENCHA_ORIGEM',origem_lat:null,origem_lon:null,destino_nome:'PREENCHA_DESTINO',destino_lat:null,destino_lon:null,janela_inicio:'PREENCHA_ISO_COM_FUSO',janela_fim:'PREENCHA_ISO_COM_FUSO',dimensoes:null,custos_operacionais:{}}],null,2),'application/json'));
        const label=el(p,'label','Arquivo JSON de operações '),arquivo=el(label,'input');arquivo.type='file';arquivo.accept='.json,application/json';arquivo.id='portal-arquivo';
        const area=el(p,'div');let leitura=0,pendentes=[];
        const enviar=botao(p,'Importar operações validadas',async()=>{
            if(importarPendente||!root.PainelSessao.podeEscrever()||!pendentes.length)return;
            importarPendente=true;enviar.disabled=true;arquivo.disabled=true;const st=mensagem(area,'Importando. Não reenvie o lote enquanto aguarda a resposta.');
            try{
                const lote=pendentes;
                const res=await root.PainelSessao.request('/api/v1/logistica/operacoes/importar-lote',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(lote)});
                const resultado=await res.json();if(!atual(v))return;
                const erros=resultado.detalhe_falhas;
                if(!Array.isArray(erros)||resultado.total_recebido!==lote.length||resultado.sucessos+resultado.falhas!==lote.length||erros.length!==resultado.falhas)throw Error('Resposta inconsistente');
                const ids=new Set(erros.map(e=>e.id_operacao));
                if(ids.size!==erros.length||erros.some(e=>!lote.some(o=>o.id_operacao===e.id_operacao)))throw Error('Resposta inconsistente');
                pendentes=[];st.textContent=resultado.sucessos+' operação(ões) gravada(s); '+resultado.falhas+' falha(s). Não reimporte as operações bem-sucedidas.';
                if(erros.length){tabela(area,['Operação','Resultado'],erros.map(e=>[e.id_operacao,e.erro]));botao(area,'Baixar somente operações com falha',()=>download('operacoes-corrigir.json',JSON.stringify(lote.filter(o=>ids.has(o.id_operacao)),null,2),'application/json'));}
                botao(area,'Conferir operações no relatório',()=>render('relatorios'));
            }catch(e){if(atual(v)){pendentes=[];st.textContent='Não foi possível confirmar o resultado completo. Algumas operações podem ter sido gravadas. Consulte as operações antes de reenviar; não haverá repetição automática.';}}
            finally{importarPendente=false;if(atual(v))arquivo.disabled=false;}
        });enviar.disabled=true;
        arquivo.onchange=async()=>{
            const l=++leitura;enviar.disabled=true;pendentes=[];area.replaceChildren();const f=arquivo.files?.[0];if(!f)return;
            try{
                if(f.size>1024*1024)throw Error('O arquivo deve ter até 1 MB.');
                const texto=await f.text();if(!atual(v)||l!==leitura)return;
                const r=D.validarImportacao(texto,usuario.tenant_id);
                if(r.erros.length){tabela(area,['Linha (operação)','Corrigir'],r.erros.map(e=>[e.linha,e.mensagem]));mensagem(area,'Nenhum dado enviado. Corrija o arquivo inteiro antes de importar.');return;}
                const existentes=await obter('/api/v1/logistica/operacoes',v);if(!atual(v)||l!==leitura)return;
                if(!Array.isArray(existentes))throw Error('Não foi possível conferir identificadores.');
                const colisao=r.operacoes.filter(o=>existentes.some(e=>e.id_operacao===o.id_operacao));
                if(colisao.length){mensagem(area,'Identificadores já cadastrados: '+colisao.map(o=>o.id_operacao).join(', ')+'. O importador cria novas operações; use identificadores novos para evitar sobrescrever viagens existentes.');return;}
                pendentes=r.operacoes;tabela(area,['Operação','Origem','Destino','Início'],pendentes.map(o=>[o.id_operacao,o.origem_nome,o.destino_nome,D.data(o.janela_inicio)]));
                mensagem(area,pendentes.length+' operação(ões) validada(s) localmente. Empresa de destino: '+usuario.tenant_id+'. Confira antes de importar.');enviar.disabled=!root.PainelSessao.podeEscrever();
            }catch(e){if(atual(v)&&l===leitura)mensagem(area,e.message||'Não foi possível ler o arquivo.');}
        };
        if(!root.PainelSessao.podeEscrever())mensagem(p,'Seu perfil permite baixar o modelo e validar o arquivo, mas não importar.');
        el(p,'p','A importação é de viagens roteáveis; não cadastra recorrência ou corredor persistente. Edição simultânea em outra sessão pode mudar os identificadores após a prévia; o contrato do backend ainda não oferece criação condicional/atômica.');
    }
    function configuracao(p){
        tabela(p,['Sessão','Valor'],[['Empresa',usuario.tenant_id],['Perfil',usuario.role],['Acesso',usuario.email||'Não informado']]);
        el(p,'h4','Premissas de caminhões e viagens');el(p,'p','As medidas e custos são cadastrados na frota e no despacho. Nos detalhes da operação, Editar premissas permite salvar custos e recalcular a comparação. A configuração financeira global da empresa continua separada desses valores por viagem.');
        const novo=botao(p,'Abrir formulário de novo despacho',()=>{encerrar();root.abrirModalDespacho();});novo.disabled=!root.PainelSessao.podeEscrever();
        botao(p,'Abrir minha frota',()=>{encerrar();root.alternarAba('FROTA');});
        el(p,'h4','Gestão de usuários e recuperação de acesso');
        el(p,'p','Administradores com acesso individual podem gerir usuários e liberar recuperação após conferir a identidade. Use a seção Administração da empresa. Na entrada, Recuperar acesso permite solicitar e concluir a recuperação.');
        botao(p,'Abrir administração da empresa',()=>navegar('administracao'));
        el(p,'h4','Corredores e rotas recorrentes');el(p,'p','A aba SP-310/SP-348 consulta o corredor de referência. Use Corredores e recorrências para cadastrar e editar corredores e agendas da sua empresa.');
        botao(p,'Cadastrar corredores e recorrências',()=>navegar('corredores'));
        botao(p,'Consultar corredor existente',()=>{encerrar();root.alternarAba('CORREDOR');});
        el(p,'h4','Exportação');el(p,'p','Relatórios exportam resumo, consulta e decisões. A seção Administração da empresa permite ao administrador individual baixar um arquivo dos dados privados do cliente, sem senhas ou sessões.');
        botao(p,'Abrir relatórios e exportações',()=>render('relatorios'));
    }
    function demonstracao(p,v){
        if(root.PainelDemonstracao)return root.PainelDemonstracao.render(p,{atual:()=>atual(v),obter:path=>obter(path,v),tabela});
        el(p,'p','DEMONSTRAÇÃO — os atalhos de contas demo funcionam somente fora de produção. O acesso individual é separado desses atalhos. Chuva simulada não é medição em campo.');
        const passos=['Entre com uma conta de demonstração em ambiente separado.','Cadastre um caminhão de teste com medidas explicitamente identificadas como exemplo.','Despache uma rota dentro da malha disponível e confira as coordenadas.','Compare cenários de chuva, rota original, alternativa, limitações e custos.','Registre uma decisão com motivo, confira o histórico e exporte o relatório.'];
        const ol=el(p,'ol');passos.forEach(s=>el(ol,'li',s));
        el(p,'p','Cenário histórico SP-310: aguardando fonte primária e associação dos trechos. O endpoint atual contém distâncias substitutas e não é acionado por esta tela como se fosse histórico validado.');
        botao(p,'Voltar à simulação existente',()=>{encerrar();root.alternarAba('URBANO');});
        el(p,'p','Esta central não insere eventos de demonstração na base operacional. O roteiro e os procedimentos de isolamento estão documentados no repositório.');
    }
    function ajuda(p){
        const passos=['Confira a empresa e o perfil antes de cadastrar ou importar.','Cadastre a frota com medidas reais, peso carregado e eixos. Dados ausentes exigem conferência.','Despache pela tela existente ou importe operações após validar o arquivo.','Abra a operação: confira fonte, data, limitações, restrições físicas, pedágios e premissas.','Compare as rotas. Se não houver alternativa ou os dados estiverem indisponíveis, não trate isso como passagem segura.','Registre a decisão e o motivo; confira se o servidor confirmou a gravação.','Na central, carregue a consulta e as decisões para baixar PDF/CSV e compartilhar internamente.'];
        const ol=el(p,'ol');passos.forEach(s=>el(ol,'li',s));
        el(p,'h4','Como ler o mapa');el(p,'p','Azul contínuo: alternativa calculada. Vermelho tracejado: rota original. Vermelho espesso: vulnerabilidade física da malha; não confirma interdição. Pedágios e restrições mantêm as camadas próprias, com dados e limitações nos detalhes.');
        el(p,'p','Histórico descreve o passado; previsão estima condições futuras; observação registra uma leitura; confirmação é o estado declarado pela fonte. Uma informação não substitui outra.');
        el(p,'p','Tempo desta sessão até a primeira consulta de relatório útil: '+(primeiro?((primeiro-inicio)/1000).toFixed(1)+' s':'ainda não registrado nesta sessão')+'. Medição apenas em memória: não é evento auditável persistido. Esse evento de onboarding ainda precisa de endpoint.');
        el(p,'h4','Quando pedir suporte');el(p,'p','Em falha de fonte, atualize a consulta e confira a idade dos dados. Em conflito de decisão, recalcule a rota. Em resultado incerto de importação, consulte as operações antes de reenviar. Nunca envie sua chave de API em relatórios ou mensagens de suporte.');
    }
    function sessao(user){limpar();usuario={tenant_id:user.tenant_id,role:user.role,email:user.email};inicio=Date.now();aviso.hidden=user.tipo_acesso==='INDIVIDUAL'&&!root.PainelDemonstracao?.estado()?.demo_isolada;}
    function limpar(){usuario=null;selecionada=null;primeiro=null;versao++;controle?.abort();dialog.close();conteudo.replaceChildren();urls.forEach(u=>URL.revokeObjectURL(u));urls.clear();}
    function selecionar(op){selecionada=op;}
    function registrarSecao(id,label,fn){
        if(telas[id])throw Error('Seção já registrada.');rotulos[id]=label;
        telas[id]=(p,v)=>fn(p,{atual:()=>atual(v),obter:path=>obter(path,v),recarregar:()=>render(id)});
        const b=botao(nav,label,()=>render(id));b.dataset.secao=id;
    }
    function navegar(id){if(!usuario)return;if(!dialog.open)dialog.showModal();render(id);}
    root.PortalOperacional={sessao,limpar,selecionar,abrir:abrir.onclick,registrarSecao,navegar};
})(window);
