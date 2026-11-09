import type { CSSProperties } from "react";
import { brl, mesCurto, percentual } from "../../lib/formato";
import { comMargem, MARGEM_PROVISAO_PCT, somaComMargem } from "../../lib/margem";
import type { Calculo, CalculoItem } from "../../lib/tipos";

const GRUPOS: { natureza: CalculoItem["natureza"]; titulo: string }[] = [
  { natureza: "IMPOSTO", titulo: "Impostos" },
  { natureza: "TAXA", titulo: "Taxas" },
  { natureza: "LOGISTICA", titulo: "Frete, transporte e armazenagem" },
  { natureza: "SERVICO", titulo: "Serviços" },
];

const ROTULOS_VARIAVEIS: Record<string, string> = {
  cif: "CIF",
  invoice_brl: "Invoice em R$",
  frete_brl: "Frete em R$",
  siscomex: "Taxa Siscomex informada",
  taxa_siscomex: "Taxa Siscomex",
  valor_taxa_liberacao: "Taxa de liberação informada",
  qtd_itens: "Itens",
  qtd_containers: "Containers",
  valor_carga: "Valor da carga",
  modal: "Modal",
  arm_aerea_manual: "Armazenagem aérea informada",
};

/** Diferença realizado − provisionado em reais, sem erro de ponto flutuante. */
function diferenca(provisionado: number, realizado: number): number {
  return (Math.round(realizado * 100) - Math.round(provisionado * 100)) / 100;
}

function textoDiferenca(d: number): string {
  if (d === 0) return brl(0);
  return `${d > 0 ? "+" : ""}${brl(d)}`;
}

function classeDiferenca(d: number): string {
  if (d > 0) return " fita-dif-mais";
  if (d < 0) return " fita-dif-menos";
  return " fita-zero";
}

function rotuloVariavel(nome: string): string {
  if (nome.endsWith("_suspenso")) return "Suspenso (não paga)";
  if (nome.startsWith("aliq.")) return `Alíquota ${nome.slice(5).toUpperCase()}`;
  if (nome.startsWith("p.")) return nome.slice(2).replace(/_/g, " ");
  return ROTULOS_VARIAVEIS[nome] ?? nome.replace(/_/g, " ");
}

function valorVariavel(nome: string, valor: string): string {
  if (nome.endsWith("_suspenso")) return Number(valor) !== 0 ? "Sim" : "Não";
  if (nome.startsWith("aliq.") || nome.endsWith("percentual") || nome.includes("_pct")) return percentual(valor);
  if (nome.startsWith("qtd") || nome === "modal" || nome.endsWith("dia_corte")) return valor;
  return brl(valor);
}

interface Props {
  calculo: Calculo;
  competenciaPrincipal: string;
  animar?: boolean;
  /** Valor realizado dos itens já fechados (código do componente → valor); os ausentes estão pendentes. */
  realizado?: Record<string, string>;
}

/**
 * Fita de cálculo: a cascada do CIF até o total provisionado. Cada componente ocupa
 * o trecho da barra correspondente à sua parcela, a partir do acumulado anterior.
 */
