// Formatação e conversão pt-BR. Valores monetários trafegam como string decimal.

const moedaBRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const numero2 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const compacto = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });

export function brl(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "–";
  return moedaBRL.format(Number(valor));
}

export function decimal2(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "–";
  return numero2.format(Number(valor));
}

export function brlCompacto(valor: string | number): string {
  return `R$ ${compacto.format(Number(valor))}`;
}

/** Percentual a partir de fração ("0.0092" → "0,92%"). */
export function percentual(valor: string | number | null | undefined, casas = 2): string {
  if (valor === null || valor === undefined || valor === "") return "–";
  const n = Number(valor) * 100;
  return `${n.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: casas + 2 })}%`;
}

export function data(iso: string | null | undefined): string {
  if (!iso) return "–";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
}

export function dataHora(iso: string | null | undefined): string {
  if (!iso) return "–";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const MESES_LONGOS = [
  "janeiro", "fevereiro", "março", "abril", "maio", "junho",
  "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
];

/** "2026-10-01" → "out/26" */
export function mesCurto(iso: string): string {
  const [a, m] = iso.split("-");
  return `${MESES[Number(m) - 1]}/${a.slice(2)}`;
}

/** "2026-10-01" → "outubro de 2026" */
export function mesLongo(iso: string): string {
  const [a, m] = iso.split("-");
  return `${MESES_LONGOS[Number(m) - 1]} de ${a}`;
}

/**
 * Converte texto digitado (aceita "1.234,56", "1234,56" e "1234.56") em string decimal "1234.56".
 * Retorna null se vazio e lança erro se inválido.
 */
export function paraDecimal(texto: string): string | null {
  const limpo = texto.trim().replace(/\s|R\$/g, "");
  if (!limpo) return null;
  let normalizado = limpo;
  if (limpo.includes(",")) {
    normalizado = limpo.replace(/\./g, "").replace(",", ".");
  } else if ((limpo.match(/\./g) ?? []).length > 1) {
    normalizado = limpo.replace(/\./g, "");
  }
  if (!/^-?\d+(\.\d+)?$/.test(normalizado)) throw new Error("Número inválido");
  return normalizado;
}

/** Exibe uma string decimal para edição em pt-BR ("1234.5" → "1.234,50"). */
export function paraEdicao(valor: string | null | undefined, casas = 2): string {
  if (valor === null || valor === undefined || valor === "") return "";
  return Number(valor).toLocaleString("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: Math.max(casas, 6),
  });
}

export function primeiroDiaMes(d: Date, deslocamento = 0): string {
  const alvo = new Date(d.getFullYear(), d.getMonth() + deslocamento, 1);
  return `${alvo.getFullYear()}-${String(alvo.getMonth() + 1).padStart(2, "0")}-01`;
}

/** Desloca a vírgula sem aritmética de ponto flutuante: "0,92" (%) → "0.0092". */
export function percentualParaFracao(texto: string): string | null {
  const d = paraDecimal(texto);
  if (d === null) return null;
  const negativo = d.startsWith("-");
  const [inteiro, frac = ""] = d.replace("-", "").split(".");
  const digitos = inteiro.padStart(3, "0") + frac;
  const pos = digitos.length - frac.length - 2;
  const resultado = `${digitos.slice(0, pos)}.${digitos.slice(pos)}`.replace(/^0+(?=\d)/, "").replace(/\.?0+$/, "");
  return (negativo ? "-" : "") + (resultado || "0");
}
