import { describe, expect, it } from "vitest";
import { diferencaProvisao, validarFechamentoItem } from "./fechamento";

describe("validarFechamentoItem", () => {
  it("aceita número e valor válidos", () => {
    const r = validarFechamentoItem(" FT-2026/0412 ", "1.234,56");
    expect(r.erros).toEqual({});
    expect(r.valor).toBe("1234.56");
  });
  it("aceita valor zero (imposto suspenso, por exemplo)", () => {
    expect(validarFechamentoItem("FT-1", "0").valor).toBe("0");
  });
  it("exige o número da fatura", () => {
    expect(validarFechamentoItem("   ", "10").erros.numero).toBe("Informe o número da fatura");
  });
  it("exige o valor", () => {
    const r = validarFechamentoItem("FT-1", "  ");
    expect(r.erros.valor).toBe("Informe o valor da fatura");
    expect(r.valor).toBeNull();
  });
  it("recusa negativo, texto que não é número e mais de 2 casas", () => {
    expect(validarFechamentoItem("FT-1", "-5,00").erros.valor).toBe("O valor não pode ser negativo");
    expect(validarFechamentoItem("FT-1", "12a").erros.valor).toBe("Valor inválido");
    expect(validarFechamentoItem("FT-1", "1,234").erros.valor).toBe("Use no máximo 2 casas decimais");
  });
  it("devolve erro do número e do valor ao mesmo tempo", () => {
    const r = validarFechamentoItem("", "x");
    expect(r.erros.numero).toBeDefined();
    expect(r.erros.valor).toBeDefined();
  });
});

describe("diferencaProvisao", () => {
  it("calcula fatura menos provisionado sem erro de ponto flutuante", () => {
    expect(diferencaProvisao("49799.04", "49919.54")).toBe(120.5);
    expect(diferencaProvisao("0.1", "0.3")).toBe(0.2);
  });
  it("fica negativa quando a fatura é menor", () => {
    expect(diferencaProvisao("1000.00", "900.00")).toBe(-100);
  });
});
