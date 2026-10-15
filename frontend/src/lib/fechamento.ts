// Validação do fechamento da despesa (número e valor da fatura), espelhando as regras da API.

import { paraDecimal } from "./formato";

export interface ResultadoFechamento {
  erros: { numero?: string; valor?: string };
  /** Valor da fatura como string decimal ("61234.56"); null quando inválido. */
  valor: string | null;
}

export function validarFechamento(numero: string, valorTexto: string): ResultadoFechamento {
  const erros: ResultadoFechamento["erros"] = {};
  let valor: string | null = null;

  if (!numero.trim()) erros.numero = "Informe o número da fatura";

  try {
    const convertido = paraDecimal(valorTexto);
    if (convertido === null) erros.valor = "Informe o valor da fatura";
    else if (Number(convertido) <= 0) erros.valor = "O valor da fatura deve ser maior que zero";
    else valor = convertido;
  } catch {
    erros.valor = "Valor inválido";
  }

  return { erros, valor: erros.valor ? null : valor };
}

/** Fatura menos provisionado, em reais com 2 casas (positivo = fatura acima da provisão). */
export function diferencaProvisao(provisionado: string | number, fatura: string | number): number {
  const centavos = (v: string | number) => Math.round(Number(v) * 100);
  return (centavos(fatura) - centavos(provisionado)) / 100;
}
