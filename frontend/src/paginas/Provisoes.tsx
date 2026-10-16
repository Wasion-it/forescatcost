import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AvisoErro, Cabecalho, Carregando, Notificacao } from "../componentes/comuns";
import { api, baixar, query } from "../lib/api";
import { useTipos } from "../lib/consultas";
import { brl, data, mesCurto, primeiroDiaMes } from "../lib/formato";
import type { Provisao } from "../lib/tipos";

type Visao = "mensal" | "por-processo" | "por-tipo";

const VISOES: { id: Visao; rotulo: string; coluna: string }[] = [
  { id: "mensal", rotulo: "Por componente", coluna: "Componente" },
  { id: "por-processo", rotulo: "Por processo", coluna: "Processo" },
  { id: "por-tipo", rotulo: "Por tipo", coluna: "Tipo de importação" },
];

export function Provisoes() {
  const [params, setParams] = useSearchParams();
  const hoje = new Date();
  const visao = (params.get("visao") as Visao) ?? "mensal";
  const de = params.get("de") ?? primeiroDiaMes(hoje, -2).slice(0, 7);
  const ate = params.get("ate") ?? primeiroDiaMes(hoje, 3).slice(0, 7);
  const tipo = params.get("tipo") ?? "";
  const tipos = useTipos();
  const [exportando, setExportando] = useState(false);
  const [erroExport, setErroExport] = useState<unknown>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const filtros = { de: `${de}-01`, ate: `${ate}-01`, tipo };
  const r = useQuery({
    queryKey: ["provisao", visao, filtros],
    queryFn: () => api.get<Provisao>(`/provisoes/${visao}${query(filtros)}`),
    placeholderData: (anterior) => anterior,
  });

  function mudar(campo: string, valor: string) {
    const p = new URLSearchParams(params);
    if (valor) p.set(campo, valor);
    else p.delete(campo);
    setParams(p, { replace: true });
  }

  async function exportar() {
    setExportando(true);
    setErroExport(null);
    try {
      await baixar(`/provisoes/${visao}/excel${query(filtros)}`, `provisao-${visao}.xlsx`);
      setAviso("Planilha exportada.");
    } catch (e) {
      setErroExport(e);
    } finally {
      setExportando(false);
    }
  }

  const coluna = VISOES.find((v) => v.id === visao)!.coluna;
  const mesAtual = primeiroDiaMes(hoje);

  return (
    <>
      <Cabecalho
        titulo="Provisões"
        descricao="Desembolso previsto por mês de competência, a partir do cálculo vigente de cada processo não cancelado."
        acoes={
          <button className="botao botao-primario" onClick={exportar} disabled={exportando || !r.data}>
            {exportando ? "Exportando…" : "Exportar planilha"}
          </button>
        }
      />
      <AvisoErro erro={erroExport} />
      <section className="painel">
        <div className="filtros">
          <div className="campo">
            <span className="rotulo" id="rotulo-visao">
              Agrupar
            </span>
            <div className="alternador" role="group" aria-labelledby="rotulo-visao">
              {VISOES.map((v) => (
                <button key={v.id} type="button" aria-pressed={visao === v.id} onClick={() => mudar("visao", v.id)}>
                  {v.rotulo}
                </button>
              ))}
            </div>
          </div>
          <div className="campo">
            <label htmlFor="p-de">Competência de</label>
            <input id="p-de" type="month" className="entrada" value={de} onChange={(e) => mudar("de", e.target.value)} />
          </div>
          <div className="campo">
            <label htmlFor="p-ate">até</label>
            <input id="p-ate" type="month" className="entrada" value={ate} onChange={(e) => mudar("ate", e.target.value)} />
          </div>
          <div className="campo">
            <label htmlFor="p-tipo">Tipo</label>
            <select id="p-tipo" className="entrada" value={tipo} onChange={(e) => mudar("tipo", e.target.value)}>
              <option value="">Todos</option>
              {tipos.data?.map((t) => (
                <option key={t.id} value={t.codigo}>
                  {t.nome}
                </option>
              ))}
            </select>
          </div>
        </div>

        {r.isLoading && <Carregando />}
        {r.error && (
          <div className="painel-corpo">
            <AvisoErro erro={r.error} />
          </div>
        )}
        {r.data && r.data.linhas.length === 0 && (
          <div className="vazio">
            <p>Nenhum valor provisionado nessas competências.</p>
          </div>
        )}
        {r.data && r.data.linhas.length > 0 && (
          <div className="tabela-rolagem">
            <table className="tabela tabela-provisao">
              <caption className="sr-only">Provisão {VISOES.find((v) => v.id === visao)!.rotulo.toLowerCase()}</caption>
              <thead>
                <tr>
                  <th scope="col">{coluna}</th>
                  {visao === "por-processo" && (
                    <>
                      <th scope="col">IP</th>
                      <th scope="col">Data</th>
                    </>
                  )}
                  {r.data.competencias.map((c) => (
                    <th scope="col" className={`num${c === mesAtual ? " coluna-atual" : ""}`} key={c}>
                      {mesCurto(c)}
                    </th>
                  ))}
                  <th scope="col" className="num">
                    Total
                  </th>
                </tr>
              </thead>
              <tbody>
                {r.data.linhas.map((ln) => (
                  <tr key={ln.chave}>
                    <th scope="row">
                      {visao === "por-processo" ? (
                        <Link to={`/importacoes/${ln.chave}`} className="linha-link processo">
                          {ln.rotulo}
                        </Link>
                      ) : (
                        ln.rotulo
                      )}
                    </th>
                    {visao === "por-processo" && (
                      <>
                        <td>{ln.numero_ip ?? <span className="suave">não gerada</span>}</td>
                        <td>{data(ln.data_referencia)}</td>
                      </>
                    )}
                    {r.data!.competencias.map((c) => (
                      <td className={`num${c === mesAtual ? " coluna-atual" : ""}${Number(ln.valores[c]) === 0 ? " suave" : ""}`} key={c}>
                        {Number(ln.valores[c]) === 0 ? "–" : brl(ln.valores[c])}
                      </td>
                    ))}
                    <td className="num">{brl(ln.total)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row" colSpan={visao === "por-processo" ? 3 : 1}>
                    Total
                  </th>
                  {r.data.competencias.map((c) => (
                    <td className={`num${c === mesAtual ? " coluna-atual" : ""}`} key={c}>
                      {brl(r.data!.totais[c])}
                    </td>
                  ))}
                  <td className="num valor-provisionado">{brl(r.data.total)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </section>
      <Notificacao texto={aviso} aoSumir={() => setAviso(null)} />
    </>
  );
}
