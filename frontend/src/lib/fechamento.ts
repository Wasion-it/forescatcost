// Validação do fechamento da despesa (número da fatura e valor realizado de cada item),
// espelhando as regras da API.

import { paraDecimal } from "./formato";

export interface DespesaInformada {
  componente_codigo: string;
  /** Valor realizado como string decimal ("1234.56"). */
  valor: string;
}

export interface ResultadoFechamento {
  erros: {
    numero?: string;
    /** Erro por item, indexado pelo código do componente. */
    itens: Record<string, string>;
    /** Erro do conjunto (ex.: total zerado). */
    total?: string;
  };
  /** Itens convertidos; null quando algum campo é inválido. */
  despesas: DespesaInformada[] | null;
  /** Soma dos itens válidos, string decimal com 2 casas. */
  total: string;
}

/**
 * @param numero número da fatura digitado
 * @param textos valor digitado por item, indexado pelo código do componente
 * @param codigos códigos dos itens que compõem a despesa (todos precisam ser informados; 0 vale)
 */
export function validarFechamento(
  numero: string,
  textos: Record<string, string>,
  codigos: string[],
): ResultadoFechamento {
  const erros: ResultadoFechamento["erros"] = { itens: {} };
  const despesas: DespesaInformada[] = [];
  let centavosTotal = 0;

  if (!numero.trim()) erros.numero = "Informe o número da fatura";

  for (const codigo of codigos) {
    try {
      const convertido = paraDecimal(textos[codigo] ?? "");
      if (convertido === null) erros.itens[codigo] = "Informe o valor";
      else if (Number(convertido) < 0) erros.itens[codigo] = "O valor não pode ser negativo";
      else if (!/^\d+(\.\d{1,2})?$/.test(convertido)) erros.itens[codigo] = "Use no máximo 2 casas decimais";
      else {
        despesas.push({ componente_codigo: codigo, valor: convertido });
        centavosTotal += Math.round(Number(convertido) * 100);
      }
    } catch {
      erros.itens[codigo] = "Valor inválido";
    }
  }

  const todosValidos = Object.keys(erros.itens).length === 0;
  if (todosValidos && centavosTotal <= 0) erros.total = "O total da despesa deve ser maior que zero";

  return {
    erros,
    despesas: todosValidos && !erros.total ? despesas : null,
    total: (centavosTotal / 100).toFixed(2),
  };
}

/** Fatura menos provisionado, em reais com 2 casas (positivo = fatura acima da provisão). */
export function diferencaProvisao(provisionado: string | number, fatura: string | number): number {
  const centavos = (v: string | number) => Math.round(Number(v) * 100);
  return (centavos(fatura) - centavos(provisionado)) / 100;
}
