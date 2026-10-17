(function(root){
    'use strict';const U=root.FluxoPainel,D=root.PortalDados;const dias=['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo'];let chaves=new Map();
    async function tela(p,ctx){
        U.el(p,'p','Corredores e agendas recorrentes são salvos na empresa. Cada viagem é criada por despacho explícito na data escolhida; não há execução automática em segundo plano. Cada despacho usa a malha e as restrições disponíveis naquele momento.');
        const editor=U.el(p,'div'),lista=U.el(p,'div');let offset=0;
        const frota=await ctx.obter('/api/v1/logistica/veiculos');if(!ctx.atual())return;
        function formCorredor(c){editor.replaceChildren();const d=c?.dados||{},f=U.el(editor,'form');U.el(f,'h4',c?'Editar corredor':'Cadastrar corredor');f.onsubmit=e=>e.preventDefault();const refs={};
            for(const[k,label,tipo,min,max]of [['nome','Nome do corredor','text'],['origem_nome','Nome da origem','text'],['origem_lat','Latitude da origem','number',-90,90],['origem_lon','Longitude da origem','number',-180,180],['destino_nome','Nome do destino','text'],['destino_lat','Latitude do destino','number',-90,90],['destino_lon','Longitude do destino','number',-180,180]])refs[k]=U.campo(f,k,label,tipo,d[k],{required:'',min,max,step:tipo==='number'?'any':undefined,maxlength:tipo==='text'?150:undefined});
            const m=U.formularioMedidas(f,d.dimensoes_referencia||{}),ativo=U.campo(f,'ativo','Corredor ativo','checkbox');ativo.checked=d.ativo!==false;
            U.botao(f,'Usar origem/destino da operação selecionada',()=>{const op=U.selecionada();if(!op?.coordenadas)throw Error('Selecione uma operação no mapa primeiro.');for(const[k,i]of Object.entries(refs))if(k!=='nome')i.value=op.coordenadas[k]??'';for(const[k,i]of Object.entries(m))i.value=op.infraestrutura?.dimensoes?.[k]??'';},{valido:ctx.atual});
            U.botao(f,'Salvar corredor',async()=>{if(!f.reportValidity())return;const dados={...U.ler(refs),ativo:ativo.checked,dimensoes_referencia:U.lerMedidas(m),...(c?{versao:c.versao}:{})};
                await U.enviar('/corredores'+(c?'/'+c.id:''),dados,c?'PUT':'POST');if(ctx.atual()){editor.replaceChildren();await carregar();}},{escrita:true,valido:ctx.atual});
            if(!root.PainelSessao.podeEscrever())f.querySelectorAll('input').forEach(i=>i.disabled=true);
        }
        function formRecorrencia(c,r){editor.replaceChildren();const d=r?.dados||{},f=U.el(editor,'form');f.onsubmit=e=>e.preventDefault();U.el(f,'h4',(r?'Editar':'Cadastrar')+' recorrência · '+c.dados.nome);
            const nome=U.campo(f,'nome','Nome da recorrência','text',d.nome,{required:'',maxlength:150}),horario=U.campo(f,'horario','Horário de partida (São Paulo)','time',d.horario_local,{required:''}),janela=U.campo(f,'janela','Duração da janela (minutos)','number',d.janela_minutos,{required:'',min:1,max:2880,step:1});
            const checks=dias.map((dia,i)=>{const x=U.campo(f,'dia'+i,dia,'checkbox');x.checked=(d.dias_semana||[]).includes(i);return x;});
            const l=U.el(f,'label','Caminhão da frota (opcional) '),veiculo=U.el(l,'select');veiculo.setAttribute('aria-label','Caminhão da frota (opcional)');U.el(veiculo,'option','Sem veículo vinculado').value='';
            frota.forEach(v=>U.el(veiculo,'option',v.id_veiculo+' · '+v.placa).value=v.id_veiculo);veiculo.value=d.id_veiculo||'';
            const m=U.formularioMedidas(f,d.dimensoes||{}),custos=U.formularioCustos(f,d.custos_operacionais||{}),ativo=U.campo(f,'ativo','Recorrência ativa','checkbox');ativo.checked=d.ativo!==false;
            U.botao(f,'Salvar recorrência',async()=>{if(!f.reportValidity())return;const selecionados=checks.flatMap((x,i)=>x.checked?[i]:[]);if(!selecionados.length)throw Error('Selecione pelo menos um dia da semana.');
                const payload={nome:nome.value,horario_local:horario.value,janela_minutos:Number(janela.value),dias_semana:selecionados,id_veiculo:veiculo.value||null,dimensoes:U.lerMedidas(m),custos_operacionais:U.ler(custos),ativo:ativo.checked,...(r?{versao:r.versao}:{})};
                await U.enviar(r?'/recorrencias/'+r.id:'/corredores/'+c.id+'/recorrencias',payload,r?'PUT':'POST');if(ctx.atual()){editor.replaceChildren();await carregar();}},{escrita:true,valido:ctx.atual});
        }
        function formDespacho(c,r){editor.replaceChildren();U.el(editor,'h4','Despachar '+r.dados.nome);U.el(editor,'p','Dias: '+r.dados.dias_semana.map(i=>dias[i]).join(', ')+' · '+r.dados.horario_local+' · America/Sao_Paulo. A malha será reavaliada para este caminhão.');
            const data=U.campo(editor,'data_local','Data da viagem','date','',{required:''});
            U.botao(editor,'Criar viagem desta recorrência',async()=>{if(!data.reportValidity())return;const k=r.id+':'+data.value;if(!chaves.has(k))chaves.set(k,crypto.randomUUID());
                const resposta=await U.enviar('/recorrencias/'+r.id+'/despachar',{data_local:data.value,chave_idempotencia:chaves.get(k)});if(!ctx.atual())return;
                U.status(editor,'Viagem '+resposta.id_operacao+(resposta.reutilizado?' já havia sido criada; nenhum despacho duplicado.':' criada.'));U.botao(editor,'Abrir viagem criada',async()=>{document.getElementById('portal-operacional').close();await root.selecionarOperacao(resposta.id_operacao);},{valido:ctx.atual});
            },{escrita:true,valido:ctx.atual});
        }
        async function carregar(){lista.replaceChildren();U.status(lista,'Consultando corredores…');const res=await ctx.obter('/api/v1/painel/corredores?offset='+offset);if(!ctx.atual())return;lista.replaceChildren();
            if(!res.items.length)U.status(lista,'Nenhum corredor cadastrado nesta página.');
            for(const c of res.items){const a=U.el(lista,'article');U.el(a,'h4',c.dados.nome+(c.dados.ativo?'':' · Inativo'));U.el(a,'p',c.dados.origem_nome+' → '+c.dados.destino_nome+' · Cadastro atualizado em '+D.data(c.atualizado_em));
                U.botao(a,'Editar '+c.dados.nome,()=>formCorredor(c),{escrita:true,valido:ctx.atual});U.botao(a,'Adicionar recorrência',()=>formRecorrencia(c),{escrita:true,valido:ctx.atual});
                for(const r of c.recorrencias){const d=U.el(a,'details');U.el(d,'summary',r.dados.nome+(r.dados.ativo?'':' · Inativa'));U.el(d,'p',r.dados.dias_semana.map(i=>dias[i]).join(', ')+' · '+r.dados.horario_local+' · Janela '+r.dados.janela_minutos+' min');
                    U.botao(d,'Editar recorrência',()=>formRecorrencia(c,r),{escrita:true,valido:ctx.atual});U.botao(d,'Preparar despacho',()=>formDespacho(c,r),{escrita:true,valido:ctx.atual});}
            }
            if(offset>0)U.botao(lista,'Página anterior de corredores',()=>{offset=Math.max(0,offset-20);return carregar();},{valido:ctx.atual});
            if(res.proximo_offset!==null)U.botao(lista,'Próxima página de corredores',()=>{offset=res.proximo_offset;return carregar();},{valido:ctx.atual});
        }
        U.botao(p,'Novo corredor',()=>formCorredor(),{escrita:true,valido:ctx.atual});await carregar();
    }
    root.PortalOperacional.registrarSecao('corredores','Corredores e recorrências',tela);
    const b=document.createElement('button');b.type='button';b.className='btn-top';b.textContent='Corredores e recorrências';b.onclick=()=>root.PortalOperacional.navegar('corredores');document.querySelector('.top-controls').prepend(b);
    root.PainelCorredores={limpar:()=>{chaves.clear();}};
})(window);
