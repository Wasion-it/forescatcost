import { describe, expect, it } from "vitest";
import { diferencaProvisao, validarFechamento } from "./fechamento";

describe("validarFechamento", () => {
  it("aceita número e valor válidos", () => {
    const r = validarFechamento(" FT-2026/0412 ", "61.234,56");
    expect(r.erros).toEqual({});
    expect(r.valor).toBe("61234.56");
  });
  it("exige o número da fatura", () => {
    expect(validarFechamento("   ", "10").erros.numero).toBe("Informe o número da fatura");
  });
  it("exige o valor da fatura", () => {
    const r = validarFechamento("FT-1", "  ");
    expect(r.erros.valor).toBe("Informe o valor da fatura");
    expect(r.valor).toBeNull();
  });
  it("recusa valor zero ou negativo", () => {
    expect(validarFechamento("FT-1", "0").erros.valor).toBe("O valor da fatura deve ser maior que zero");
    expect(validarFechamento("FT-1", "-5,00").erros.valor).toBe("O valor da fatura deve ser maior que zero");
  });
  it("recusa texto que não é número", () => {
    expect(validarFechamento("FT-1", "12a").erros.valor).toBe("Valor inválido");
  });
  it("devolve os dois erros ao mesmo tempo", () => {
    const r = validarFechamento("", "0");
    expect(Object.keys(r.erros).sort()).toEqual(["numero", "valor"]);
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
