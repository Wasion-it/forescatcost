# 04. Motor de Cálculo

O motor é o núcleo do sistema e o maior risco de negócio. Ele deve ser um módulo de domínio puro (sem banco, sem HTTP): recebe entradas + parâmetros e devolve resultados + memória. Isso o torna determinístico, testável e reutilizável para cálculo oficial, simulação e recálculo em lote.

## 1. Pipeline

Os componentes formam um grafo de dependências. O motor ordena topologicamente as fórmulas e rejeita ciclos no momento da publicação.

```mermaid
flowchart TD
    E[Entradas do processo] --> CONV[Conversão cambial<br/>invoice_brl, frete_brl, seguro_brl]
    CONV --> CIF[CIF]
    CIF --> II[II]
    CIF --> PIS[PIS]
    CIF --> COFINS[COFINS]
    II --> IPI[IPI]
    E --> SISC[Taxa Siscomex]
    CIF & II & IPI & PIS & COFINS --> ICMS[ICMS por dentro]
    E --> TCIF[TCIF]
    CIF --> TL[Transporte local]
    CIF --> AM[Armazenagem marítima]
    CIF --> AA[Armazenagem aérea]
    E --> DESP[Despachante]
    CONV --> FI[Frete internacional]
    E --> LIB[Taxa de liberação]
    SISC & ICMS & TCIF & TL & AM & AA & DESP & FI & LIB --> TOT[Total provisionado<br/>soma dos itens com compoe_provisao]
    TOT --> COMP[Atribuição de competência]
```

## 2. Dicionário de variáveis (lista branca)

| Variável | Origem |
|----------|--------|
| `invoice_brl`, `frete_brl`, `seguro_brl` | Valor × taxa da moeda (RN01) |
| `valor_invoice`, `valor_frete`, `taxa_usd`, `taxa_cny` | Entrada |
| `siscomex`, `valor_taxa_liberacao`, `qtd_itens`, `qtd_containers`, `peso_bruto`, `peso_liquido` | Entrada |
| `modal`, `tipo_importacao` | Entrada (texto, para condições) |
| `cif`, `ii`, `ipi`, `pis`, `cofins`, `icms`, ... | Resultado de componentes anteriores |
| `valor_carga` | Alias configurável (padrão: `cif`), pendente de confirmação |
| `aliq.<imposto>` | Alíquota vigente (ou override do processo) |
| `p.<chave>` | Parâmetro vigente resolvido no escopo do processo (tipo, transportadora, despachante, terminal) |

Funções permitidas: `min`, `max`, `round`, `se(cond, a, b)`, `arred(x, casas)`. Nada além disso.

## 3. Fórmulas padrão (versão 1)

As fórmulas de impostos são uma proposta baseada na sistemática usual de importação e precisam ser validadas pelo Fiscal, especialmente por causa dos benefícios da ZFM por tipo de importação.

| Componente | Expressão padrão | Provisão | Competência |
|------------|------------------|----------|-------------|
| CIF | `invoice_brl + frete_brl + siscomex` | Não (base) | – |
| II | `se(p.ii_suspenso == 1, 0, cif * aliq.ii)` | Sim | Mês da IP |
| IPI | `se(p.ipi_suspenso == 1, 0, (cif + ii) * aliq.ipi)` | Sim | Mês da IP |
| PIS | `cif * aliq.pis` | Sim | Mês da IP |
| COFINS | `cif * aliq.cofins` | Sim | Mês da IP |
| Taxa Siscomex | `siscomex` | Sim | Mês da IP |
| ICMS | `(cif + ii + ipi + pis + cofins) / (1 - aliq.icms) * aliq.icms` | Sim | Mês da IP |
| TCIF | `qtd_itens * p.tcif_valor_item + p.tcif_valor_ip` | Sim | Corte dia 15 |
| Transporte local | `qtd_containers * p.tl_valor_container + valor_carga * p.tl_percentual` | Sim | Mês da IP |
| Armazenagem marítima | `se(modal == 'MARITIMO', max(cif * p.arm_mar_pct_periodo1, p.arm_mar_minimo), 0)` | Sim | Mês da IP |
| Armazenagem aérea | Pendente. Até a definição: `p.arm_aerea_valor_manual` | Sim | Mês da IP |
| Despachante | `p.despachante_honorario_ip` | Sim | Mês da IP |
| Frete internacional | `frete_brl` | Sim | Mês da IP |
| Taxa de liberação | `valor_taxa_liberacao` (informada em cada processo) | Sim | Mês da IP |

Valores iniciais dos parâmetros:

