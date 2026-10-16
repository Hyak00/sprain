/* Formatos de importação e exportação. Sem acesso à rede ou credenciais. */
(function(root){
    'use strict';
    const campos=['id_operacao','id_veiculo','origem_nome','origem_lat','origem_lon','destino_nome','destino_lat','destino_lon','janela_inicio','janela_fim','dimensoes','custos_operacionais'];
    const limites={altura_m:10,largura_m:10,comprimento_m:100,peso_total_t:300,eixos:15};
    const custos=['custo_por_km','custo_hora_motorista','custo_operacional_veiculo_hora','custo_atraso_hora','prejuizo_potencial_alagamento','consumo_km_l','preco_combustivel_litro','custo_por_km_sem_combustivel','combustivel_data_coleta'];
    const objeto=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
    const finito=v=>typeof v==='number'&&Number.isFinite(v);
    const iso=v=>{
        if(typeof v!=='string'||!/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(v)||!Number.isFinite(Date.parse(v)))return false;
        const dia=v.slice(0,10);return new Date(dia+'T00:00:00Z').toISOString().slice(0,10)===dia;
    };
    function validarImportacao(texto,empresa){
        if(typeof texto!=='string'||new TextEncoder().encode(texto).length>1024*1024)throw Error('O arquivo deve ter até 1 MB.');
        let dados;try{dados=JSON.parse(texto.replace(/^\uFEFF/,''));}catch{throw Error('JSON inválido. Use o modelo e mantenha a estrutura do arquivo.');}
        if(!Array.isArray(dados)||dados.length<1||dados.length>100)throw Error('Informe uma lista JSON com 1 a 100 operações.');
        const ids=new Set(),erros=[],operacoes=[];
        dados.forEach((o,i)=>{
            const falhar=m=>erros.push({linha:i+1,mensagem:m});
            if(!objeto(o)){falhar('A operação precisa ser um objeto.');return;}
            const desconhecidos=Object.keys(o).filter(k=>!campos.includes(k)&&k!=='tenant_id');
            if(desconhecidos.length)falhar('Campos não suportados: '+desconhecidos.join(', '));
            if(o.tenant_id!==undefined&&o.tenant_id!==empresa)falhar('A empresa do arquivo difere da sessão.');
            for(const chave of ['id_operacao','origem_nome','destino_nome'])if(typeof o[chave]!=='string'||!o[chave].trim()||o[chave].length>200)falhar(chave+': informe um texto de até 200 caracteres.');
            if(typeof o.id_operacao==='string'){
                if(ids.has(o.id_operacao.trim()))falhar('Identificador de operação repetido no arquivo.');ids.add(o.id_operacao.trim());
                if(!/^[A-Za-z0-9_.-]{1,100}$/.test(o.id_operacao))falhar('id_operacao: use até 100 letras, números, ponto, hífen ou sublinhado.');
            }
            if(o.id_veiculo!==undefined&&o.id_veiculo!==null&&(typeof o.id_veiculo!=='string'||!o.id_veiculo.trim()||o.id_veiculo.length>100))falhar('id_veiculo inválido.');
            for(const [chave,min,max] of [['origem_lat',-90,90],['destino_lat',-90,90],['origem_lon',-180,180],['destino_lon',-180,180]])if(!finito(o[chave])||o[chave]<min||o[chave]>max)falhar(chave+': coordenada numérica fora do intervalo.');
            for(const chave of ['janela_inicio','janela_fim'])if(!iso(o[chave]))falhar(chave+': use data/hora ISO com fuso, por exemplo 2026-10-20T08:00:00-03:00.');
            if(iso(o.janela_inicio)&&iso(o.janela_fim)&&Date.parse(o.janela_fim)<=Date.parse(o.janela_inicio))falhar('O fim da janela deve ser posterior ao início.');
            if(o.dimensoes!==undefined&&o.dimensoes!==null){
                if(!objeto(o.dimensoes))falhar('dimensoes deve ser um objeto com as cinco medidas.');
                else{
                    if(Object.keys(o.dimensoes).some(k=>!Object.hasOwn(limites,k)))falhar('Medida desconhecida.');
                    for(const [k,max]of Object.entries(limites))if(!finito(o.dimensoes[k])||o.dimensoes[k]<=0||o.dimensoes[k]>max||(k==='eixos'&&(!Number.isInteger(o.dimensoes[k])||o.dimensoes[k]<2)))falhar('dimensoes.'+k+': valor inválido ou ausente.');
                }
            }
            if(o.custos_operacionais!==undefined&&o.custos_operacionais!==null){
                if(!objeto(o.custos_operacionais))falhar('custos_operacionais deve ser um objeto.');
                else for(const [k,v]of Object.entries(o.custos_operacionais)){
                    if(!custos.includes(k)){falhar('Premissa não suportada: '+k);continue;}
                    if(v===null)continue;
                    if(k==='combustivel_data_coleta'){
                        if(typeof v!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(v)||!Number.isFinite(Date.parse(v))||new Date(v).toISOString().slice(0,10)!==v)falhar('Data de coleta inválida.');
                    }else if(!finito(v)||v<0||(['consumo_km_l','preco_combustivel_litro'].includes(k)&&(v<=0||v>100)))falhar('Premissa inválida: '+k);
                }
            }
            operacoes.push(Object.fromEntries(campos.filter(k=>Object.hasOwn(o,k)).map(k=>[k,o[k]])));
        });
        return {operacoes,erros};
    }
    function csv(linhas){
        const celula=v=>{let s=v==null?'':String(v);if(typeof v!=='number'&&/^[\s]*[=+\-@\t\r]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};
        return '\uFEFF'+linhas.map(l=>l.map(celula).join(';')).join('\r\n');
    }
    const moeda=v=>finito(v)?v.toLocaleString('pt-BR',{style:'currency',currency:'BRL'}):'Não informado';
    const data=v=>iso(v)?new Date(v).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'})+' (Brasília)':'Não informado';
    function linhasDecisao(op,historico,empresa,recebido){
        const f=op?.infraestrutura?.financeiro||{},m=op?.metricas||{};
        const alternativa=op?.validacao_rota?.rota_alternativa_disponivel===true&&op?.geometrias?.rota_alternativa_geojson?.features?.some(v=>['LineString','MultiLineString'].includes(v?.geometry?.type)&&v.geometry.coordinates?.length>0);
        const linhas=['SPRain | Relatório de consulta e decisões','Empresa: '+empresa,'Operação: '+(op?.id_operacao||'Não informada'),
            'Consulta recebida em: '+data(recebido),'Data da fotografia do cálculo: não fornecida pela API.',
            'Origem: '+(op?.coordenadas?.origem_nome||'Não informada'),'Destino: '+(op?.coordenadas?.destino_nome||'Não informado'),
            'Caminhão: '+(op?.id_veiculo||'Não informado')+' | '+(op?.placa||'Sem placa'),
            'Recomendação: '+(op?.acao_recomendada||'Não informada'),'Justificativa: '+(op?.justificativa||'Não informada'),
            'Original: '+(finito(m.distancia_original_km)?m.distancia_original_km+' km':'Não informado'),
            'Tempo original nominal: '+(finito(m.tempo_original_min)?m.tempo_original_min+' min':'Não informado'),
            'Alternativa: '+(alternativa&&finito(m.distancia_alternativa_km)?m.distancia_alternativa_km+' km':'Não disponível'),
            'Tempo alternativo nominal: '+(alternativa&&finito(m.tempo_alternativo_min)?m.tempo_alternativo_min+' min':'Não disponível'),
            'Custo original estimado, parcelas conhecidas: '+moeda(f.custo_original_conhecido_brl),
            'Alternativa disponível com geometria: '+(alternativa?'sim':'não'),
            'Custo alternativo estimado, parcelas conhecidas: '+moeda(alternativa?f.custo_alternativa_conhecido_brl:null),
            'Diferença de custo: '+moeda(alternativa?f.custo_desvio_brl:null),'Economia operacional estimada: '+moeda(alternativa?f.economia_operacional_conhecida_brl:null),
            'Impacto potencial evitado: '+moeda(alternativa?f.prejuizo_potencial_evitado_brl:null),'Economia líquida potencial: '+moeda(alternativa?f.economia_liquida_potencial_brl:null),
            'Economia comprovada: não disponível.','Custo observado: não disponível.','Valores de planejamento; não comprovam dinheiro economizado.',
            'Limitações: '+(op?.validacao_rota?.avisos_limitacao||'Cobertura não informada.'),
            'Infraestrutura: '+(op?.infraestrutura?.aviso||'Não informada.'),'Histórico de decisões:'];
        if(!Array.isArray(historico))linhas.push('Indisponível nesta consulta.');
        else if(!historico.length)linhas.push('Nenhuma decisão retornada.');
        else historico.forEach(d=>linhas.push('#'+d.id_decisao+' | '+d.decisao+' | '+data(d.registrado_em),'Motivo: '+d.motivo_gestor,'Autoria individual: não fornecida neste contrato.'));
        linhas.push('Fontes: endpoints explicacao e decisoes da operação autenticada.','Medidas efetivas atuais (não são fotografia datada da recomendação):');
        const medidas={altura_m:'Altura (m)',largura_m:'Largura (m)',comprimento_m:'Comprimento (m)',peso_total_t:'Peso total (t)',eixos:'Eixos'};
        for(const [k,label]of Object.entries(medidas))linhas.push(label+': '+(op?.infraestrutura?.dimensoes?.[k]??'Não informado'));
        linhas.push('Premissas financeiras retornadas pelo cálculo:');
        if(!Object.keys(f.premissas||{}).length)linhas.push('Não informadas.');
        else for(const [k,v]of Object.entries(f.premissas))linhas.push(k+': '+(v??'Não informado'));
        for(const [tipo,infra]of [['Original',op?.infraestrutura?.original],['Alternativa',alternativa?op?.infraestrutura?.alternativa:null]]){
            linhas.push(tipo+' | Pedágios conhecidos: '+moeda(infra?.pedagios?.subtotal_conhecido_reais),tipo+' | Tarifas pendentes: '+(infra?.pedagios?.tarifas_pendentes??'Não informado'));
            const pontos=infra?.pontos_mapa?.features||[];
            linhas.push(tipo+' | Pontos físicos retornados: '+pontos.length+'. Cobertura parcial; confirmar a sinalização.');
            if(pontos.length>100)linhas.push('Este relatório lista os primeiros 100 pontos; consulte o JSON integral para os demais.');
            pontos.slice(0,100).forEach(p=>{const a=p.properties||{};linhas.push((a.tipo||'Ponto')+' | '+(a.nome||'Sem nome')+' | '+(a.status||'Situação não informada'),'Fonte: '+(a.fonte||'Não informada')+' | Revisar até: '+(a.valido_ate||'Não informado'));});
        }
        return linhas;
    }
    root.PortalDados={validarImportacao,csv,moeda,data,linhasDecisao};
    if(typeof module!=='undefined'&&module.exports)module.exports=root.PortalDados;
})(typeof window!=='undefined'?window:globalThis);
