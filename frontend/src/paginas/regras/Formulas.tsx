import { useQuery } from "@tanstack/react-query";
import { AvisoErro, Cabecalho, Carregando } from "../../componentes/comuns";
import { api } from "../../lib/api";
import { data } from "../../lib/formato";
import type { ComponenteCusto } from "../../lib/tipos";

const NATUREZA: Record<string, string> = {
  BASE: "Base de cálculo",
  IMPOSTO: "Imposto",
  TAXA: "Taxa",
  LOGISTICA: "Logística",
  SERVICO: "Serviço",
};

const COMPETENCIA: Record<string, string> = {
  MES_REFERENCIA: "Mês da declaração",
  CORTE_DIA: "Mês seguinte após o dia de corte",
};

export function Formulas() {
  const r = useQuery({ queryKey: ["componentes"], queryFn: () => api.get<ComponenteCusto[]>("/componentes") });
  if (r.isLoading) return <Carregando />;
  if (r.error || !r.data) return <AvisoErro erro={r.error} />;
  return (
    <>
      <Cabecalho
        titulo="Fórmulas"
        descricao="Componentes de custo na ordem de cálculo, com a fórmula vigente de cada um."
      />
      <div className="aviso bloco">
        <p>
          Nesta versão as fórmulas são publicadas pela equipe de sistemas, com revisão e testes automatizados. O editor com
          aprovação em duas etapas está previsto na próxima release.
        </p>
      </div>
      <section className="painel">
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr>
                <th scope="col">Componente</th>
                <th scope="col">Fórmula vigente</th>
                <th scope="col">Natureza</th>
                <th scope="col">Competência</th>
                <th scope="col">Entra no total</th>
              </tr>
            </thead>
            <tbody>
              {r.data.map((c) => (
                <tr key={c.id}>
                  <td>
                    <strong>{c.nome}</strong>
                    <br />
                    <code className="suave">{c.codigo.toLowerCase()}</code>
                  </td>
                  <td>
                    {c.formula ? (
                      <>
                        <code className="formula">{c.formula.expressao}</code>
                        <span className="ajuda-linha">
                          v{c.formula.versao}, desde {data(c.formula.vigencia_inicio)}
                        </span>
                      </>
                    ) : (
                      <span className="suave">sem fórmula vigente</span>
                    )}
                  </td>
                  <td>{NATUREZA[c.natureza] ?? c.natureza}</td>
                  <td>{COMPETENCIA[c.regra_competencia] ?? c.regra_competencia}</td>
                  <td>{c.compoe_provisao ? "Sim" : "Não, só base"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
