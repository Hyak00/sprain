/* Execução declarada pelo cliente. Usa o histórico e a correção do contrato existente. */
(function (root) {
  "use strict";
  const U = root.FluxoPainel,
    D = root.PortalDados;
  let geracao = 0,
    controle,
    caixa;
  const gravacoes = new Set();
  const rotas = {
    ORIGINAL: "Rota original",
    DESVIO: "Desvio",
    OUTRA: "Outra rota",
    NAO_INFORMADA: "Não informada",
  };
  const fontes = {
    RELATO_OPERADOR: "Relato do operador",
    TELEMETRIA: "Telemetria",
    DOCUMENTO: "Documento",
  };
  function limpar() {
    geracao++;
    controle?.abort();
    caixa?.replaceChildren();
  }
  function horarioLocal(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
  }
  async function exibir(parent, operacao) {
    limpar();
    if (!caixa || caixa.parentElement !== parent) {
      caixa?.remove();
      caixa = U.el(parent, "section");
      caixa.className = "ux-resultados";
      caixa.setAttribute("role", "region");
      caixa.setAttribute("aria-label", "Resultado informado da viagem");
    }
    const n = geracao,
      vigente = () => n === geracao && !!root.PainelSessao.perfil();
    controle = new AbortController();
    const sinal = controle.signal;
    const url =
      "/api/v1/logistica/operacoes/" +
      encodeURIComponent(operacao) +
      "/resultados-viagem";
    U.el(caixa, "h3", "Resultado da viagem");
    U.el(
      caixa,
      "p",
      "Depois da execução, informe o que aconteceu. Medidas e fontes são autodeclaradas, sem verificação de documentos; não comprovam economia.",
    );
    const aviso = U.status(caixa, "Carregando o histórico informado…");
    const atual = U.el(caixa, "div"),
      formulario = U.el(caixa, "div"),
      historico = U.el(caixa, "div");
    let ultimo = null,
      carregado = false,
      offset = 0,
      pagina = 0;
    const valor = (v, unidade) =>
      v === null || v === undefined ? "Não informado" : String(v) + unidade;
    function registro(p, r) {
      U.el(
        p,
        "p",
        "Conclusão: " +
          D.data(r.finalizada_em) +
          " · " +
          (rotas[r.rota_executada] || "Não informada"),
      );
      U.el(
        p,
        "p",
        "Duração: " +
          valor(r.duracao_real_min, " min") +
          " · Distância: " +
          valor(r.distancia_real_km, " km") +
          " · Custo informado: " +
          D.moeda(r.custo_real_brl),
      );
      U.el(
        p,
        "p",
        "Fonte declarada: " +
          (fontes[r.fonte] || "Não informada") +
          " · Registro: " +
          D.data(r.registrada_em),
      );
      U.el(
        p,
        "p",
        "Referência: " +
          (r.referencia_evidencia || "Não informada") +
          " · Decisão vinculada: " +
          (r.id_decisao ?? "Sem vínculo"),
      );
      U.el(p, "p", "Observações: " + (r.observacoes || "Não informadas"));
      U.el(
        p,
        "p",
        "Registro " +
          r.id +
          (r.substitui_id ? " · Corrige " + r.substitui_id : "") +
          " · Usuário: " +
          (r.usuario_id || "Credencial sem identidade individual"),
      );
    }
    function editar() {
      if (!vigente() || !carregado || !root.PainelSessao.podeEscrever()) return;
      formulario.replaceChildren();
      U.el(
        formulario,
        "h4",
        ultimo ? "Corrigir resultado atual" : "Informar execução",
      );
      U.el(
        formulario,
        "p",
        ultimo
          ? "A correção cria um novo registro e preserva o anterior. Confira todos os campos antes de salvar."
          : "Informe a conclusão e ao menos uma medida. Em branco significa desconhecido; zero é um valor informado.",
      );
      const form = U.el(formulario, "form");
      form.onsubmit = (e) => e.preventDefault();
      const refs = {};
      refs.finalizada_em = U.campo(
        form,
        "finalizada_em",
        "Conclusão da viagem (horário do seu navegador)",
        "datetime-local",
        horarioLocal(ultimo?.finalizada_em),
        { required: "" },
      );
      function selecao(nome, label, opcoes, padrao) {
        const l = U.el(form, "label", label),
          s = U.el(l, "select");
        s.name = nome;
        s.setAttribute("aria-label", label);
        for (const [k, texto] of Object.entries(opcoes))
          U.el(s, "option", texto).value = k;
        s.value = ultimo?.[nome] || padrao;
        refs[nome] = s;
      }
      selecao(
        "rota_executada",
        "Rota efetivamente percorrida",
        rotas,
        "NAO_INFORMADA",
      );
      for (const [k, label, max] of [
        ["duracao_real_min", "Duração informada (min)", 1000000],
        ["distancia_real_km", "Distância informada (km)", 1000000],
        ["custo_real_brl", "Custo informado (R$)", 1000000000],
      ]) {
        refs[k] = U.campo(form, k, label, "number", ultimo?.[k] ?? "", {
          min: 0,
          max,
          step: "0.01",
        });
      }
      selecao("fonte", "Fonte do resultado", fontes, "RELATO_OPERADOR");
      refs.referencia_evidencia = U.campo(
        form,
        "referencia_evidencia",
        "Referência da evidência (obrigatória para documento)",
        "text",
        ultimo?.referencia_evidencia ?? "",
        { maxlength: 200 },
      );
      refs.id_decisao = U.campo(
        form,
        "id_decisao",
        "Número da decisão vinculada (opcional)",
        "number",
        ultimo?.id_decisao ?? "",
        { min: 1, max: Number.MAX_SAFE_INTEGER, step: 1 },
      );
      const label = U.el(form, "label", "Observações sobre a execução"),
        obs = U.el(label, "textarea");
      obs.name = "observacoes";
      obs.maxLength = 1000;
      obs.value = ultimo?.observacoes ?? "";
      refs.observacoes = obs;
      const feedback = U.status(
        formulario,
        gravacoes.has(operacao)
          ? "Existe um envio em andamento. Consulte o histórico antes de tentar novamente."
          : "Nenhum registro é enviado antes da confirmação.",
      );
      const salvar = U.botao(
        formulario,
        ultimo ? "Salvar correção do resultado" : "Salvar resultado da viagem",
        async () => {
          if (
            !vigente() ||
            gravacoes.has(operacao) ||
            !root.PainelSessao.podeEscrever() ||
            !form.reportValidity()
          )
            return;
          const data = new Date(refs.finalizada_em.value);
          if (!Number.isFinite(data.getTime()) || data.getTime() > Date.now()) {
            feedback.textContent =
              "Informe uma conclusão válida, sem data futura.";
            return;
          }
          const medidas = [
            "duracao_real_min",
            "distancia_real_km",
            "custo_real_brl",
          ];
          if (!medidas.some((k) => refs[k].value !== "")) {
            feedback.textContent =
              "Informe ao menos duração, distância ou custo da viagem.";
            return;
          }
          if (
            refs.fonte.value === "DOCUMENTO" &&
            !refs.referencia_evidencia.value.trim()
          ) {
            feedback.textContent = "Informe a referência do documento.";
            return;
          }
          const body = {
            finalizada_em: data.toISOString(),
            rota_executada: refs.rota_executada.value,
            fonte: refs.fonte.value,
            substitui_id: ultimo?.id ?? null,
          };
          for (const k of medidas)
            body[k] = refs[k].value === "" ? null : refs[k].value;
          body.id_decisao =
            refs.id_decisao.value === "" ? null : Number(refs.id_decisao.value);
          body.referencia_evidencia =
            refs.referencia_evidencia.value.trim() || null;
          body.observacoes = refs.observacoes.value.trim() || null;
          gravacoes.add(operacao);
          feedback.textContent = "Salvando no servidor…";
          try {
            const res = await root.PainelSessao.request(url, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(body),
            });
            const r = await res.json();
            if (!vigente()) return;
            gravacoes.delete(operacao);
            ultimo = r;
            formulario.replaceChildren();
            atual.replaceChildren();
            U.el(atual, "h4", "Último resultado informado");
            registro(atual, r);
            aviso.textContent =
              "Resultado salvo no servidor. Registro autodeclarado, não verificado.";
            U.botao(formulario, "Corrigir este resultado", editar, {
              escrita: true,
              valido: vigente,
            });
            await carregar(0, false);
          } catch (e) {
            if (!vigente() || e?.silencioso) return;
            if (e.status === 422) {
              feedback.textContent =
                "Confira as medidas, a fonte e o número da decisão: ela deve pertencer a esta viagem. Os campos foram preservados para correção.";
              return;
            }
            feedback.textContent =
              e.status === 409
                ? "O resultado mudou. Atualize o histórico e confira o registro atual antes de corrigir."
                : "Não foi possível confirmar o resultado do envio. Atualize o histórico antes de reenviar. " +
                  U.erro(e);
            // Um timeout pode ocorrer depois de o servidor gravar. Exige nova leitura.
            salvar.disabled = true;
            carregado = false;
          } finally {
            gravacoes.delete(operacao);
          }
        },
        { escrita: true, valido: () => vigente() && carregado },
      );
      salvar.disabled = gravacoes.has(operacao);
    }
    async function carregar(inicio = 0, preparar = true) {
      const leitura = ++pagina;
      try {
        const res = await root.PainelSessao.request(url + "?offset=" + inicio, {
          signal: sinal,
        });
        const d = await res.json();
        if (!vigente() || leitura !== pagina) return;
        if (!Array.isArray(d.items)) throw Error("Histórico inválido.");
        offset = inicio;
        historico.replaceChildren();
        if (inicio === 0 && preparar) {
          ultimo = d.items[0] || null;
          carregado = true;
          atual.replaceChildren();
          formulario.replaceChildren();
          if (ultimo) {
            U.el(atual, "h4", "Último resultado informado");
            registro(atual, ultimo);
          } else
            U.el(atual, "p", "Nenhum resultado informado para esta viagem.");
          if (root.PainelSessao.podeEscrever()) {
            if (ultimo)
              U.botao(formulario, "Corrigir este resultado", editar, {
                escrita: true,
                valido: vigente,
              });
            else editar();
          } else
            U.el(
              formulario,
              "p",
              "Seu perfil permite consultar os resultados, sem registrar ou corrigir.",
            );
          aviso.textContent =
            "Histórico recebido do servidor. Dados autodeclarados, não verificados.";
        }
        U.el(historico, "h4", "Histórico de resultados e correções");
        for (const r of d.items) {
          const a = U.el(historico, "article");
          registro(a, r);
        }
        if (!d.items.length)
          U.el(historico, "p", "Nenhum registro nesta página.");
        if (offset > 0)
          U.botao(
            historico,
            "Resultados mais recentes",
            () => carregar(Math.max(0, offset - 20), false),
            { valido: vigente },
          );
        if (d.proximo_offset !== null)
          U.botao(
            historico,
            "Resultados anteriores",
            () => carregar(d.proximo_offset, false),
            { valido: vigente },
          );
      } catch (e) {
        if (vigente() && leitura === pagina && !e?.silencioso)
          aviso.textContent =
            "Histórico indisponível. Atualize antes de registrar ou corrigir. " +
            U.erro(e);
      }
    }
    U.botao(
      caixa,
      "Atualizar resultados da viagem",
      () => {
        if (!gravacoes.has(operacao)) return exibir(parent, operacao);
      },
      { valido: vigente },
    );
    await carregar();
  }
  root.ResultadosViagem = { exibir, limpar };
})(window);