| Chave | Escopo | Valor inicial |
|-------|--------|---------------|
| `tcif_valor_item` | Global | 45,00 |
| `tcif_valor_ip` | Global | 245,00 |
| `competencia_dia_corte` | Global | 15 |
| `tl_valor_container` | Transportadora | a cadastrar |
| `tl_percentual` | Transportadora | 0,0006 (0,06%) |
| `arm_mar_pct_periodo1` | Terminal | 0,0092 (0,92%) |
| `arm_mar_minimo` | Terminal | 0 (a confirmar) |
| `despachante_honorario_ip` | Despachante × tipo | 715,00 (Industrialização) / 900,00 (Uso e Consumo e Adicionar Ativo) |
| `ii_suspenso` | Tipo de importação | 1 (suspenso, não paga). Booleano: 0 ou 1 |
| `ipi_suspenso` | Tipo de importação | 1 (suspenso, não paga). Booleano: 0 ou 1 |

Atenção a estes pontos:
- Como o CIF atual já inclui o Siscomex, a fórmula do ICMS não soma o Siscomex de novo. Se o Fiscal decidir tirar o Siscomex do CIF, as duas fórmulas mudam juntas (nova versão de ambas). O componente Taxa Siscomex (grupo de impostos) mostra o valor e compõe a provisão.
- Com II e IPI suspensos (padrão), os dois valem 0,00 e o ICMS parte de CIF + PIS + COFINS. Com `ii_suspenso` ou `ipi_suspenso` = 0 para um tipo, a fórmula volta a calcular o imposto e o ICMS o inclui. A memória do item guarda `suspenso: true` quando a suspensão se aplica.
- A taxa de liberação é um componente próprio e vem do processo, nunca de um parâmetro fixo.
- AFRMM e transporte secundário foram removidos. Os componentes ficam inativos no banco só para preservar o histórico de cálculos antigos.
- O frete aparece no CIF (base) e no componente "Frete internacional" (desembolso). Por isso o total soma apenas itens com `compoe_provisao = true` (RN20).

## 4. Regra de competência

```python
def competencia(data_ref: date, regra: RegraCompetencia, dia_corte: int) -> date:
    """Retorna o 1º dia do mês de competência."""
    inicio_mes = data_ref.replace(day=1)
    if regra is RegraCompetencia.CORTE_DIA and data_ref.day > dia_corte:
        return inicio_mes + relativedelta(months=1)
    return inicio_mes
```

`data_ref` = data da IP. Se ainda não houver IP, usa a data prevista. Isso define a competência inicial. Quando a IP for informada, o recálculo pode mover a competência, e a mudança fica visível na comparação de versões.

## 5. Avaliação segura de fórmulas

- Nunca usar `eval`/`exec` do Python.
- Usar um avaliador de expressões restrito: parser AST com lista branca de nós (números, nomes, operadores aritméticos, comparação, chamadas às funções permitidas) ou uma biblioteca como `simpleeval`, configurada sem atributos nem funções além da lista.
- Todos os números entram como `Decimal`. O contexto decimal usa precisão de 28 dígitos e `ROUND_HALF_UP`.
- Validação na publicação: sintaxe, variáveis existentes, ausência de ciclos e execução dos casos de teste do componente.

## 6. Estratégia: fórmula × código

| Abordagem | Uso |
|-----------|-----|
| Expressão parametrizada (tabela `formula`) | CIF, impostos, TCIF, transportes, despachante, frete. Cobre o requisito "fórmula pode ser alterada" |
| Estratégia em código + parâmetros | Casos com lógica de tabela/faixas (armazenagem por períodos e faixas de peso, regras do Chibatão). Plugável via registro de estratégias, referenciada por `componente_custo.estrategia` |

Um editor de fórmulas genérico demais vira uma "planilha dentro do sistema" e perde a governança. A combinação acima mantém flexibilidade com testes.

## 7. Memória de cálculo

Cada `calculo_item.memoria` guarda o suficiente para reproduzir e explicar o valor:

```json
{
  "componente": "ICMS",
  "formula_versao": 1,
  "expressao": "(cif + ii + ipi + pis + cofins) / (1 - aliq.icms) * aliq.icms",
  "variaveis": {
    "cif": "152340.55", "ii": "0.00", "ipi": "0.00",
    "pis": "3199.15", "cofins": "14700.86",
    "aliq.icms": "0.180000"
  },
  "origem_aliquota": {"aliq.icms": "TABELA vigente desde 2026-01-01"},
  "valor_bruto": "37639.9668...",
  "valor": "37639.97",
  "competencia": "2026-10-01"
}
```

(Valores ilustrativos.)

O `calculo.hash_integridade` (SHA-256 das entradas, parâmetros e resultados) permite detectar adulteração.

## 8. Estratégia de testes do motor

1. Golden cases: coletar de 20 a 30 processos reais já calculados nas planilhas (os dois tipos, os dois modais, IP antes e depois do dia 15, moedas USD e CNY). Eles viram testes automatizados com tolerância de R$ 0,01 por componente.
2. Testes unitários por componente e pela regra de competência (dias 15, 16, 31, virada de ano).
3. Testes de propriedade (Hypothesis): valores nunca negativos, monotonicidade (mais containers não reduz o custo), determinismo.
4. Período paralelo: 1 a 2 ciclos de fechamento rodando sistema e planilha juntos, com relatório de divergências.
