import { describe, expect, it } from "vitest";
import { data, mesCurto, paraDecimal, percentual, percentualParaFracao } from "./formato";

describe("percentualParaFracao", () => {
  it("converte sem erro de ponto flutuante", () => {
    expect(percentualParaFracao("0,92")).toBe("0.0092");
    expect(percentualParaFracao("0,06")).toBe("0.0006");
    expect(percentualParaFracao("18")).toBe("0.18");
    expect(percentualParaFracao("9,65")).toBe("0.0965");
    expect(percentualParaFracao("100")).toBe("1");
    expect(percentualParaFracao("0")).toBe("0");
  });
});

describe("paraDecimal", () => {
  it("aceita formato brasileiro", () => {
    expect(paraDecimal("1.234,56")).toBe("1234.56");
    expect(paraDecimal("1234,5")).toBe("1234.5");
  });
  it("aceita ponto decimal colado de sistemas", () => {
    expect(paraDecimal("1234.56")).toBe("1234.56");
  });
  it("trata vários pontos como milhar", () => {
    expect(paraDecimal("1.234.567")).toBe("1234567");
  });
  it("vazio vira null e texto inválido gera erro", () => {
    expect(paraDecimal("  ")).toBeNull();
    expect(() => paraDecimal("12a")).toThrow();
  });
});

describe("exibição", () => {
  it("formata datas e meses", () => {
    expect(data("2026-10-16")).toBe("16/10/2026");
    expect(mesCurto("2026-11-01")).toBe("nov/26");
  });
  it("formata percentuais a partir de fração", () => {
    expect(percentual("0.0092")).toBe("0,92%");
    expect(percentual("0.18")).toBe("18%");
  });
});
