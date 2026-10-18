/* Ativação guiada usa os cadastros existentes; tempo e primeiro resultado vêm do servidor. */
(function(root){
 'use strict';
 const U=root.FluxoPainel,D=root.PortalDados;
 const abrirAba=aba=>{document.getElementById('portal-operacional').close();root.alternarAba(aba);};
 async function confirmar(id){
  return U.enviar('/onboarding/primeiro-resultado',{consulta_id:id});
 }
 async function render(p,ctx){
  const dados=await ctx.obter('/api/v1/painel/onboarding');if(!ctx.atual())return;
  U.el(p,'p','Prepare a empresa para a primeira análise. Os passos usam os mesmos cadastros, cálculos e permissões do painel.');
  const c=dados.cadastros,o=dados.onboarding;
  const resumo=U.el(p,'article');resumo.className='ux-onboarding-resumo';
  U.el(resumo,'h4',o?.primeiro_resultado_em?'Primeiro resultado registrado':o?'Configuração em andamento':'Comece a configuração do cliente');
  U.el(resumo,'p',o?'Início: '+D.data(o.iniciado_em):'A medição começa quando você iniciar; contas demonstrativas e cadastros existentes não comprovam uma ativação real.');
  if(o?.primeiro_resultado_em){
   U.el(resumo,'p','Primeira comparação confirmada: '+D.data(o.primeiro_resultado_em));
   U.el(resumo,'strong','Tempo até o primeiro resultado: '+Number(o.tempo_ate_primeiro_resultado_segundos).toLocaleString('pt-BR',{maximumFractionDigits:1})+' segundos');
   U.el(resumo,'p','Consulta vinculada: '+(o.consulta_id||'Não disponível por retenção do histórico.'));
  }else if(!o)U.botao(resumo,'Iniciar configuração do cliente',async()=>{await U.enviar('/onboarding/iniciar',{});if(ctx.atual())ctx.recarregar();},{escrita:true,valido:ctx.atual});
  const etapas=U.el(p,'ol');etapas.className='ux-etapas';
  function etapa(titulo,estado,descricao,acoes){
   const li=U.el(etapas,'li'),a=U.el(li,'article');U.el(a,'h4',titulo);const s=U.el(a,'span',estado);s.className='ux-etapa-estado';
   U.el(a,'p',descricao);for(const[label,fn]of acoes)U.botao(a,label,fn,{valido:ctx.atual});
  }
  etapa('Confira a empresa e os custos',c.financeiro?'Padrões cadastrados':'Conferência necessária','Empresa: '+dados.empresa+'. Confira os valores usados no cálculo; o cadastro não comprova que estejam corretos.',
   [['Conferir premissas financeiras',()=>root.PortalOperacional.navegar('financeiro')]]);
  etapa('Cadastre os caminhões',c.caminhoes+' cadastrado(s)','Informe medidas reais, peso com carga, eixos e consumo. Cadastro sem medidas não confirma passagem.',
   [['Abrir minha frota',()=>abrirAba('FROTA')]]);
  etapa('Defina o corredor',c.corredores+' ativo(s)','Cadastre origem, destino e, se necessário, a agenda recorrente da empresa.',
   [['Cadastrar corredores e recorrências',()=>root.PortalOperacional.navegar('corredores')]]);
  etapa('Prepare a primeira viagem',c.viagens+' cadastrada(s)','Despache uma viagem ou importe o arquivo JSON após conferir a prévia e tratar erros por item.',
   [['Importar rotas do cliente',()=>root.PortalOperacional.navegar('importacao')],['Abrir formulário de novo despacho',()=>{document.getElementById('portal-operacional').close();root.abrirModalDespacho();}]]);
  etapa('Confira e confirme o resultado',o?.primeiro_resultado_em?'Resultado confirmado':'Confirmação pendente','Abra uma viagem depois de iniciar. Confira fontes, rota e custos; use “Confirmar primeiro resultado útil” nos detalhes quando a comparação ajudar sua análise.',
   [['Consultar viagens',()=>abrirAba('URBANO')],['Abrir relatórios e exportações',()=>root.PortalOperacional.navegar('relatorios')]]);
  U.el(p,'p',dados.criterio);
  if(!root.PainelSessao.podeEscrever())U.el(p,'p','Seu perfil permite acompanhar as etapas. Iniciar e confirmar a configuração exige OPERATOR ou ADMIN.');
 }
 root.PainelOnboarding={render,confirmar};
 root.PortalOperacional.registrarSecao('onboarding','Configurar primeiro cliente',render);
})(window);
