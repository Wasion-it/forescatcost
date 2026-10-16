import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type ComponentProps, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { PERM, useAuth } from "../../auth/Autenticacao";
import { AvisoErro, Cabecalho, Carregando } from "../../componentes/comuns";
import { api, ErroApi } from "../../lib/api";
import { useDespachantes, useTerminais, useTipos, useTransportadoras } from "../../lib/consultas";
import { brl, paraDecimal, paraEdicao } from "../../lib/formato";
import type { Importacao, ImportacaoEntrada } from "../../lib/tipos";

// Campos numéricos são editados como texto pt-BR e convertidos no envio
const DECIMAIS = [
  "valor_invoice", "valor_frete", "valor_taxa_liberacao", "taxa_usd", "taxa_cny", "valor_siscomex",
  "peso_bruto_kg", "peso_liquido_kg", "valor_armazenagem_aerea",
] as const;
type CampoDecimal = (typeof DECIMAIS)[number];
type Formulario = Omit<ImportacaoEntrada, CampoDecimal | "qtd_itens" | "qtd_containers"> &
  Record<CampoDecimal, string> & { qtd_itens: string; qtd_containers: string };

const CASAS: Record<CampoDecimal, number> = {
  valor_invoice: 2, valor_frete: 2, valor_taxa_liberacao: 2, valor_siscomex: 2, valor_armazenagem_aerea: 2,
  taxa_usd: 4, taxa_cny: 4, peso_bruto_kg: 0, peso_liquido_kg: 0,
};

const VAZIO: Formulario = {
  numero_ip: "",
  data_ip: "",
  data_prevista: "",
  tipo_importacao_id: "",
  modal: "MARITIMO",
  valor_invoice: "",
  moeda_invoice: "USD",
  valor_frete: "",
  moeda_frete: "USD",
  qtd_itens: "",
  qtd_containers: "",
  taxa_usd: "",
  taxa_cny: "",
  valor_siscomex: "",
  valor_taxa_liberacao: "",
  peso_bruto_kg: "",
  peso_liquido_kg: "",
  valor_armazenagem_aerea: "",
  transportadora_local_id: "",
  despachante_id: "",
  terminal_id: "",
  observacoes: "",
};

function deImportacao(i: Importacao): Formulario {
  const f = { ...VAZIO };
  for (const k of Object.keys(VAZIO) as (keyof Formulario)[]) {
    const v = i[k as keyof Importacao];
    (f as Record<string, unknown>)[k] = v ?? "";
  }
  for (const k of DECIMAIS) f[k] = paraEdicao(i[k], CASAS[k]);
  f.qtd_itens = String(i.qtd_itens);
  f.qtd_containers = String(i.qtd_containers);
  return f;
}

function paraEnvio(f: Formulario): { corpo: ImportacaoEntrada | null; erros: Record<string, string> } {
  const erros: Record<string, string> = {};
  const corpo: Record<string, unknown> = { ...f };
  for (const k of DECIMAIS) {
    try {
      corpo[k] = paraDecimal(f[k]);
    } catch {
      erros[k] = "Número inválido";
    }
  }
  for (const k of ["qtd_itens", "qtd_containers"] as const) {
    if (f[k] === "" || !/^\d+$/.test(f[k])) erros[k] = "Informe um número inteiro";
    else corpo[k] = Number(f[k]);
  }
  for (const k of ["valor_siscomex", "valor_taxa_liberacao", "peso_bruto_kg", "peso_liquido_kg", "valor_armazenagem_aerea"] as const) {
    corpo[k] = corpo[k] ?? "0";
  }
  for (const k of ["valor_invoice", "valor_frete"] as const) if (corpo[k] === null) erros[k] = "Obrigatório";
  if (!f.tipo_importacao_id) erros.tipo_importacao_id = "Selecione o tipo";
  for (const k of [
    "numero_ip", "data_ip", "data_prevista", "transportadora_local_id",
    "despachante_id", "terminal_id", "observacoes",
  ] as const) {
    if (corpo[k] === "") corpo[k] = null;
  }
  return { corpo: Object.keys(erros).length ? null : (corpo as unknown as ImportacaoEntrada), erros };
}

