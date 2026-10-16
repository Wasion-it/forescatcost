import { describe, expect, it } from "vitest";
import { diferencaProvisao, validarFechamento } from "./fechamento";

describe("validarFechamento", () => {
  const codigos = ["II", "IPI", "ICMS"];

  it("aceita número e valores válidos, somando os itens", () => {
    const r = validarFechamento(" FT-2026/0412 ", { II: "1.234,56", IPI: "0", ICMS: "100,10" }, codigos);
    expect(r.erros).toEqual({ itens: {} });
    expect(r.despesas).toEqual([
      { componente_codigo: "II", valor: "1234.56" },
      { componente_codigo: "IPI", valor: "0" },
      { componente_codigo: "ICMS", valor: "100.10" },
    ]);
    expect(r.total).toBe("1334.66");
  });
  it("exige o número da fatura", () => {
    expect(validarFechamento("   ", { II: "1", IPI: "1", ICMS: "1" }, codigos).erros.numero).toBe(
      "Informe o número da fatura",
    );
  });
  it("exige o valor de cada item, indicando qual falta", () => {
    const r = validarFechamento("FT-1", { II: "10", IPI: "  " }, codigos);
    expect(r.erros.itens).toEqual({ IPI: "Informe o valor", ICMS: "Informe o valor" });
    expect(r.despesas).toBeNull();
  });
  it("aceita zero em um item, mas recusa negativo", () => {
    expect(validarFechamento("FT-1", { II: "0", IPI: "5", ICMS: "5" }, codigos).despesas).not.toBeNull();
    const r = validarFechamento("FT-1", { II: "-5,00", IPI: "5", ICMS: "5" }, codigos);
    expect(r.erros.itens.II).toBe("O valor não pode ser negativo");
  });
  it("recusa texto que não é número e mais de 2 casas", () => {
    const r = validarFechamento("FT-1", { II: "12a", IPI: "1,234", ICMS: "1" }, codigos);
    expect(r.erros.itens.II).toBe("Valor inválido");
    expect(r.erros.itens.IPI).toBe("Use no máximo 2 casas decimais");
  });
  it("recusa total zerado", () => {
    const r = validarFechamento("FT-1", { II: "0", IPI: "0,00", ICMS: "0" }, codigos);
    expect(r.erros.total).toBe("O total da despesa deve ser maior que zero");
    expect(r.despesas).toBeNull();
  });
  it("devolve erro do número e dos itens ao mesmo tempo", () => {
    const r = validarFechamento("", { II: "x" }, codigos);
    expect(r.erros.numero).toBeDefined();
    expect(Object.keys(r.erros.itens).sort()).toEqual(["ICMS", "II", "IPI"]);
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
