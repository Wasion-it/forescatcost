import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AvisoErro, Cabecalho, Carregando, Paginacao } from "../../componentes/comuns";
import { api, query } from "../../lib/api";
import { dataHora } from "../../lib/formato";
import type { RegistroAuditoria } from "../../lib/tipos";

const TABELAS: Record<string, string> = {
  importacao: "Importações",
  calculo: "Cálculos",
  parametro_valor: "Valores de parâmetros",
  aliquota: "Alíquotas",
  usuario: "Usuários",
  usuario_perfil: "Perfis de usuário",
  transportadora: "Transportadoras",
  despachante: "Despachantes",
  terminal: "Terminais",
  formula: "Fórmulas",
  componente_custo: "Componentes de custo",
  parametro: "Parâmetros",
  imposto: "Impostos",
  tipo_importacao: "Tipos de importação",
};

const ACOES = { INSERT: "Inclusão", UPDATE: "Alteração", DELETE: "Exclusão" };
const TAMANHO = 50;

function formatar(v: unknown): string {
  if (v === null || v === undefined) return "vazio";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function Auditoria() {
  const [tabela, setTabela] = useState("");
  const [de, setDe] = useState("");
  const [ate, setAte] = useState("");
  const [pagina, setPagina] = useState(1);
  const tabelas = useQuery({ queryKey: ["auditoria-tabelas"], queryFn: () => api.get<string[]>("/auditoria/tabelas") });
  const r = useQuery({
    queryKey: ["auditoria", tabela, de, ate, pagina],
    queryFn: () =>
      api.get<{ itens: RegistroAuditoria[]; total: number }>(`/auditoria${query({ tabela, de, ate, pagina, tamanho: TAMANHO })}`),
    placeholderData: (anterior) => anterior,
  });

  return (
    <>
      <Cabecalho
        titulo="Auditoria"
        descricao="Toda inclusão e alteração gravada no banco, com autor e valores antes e depois. A trilha não pode ser editada."
      />
      <section className="painel">
        <div className="filtros">
          <div className="campo">
            <label htmlFor="a-tabela">Registro</label>
            <select
              id="a-tabela"
              className="entrada"
              value={tabela}
              onChange={(e) => {
                setTabela(e.target.value);
                setPagina(1);
              }}
            >
              <option value="">Todos</option>
              {tabelas.data?.map((t) => (
                <option key={t} value={t}>
                  {TABELAS[t] ?? t}
                </option>
              ))}
            </select>
          </div>
          <div className="campo">
            <label htmlFor="a-de">De</label>
            <input id="a-de" type="date" className="entrada" value={de} onChange={(e) => { setDe(e.target.value); setPagina(1); }} />
          </div>
          <div className="campo">
            <label htmlFor="a-ate">Até</label>
            <input id="a-ate" type="date" className="entrada" value={ate} onChange={(e) => { setAte(e.target.value); setPagina(1); }} />
          </div>
        </div>
        {r.isLoading && <Carregando />}
        <AvisoErro erro={r.error} />
        {r.data && (
          <>
            <div className="tabela-rolagem">
              <table className="tabela">
                <thead>
                  <tr>
                    <th scope="col">Quando</th>
                    <th scope="col">Quem</th>
                    <th scope="col">Ação</th>
                    <th scope="col">Registro</th>
                    <th scope="col">O que mudou</th>
                  </tr>
                </thead>
                <tbody>
                  {r.data.itens.map((a) => (
                    <tr key={a.id}>
                      <td className="sem-quebra">{dataHora(a.ocorrido_em)}</td>
                      <td>{a.usuario_nome}</td>
                      <td>{ACOES[a.acao]}</td>
                      <td>
                        {TABELAS[a.tabela] ?? a.tabela}
                        <span className="ajuda-linha codigo">{a.registro_id.slice(0, 8)}</span>
                      </td>
                      <td>
                        {a.acao === "UPDATE" && a.campos_alterados ? (
                          <ul className="diferencas">
                            {a.campos_alterados.map((c) => (
                              <li key={c}>
                                <strong>{c.replace(/_/g, " ")}</strong>: {formatar(a.dados_antes?.[c])} → {formatar(a.dados_depois?.[c])}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <details>
                            <summary>Ver dados</summary>
                            <pre className="json">{JSON.stringify(a.dados_depois ?? a.dados_antes, null, 2)}</pre>
                          </details>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Paginacao pagina={pagina} tamanho={TAMANHO} total={r.data.total} aoMudar={setPagina} />
          </>
        )}
      </section>
    </>
  );
}
