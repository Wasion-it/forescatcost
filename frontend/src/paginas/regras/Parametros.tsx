import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { PERM, useAuth } from "../../auth/Autenticacao";
import { AvisoErro, Cabecalho, Carregando, Dialogo, Notificacao } from "../../componentes/comuns";
import { api } from "../../lib/api";
import { useDespachantes, useTerminais, useTipos, useTransportadoras } from "../../lib/consultas";
import { brl, data, paraDecimal, percentual, percentualParaFracao } from "../../lib/formato";
import type { Parametro, Vigencia } from "../../lib/tipos";

const ESCOPOS: Record<string, string> = {
  GLOBAL: "Valor único",
  TIPO_IMPORTACAO: "Por tipo de importação",
  TRANSP_LOCAL: "Por transportadora local",
  TRANSP_SECUNDARIA: "Por transportadora secundária",
  DESPACHANTE: "Por despachante",
  TERMINAL: "Por terminal",
};

export function exibirValor(tipo: Parametro["tipo_valor"], valor: string): string {
  if (tipo === "PERCENTUAL") return percentual(valor, 4);
  if (tipo === "INTEIRO") return String(Number(valor));
  return brl(valor);
}

export function Parametros() {
  const { pode } = useAuth();
  const [editando, setEditando] = useState<Parametro | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const r = useQuery({ queryKey: ["parametros"], queryFn: () => api.get<Parametro[]>("/parametros") });

  if (r.isLoading) return <Carregando />;
  if (r.error || !r.data) return <AvisoErro erro={r.error} />;

  const grupos = Array.from(new Set(r.data.map((p) => p.grupo)));

  return (
    <>
      <Cabecalho
        titulo="Parâmetros"
        descricao="Valores usados nas fórmulas. Uma alteração cria uma nova vigência e não muda cálculos já registrados."
      />
      {grupos.map((g) => (
        <section className="painel" key={g} aria-labelledby={`g-${g}`}>
          <div className="painel-topo">
            <h2 id={`g-${g}`}>{g}</h2>
          </div>
          <div className="tabela-rolagem">
            <table className="tabela tabela-parametros">
              <colgroup>
                <col className="c-param" />
                <col className="c-aplicacao" />
                <col className="c-valor" />
                <col className="c-desde" />
                <col className="c-acoes" />
              </colgroup>
              <thead>
                <tr>
                  <th scope="col">Parâmetro</th>
                  <th scope="col">Aplicação</th>
                  <th scope="col" className="num">
                    Valor vigente
                  </th>
                  <th scope="col">Desde</th>
                  <th scope="col">
                    <span className="sr-only">Ações</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {r.data!
                  .filter((p) => p.grupo === g)
                  .map((p) => (
                    <tr key={p.id}>
                      <td>
                        <strong>{p.descricao}</strong>
                        <br />
                        <code className="suave">p.{p.chave}</code>
                      </td>
                      <td>{ESCOPOS[p.escopo] ?? p.escopo}</td>
                      <td className="num">
                        {p.valores.length === 0 && <span className="suave">sem valor</span>}
                        {p.valores.map((v) => (
                          <div key={v.escopo_ref_id ?? "padrao"}>
                            {p.escopo !== "GLOBAL" && <span className="suave">{v.escopo_ref_nome}: </span>}
                            {v.vigente ? exibirValor(p.tipo_valor, v.vigente.valor) : <span className="suave">sem vigência hoje</span>}
                            {proximaVigencia(v.historico) && (
                              <span className="ajuda-linha">
                                {exibirValor(p.tipo_valor, proximaVigencia(v.historico)!.valor)} a partir de {data(proximaVigencia(v.historico)!.vigencia_inicio)}
                              </span>
                            )}
                          </div>
                        ))}
                      </td>
                      <td>
                        {p.valores.map((v) => (
                          <div key={v.escopo_ref_id ?? "padrao"}>{data(v.vigente?.vigencia_inicio)}</div>
                        ))}
                      </td>
                      <td className="num">
                        {pode(PERM.parametroEditar) && (
                          <button className="botao botao-pequeno" onClick={() => setEditando(p)}>
                            Nova vigência
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
      {editando && (
        <DialogoVigencia
          parametro={editando}
          aoFechar={() => setEditando(null)}
          aoSalvar={() => {
            setEditando(null);
            setAviso("Nova vigência registrada.");
          }}
        />
      )}
      <Notificacao texto={aviso} aoSumir={() => setAviso(null)} />
    </>
  );
}

function proximaVigencia(historico: Vigencia[]): Vigencia | undefined {
  const hoje = new Date().toISOString().slice(0, 10);
  return historico.find((h) => h.vigencia_inicio > hoje);
}

function amanha(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
}

function DialogoVigencia({ parametro, aoFechar, aoSalvar }: { parametro: Parametro; aoFechar: () => void; aoSalvar: () => void }) {
  const cliente = useQueryClient();
  const tipos = useTipos();
  const transp = useTransportadoras();
  const desp = useDespachantes();
  const term = useTerminais();
  const [ref, setRef] = useState("");
  const [valor, setValor] = useState("");
  const [inicio, setInicio] = useState(amanha());
  const [justificativa, setJustificativa] = useState("");
  const [erroLocal, setErroLocal] = useState<string | null>(null);

  const opcoes: { id: string; nome: string }[] =
    {
      GLOBAL: [],
      TIPO_IMPORTACAO: tipos.data ?? [],
      TRANSP_LOCAL: transp.data?.filter((t) => t.tipo_servico !== "SECUNDARIO") ?? [],
      TRANSP_SECUNDARIA: transp.data?.filter((t) => t.tipo_servico !== "LOCAL") ?? [],
      DESPACHANTE: desp.data ?? [],
      TERMINAL: term.data ?? [],
    }[parametro.escopo] ?? [];

  const salvar = useMutation({
    mutationFn: (corpo: object) => api.post(`/parametros/${parametro.id}/vigencias`, corpo),
    onSuccess: () => {
      cliente.invalidateQueries({ queryKey: ["parametros"] });
      aoSalvar();
    },
  });

  const atual = parametro.valores.find((v) => (v.escopo_ref_id ?? "") === ref)?.vigente;
  const percentualTipo = parametro.tipo_valor === "PERCENTUAL";

  function enviar() {
    setErroLocal(null);
    let convertido: string | null;
    try {
      convertido = percentualTipo ? percentualParaFracao(valor) : paraDecimal(valor);
    } catch {
      setErroLocal("Valor inválido.");
      return;
    }
    if (convertido === null) {
      setErroLocal("Informe o valor.");
      return;
    }
    salvar.mutate({ escopo_ref_id: ref || null, valor: convertido, vigencia_inicio: inicio, justificativa });
  }

  return (
    <Dialogo
      aberto
      titulo={parametro.descricao}
      aoFechar={aoFechar}
      rodape={
        <>
          <button className="botao botao-texto" onClick={aoFechar}>
            Cancelar
          </button>
          <button className="botao botao-primario" disabled={salvar.isPending || justificativa.trim().length < 5 || !valor} onClick={enviar}>
            Registrar vigência
          </button>
        </>
      }
    >
      {parametro.escopo !== "GLOBAL" && (
        <div className="campo">
          <label htmlFor="v-ref">Aplicar a</label>
          <select id="v-ref" className="entrada" value={ref} onChange={(e) => setRef(e.target.value)}>
            <option value="">Valor padrão (quando não houver valor específico)</option>
            {opcoes.map((o) => (
              <option key={o.id} value={o.id}>
                {o.nome}
              </option>
            ))}
          </select>
        </div>
      )}
      <p className="suave">Valor atual: {atual ? `${exibirValor(parametro.tipo_valor, atual.valor)} desde ${data(atual.vigencia_inicio)}` : "nenhum"}</p>
      <div className="grade-campos">
        <div className="campo">
          <label htmlFor="v-valor">{percentualTipo ? "Novo valor (%)" : parametro.tipo_valor === "INTEIRO" ? "Novo valor" : "Novo valor (R$)"}</label>
          <input id="v-valor" className="entrada num" inputMode="decimal" value={valor} onChange={(e) => setValor(e.target.value)} placeholder={percentualTipo ? "0,92" : ""} />
        </div>
        <div className="campo">
          <label htmlFor="v-inicio">Vale a partir de</label>
          <input id="v-inicio" type="date" className="entrada" value={inicio} onChange={(e) => setInicio(e.target.value)} />
        </div>
      </div>
      <div className="campo">
        <label htmlFor="v-just">Justificativa</label>
        <input id="v-just" className="entrada" value={justificativa} onChange={(e) => setJustificativa(e.target.value)} maxLength={300} placeholder="Ex.: reajuste contratual de novembro" />
        <span className="ajuda">A vigência anterior é encerrada na véspera da nova data.</span>
      </div>
      {erroLocal && (
        <div className="aviso aviso-erro" role="alert">
          {erroLocal}
        </div>
      )}
      <AvisoErro erro={salvar.error} />
    </Dialogo>
  );
}
