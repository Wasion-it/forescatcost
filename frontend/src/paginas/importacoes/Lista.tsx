import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { PERM, useAuth } from "../../auth/Autenticacao";
import { AvisoErro, Cabecalho, Carregando, Paginacao, Status } from "../../componentes/comuns";
import { api, query } from "../../lib/api";
import { useTipos } from "../../lib/consultas";
import { brl, data } from "../../lib/formato";
import type { ImportacaoResumo, Pagina } from "../../lib/tipos";

const TAMANHO = 25;

export function ListaImportacoes() {
  const { pode } = useAuth();
  const [params, setParams] = useSearchParams();
  const tipos = useTipos();
  const filtros = {
    q: params.get("q") ?? "",
    tipo: params.get("tipo") ?? "",
    status: params.get("status") ?? "",
    de: params.get("de") ?? "",
    ate: params.get("ate") ?? "",
  };
  const pagina = Number(params.get("pagina") ?? 1);
  const [rascunho, setRascunho] = useState(filtros);

  const consulta = useQuery({
    queryKey: ["importacoes", filtros, pagina],
    queryFn: () => api.get<Pagina<ImportacaoResumo>>(`/importacoes${query({ ...filtros, pagina, tamanho: TAMANHO })}`),
    placeholderData: (anterior) => anterior,
  });

  function aplicar(novos: typeof filtros, novaPagina = 1) {
    const p = new URLSearchParams();
    Object.entries(novos).forEach(([k, v]) => v && p.set(k, v));
    if (novaPagina > 1) p.set("pagina", String(novaPagina));
    setParams(p);
  }

  return (
    <>
      <Cabecalho
        titulo="Importações"
        descricao="Processos cadastrados pelo PCM, com o total provisionado do cálculo vigente."
        acoes={
          pode(PERM.importacaoEditar) && (
            <Link to="/importacoes/nova" className="botao botao-primario">
              Nova importação
            </Link>
          )
        }
      />
      <section className="painel">
        <form
          className="filtros"
          onSubmit={(e) => {
            e.preventDefault();
            aplicar(rascunho);
          }}
        >
          <div className="campo" style={{ flex: "1 1 220px" }}>
            <label htmlFor="f-q">Buscar</label>
            <input
              id="f-q"
              className="entrada"
              placeholder="DI, IMP-00012 ou observação"
              value={rascunho.q}
              onChange={(e) => setRascunho({ ...rascunho, q: e.target.value })}
            />
          </div>
          <div className="campo">
            <label htmlFor="f-tipo">Tipo</label>
            <select id="f-tipo" className="entrada" value={rascunho.tipo} onChange={(e) => setRascunho({ ...rascunho, tipo: e.target.value })}>
              <option value="">Todos</option>
              {tipos.data?.map((t) => (
                <option key={t.id} value={t.codigo}>
                  {t.nome}
                </option>
              ))}
            </select>
          </div>
          <div className="campo">
            <label htmlFor="f-status">Situação</label>
            <select id="f-status" className="entrada" value={rascunho.status} onChange={(e) => setRascunho({ ...rascunho, status: e.target.value })}>
              <option value="">Todas</option>
              <option value="RASCUNHO">Rascunho</option>
              <option value="CALCULADO">Calculado</option>
              <option value="DESATUALIZADO">Precisa recalcular</option>
              <option value="CANCELADO">Cancelado</option>
            </select>
          </div>
          <div className="campo">
            <label htmlFor="f-de">Data de</label>
            <input id="f-de" type="date" className="entrada" value={rascunho.de} onChange={(e) => setRascunho({ ...rascunho, de: e.target.value })} />
          </div>
          <div className="campo">
            <label htmlFor="f-ate">até</label>
            <input id="f-ate" type="date" className="entrada" value={rascunho.ate} onChange={(e) => setRascunho({ ...rascunho, ate: e.target.value })} />
          </div>
          <div className="acoes">
            <button type="submit" className="botao">
              Filtrar
            </button>
            <button
              type="button"
              className="botao botao-texto"
              onClick={() => {
                const vazio = { q: "", tipo: "", status: "", de: "", ate: "" };
                setRascunho(vazio);
                aplicar(vazio);
              }}
            >
              Limpar
            </button>
          </div>
        </form>

        {consulta.isLoading && <Carregando />}
        {consulta.error && (
          <div className="painel-corpo">
            <AvisoErro erro={consulta.error} />
          </div>
        )}
        {consulta.data && consulta.data.itens.length === 0 && (
          <div className="vazio">
            <p>Nenhum processo encontrado com esses filtros.</p>
            {pode(PERM.importacaoEditar) && (
              <Link to="/importacoes/nova" className="botao">
                Cadastrar importação
              </Link>
            )}
          </div>
        )}
        {consulta.data && consulta.data.itens.length > 0 && (
          <>
            <div className="tabela-rolagem">
              <table className="tabela">
                <caption className="sr-only">Lista de importações</caption>
                <thead>
                  <tr>
                    <th scope="col">Processo</th>
                    <th scope="col">Declaração</th>
                    <th scope="col">Data</th>
                    <th scope="col">Tipo</th>
                    <th scope="col">Modal</th>
                    <th scope="col">Situação</th>
                    <th scope="col" className="num">
                      Provisionado
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {consulta.data.itens.map((i) => (
                    <tr key={i.id}>
                      <td>
                        <Link to={`/importacoes/${i.id}`} className="linha-link processo">
                          {i.numero_processo}
                        </Link>
                      </td>
                      <td>{i.numero_declaracao ?? <span className="suave">{i.tipo_declaracao} não registrada</span>}</td>
                      <td>
                        {data(i.data_referencia)}
                        {!i.data_declaracao && <span className="suave"> (prevista)</span>}
                      </td>
                      <td>{i.tipo_importacao.nome}</td>
                      <td>{i.modal === "MARITIMO" ? "Marítimo" : "Aéreo"}</td>
                      <td>
                        <Status status={i.status} desatualizado={i.calculo_desatualizado} />
                      </td>
                      <td className="num">
                        {i.status === "CANCELADO" ? <s className="suave">{brl(i.total_provisionado)}</s> : brl(i.total_provisionado)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td colSpan={6}>Total desta página (sem cancelados)</td>
                    <td className="num valor-provisionado">
                      {brl(
                        consulta.data.itens
                          .filter((i) => i.status !== "CANCELADO")
                          .reduce((s, i) => s + Number(i.total_provisionado ?? 0), 0),
                      )}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
            <Paginacao
              pagina={pagina}
              tamanho={TAMANHO}
              total={consulta.data.total}
              aoMudar={(p) => aplicar(filtros, p)}
            />
          </>
        )}
      </section>
    </>
  );
}
