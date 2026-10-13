import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { PERM, useAuth } from "../auth/Autenticacao";
import { AvisoErro, Carregando } from "../componentes/comuns";
import { api } from "../lib/api";
import { brl, brlCompacto, mesCurto, mesLongo } from "../lib/formato";
import type { Dashboard } from "../lib/tipos";

const CORES_TIPO: Record<string, string> = {
  INDUSTRIALIZACAO: "var(--agua)",
  USO_CONSUMO: "var(--solimoes)",
};

const NATUREZAS: Record<string, string> = {
  IMPOSTO: "Impostos",
  TAXA: "Taxas",
  LOGISTICA: "Frete, transporte e armazenagem",
  SERVICO: "Serviços",
};

export function Painel() {
  const { pode } = useAuth();
  const d = useQuery({ queryKey: ["dashboard"], queryFn: () => api.get<Dashboard>("/dashboard") });

  if (d.isLoading) return <Carregando />;
  if (d.error || !d.data) return <AvisoErro erro={d.error} />;
  const { kpis, serie, por_tipo, composicao, competencia_atual, importacoes_por_mes } = d.data;
  const proximo = serie[serie.findIndex((s) => s.competencia === competencia_atual) + 1]?.competencia;
  const totalComposicao = composicao.reduce((s, c) => s + Number(c.valor), 0);

  return (
    <div className="painel-inicio">
      <header className="resumo-mes">
        <p className="suave">Provisão de {mesLongo(competencia_atual)}</p>
        <p className="resumo-frase">
          <strong className="num">{brl(kpis.provisao_mes_atual)}</strong> a desembolsar neste mês e{" "}
          <strong className="num">{brl(kpis.provisao_proximo_mes)}</strong> em {proximo ? mesLongo(proximo).split(" de ")[0] : "seguida"}.
        </p>
      </header>

      <section className="painel" aria-labelledby="t-serie">
        <div className="painel-topo">
          <h2 id="t-serie">Provisão por competência</h2>
          <ul className="legenda">
            {por_tipo.map((t) => (
              <li key={t.codigo}>
                <span className="legenda-cor" style={{ background: CORES_TIPO[t.codigo] ?? "var(--negro-3)" }} aria-hidden="true" />
                {t.nome}
              </li>
            ))}
          </ul>
        </div>
        <div className="painel-corpo">
          <GraficoMensal dados={d.data} />
        </div>
      </section>

      <div className="painel-colunas">
        <section className="painel" aria-labelledby="t-pendencias">
          <div className="painel-topo">
            <h2 id="t-pendencias">Pendências do PCM</h2>
          </div>
          <ul className="pendencias">
            <li>
              <Link to="/importacoes?status=DESATUALIZADO">
                <strong>{kpis.desatualizados}</strong>
                <span>{kpis.desatualizados === 1 ? "processo precisa" : "processos precisam"} de recálculo</span>
              </Link>
            </li>
            <li>
              <Link to="/importacoes?status=RASCUNHO">
                <strong>{kpis.rascunhos}</strong>
                <span>{kpis.rascunhos === 1 ? "rascunho" : "rascunhos"} sem cálculo</span>
              </Link>
            </li>
            <li>
              <Link to="/importacoes">
                <strong>{kpis.processos_ativos}</strong>
                <span>processos ativos no total</span>
              </Link>
            </li>
          </ul>
          {pode(PERM.importacaoEditar) && (
            <div className="painel-corpo">
              <Link to="/importacoes/nova" className="botao botao-primario">
                Nova importação
              </Link>
            </div>
          )}
        </section>

        <section className="painel" aria-labelledby="t-composicao">
          <div className="painel-topo">
            <h2 id="t-composicao">Do que é feita a provisão</h2>
            <span className="suave">12 meses exibidos</span>
          </div>
          <div className="painel-corpo">
            <div className="composicao-barra" aria-hidden="true">
              {composicao.map((c) => (
                <span key={c.natureza} className={`comp-${c.natureza.toLowerCase()}`} style={{ flexGrow: Number(c.valor) }} />
              ))}
            </div>
            <table className="tabela tabela-compacta">
              <caption className="sr-only">Composição da provisão por natureza</caption>
              <tbody>
                {composicao.map((c) => (
                  <tr key={c.natureza}>
                    <td>
                      <span className={`legenda-cor comp-${c.natureza.toLowerCase()}`} aria-hidden="true" /> {NATUREZAS[c.natureza] ?? c.natureza}
                    </td>
                    <td className="num">{totalComposicao ? `${((Number(c.valor) / totalComposicao) * 100).toFixed(1).replace(".", ",")}%` : "–"}</td>
                    <td className="num">{brl(c.valor)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="painel" aria-labelledby="t-tipos">
          <div className="painel-topo">
            <h2 id="t-tipos">Por tipo de importação</h2>
          </div>
          <div className="painel-corpo">
            <table className="tabela tabela-compacta">
              <caption className="sr-only">Provisão por tipo de importação</caption>
              <tbody>
                {por_tipo.map((t) => (
                  <tr key={t.codigo}>
                    <td>
                      <span className="legenda-cor" style={{ background: CORES_TIPO[t.codigo] }} aria-hidden="true" /> {t.nome}
                    </td>
                    <td className="num">{brl(t.valor)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="suave nota">
              Importações registradas por mês:{" "}
              {importacoes_por_mes
                .filter((m) => m.quantidade > 0)
                .map((m) => `${mesCurto(m.mes)} ${m.quantidade}`)
                .join(", ") || "nenhuma"}
              .
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}

function GraficoMensal({ dados }: { dados: Dashboard }) {
  const { serie, competencia_atual, por_tipo, importacoes_por_mes } = dados;
  const largura = 960;
  const altura = 260;
  const margem = { topo: 16, base: 44, esquerda: 92, direita: 8 };
  const max = Math.max(1, ...serie.map((s) => Number(s.total)));
  const escala = (v: number) => ((altura - margem.topo - margem.base) * v) / max;
  const passo = (largura - margem.esquerda - margem.direita) / serie.length;
  const larguraBarra = Math.min(46, passo * 0.56);
  const tipos = por_tipo.map((t) => t.codigo);
  const marcas = [0, 0.5, 1].map((f) => f * max);
  const contagem = Object.fromEntries(importacoes_por_mes.map((m) => [m.mes, m.quantidade]));

  return (
    <figure className="grafico">
      <div className="grafico-area">
      <svg viewBox={`0 0 ${largura} ${altura}`} role="img" aria-labelledby="grafico-desc" preserveAspectRatio="xMidYMid meet">
        <desc id="grafico-desc">Barras empilhadas com a provisão mensal por tipo de importação. Os valores estão na tabela abaixo.</desc>
        {marcas.map((m) => {
          const y = altura - margem.base - escala(m);
          return (
            <g key={m}>
              <line x1={margem.esquerda} x2={largura - margem.direita} y1={y} y2={y} className="grade-linha" />
              <text x={margem.esquerda - 8} y={y + 4} textAnchor="end" className="eixo">
                {m === 0 ? "0" : brlCompacto(m)}
              </text>
            </g>
          );
        })}
        {serie.map((s, i) => {
          const x = margem.esquerda + passo * i + (passo - larguraBarra) / 2;
          let y = altura - margem.base;
          const atual = s.competencia === competencia_atual;
          const futuro = s.competencia > competencia_atual;
          return (
            <g key={s.competencia} className={futuro ? "barra-futura" : undefined}>
              {atual && (
                <rect x={margem.esquerda + passo * i + 2} y={margem.topo - 8} width={passo - 4} height={altura - margem.topo - margem.base + 8} className="mes-atual" />
              )}
              {tipos.map((t) => {
                const h = escala(Number(s.por_tipo[t] ?? 0));
                y -= h;
                return h > 0 ? <rect key={t} x={x} y={y} width={larguraBarra} height={h} fill={CORES_TIPO[t] ?? "var(--negro-3)"} /> : null;
              })}
              <text x={x + larguraBarra / 2} y={altura - margem.base + 18} textAnchor="middle" className={atual ? "eixo eixo-atual" : "eixo"}>
                {mesCurto(s.competencia)}
              </text>
              <text x={x + larguraBarra / 2} y={altura - margem.base + 34} textAnchor="middle" className="eixo eixo-fraco">
                {contagem[s.competencia] ? `${contagem[s.competencia]} DI` : ""}
              </text>
            </g>
          );
        })}
      </svg>
      </div>
      <details className="grafico-dados">
        <summary>Ver valores em tabela</summary>
        <div className="tabela-rolagem">
          <table className="tabela tabela-compacta">
            <thead>
              <tr>
                <th scope="col">Competência</th>
                {por_tipo.map((t) => (
                  <th scope="col" className="num" key={t.codigo}>
                    {t.nome}
                  </th>
                ))}
                <th scope="col" className="num">
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {serie.map((s) => (
                <tr key={s.competencia}>
                  <th scope="row">{mesCurto(s.competencia)}</th>
                  {por_tipo.map((t) => (
                    <td className="num" key={t.codigo}>
                      {brl(s.por_tipo[t.codigo] ?? 0)}
                    </td>
                  ))}
                  <td className="num">{brl(s.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