export function FitaCalculo({ calculo, competenciaPrincipal, animar = false, realizado }: Props) {
  const base = calculo.itens.filter((i) => !i.compoe_provisao);
  const total = Number(calculo.total_provisionado) || 1;
  const comRealizado = Boolean(realizado && Object.keys(realizado).length > 0);
  // Itens ainda sem fatura ficam de fora do realizado e da diferença (não valem zero)
  const fechado = (codigo: string) => realizado?.[codigo] !== undefined;
  const valorRealizado = (codigo: string) => Number(realizado?.[codigo] ?? 0);
  /** Realizado e diferença somados apenas sobre os itens já fechados. */
  const somaFechados = (itens: CalculoItem[]) => {
    const fechados = itens.filter((i) => fechado(i.componente_codigo));
    const soma = fechados.reduce((s, i) => s + valorRealizado(i.componente_codigo), 0);
    const dif = fechados.reduce((s, i) => s + diferenca(Number(i.valor), valorRealizado(i.componente_codigo)), 0);
    return { algum: fechados.length > 0, todos: fechados.length === itens.length, soma, dif: Math.round(dif * 100) / 100 };
  };
  let acumulado = 0;
  let indice = 0;

  const despesa = calculo.itens.filter((i) => i.compoe_provisao);
  const geral = somaFechados(despesa);
  const totalComMargem = somaComMargem(despesa.map((i) => i.valor));
  const tituloMargem = `Provisionado + ${MARGEM_PROVISAO_PCT}% de margem, calculado item a item`;

  return (
    <div className={`fita${animar ? " fita-animada" : ""}${comRealizado ? " fita-com-realizado" : ""}`}>
      {base.map((item) => (
        <div className="fita-base" key={item.componente_codigo}>
          <div>
            <span className="fita-base-rotulo">Base de cálculo</span>
            <strong>{item.componente_nome}</strong>
            <code>{item.expressao}</code>
          </div>
          <span className="num fita-base-valor">{brl(item.valor)}</span>
        </div>
      ))}

      <div className="fita-colunas" aria-hidden="true">
        <span className="fita-col-vazia" />
        <span className="num">Provisionado</span>
        <span className="num" title={tituloMargem}>
          Com margem ({MARGEM_PROVISAO_PCT}%)
        </span>
        {comRealizado && (
          <>
            <span className="num">Realizado</span>
            <span className="num">Diferença</span>
          </>
        )}
      </div>

      {GRUPOS.map((g) => {
        const itens = calculo.itens.filter((i) => i.compoe_provisao && i.natureza === g.natureza);
        if (itens.length === 0) return null;
        const subtotal = itens.reduce((s, i) => s + Number(i.valor), 0);
        const grupo = somaFechados(itens);
        return (
          <section className="fita-grupo" key={g.natureza} aria-label={g.titulo}>
            <header className="fita-grupo-topo">
              <h3>{g.titulo}</h3>
              <span className="num">{brl(subtotal)}</span>
              <span className="num" title={tituloMargem}>
                {brl(somaComMargem(itens.map((i) => i.valor)))}
              </span>
              {comRealizado &&
                (grupo.algum ? (
                  <>
                    <span className="num" title={grupo.todos ? undefined : "Soma dos itens já fechados"}>
                      {brl(grupo.soma)}
                    </span>
                    <span className={`num${classeDiferenca(grupo.dif)}`}>{textoDiferenca(grupo.dif)}</span>
                  </>
                ) : (
                  <>
                    <span className="num fita-zero">–</span>
                    <span className="num fita-zero">–</span>
                  </>
                ))}
            </header>
            {itens.map((item) => {
              const valor = Number(item.valor);
              const inicio = (acumulado / total) * 100;
              const largura = (valor / total) * 100;
              acumulado += valor;
              const estilo = { "--inicio": `${inicio}%`, "--largura": `${largura}%`, "--i": indice++ } as CSSProperties;
              const outroMes = item.competencia !== competenciaPrincipal;
              return (
                <details className="fita-linha" key={item.componente_codigo} style={estilo}>
                  <summary>
                    <span className="fita-nome">
                      <span className="fita-nome-linha">
                        {item.componente_nome}
                        {item.memoria.suspenso && (
                          <span className="fita-suspenso" title="Suspenso: não paga neste processo">
                            Suspenso
                          </span>
                        )}
                      </span>
                      {outroMes && (
                        <span className="fita-competencia" title="Competência diferente do mês da IP">
                          provisiona em {mesCurto(item.competencia)}
                        </span>
                      )}
                    </span>
                    <span className="fita-trilha" aria-hidden="true">
                      <span className="fita-barra" />
                    </span>
                    <span className={`num fita-valor${valor === 0 ? " fita-zero" : ""}`}>
                      <span className="sr-only">Provisionado: </span>
                      {brl(item.valor)}
                    </span>
                    <span className={`num fita-margem${valor === 0 ? " fita-zero" : ""}`}>
                      <span className="sr-only">Com margem de {MARGEM_PROVISAO_PCT}%: </span>
                      {brl(comMargem(item.valor))}
                    </span>
                    {comRealizado &&
                      (fechado(item.componente_codigo) ? (
                        <>
                          <span className="num fita-valor">{brl(valorRealizado(item.componente_codigo))}</span>
                          <span
                            className={`num fita-valor${classeDiferenca(
                              diferenca(valor, valorRealizado(item.componente_codigo)),
                            )}`}
                          >
                            {textoDiferenca(diferenca(valor, valorRealizado(item.componente_codigo)))}
                          </span>
                        </>
                      ) : (
                        <>
                          <span className="num fita-valor fita-pendente">Pendente</span>
                          <span className="num fita-valor fita-zero">–</span>
                        </>
                      ))}
                  </summary>
                  <div className="fita-memoria">
                    <p>
                      <code>{item.expressao}</code>
                      {item.formula_versao && <span className="suave"> fórmula v{item.formula_versao}</span>}
                    </p>
                    <dl>
                      {Object.entries(item.memoria.variaveis).map(([nome, v]) => (
                        <div key={nome}>
                          <dt>{rotuloVariavel(nome)}</dt>
                          <dd>
                            <span className="num">{valorVariavel(nome, v)}</span>
                            {item.memoria.origens[nome] && <span className="suave">{item.memoria.origens[nome]}</span>}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                </details>
              );
            })}
          </section>
        );
      })}

      <div className="fita-total">
        <span>Total provisionado</span>
        <strong className="num">{brl(calculo.total_provisionado)}</strong>
      </div>
      <div className="fita-total fita-total-margem" title={tituloMargem}>
        <span>Com margem de {MARGEM_PROVISAO_PCT}%</span>
        <strong className="num">{brl(totalComMargem)}</strong>
      </div>
      {comRealizado && (
        <div className="fita-total fita-total-realizado">
          <span>{geral.todos ? "Total realizado" : "Realizado até agora"}</span>
          <strong className="num">{brl(geral.soma)}</strong>
          <em
            className={`num${classeDiferenca(geral.dif)}`}
            title={geral.todos ? "Realizado menos provisionado" : "Realizado menos provisionado, só dos itens já fechados"}
          >
            {textoDiferenca(geral.dif)}
          </em>
        </div>
      )}
    </div>
  );
}
