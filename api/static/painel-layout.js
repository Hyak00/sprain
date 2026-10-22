/* Navegação por páginas e detalhes por abas. Reutiliza os nós e contratos existentes. */
(function (root) {
  "use strict";
  const U = root.FluxoPainel,
    D = root.PortalDados,
    E = root.PainelExperiencia;
  const $ = (s) => document.querySelector(s);
  const rail = $("#ux-navegacao"),
    antigo = $("#ux-menu-conteudo");
  const portal = $("#portal-operacional"),
    navPortal = portal.querySelector("nav");
  const workspace = $(".workspace"),
    inspector = $("#inspector");
  const apoio = U.el(document.body, "div");
  apoio.id = "ux-apoio";
  apoio.hidden = true;
  let usuario = null,
    operacaoAtual = null,
    ultimaAba = "URBANO",
    abaDetalhe = "resumo";
  let secundarios = [],
    focoRetorno = null,
    recalculo = null,
    sequenciaRecalculo = 0;
  antigo.hidden = true;
  antigo.removeAttribute("aria-label");
  antigo.id = "ux-atalhos-anteriores";
  const nav = U.el(rail, "nav");
  nav.id = "ux-menu-conteudo";
  nav.setAttribute("aria-label", "Navegação principal");
  navPortal.setAttribute("role", "group");
  navPortal.setAttribute("aria-label", "Páginas do painel");
  const pequenos = root.matchMedia("(max-width:900px)");
  const menu = $("#ux-menu");
  function recolher() {
    if (pequenos.matches) {
      nav.hidden = true;
      menu.setAttribute("aria-expanded", "false");
    }
  }
  function ajustar() {
    antigo.hidden = true;
    nav.hidden = pequenos.matches;
    menu.setAttribute("aria-expanded", String(!nav.hidden));
    root.dispatchEvent(new root.Event("resize"));
  }
  menu.onclick = () => {
    nav.hidden = !nav.hidden;
    menu.setAttribute("aria-expanded", String(!nav.hidden));
  };
  pequenos.addEventListener("change", ajustar);
  rail.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && pequenos.matches) {
      recolher();
      menu.focus();
    }
  });
  const bases = ["tab-urbano", "tab-frota", "tab-corredor"].map((id) =>
    document.getElementById(id),
  );
  bases.forEach((b) => b.addEventListener("click", recolher));
  const marca = $(".ux-marca");
  marca.textContent = "SPRain";
  $(".brand-title").textContent = "Painel operacional";
  const empresa = antigo.querySelector(".ux-empresa");
  empresa.className = "ux-empresa";
  rail.appendChild(empresa);
  const central = $('.top-controls [aria-haspopup="dialog"]');
  central.textContent = "Minha empresa";
  central.removeAttribute("aria-haspopup");
  central.onclick = () => root.PortalOperacional.navegar("configuracao");

  const cab = U.el(document.body, "section");
  cab.className = "ux-cabecalho-pagina";
  cab.hidden = true;
  workspace.before(cab);
  const titulos = U.el(cab, "div"),
    titulo = U.el(titulos, "h1", "Viagens"),
    subtitulo = U.el(
      titulos,
      "p",
      "Acompanhe a operação e tome decisões com os dados disponíveis.",
    );
  const acoes = U.el(cab, "div");
  acoes.className = "ux-acoes-pagina";
  for (const seletor of [
    '[data-acao="abrirModalDespacho"]',
    '[data-acao="abrirModalManifesto"]',
    '[data-acao="exportarCsv"]',
  ]) {
    const b = document.querySelector(seletor);
    if (b) acoes.appendChild(b);
  }
  const chamada = $(".ux-atencao"),
    indicador = chamada.querySelector('[role="status"]');
  const visao = U.el(document.body, "section");
  visao.className = "ux-visao-geral";
  visao.hidden = true;
  cab.after(visao);
  const fluxo = U.el(document.body, "nav");
  fluxo.id = "ux-fluxo-viagem";
  fluxo.hidden = true;
  fluxo.setAttribute("aria-label", "Passos da análise da viagem");
  visao.after(fluxo);
  const passos = new Map();
  for (const [id, texto] of [
    ["selecionar", "Selecionar viagem"],
    ["alertas", "Entender alertas"],
    ["custos", "Comparar rotas"],
    ["decisao", "Registrar decisão"],
  ]) {
    const b = U.el(fluxo, "button");
    b.type = "button";
    b.setAttribute("aria-label", "Etapa " + (passos.size + 1) + ": " + texto);
    U.el(b, "span", String(passos.size + 1)).setAttribute("aria-hidden", "true");
    U.el(b, "strong", texto);
    b.dataset.passo = id;
    b.onclick = () => {
      if (id === "selecionar") {
        const fechando = comparacao.open;
        focoRetorno = fechando ? $(".search-box") : null;
        voltarOperacoes();
        if (!fechando) $(".search-box").focus();
      } else abrirComparacao(id);
    };
    passos.set(id, b);
  }
  function atualizarPassos() {
    fluxo.hidden = !usuario || !["URBANO", "VIAGEM"].includes(document.body.dataset.area);
    const atual = document.body.dataset.area === "VIAGEM"
      ? (["decisao", "alertas"].includes(abaDetalhe) ? abaDetalhe : "custos")
      : "selecionar";
    passos.forEach((b, id) => {
      b.disabled = id !== "selecionar" && (!operacaoAtual || comparar.disabled || !!recalculo);
      if (id === atual) b.setAttribute("aria-current", "step");
      else b.removeAttribute("aria-current");
    });
  }
  visao.appendChild($(".kpi-grid"));
  const situacao = U.el(visao, "div");
  situacao.className = "ux-situacao";
  situacao.appendChild(indicador);
  const atualizar = chamada.querySelector("button");
  if (atualizar) situacao.appendChild(atualizar);
  chamada.hidden = true;
  const simulacao = $(".ux-simulacao");
  apoio.appendChild(simulacao);
  const orientacao = chamada.querySelector("details");
  if (orientacao) apoio.appendChild(orientacao);
  const manifesto = $("#modal-manifesto"),
    cardManifesto = manifesto.querySelector(".despacho-card");
  function guardarPaineis() {
    if (cardManifesto.parentElement !== manifesto) {
      const pendente = root.PainelManifesto.emAndamento();
      root.PainelManifesto.resetar();
      manifesto.appendChild(cardManifesto);
      if (pendente && usuario)
        root.PainelSessao.aviso(
          "A importação pode continuar no servidor. Confira as viagens antes de reenviar o arquivo.",
        );
    }
    if (simulacao.parentElement !== apoio) apoio.appendChild(simulacao);
  }
  root.PortalOperacional.registrarSecao(
    "manifesto",
    "Importar viagens (CSV)",
    (p) => {
      root.PainelManifesto.resetar();
      p.appendChild(cardManifesto);
      if (!root.PainelSessao.podeEscrever()) {
        U.el(
          p,
          "p",
          "Seu perfil permite consultar. A importação exige permissão de operador ou administrador.",
        ).className = "ux-nota";
        cardManifesto
          .querySelectorAll("input,button")
          .forEach((b) => (b.disabled = true));
      } else
        cardManifesto
          .querySelectorAll("input,button")
          .forEach((b) => (b.disabled = false));
      $("#btn-confirmar-manifesto").disabled = true;
      const json = U.el(p, "button", "Importar arquivo JSON");
      json.type = "button";
      json.onclick = () => root.PortalOperacional.navegar("importacao");
    },
  );
  root.PortalOperacional.registrarSecao(
    "simulacao",
    "Simulação de chuva",
    (p) => {
      U.el(
        p,
        "p",
        "Defina um cenário para comparar o efeito da chuva. A simulação não representa uma medição em tempo real.",
      ).className = "ux-nota";
      p.appendChild(simulacao);
      expandir(simulacao);
      const voltar = U.el(p, "button", "Ver viagens no mapa");
      voltar.type = "button";
      voltar.onclick = voltarOperacoes;
    },
  );
  const rotulosCurtos = {
    plano: "Plano e consumo",
    relatorios: "Relatórios",
    qualidade: "Fontes e serviços",
    importacao: "Importação JSON",
    configuracao: "Minha empresa",
    demonstracao: "Demonstração",
    ajuda: "Guia de uso",
    consultas: "Histórico",
    corredores: "Corredores",
    relatos: "Reportar ocorrência",
    administracao: "Equipe e acesso",
    financeiro: "Custos da empresa",
    onboarding: "Primeiro cliente",
    interno: "Operação interna",
    manifesto: "Importar viagens",
    simulacao: "Simulação de chuva",
  };
  const grupos = [
    [
      "OPERAÇÃO",
      ["tab-urbano", "manifesto", "corredores", "tab-frota", "tab-corredor"],
    ],
    [
      "ANÁLISE",
      ["relatorios", "consultas", "relatos", "qualidade", "simulacao"],
    ],
    [
      "EMPRESA",
      ["financeiro", "plano", "administracao", "onboarding", "configuracao"],
    ],
    ["APOIO", ["demonstracao", "ajuda", "interno"]],
  ];
  const atalhos = new Map();
  function montarNavegacao() {
    nav.replaceChildren();
    atalhos.clear();
    grupos.forEach(([nome, ids]) => {
      const g = U.el(nav, "div");
      g.className = "ux-grupo-nav";
      U.el(g, "p", nome);
      ids.forEach((id) => {
        const b = id.startsWith("tab-")
          ? document.getElementById(id)
          : navPortal.querySelector('[data-secao="' + id + '"]');
        if (!b) return;
        const label = b.getAttribute("aria-label") || b.textContent;
        b.setAttribute("aria-label", label);
        b.textContent =
          rotulosCurtos[id] ||
          (id === "tab-urbano"
            ? "Viagens"
            : id === "tab-frota"
              ? "Frota"
              : "Corredor de referência");
        b.dataset.pagina = id;
        if (!id.startsWith("tab-"))
          b.onclick = () => root.PortalOperacional.navegar(id);
        b.addEventListener("click", recolher);
        g.appendChild(b);
        atalhos.set(id, b);
      });
    });
    // Importação JSON permanece acessível na página de importação CSV; registro original conservado.
    apoio.appendChild(navPortal);
    apoio.appendChild(central);
  }
  montarNavegacao();
  function marcar(id) {
    atalhos.forEach((b, k) => {
      if (k === id) b.setAttribute("aria-current", "page");
      else b.removeAttribute("aria-current");
    });
  }
  const textos = {
    plano: [
      "Plano e consumo",
      "Confira os limites e o uso observado da empresa.",
    ],
    relatorios: [
      "Relatórios",
      "Consulte os resultados do piloto e compartilhe os dados da empresa.",
    ],
    corredores: ["Corredores", "Organize percursos, recorrências e despachos."],
    manifesto: [
      "Importar viagens",
      "Envie o manifesto, confira a prévia e confirme a importação.",
    ],
    consultas: [
      "Histórico",
      "Reabra consultas e decisões com a fotografia dos dados usados.",
    ],
    qualidade: [
      "Fontes e serviços",
      "Confira atualização, cobertura e disponibilidade dos dados.",
    ],
    relatos: [
      "Reportar ocorrência",
      "Registre o que foi observado ou informe um alerta incorreto.",
    ],
    financeiro: [
      "Custos da empresa",
      "Confira e ajuste as premissas financeiras.",
    ],
    administracao: [
      "Equipe e acesso",
      "Gerencie usuários, papéis e recuperação de acesso.",
    ],
    onboarding: [
      "Primeiro cliente",
      "Prepare a empresa para a primeira análise.",
    ],
    simulacao: [
      "Simulação de chuva",
      "Compare um cenário sem confundi-lo com observação meteorológica.",
    ],
    configuracao: [
      "Minha empresa",
      "Consulte a sessão e as configurações da empresa.",
    ],
    demonstracao: [
      "Demonstração",
      "Apresente um cenário separado da operação real.",
    ],
    ajuda: [
      "Guia de uso",
      "Entenda os passos e a leitura dos dados do painel.",
    ],
    interno: ["Operação interna", "Acompanhe fontes, importações e serviços."],
  };
  function cabecalho(nome, descricao, operacoes) {
    titulo.textContent = nome;
    subtitulo.textContent = descricao;
    acoes.hidden = !operacoes;
    visao.hidden = !operacoes;
  }
  function modo(nome) {
    document.body.dataset.area = nome;
    atualizarPassos();
    root.scrollTo({ top: 0, behavior: "instant" });
    root.dispatchEvent(new root.Event("resize"));
  }
  function voltarOperacoes() {
    if (portal.open) portal.close();
    if (comparacao.open) comparacao.close();
    root.alternarAba("URBANO");
  }

  // A seleção no mapa oferece acesso direto aos seis assuntos da viagem.
  const resumo = U.el($("#map-container"), "article");
  resumo.id = "ux-rota-resumo";
  resumo.hidden = true;
  resumo.setAttribute("aria-label", "Viagem selecionada");
  const codigo = U.el(resumo, "p");
  codigo.className = "ux-sobretitulo";
  const nome = U.el(resumo, "h2");
  const mensagem = U.el(resumo, "p");
  mensagem.setAttribute("role", "status");
  const natureza = U.el(resumo, "p");
  natureza.className = "ux-natureza";
  const atalhosRota = U.el(resumo, "div");
  atalhosRota.className = "ux-atalhos-rota";
  const comparar = U.el(atalhosRota, "button", "Comparar rotas");
  comparar.type = "button";
  comparar.className = "ux-primario";
  comparar.disabled = true;
  const comparacao = U.el(document.body, "dialog");
  comparacao.id = "ux-comparar";
  comparacao.setAttribute("role", "region");
  comparacao.setAttribute("aria-label", "Detalhes da viagem");
  const voltar = U.el(comparacao, "button", "← Voltar às viagens");
  voltar.type = "button";
  voltar.className = "ux-voltar";
  voltar.onclick = () => comparacao.close();
  const status = U.status(comparacao, "");
  status.className = "ux-carga-comparacao";
  comparacao.appendChild(inspector);
  const head = inspector.querySelector(".insp-header");
  head.querySelector("button").onclick = () => comparacao.close();
  const tabs = U.el(inspector, "div");
  tabs.className = "ux-abas-viagem";
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", "Detalhes da viagem");
  const painels = {},
    botoes = {};
  const orientacoes = {
    resumo: "Confira a recomendação e as medidas da viagem. Depois examine os alertas e suas fontes.",
    restricoes: "Confira o caminhão, as tarifas e os limites conhecidos. Informação ausente não confirma passagem.",
    postos: "Confira localização, fonte e data da coleta. Preço histórico não é preço garantido no posto.",
    custos: "Compare distância, tempo e custos das duas rotas. As premissas e o recálculo ficam logo abaixo.",
    alertas: "Confira o que foi detectado, a fonte, a validade e as limitações antes de comparar as opções.",
    decisao: "Registre a escolha e o motivo. Depois da viagem, informe o resultado observado nesta mesma página.",
  };
  const secoes = [
    ["resumo", "Resumo"],
    ["restricoes", "Pedágios e pontes"],
    ["postos", "Postos e histórico"],
    ["custos", "Custos e recálculo"],
    ["alertas", "Alertas e fontes"],
    ["decisao", "Decisão"],
  ];
  secoes.forEach(([id, label], i) => {
    const b = U.el(tabs, "button", label);
    b.type = "button";
    b.id = "ux-aba-" + id;
    b.setAttribute("role", "tab");
    b.setAttribute("aria-controls", "ux-painel-" + id);
    b.onclick = () => escolherAba(id);
    botoes[id] = b;
    b.onkeydown = (e) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
      e.preventDefault();
      const n =
        e.key === "Home"
          ? 0
          : e.key === "End"
            ? secoes.length - 1
            : (i + (e.key === "ArrowRight" ? 1 : -1) + secoes.length) %
              secoes.length;
      escolherAba(secoes[n][0]);
      botoes[secoes[n][0]].focus();
    };
    const p = U.el(inspector, "section");
    p.id = "ux-painel-" + id;
    p.setAttribute("role", "tabpanel");
    p.setAttribute("aria-labelledby", b.id);
    painels[id] = p;
    U.el(p, "p", orientacoes[id]).className = "ux-orientacao-aba";
  });
  function dono(no) {
    while (no && no.parentElement !== inspector) no = no.parentElement;
    return no;
  }
  const move = (no, id) => {
    if (no) painels[id].appendChild(no);
  };
  move(dono($("#input-motivo-gestor")), "decisao");
  move($("#infra-auditoria"), "restricoes");
  // O módulo de postos cria uma caixa persistente, vazia antes da primeira consulta.
  const postos = Array.from(inspector.children).find(
    (n) => n.tagName === "DETAILS" && n.classList.contains("infra-complemento"),
  );
  move(postos, "postos");
  move(inspector.querySelector(".ux-comparacao"), "custos");
  move(inspector.querySelector(".mvp-complemento"), "custos");
  move(dono($("#modal-trechos-lista")), "alertas");
  const detalhesFinanceiros = inspector.querySelector(".ac-painel");
  if (detalhesFinanceiros) apoio.appendChild(detalhesFinanceiros);
  for (const no of Array.from(inspector.children))
    if (no !== head && no !== tabs && !Object.values(painels).includes(no))
      move(no, "resumo");
  function expandir(p) {
    const ds = [
      ...(p.tagName === "DETAILS" ? [p] : []),
      ...p.querySelectorAll("details"),
    ];
    ds.forEach((d) => {
      if (
        d.querySelector("summary")?.textContent.includes("Fotografia integral")
      )
        return;
      d.open = true;
      d.classList.add("ux-detalhe-aberto");
      const s = d.querySelector(":scope > summary");
      if (s) {
        s.onclick = (e) => e.preventDefault();
        s.onkeydown = (e) => {
          if (e.key === "Enter" || e.key === " ") e.preventDefault();
        };
      }
    });
  }
  function iniciarRecalculo() {
    const token = ++sequenciaRecalculo;
    recalculo = token;
    Object.values(botoes).forEach((b) => (b.disabled = true));
    comparacao.setAttribute("aria-busy", "true");
    status.textContent =
      "Salvando premissas e recalculando a viagem. Aguarde para comparar e decidir.";
    atualizarPassos();
    return token;
  }
  function finalizarRecalculo(token) {
    if (token !== recalculo) return;
    recalculo = null;
    Object.values(botoes).forEach((b) => (b.disabled = false));
    comparacao.removeAttribute("aria-busy");
    status.textContent = "";
    atualizarPassos();
  }
  function escolherAba(id) {
    abaDetalhe = id;
    Object.keys(painels).forEach((k) => {
      painels[k].hidden = k !== id;
      botoes[k].setAttribute("aria-selected", String(k === id));
      botoes[k].tabIndex = k === id ? 0 : -1;
    });
    expandir(painels[id]);
    if (id === "decisao" && operacaoAtual)
      root.ResultadosViagem.exibir(painels.decisao, operacaoAtual.id_operacao);
    atualizarPassos();
  }
  function abrirComparacao(id = "resumo") {
    if (comparar.disabled || !operacaoAtual) return;
    if (portal.open) portal.close();
    if (
      !Array.from(inspector.querySelectorAll("summary")).some(
        (s) => s.textContent === "Postos, historico e atualizacao dos dados",
      )
    )
      root.DadosViagem.exibir([
        operacaoAtual.geometrias?.rota_original_geojson,
        operacaoAtual.geometrias?.rota_alternativa_geojson,
      ]);
    escolherAba(id);
    comparacao.show();
    modo("VIAGEM");
    cabecalho("Detalhes da viagem", codigo.textContent, false);
    marcar("tab-urbano");
    comparacao.scrollTop = 0;
    botoes[id].focus();
  }
  comparar.onclick = () => abrirComparacao();
  for (const [id, label] of [
    ["restricoes", "Pedágios e pontes"],
    ["decisao", "Registrar decisão"],
  ]) {
    const b = U.el(atalhosRota, "button", label);
    b.type = "button";
    b.dataset.detalhe = id;
    b.onclick = () => abrirComparacao(id);
  }
  comparacao.addEventListener("close", () => {
    if (comparacao.open || portal.open) return;
    exibirBase(ultimaAba);
    const alvo = focoRetorno;
    focoRetorno = null;
    if (usuario && alvo) alvo.focus();
    else if (usuario && !comparar.disabled) comparar.focus();
  });
  comparacao.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      comparacao.close();
    }
  });

  const anteriorSelecionar = E.selecionar;
  E.selecionar = (op) => {
    root.ResultadosViagem.limpar();
    operacaoAtual = op;
    anteriorSelecionar(op);
    inspector.hidden = false;
    comparar.disabled = false;
    resumo.hidden = false;
    status.textContent = "";
    comparacao.removeAttribute("aria-busy");
    codigo.textContent =
      op.id_operacao + " · " + (op.id_veiculo || "Caminhão não informado");
    nome.textContent =
      op.coordenadas?.origem_nome && op.coordenadas?.destino_nome
        ? op.coordenadas.origem_nome + " → " + op.coordenadas.destino_nome
        : "Viagem selecionada";
    mensagem.textContent =
      op.justificativa ||
      "Justificativa não informada. Confira os detalhes antes de decidir.";
    const c = op.contexto_consulta || {};
    natureza.textContent =
      (c.natureza || "Natureza não informada") +
      " · Cálculo: " +
      D.data(c.calculo_gerado_em);
    secundarios.forEach((n) => n.remove());
    secundarios = [];
    if (detalhesFinanceiros)
      for (const d of Array.from(detalhesFinanceiros.children)) {
        const k = d
          .querySelector("summary")
          ?.textContent.startsWith("Comparação")
          ? "custos"
          : "alertas";
        move(d, k);
        secundarios.push(d);
      }
    escolherAba(abaDetalhe);
    atualizarPassos();
  };
  function limparSelecao() {
    root.ResultadosViagem.limpar();
    operacaoAtual = null;
    comparar.disabled = true;
    resumo.hidden = true;
    codigo.textContent = "";
    nome.textContent = "";
    mensagem.textContent = "";
    natureza.textContent = "";
    status.textContent = "";
    secundarios.forEach((n) => n.remove());
    secundarios = [];
    atualizarPassos();
  }
  function carregando(id) {
    resumo.hidden = false;
    comparar.disabled = true;
    atualizarPassos();
    codigo.textContent = id;
    nome.textContent = "Consultando viagem…";
    mensagem.textContent = "Carregando rotas, fontes e custos.";
    if (comparacao.open) {
      inspector.hidden = true;
      status.textContent = "Atualizando a viagem…";
      comparacao.setAttribute("aria-busy", "true");
    }
  }
  function erro() {
    inspector.hidden = true;
    comparar.disabled = true;
    atualizarPassos();
    resumo.hidden = false;
    nome.textContent = "Consulta indisponível";
    mensagem.textContent =
      "Selecione a viagem novamente para tentar. A comparação anterior não é reutilizada.";
    status.textContent = mensagem.textContent;
    comparacao.removeAttribute("aria-busy");
  }

  function exibirBase(tipo) {
    ultimaAba = tipo;
    modo(tipo);
    marcar(
      tipo === "FROTA"
        ? "tab-frota"
        : tipo === "CORREDOR"
          ? "tab-corredor"
          : "tab-urbano",
    );
    cabecalho(
      tipo === "FROTA"
        ? "Frota"
        : tipo === "CORREDOR"
          ? "Corredor de referência"
          : "Viagens",
      tipo === "FROTA"
        ? "Cadastre os veículos e mantenha medidas e custos atualizados."
        : tipo === "CORREDOR"
          ? "Consulte o cenário regional, custos e limitações."
          : "Acompanhe a operação e tome decisões com os dados disponíveis.",
      tipo === "URBANO",
    );
  }
  const anteriorAba = E.aba;
  E.aba = (tipo) => {
    concluirMapa();
    if (portal.open) portal.close();
    if (comparacao.open) comparacao.close();
    anteriorAba(tipo);
    exibirBase(tipo);
  };
  E.secao = (id) => {
    guardarPaineis();
    if (comparacao.open) comparacao.close();
    modo("PAGINA");
    marcar(id === "importacao" ? "manifesto" : id);
    const t = textos[id] || [id, ""];
    cabecalho(t[0], t[1], false);
    $("#portal-titulo").textContent = t[0];
  };
  portal.setAttribute("role", "region");
  portal.setAttribute("aria-label", "Página do painel");
  portal.querySelector(".portal-cab button").textContent =
    "← Voltar às viagens";
  portal.addEventListener("close", () => {
    if (portal.open) return;
    guardarPaineis();
    if (!comparacao.open && usuario) exibirBase(ultimaAba);
  });
  portal.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      portal.close();
    }
  });
  const anteriorSessao = E.sessao,
    anteriorLimpar = E.limpar;
  E.sessao = (user) => {
    usuario = user;
    anteriorSessao(user);
    cab.hidden = false;
    E.aba("URBANO");
    ajustar();
  };
  E.limpar = () => {
    finalizarRecalculo(recalculo);
    usuario = null;
    focoRetorno = null;
    comparacao.close();
    if (portal.open) portal.close();
    guardarPaineis();
    root.PainelManifesto.resetar();
    limparSelecao();
    cab.hidden = true;
    visao.hidden = true;
    document.body.classList.remove("ux-escolhendo-mapa");
    anteriorLimpar();
  };
  const voltarFrota = U.el(
    $("#map-container"),
    "button",
    "Concluir escolha no mapa",
  );
  voltarFrota.id = "ux-voltar-frota";
  voltarFrota.type = "button";
  voltarFrota.onclick = concluirMapa;
  function concluirMapa() {
    root.CadastroInfra.cancelarEscolha?.();
    document.body.classList.remove("ux-escolhendo-mapa");
    root.dispatchEvent(new root.Event("resize"));
  }
  root.PainelLayout = {
    iniciarRecalculo,
    finalizarRecalculo,
    carregando,
    erro,
    limparSelecao,
    abrirManifesto: () => root.PortalOperacional.navegar("manifesto"),
    fecharManifesto: voltarOperacoes,
    escolherMapa: () => {
      document.body.classList.add("ux-escolhendo-mapa");
      root.dispatchEvent(new root.Event("resize"));
      $("#map-container").scrollIntoView({ block: "nearest" });
    },
    concluirMapa,
  };
  // Os campos originais continuam com os mesmos IDs e handlers.
  const cadastro = $("#frota-panel .panel-card");
  for (const [id, texto] of [
    ["veic-id", "Identificação do caminhão"],
    ["veic-placa", "Placa"],
    ["veic-modelo", "Modelo"],
    ["veic-tipo", "Tipo de caminhão"],
  ]) {
    const campo = document.getElementById(id),
      label = document.createElement("label");
    label.className = "ux-campo-frota";
    label.textContent = texto;
    campo.before(label);
    label.appendChild(campo);
  }
  const salvarFrota = cadastro.querySelector(
    '[data-acao="cadastrarNovoCaminhao"]',
  );
  $("#infra-veic").after(salvarFrota, $("#veic-feedback"));
  const legenda = $(".map-legend>details");
  if (legenda) {
    legenda.open = true;
    legenda.classList.add("ux-legenda-aberta");
  }
  const zona = $("#drop-zone-manifesto");
  zona.setAttribute("role", "button");
  zona.setAttribute("tabindex", "0");
  zona.setAttribute("aria-label", "Selecionar manifesto CSV");
  zona.onkeydown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (root.PainelSessao.podeEscrever()) $("#manifesto-file-input").click();
    }
  };
  escolherAba("resumo");
  ajustar();
})(window);
