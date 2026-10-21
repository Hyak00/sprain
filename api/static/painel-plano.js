/* Leitura das cotas já publicadas pelo backend; sem editar contratos ou preços. */
(function (root) {
  "use strict";
  const U = root.FluxoPainel,
    D = root.PortalDados;
  async function render(p, ctx) {
    if (root.PainelSessao.perfil() !== "ADMIN") {
      U.el(
        p,
        "p",
        "Somente administradores podem consultar o plano e o consumo da empresa.",
      );
      return;
    }
    const d = await ctx.obter("/api/v1/operacional/plano");
    if (!ctx.atual()) return;
    const a = d.assinatura;
    U.el(p, "h4", a?.nome || "Assinatura não configurada");
    U.el(
      p,
      "p",
      "Empresa: " +
        d.empresa +
        " · Período: " +
        d.periodo +
        " · Fuso: " +
        d.fuso_periodo,
    );
    if (a) {
      U.el(
        p,
        "p",
        "Situação registrada: " +
          a.status_registrado +
          " · Atualização: " +
          D.data(a.atualizado_em),
      );
    }
    const t = U.el(p, "table"),
      head = U.el(U.el(t, "thead"), "tr");
    U.el(t, "caption", "Uso e limites retornados pelo servidor");
    for (const s of ["Recurso", "Uso observado", "Limite configurado"])
      U.el(head, "th", s).scope = "col";
    const body = U.el(t, "tbody");
    for (const [k, nome] of [
      ["usuarios_ativos", "Usuários ativos"],
      ["corredores_ativos", "Corredores ativos"],
      ["consultas_mes", "Consultas no mês"],
      ["chamadas_externas_mes", "Chamadas externas no mês"],
    ]) {
      const tr = U.el(body, "tr");
      U.el(tr, "th", nome).scope = "row";
      U.el(
        tr,
        "td",
        typeof d.uso?.[k] === "number" ? String(d.uso[k]) : "Não medido",
      );
      U.el(
        tr,
        "td",
        typeof a?.limites?.[k] === "number"
          ? String(a.limites[k])
          : "Não definido",
      );
    }
    U.el(
      p,
      "p",
      "As cotas cadastradas e as permissões são verificadas no servidor. Dados não medidos não significam consumo zero.",
    );
    U.el(
      p,
      "p",
      "Custo de servir: " +
        D.moeda(d.uso?.custo_servir_brl) +
        ". Esta tela não altera a assinatura nem efetua cobrança.",
    );
    U.botao(p, "Atualizar plano e consumo", () => ctx.recarregar(), {
      valido: ctx.atual,
    });
  }
  root.PortalOperacional.registrarSecao("plano", "Plano e consumo", render);
  document.querySelector('[data-secao="plano"]').setAttribute("data-admin", "");
})(window);