export function FormularioImportacao() {
  const { id } = useParams();
  const editando = Boolean(id);
  const navegar = useNavigate();
  const cliente = useQueryClient();
  const { pode } = useAuth();
  const tipos = useTipos();
  const transportadoras = useTransportadoras();
  const despachantes = useDespachantes();
  const terminais = useTerminais();

  const existente = useQuery({
    queryKey: ["importacao", id],
    queryFn: () => api.get<Importacao>(`/importacoes/${id}`),
    enabled: editando,
  });

  const [f, setF] = useState<Formulario>(VAZIO);
  const [errosLocais, setErrosLocais] = useState<Record<string, string>>({});

  useEffect(() => {
    if (existente.data) setF(deImportacao(existente.data));
  }, [existente.data]);

  const salvar = useMutation({
    mutationFn: async ({ corpo }: { corpo: ImportacaoEntrada; calcular: boolean }) =>
      editando
        ? api.put<Importacao>(`/importacoes/${id}`, { ...corpo, versao: existente.data!.versao })
        : api.post<Importacao>("/importacoes", corpo),
    onSuccess: (imp, { calcular }) => {
      cliente.invalidateQueries({ queryKey: ["importacoes"] });
      cliente.setQueryData(["importacao", imp.id], imp);
      navegar(`/importacoes/${imp.id}${calcular ? "?calcular=1" : ""}`);
    },
  });

  const errosServidor = salvar.error instanceof ErroApi ? salvar.error.campos : {};
  const erros = { ...errosServidor, ...errosLocais };

  const transportLocais = transportadoras.data ?? [];
  const terminaisModal = terminais.data?.filter((t) => t.modal === f.modal) ?? [];

  const previa = useMemo(() => {
    const taxa = (moeda: string) => {
      if (moeda === "BRL") return 1;
      const t = moeda === "USD" ? f.taxa_usd : f.taxa_cny;
      try {
        return Number(paraDecimal(t) ?? NaN);
      } catch {
        return NaN;
      }
    };
    const num = (s: string) => {
      try {
        return Number(paraDecimal(s) ?? 0);
      } catch {
        return NaN;
      }
    };
    const invoice = num(f.valor_invoice) * taxa(f.moeda_invoice);
    const frete = num(f.valor_frete) * taxa(f.moeda_frete);
    // CIF = valor aduaneiro (invoice + frete). A Taxa Siscomex fica fora e entra só no ICMS.
    const cif = invoice + frete;
    return { invoice, frete, cif };
  }, [f]);

  function atualizar<K extends keyof Formulario>(campo: K, valor: Formulario[K]) {
    setF((atual) => ({ ...atual, [campo]: valor }));
    if (errosLocais[campo]) setErrosLocais(({ [campo]: _, ...resto }) => resto);
  }

  function enviar(calcular: boolean) {
    return (e?: FormEvent) => {
      e?.preventDefault();
      const { corpo, erros: novos } = paraEnvio(f);
      setErrosLocais(novos);
      if (corpo) salvar.mutate({ corpo, calcular });
    };
  }

  if (editando && existente.isLoading) return <Carregando />;
  if (existente.error) return <AvisoErro erro={existente.error} />;

  const titulo = editando ? `Editar ${existente.data?.numero_processo}` : "Nova importação";
  const fechado = existente.data?.status === "FECHADO";
  const usaUSD = f.moeda_invoice === "USD" || f.moeda_frete === "USD";
  const usaCNY = f.moeda_invoice === "CNY" || f.moeda_frete === "CNY";

  const campoTexto = (campo: keyof Formulario, rotulo: string, extra: ComponentProps<"input"> = {}, ajuda?: ReactNode) => (
    <Campo id={campo} rotulo={rotulo} erro={erros[campo]} ajuda={ajuda}>
      <input
        id={campo}
        className="entrada"
        value={String(f[campo] ?? "")}
        onChange={(e) => atualizar(campo, e.target.value as never)}
        aria-invalid={Boolean(erros[campo])}
        aria-describedby={erros[campo] ? `${campo}-erro` : ajuda ? `${campo}-ajuda` : undefined}
        {...extra}
      />
    </Campo>
  );

  const campoNumero = (campo: CampoDecimal | "qtd_itens" | "qtd_containers", rotulo: string, ajuda?: ReactNode) =>
    campoTexto(
      campo,
      rotulo,
      {
        className: "entrada num",
        inputMode: campo.startsWith("qtd") ? "numeric" : "decimal",
        onBlur: () => {
          if (campo.startsWith("qtd")) return;
          try {
            const d = paraDecimal(f[campo]);
            if (d !== null) atualizar(campo, paraEdicao(d, CASAS[campo as CampoDecimal]));
          } catch {
            /* mantém o texto para o usuário corrigir */
          }
        },
      },
      ajuda,
    );

  const seletor = (campo: keyof Formulario, rotulo: string, opcoes: { id: string; nome: string }[], vazio = "Não informado") => (
    <Campo id={campo} rotulo={rotulo} erro={erros[campo]}>
      <select
        id={campo}
        className="entrada"
        value={String(f[campo] ?? "")}
        onChange={(e) => atualizar(campo, e.target.value as never)}
        aria-invalid={Boolean(erros[campo])}
      >
        <option value="">{vazio}</option>
        {opcoes.map((o) => (
          <option key={o.id} value={o.id}>
            {o.nome}
          </option>
        ))}
      </select>
    </Campo>
  );

  return (
    <form onSubmit={enviar(false)} noValidate>
      <Cabecalho
        titulo={titulo}
        descricao="Os valores em moeda estrangeira são convertidos com as taxas informadas neste processo."
      />

      {fechado && (
        <div className="aviso aviso-atencao" style={{ marginBottom: "var(--e-5)" }}>
          <p>A despesa deste processo está fechada. Ele não pode mais ser editado.</p>
        </div>
      )}
      {existente.data?.status === "CALCULADO" && (
        <div className="aviso aviso-atencao" style={{ marginBottom: "var(--e-5)" }}>
          <p>Este processo já foi calculado. Depois de salvar, recalcule para atualizar a provisão.</p>
        </div>
      )}

      <section className="painel" aria-labelledby="sec-ip">
        <div className="painel-topo">
          <h2 id="sec-ip">IP</h2>
        </div>
        <div className="painel-corpo grade-campos">
          {campoTexto(
            "numero_ip",
            "Número da IP",
            { placeholder: "IP-26-0001", maxLength: 30 },
            "Identificador da provisão. Deixe em branco se ainda não foi gerado",
          )}
          {campoTexto("data_ip", "Data da IP", { type: "date" })}
          {campoTexto("data_prevista", "Data prevista", { type: "date" }, "Usada para a competência enquanto não houver data da IP")}
          {seletor("tipo_importacao_id", "Tipo de importação", tipos.data ?? [], "Selecione")}
          <Campo id="modal" rotulo="Modal">
            <select
              id="modal"
              className="entrada"
              value={f.modal}
              onChange={(e) => {
                atualizar("modal", e.target.value as "MARITIMO" | "AEREO");
                atualizar("terminal_id", "");
              }}
            >
              <option value="MARITIMO">Marítimo</option>
              <option value="AEREO">Aéreo</option>
            </select>
          </Campo>
        </div>
      </section>

      <section className="painel" aria-labelledby="sec-valores">
        <div className="painel-topo">
          <h2 id="sec-valores">Valores e câmbio</h2>
        </div>
        <div className="painel-corpo grade-campos">
          {campoNumero("valor_invoice", "Valor da invoice")}
          <Campo id="moeda_invoice" rotulo="Moeda da invoice">
            <select id="moeda_invoice" className="entrada" value={f.moeda_invoice} onChange={(e) => atualizar("moeda_invoice", e.target.value)}>
              <option value="USD">USD</option>
              <option value="CNY">CNY</option>
              <option value="BRL">BRL</option>
            </select>
          </Campo>
          {campoNumero("valor_frete", "Frete internacional")}
          <Campo id="moeda_frete" rotulo="Moeda do frete">
            <select id="moeda_frete" className="entrada" value={f.moeda_frete} onChange={(e) => atualizar("moeda_frete", e.target.value)}>
              <option value="USD">USD</option>
              <option value="CNY">CNY</option>
              <option value="BRL">BRL</option>
            </select>
          </Campo>
          {campoNumero("valor_taxa_liberacao", "Taxa de liberação (R$)", "Varia a cada processo. Informe o valor cobrado.")}
          {campoNumero("taxa_usd", usaUSD ? "Taxa USD" : "Taxa USD (opcional)")}
          {campoNumero("taxa_cny", usaCNY ? "Taxa CNY" : "Taxa CNY (opcional)")}
          {campoNumero(
            "valor_siscomex",
            "Taxa Siscomex (R$)",
            "Deixe em branco para o sistema estimar pelo nº de itens (tabela oficial). Informe só se já souber o valor real.",
          )}
          {f.modal === "AEREO" &&
            campoNumero("valor_armazenagem_aerea", "Armazenagem aérea (R$)", "Informada manualmente até a regra ser definida")}
          <div className="largo previa-cif" aria-live="polite">
            <span>
              Invoice <strong className="num">{Number.isFinite(previa.invoice) ? brl(previa.invoice) : "–"}</strong>
            </span>
            <span>
              Frete <strong className="num">{Number.isFinite(previa.frete) ? brl(previa.frete) : "–"}</strong>
            </span>
            <span>
              CIF estimado <strong className="num">{Number.isFinite(previa.cif) ? brl(previa.cif) : "–"}</strong>
            </span>
          </div>
        </div>
      </section>

      <section className="painel" aria-labelledby="sec-logistica">
        <div className="painel-topo">
          <h2 id="sec-logistica">Carga e logística</h2>
        </div>
        <div className="painel-corpo grade-campos">
          {campoNumero("qtd_itens", "Quantidade de itens")}
          {campoNumero("qtd_containers", "Quantidade de containers")}
          {campoNumero("peso_bruto_kg", "Peso bruto (kg)")}
          {campoNumero("peso_liquido_kg", "Peso líquido (kg)")}
          {seletor("transportadora_local_id", "Transportadora local", transportLocais, "Usar valores padrão")}
          {seletor("despachante_id", "Despachante", despachantes.data ?? [])}
          {seletor("terminal_id", "Terminal de armazenagem", terminaisModal, "Usar valores padrão")}
          <div className="campo largo">
            <label htmlFor="observacoes">Observações</label>
            <textarea id="observacoes" className="entrada" value={f.observacoes ?? ""} onChange={(e) => atualizar("observacoes", e.target.value)} maxLength={2000} />
          </div>
        </div>
      </section>

      <div style={{ marginTop: "var(--e-5)" }}>
        <AvisoErro erro={salvar.error} />
        {Object.keys(errosLocais).length > 0 && (
          <div className="aviso aviso-erro" role="alert">
            <p>Revise os campos destacados.</p>
          </div>
        )}
      </div>

      <div className="barra-acoes">
        <Link to={editando ? `/importacoes/${id}` : "/importacoes"} className="botao botao-texto">
          Cancelar
        </Link>
        <button type="submit" className="botao" disabled={salvar.isPending || fechado}>
          {editando ? "Salvar alterações" : "Salvar rascunho"}
        </button>
        {pode(PERM.calcular) && (
          <button type="button" className="botao botao-primario" disabled={salvar.isPending || fechado} onClick={enviar(true)}>
            {salvar.isPending ? "Salvando…" : "Salvar e calcular"}
          </button>
        )}
      </div>
    </form>
  );
}

function Campo({ id, rotulo, erro, ajuda, children }: { id: string; rotulo: string; erro?: string; ajuda?: ReactNode; children: ReactNode }) {
  return (
    <div className="campo">
      <label htmlFor={id}>{rotulo}</label>
      {children}
      {erro ? (
        <span className="erro-campo" id={`${id}-erro`}>
          {erro}
        </span>
      ) : (
        ajuda && (
          <span className="ajuda" id={`${id}-ajuda`}>
            {ajuda}
          </span>
        )
      )}
    </div>
  );
}
