// Margem de segurança sobre a provisão ("gordura"): o valor pedido na aprovação fica 20% acima do
// provisionado em cada item, para a fatura não exigir nova aprovação se vier um pouco maior.

// Mesmo valor da planilha exportada (backend/app/modules/importacoes/excel.py).
export const MARGEM_PROVISAO_PCT = 20;

/** Valor com a margem, arredondado a centavos (aplicado item a item). */
export function comMargem(valor: string | number): number {
  const centavos = Math.round(Number(valor) * 100);
  return Math.round((centavos * (100 + MARGEM_PROVISAO_PCT)) / 100) / 100;
}

/** Soma dos valores com margem de cada item (soma dos arredondados, como na aprovação). */
export function somaComMargem(valores: (string | number)[]): number {
  const centavos = valores.reduce<number>((s, v) => s + Math.round(comMargem(v) * 100), 0);
  return centavos / 100;
}
