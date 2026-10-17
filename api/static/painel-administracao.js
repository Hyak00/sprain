/* Administração complementar. Autorizações e isolamento são revalidados no servidor. */
(function(root){
    'use strict';
    const F=root.FluxoPainel, P=root.PortalOperacional;
    const {el,campo,status}=F;
    const identidade=()=>root.PainelSessao.identidade?.();
    const admin=()=>{const u=identidade();return u?.role==='ADMIN'&&u?.tipo_acesso==='INDIVIDUAL'&&!!u.usuario_id;};
    function erro(e){return F.erro(e)||'Ação cancelada.';}
    function acao(p,label,ctx,fn,restrita=true){
        const b=el(p,'button',label);b.type='button';b.disabled=restrita&&!admin();
        b.onclick=async()=>{
            if(b.disabled||!ctx.atual()||(restrita&&!admin()))return;
            b.disabled=true;b.setAttribute('aria-busy','true');
            try{await fn();}catch(e){if(ctx.atual()&&!e?.silencioso)status(p,erro(e)+' Confira a lista atual antes de repetir uma gravação.');}
            finally{if(ctx.atual()&&b.isConnected){b.disabled=restrita&&!admin();b.removeAttribute('aria-busy');}}
        };return b;
    }
    async function enviar(path,body,method='POST'){
        const r=await root.PainelSessao.request(path,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});return r.json();
    }
    function papel(p,valor){const l=el(p,'label','Papel de acesso'),s=el(l,'select');s.name='papel';
        for(const [v,n]of [['VIEWER','Consulta'],['OPERATOR','Operação'],['ADMIN','Administração']]){const o=el(s,'option',n);o.value=v;}s.value=valor;return s;}
    function confirmar(p,label){const l=el(p,'label'),i=el(l,'input');i.type='checkbox';i.required=true;el(l,'span',label);return i;}
    async function usuarios(p,ctx,offset=0){
        const r=await ctx.obter('/api/v1/acesso/usuarios?limit=20&offset='+offset);if(!ctx.atual())return;
        const lista=el(p,'section');el(lista,'h4','Usuários da empresa');
        el(lista,'p','ADMIN administra; OPERATOR opera e registra; VIEWER consulta. Alterar papel ou desativar encerra as sessões do usuário. Sua própria conta não pode ser alterada aqui.');
        if(!r.usuarios.length)status(lista,'Nenhum usuário encontrado.');
        for(const u of r.usuarios){
            const a=el(lista,'article');el(a,'h5',u.email);el(a,'p',u.papel+' · '+(u.ativo?'Ativo':'Desativado'));
            if(!u.ativo||u.id===identidade()?.usuario_id)continue;
            const s=papel(a,u.papel),ok=confirmar(a,'Conferi o usuário e o novo papel.');
            acao(a,'Salvar papel de '+u.email,ctx,async()=>{
                if(!ok.checked){status(a,'Confirme a alteração de papel.');return;}
                await enviar('/api/v1/acesso/usuarios/'+encodeURIComponent(u.id)+'/papel',{papel:s.value},'PATCH');
                if(ctx.atual())await ctx.recarregar();
            });
            const desativar=confirmar(a,'Confirmo a desativação deste usuário.');
            acao(a,'Desativar '+u.email,ctx,async()=>{
                if(!desativar.checked){status(a,'Confirme a desativação.');return;}
                await enviar('/api/v1/acesso/usuarios/'+encodeURIComponent(u.id)+'/desativar',{});
                if(ctx.atual())await ctx.recarregar();
            });
        }
        if(offset>0)acao(lista,'Usuários anteriores',ctx,async()=>{lista.remove();await usuarios(p,ctx,Math.max(0,offset-20));});
        if(offset+20<r.total)acao(lista,'Próximos usuários',ctx,async()=>{lista.remove();await usuarios(p,ctx,offset+20);});
    }
    async function recuperacoes(p,ctx,offset=0){
        const pagina=await ctx.obter('/api/v1/administracao/recuperacao?offset='+offset);if(!ctx.atual())return;
        const lista=el(p,'section');el(lista,'h4','Recuperações de acesso pendentes');
        el(lista,'p','Confira a identidade por um canal já conhecido antes de liberar. O sistema não envia e-mail. O código vale 30 minutos, funciona uma única vez e deve ser entregue em particular.');
        if(!pagina.items.length)status(lista,'Nenhuma solicitação pendente.');
        for(const r of pagina.items){
            const a=el(lista,'article');el(a,'h5',r.email);el(a,'p','Solicitado: '+root.PortalDados.data(r.criado_em)+' · Validade: '+root.PortalDados.data(r.expira_em));
            if(!r.liberado_em){const ok=confirmar(a,'Conferi a identidade por um canal já conhecido.');
                const liberar=acao(a,'Liberar código para '+r.email,ctx,async()=>{
                    if(!ok.checked){status(a,'Confira a identidade antes de liberar.');return;}
                    const d=await enviar('/api/v1/administracao/recuperacao/'+r.id+'/liberar',{identidade_conferida:true});
                    if(!ctx.atual())return;
                    liberar.remove();ok.disabled=true;
                    const c=campo(a,'codigo_liberado','Código temporário (copie e entregue em particular)','text',d.codigo,{readonly:''});c.autocomplete='off';
                    status(a,d.mensagem+' Expira: '+root.PortalDados.data(d.expira_em));
                });
            }else status(a,'Código já liberado. Se foi perdido, cancele e peça ao usuário uma nova solicitação.');
            acao(a,'Cancelar recuperação de '+r.email,ctx,async()=>{
                await enviar('/api/v1/administracao/recuperacao/'+r.id+'/cancelar',{});if(ctx.atual())await ctx.recarregar();
            });
        }
        if(offset>0)acao(lista,'Recuperações anteriores',ctx,async()=>{lista.remove();await recuperacoes(p,ctx,Math.max(0,offset-50));});
        if(pagina.proximo_offset!==null)acao(lista,'Próximas recuperações',ctx,async()=>{lista.remove();await recuperacoes(p,ctx,pagina.proximo_offset);});
    }
    P.registrarSecao('administracao','Administração da empresa',async(p,ctx)=>{
        if(!admin()){status(p,'A gestão de usuários, recuperação e exportação integral exige ADMIN com conta individual. Contas de demonstração e chaves de integração não administram identidades.');return;}
        const novo=el(p,'details');el(novo,'summary','Criar usuário');const form=el(novo,'form');form.onsubmit=e=>e.preventDefault();
        const email=campo(form,'email','E-mail do usuário','email','',{required:'',maxlength:254});email.autocomplete='off';
        const senha=campo(form,'senha','Senha inicial (15 a 256 caracteres)','password','',{required:'',minlength:15,maxlength:256});senha.autocomplete='new-password';
        const s=papel(form,'VIEWER');
        const criar=acao(novo,'Criar usuário',ctx,async()=>{
            if(!form.reportValidity())return;
            await enviar('/api/v1/acesso/usuarios',{email:email.value,senha:senha.value,papel:s.value});
            senha.value='';form.remove();criar.remove();if(ctx.atual()){status(novo,'Usuário criado. Atualize a lista para consultar.');}
        });
        acao(p,'Atualizar administração',ctx,()=>ctx.recarregar());
        await usuarios(p,ctx);if(!ctx.atual())return;await recuperacoes(p,ctx);if(!ctx.atual())return;
        const exp=el(p,'section');el(exp,'h4','Exportar dados do cliente');
        el(exp,'p','Arquivo ZIP com JSON Lines e manifesto: frota, viagens, rotas, recomendações, cenários, decisões, corredores, agendas, consultas, relatos, premissas, usuários, auditorias, feedback e infraestrutura/malha privada. Inclui viagens do módulo cliente quando utilizado e eventos configurados nos webhooks, sem URLs ou segredos. Fotografia consistente da sua empresa. Não inclui senhas, sessões, códigos de recuperação, outras empresas ou bases públicas compartilhadas. Limites: 100 MB descompactados e 19 MB no ZIP.');
        const ok=confirmar(exp,'Entendo que o arquivo contém dados privados da minha empresa e vou guardá-lo com acesso restrito.');
        acao(exp,'Baixar dados da minha empresa (ZIP)',ctx,async()=>{
            if(!ok.checked){status(exp,'Confirme o destino seguro do arquivo.');return;}
            const st=status(exp,'Preparando a exportação…');
            const r=await root.PainelSessao.request('/api/v1/administracao/exportacao',{timeout:90000});const blob=await r.blob();
            if(!ctx.atual())return;
            const url=URL.createObjectURL(blob),a=el(exp,'a');a.href=url;a.download='sprain-dados-cliente.zip';a.click();a.remove();
            setTimeout(()=>URL.revokeObjectURL(url),1000);st.textContent='Arquivo preparado e download solicitado ao navegador. Confira o manifesto e as contagens.';
        });
    });
    P.registrarSecao('financeiro','Premissas financeiras',async(p,ctx)=>{
        const d=await ctx.obter('/api/v1/administracao/financeiro');if(!ctx.atual())return;
        el(p,'p','Padrões da empresa para novos despachos, inclusive importações e recorrências. Prioridade: valores da viagem, depois frota, depois empresa, depois referências do sistema. Não muda viagens existentes nem seus históricos. Para recalcular uma viagem existente, edite as premissas na comparação.');
        el(p,'p','Fonte: configuração informada pela empresa. Atualização: '+root.PortalDados.data(d.atualizado_em)+'. Versão: '+d.versao+'.');
        const form=el(p,'form');form.onsubmit=e=>e.preventDefault();const refs=F.formularioCustos(form,d.custos);form.querySelector('details').open=true;
        form.querySelector('details p').textContent='Em branco: remover o padrão da empresa para esse campo. Os valores da frota/viagem continuam prioritários. Custo total por km informado tem prioridade sobre seus componentes; combustível não é somado novamente.';
        const ref=el(p,'details');el(ref,'summary','Referências gerais do sistema quando não houver valor informado');el(ref,'pre',JSON.stringify(d.referencias_sistema,null,2));
        if(!admin()){form.querySelectorAll('input').forEach(i=>i.disabled=true);status(p,'Consulta permitida. Somente ADMIN com conta individual pode salvar padrões da empresa.');}
        acao(p,'Salvar padrões financeiros',ctx,async()=>{
            if(!form.reportValidity())return;
            await enviar('/api/v1/administracao/financeiro',{versao:d.versao,custos:F.ler(refs)},'PUT');
            if(ctx.atual())await ctx.recarregar();
        });
    });

    // Recuperação pública: códigos e senhas não vão para URL, armazenamento ou logs.
    const dialog=el(document.body,'dialog');dialog.id='painel-recuperacao';dialog.setAttribute('aria-labelledby','recuperacao-titulo');
    el(dialog,'h2','Recuperar acesso').id='recuperacao-titulo';
    const fechar=el(dialog,'button','Fechar recuperação');fechar.type='button';fechar.onclick=()=>dialog.close();
    const area=el(dialog,'div');let geracao=0;
    const login=document.getElementById('login-senha');
    const abrir=el(login.parentElement,'button','Recuperar acesso');abrir.type='button';
    dialog.addEventListener('close',()=>{geracao++;area.replaceChildren();abrir.focus();});
    abrir.onclick=()=>{
        const v=++geracao;area.replaceChildren();
        el(area,'p','Solicite ao administrador da sua empresa. Ele confere sua identidade e entrega um código em particular. Se nenhum administrador conseguir entrar, o responsável pelo servidor pode gerar o código pelo procedimento documentado.');
        const form=el(area,'form');form.onsubmit=e=>e.preventDefault();
        const email=campo(form,'email_recuperacao','E-mail da conta','email','',{required:'',maxlength:254});email.autocomplete='username';
        const st=status(area,'Informe o e-mail para solicitar ou preencha o código recebido e uma nova senha.');
        const codigo=campo(form,'codigo_recuperacao','Código recebido do administrador','text','',{minlength:20,maxlength:100});codigo.autocomplete='off';
        const senha=campo(form,'senha_recuperacao','Nova senha (15 a 256 caracteres)','password','',{minlength:15,maxlength:256});senha.autocomplete='new-password';
        const confirmarSenha=campo(form,'confirmacao_senha','Repita a nova senha','password','',{minlength:15,maxlength:256});confirmarSenha.autocomplete='new-password';
        let ocupado=false;
        function publico(label,path,body,validar){const b=el(area,'button',label);b.type='button';b.onclick=async()=>{
            if(ocupado||v!==geracao||!validar())return;
            ocupado=true;area.querySelectorAll('button').forEach(x=>x.disabled=true);st.textContent='Processando…';
            try{const r=await root.PainelSessao.request('/api/v1/administracao/recuperacao/'+path,{publico:true,method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body())});const d=await r.json();
                if(v!==geracao)return;st.textContent=d.mensagem;
                if(path==='concluir'){form.remove();area.querySelectorAll('button').forEach(x=>x.remove());}
            }catch(e){if(v===geracao&&!e?.silencioso)st.textContent=erro(e);}
            finally{ocupado=false;if(v===geracao)area.querySelectorAll('button').forEach(x=>x.disabled=false);}
        };}
        publico('Solicitar recuperação','solicitar',()=>({email:email.value}),()=>email.reportValidity());
        publico('Definir nova senha','concluir',()=>({email:email.value,codigo:codigo.value,senha:senha.value}),()=>{
            codigo.required=true;senha.required=true;confirmarSenha.required=true;
            if(!form.reportValidity())return false;
            if(senha.value!==confirmarSenha.value){st.textContent='As senhas precisam ser iguais.';return false;}return true;
        });
        dialog.showModal();email.focus();
    };
})(window);
