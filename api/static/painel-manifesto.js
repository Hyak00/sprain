(function() {
    let arquivoSelecionado = null;
    let relatorioAtual = null;
    let conteudoTextoOriginal = "";

    function abrir() {
        resetar();
        const m = document.getElementById("modal-manifesto");
        if (m) m.style.display = "flex";
        atualizarVisibilidadeDemo();
    }

    function atualizarVisibilidadeDemo() {
        const btnDemo = document.getElementById("btn-demo-araraquara");
        if (!btnDemo) return;
        let tenant = "";
        if (window.PainelSessao && typeof window.PainelSessao.empresa === "function") {
            tenant = window.PainelSessao.empresa() || "";
        }
        if (!tenant) {
            const el = document.getElementById("lbl-user-tenant");
            if (el) tenant = el.innerText || "";
        }
        const ehDemo = tenant.toLowerCase().indexOf("demo") >= 0;
        btnDemo.style.display = ehDemo ? "inline-block" : "none";
    }

    function fechar() {
        const m = document.getElementById("modal-manifesto");
        if (m) m.style.display = "none";
        resetar();
    }

    function resetar() {
        arquivoSelecionado = null;
        relatorioAtual = null;
        conteudoTextoOriginal = "";
        mostrarEstado("inicial");
        const fin = document.getElementById("manifesto-file-input");
        if (fin) fin.value = "";
    }

    function mostrarEstado(estado) {
        ["inicial", "carregando", "erro", "previa", "sucesso"].forEach(function(nome) {
            const el = document.getElementById("manifesto-estado-" + nome);
            if (el) el.style.display = "none";
        });
        const ativo = document.getElementById("manifesto-estado-" + estado);
        if (ativo) ativo.style.display = "block";
    }

    async function baixarModelo() {
        try {
            const res = await fetch("/api/v1/logistica/operacoes/manifesto-modelo");
            if (!res.ok) throw new Error("Falha no download");
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "manifesto_modelo.csv";
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(function() { window.URL.revokeObjectURL(url); }, 1000);
        } catch (e) {
            alert("Nao foi possivel baixar o arquivo modelo no momento.");
        }
    }

    async function processarArquivo(file) {
        if (!file) return;
        const nome = (file.name || "").toLowerCase();
        if (!nome.endsWith(".csv")) {
            exibirErro("Extensao de arquivo invalida. Apenas arquivos .csv sao permitidos.");
            return;
        }
        if (file.size > 5 * 1024 * 1024) {
            exibirErro("Arquivo excede o limite maximo de 5 MB.");
            return;
        }

        arquivoSelecionado = file;
        try {
            conteudoTextoOriginal = await file.text();
        } catch (e) {
            conteudoTextoOriginal = "";
        }

        mostrarEstado("carregando");
        const msgEl = document.getElementById("manifesto-msg-carregando");
        if (msgEl) msgEl.textContent = "Validando dados, fuso horario e consistencia das viagens...";

        const formData = new FormData();
        formData.append("file", file);

        try {
            const headers = {};
            if (window.API_KEY) headers["X-API-Key"] = window.API_KEY;
            const res = await fetch("/api/v1/logistica/operacoes/importar-manifesto?dry_run=true", {
                method: "POST",
                headers: headers,
                body: formData
            });

            if (!res.ok) {
                const errData = await res.json().catch(function() { return {}; });
                exibirErro(errData.detail || "Erro de comunicacao ao validar manifesto.");
                return;
            }

            const dados = await res.json();
            relatorioAtual = dados;

            if (dados.erros && dados.erros.length === 1 && dados.erros[0].campo === "arquivo") {
                exibirErro(dados.erros[0].mensagem);
                return;
            }

            exibirPrevia(dados);
        } catch (e) {
            exibirErro("Falha de conexao ao enviar a planilha para analise.");
        }
    }

    function exibirErro(msg) {
        mostrarEstado("erro");
        const el = document.getElementById("manifesto-msg-erro");
        if (el) el.textContent = msg;
    }

    function exibirPrevia(relatorio) {
        mostrarEstado("previa");
        const r = relatorio.resumo || {};
        const elTotal = document.getElementById("prev-total");
        const elValidas = document.getElementById("prev-validas");
        const elCadastradas = document.getElementById("prev-cadastradas");
        const elDuplicadas = document.getElementById("prev-duplicadas");
        const elRejeitadas = document.getElementById("prev-rejeitadas");

        if (elTotal) elTotal.textContent = r.total_linhas || 0;
        if (elValidas) elValidas.textContent = r.validas || 0;
        if (elCadastradas) elCadastradas.textContent = r.ja_cadastradas || 0;
        if (elDuplicadas) elDuplicadas.textContent = r.duplicadas || 0;
        if (elRejeitadas) elRejeitadas.textContent = r.rejeitadas || 0;

        const btnConf = document.getElementById("btn-confirmar-manifesto");
        if (btnConf) {
            const qtdValidas = r.validas || 0;
            if (qtdValidas > 0) {
                btnConf.disabled = false;
                btnConf.textContent = "Confirmar importacao de " + qtdValidas + " viagens";
                btnConf.style.opacity = "1";
                btnConf.style.cursor = "pointer";
            } else {
                btnConf.disabled = true;
                btnConf.textContent = "Nenhuma viagem valida para importar";
                btnConf.style.opacity = "0.5";
                btnConf.style.cursor = "not-allowed";
            }
        }

        const areaErros = document.getElementById("container-erros-manifesto");
        const tbodyErros = document.getElementById("tabela-erros-manifesto");
        const btnRejeitadas = document.getElementById("btn-baixar-rejeitadas");

        if (tbodyErros) tbodyErros.replaceChildren();

        const erros = relatorio.erros || [];
        if (erros.length > 0 && areaErros && tbodyErros) {
            areaErros.style.display = "block";
            erros.forEach(function(err) {
                const tr = document.createElement("tr");

                const tdLinha = document.createElement("td");
                tdLinha.textContent = "Linha " + err.linha;
                tdLinha.style.fontWeight = "bold";
                tdLinha.style.color = "rgb(248, 113, 113)";

                const tdCampo = document.createElement("td");
                tdCampo.textContent = err.campo;

                const tdValor = document.createElement("td");
                tdValor.textContent = err.valor || "-";
                tdValor.className = "mono";

                const tdMsg = document.createElement("td");
                tdMsg.textContent = err.mensagem;

                tr.appendChild(tdLinha);
                tr.appendChild(tdCampo);
                tr.appendChild(tdValor);
                tr.appendChild(tdMsg);
                tbodyErros.appendChild(tr);
            });
            if (btnRejeitadas) btnRejeitadas.style.display = "inline-block";
        } else {
            if (areaErros) areaErros.style.display = "none";
            if (btnRejeitadas) btnRejeitadas.style.display = "none";
        }

        const areaAvisos = document.getElementById("container-avisos-manifesto");
        const listaAvisos = document.getElementById("lista-avisos-manifesto");
        if (listaAvisos) listaAvisos.replaceChildren();

        const avisos = relatorio.avisos || [];
        if (avisos.length > 0 && areaAvisos && listaAvisos) {
            areaAvisos.style.display = "block";
            avisos.forEach(function(av) {
                const li = document.createElement("li");
                li.textContent = "Linha " + av.linha + " (" + av.campo + "): " + av.mensagem;
                listaAvisos.appendChild(li);
            });
        } else {
            if (areaAvisos) areaAvisos.style.display = "none";
        }
    }

    async function confirmarImportacao() {
        if (!arquivoSelecionado) return;
        mostrarEstado("carregando");
        const msgEl = document.getElementById("manifesto-msg-carregando");
        if (msgEl) msgEl.textContent = "Gravando viagens no banco e iniciando monitoramento...";

        const formData = new FormData();
        formData.append("file", arquivoSelecionado);

        try {
            const headers = {};
            if (window.API_KEY) headers["X-API-Key"] = window.API_KEY;
            const res = await fetch("/api/v1/logistica/operacoes/importar-manifesto?dry_run=false", {
                method: "POST",
                headers: headers,
                body: formData
            });

            if (!res.ok) {
                const errData = await res.json().catch(function() { return {}; });
                exibirErro(errData.detail || "Erro ao gravar viagens no banco de dados.");
                return;
            }

            const resultado = await res.json();
            mostrarEstado("sucesso");
            const elQtd = document.getElementById("manifesto-sucesso-qtd");
            if (elQtd) elQtd.textContent = resultado.importadas || 0;

            if (typeof carregarOperacoesDoBackend === "function") {
                carregarOperacoesDoBackend();
            }
            if (typeof executarSimulacao === "function") {
                executarSimulacao();
            }
        } catch (e) {
            exibirErro("Nao foi possivel confirmar a gravacao das viagens.");
        }
    }

    function baixarLinhasRejeitadas() {
        if (!relatorioAtual || !relatorioAtual.erros || !conteudoTextoOriginal) return;

        const linhasArquivo = conteudoTextoOriginal.split(/\r?\n/);
        const mapaErros = {};
        relatorioAtual.erros.forEach(function(e) {
            if (!mapaErros[e.linha]) {
                mapaErros[e.linha] = e.mensagem;
            }
        });

        const cabecalho = (linhasArquivo[0] || "").trim();
        const separador = cabecalho.indexOf(";") >= 0 ? ";" : ",";
        const novoCabecalho = cabecalho ? cabecalho + separador + "motivo_rejeicao\r\n" : "linha" + separador + "motivo_rejeicao\r\n";
        let csvRejeitadas = novoCabecalho;

        Object.keys(mapaErros).forEach(function(numLinhaStr) {
            const numLinha = parseInt(numLinhaStr, 10);
            const idx = numLinha - 1;
            const conteudoLinha = (linhasArquivo[idx] || "").trim();
            const motivo = (mapaErros[numLinhaStr] || "").replace(/;/g, " - ");
            if (conteudoLinha) {
                csvRejeitadas += conteudoLinha + separador + motivo + "\r\n";
            }
        });

        const blob = new Blob([csvRejeitadas], { type: "text/csv;charset=utf-8;" });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "manifesto_rejeitadas.csv";
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(function() { window.URL.revokeObjectURL(url); }, 1000);
    }

    async function carregarDemoAraraquara() {
        try {
            const res = await fetch("/static/manifesto_araraquara_demo.csv");
            if (!res.ok) throw new Error("Falha ao obter demo");
            const blob = await res.blob();
            const file = new File([blob], "manifesto_araraquara_demo.csv", { type: "text/csv" });
            await processarArquivo(file);
        } catch (e) {
            exibirErro("Nao foi possivel carregar as viagens de exemplo de Araraquara.");
        }
    }

    window.PainelManifesto = {
        abrir: abrir,
        fechar: fechar,
        baixarModelo: baixarModelo,
        carregarDemoAraraquara: carregarDemoAraraquara,
        processarArquivo: processarArquivo,
        confirmarImportacao: confirmarImportacao,
        baixarLinhasRejeitadas: baixarLinhasRejeitadas,
        resetar: resetar
    };
})();
