import type { CSSProperties } from "react";
import { brl, mesCurto, percentual } from "../../lib/formato";
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
  siscomex: "Siscomex",
  qtd_itens: "Itens",
  qtd_containers: "Containers",
  valor_carga: "Valor da carga",
  modal: "Modal",
  arm_aerea_manual: "Armazenagem aérea informada",
};

function rotuloVariavel(nome: string): string {
  if (nome.startsWith("aliq.")) return `Alíquota ${nome.slice(5).toUpperCase()}`;
  if (nome.startsWith("p.")) return nome.slice(2).replace(/_/g, " ");
  return ROTULOS_VARIAVEIS[nome] ?? nome.replace(/_/g, " ");
}

function valorVariavel(nome: string, valor: string): string {
  if (nome.startsWith("aliq.") || nome.endsWith("percentual") || nome.includes("_pct")) return percentual(valor);
  if (nome.startsWith("qtd") || nome === "modal" || nome.endsWith("dia_corte")) return valor;
  return brl(valor);
}

interface Props {
  calculo: Calculo;
  competenciaPrincipal: string;
  animar?: boolean;
}

/**
 * Fita de cálculo: a cascada do CIF até o total provisionado. Cada componente ocupa
 * o trecho da barra correspondente à sua parcela, a partir do acumulado anterior.
 */
export function FitaCalculo({ calculo, competenciaPrincipal, animar = false }: Props) {
  const base = calculo.itens.filter((i) => !i.compoe_provisao);
  const total = Number(calculo.total_provisionado) || 1;
  let acumulado = 0;
  let indice = 0;

  return (
    <div className={`fita${animar ? " fita-animada" : ""}`}>
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

      {GRUPOS.map((g) => {
        const itens = calculo.itens.filter((i) => i.compoe_provisao && i.natureza === g.natureza);
        if (itens.length === 0) return null;
        const subtotal = itens.reduce((s, i) => s + Number(i.valor), 0);
        return (
          <section className="fita-grupo" key={g.natureza} aria-label={g.titulo}>
            <header className="fita-grupo-topo">
              <h3>{g.titulo}</h3>
              <span className="num">{brl(subtotal)}</span>
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
                      {item.componente_nome}
                      {outroMes && (
                        <span className="fita-competencia" title="Competência diferente do mês da declaração">
                          provisiona em {mesCurto(item.competencia)}
                        </span>
                      )}
                    </span>
                    <span className="fita-trilha" aria-hidden="true">
                      <span className="fita-barra" />
                    </span>
                    <span className={`num fita-valor${valor === 0 ? " fita-zero" : ""}`}>{brl(item.valor)}</span>
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
    </div>
  );
}
