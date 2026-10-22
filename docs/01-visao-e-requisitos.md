# 01. Visão e Requisitos Funcionais

## 1. Visão do produto

Para o PCM, que hoje calcula em planilhas a previsão de desembolso das importações, o Forecast de Importação é um sistema web que centraliza os processos, calcula automaticamente custos e impostos com regras parametrizáveis e versionadas, e entrega ao Financeiro provisões mensais confiáveis e rastreáveis.

### 1.1 Problema atual
- Cálculos manuais em planilhas, sujeitos a erro de fórmula e digitação.
- Sem histórico confiável: não se sabe com que taxas e percentuais uma previsão antiga foi feita.
- Informação dispersa, consolidação mensal manual para o Financeiro.
- Mudança de taxa ou percentual exige editar várias planilhas.

### 1.2 Objetivos e indicadores de sucesso

| Objetivo | Indicador | Meta sugerida |
|----------|-----------|---------------|
| Automatizar cálculos | % de processos calculados no sistema | 100% após o período paralelo |
| Reduzir erros | Divergência sistema × planilha validada | 0 na homologação (tolerância de R$ 0,01 por componente) |
| Agilizar a provisão | Tempo para gerar a provisão mensal | De horas para minutos |
| Rastreabilidade | Cálculos com memória e snapshot de parâmetros | 100% |
| Acurácia da previsão (fase 2) | Desvio previsto × realizado | Acompanhar e reduzir mês a mês |

### 1.3 Escopo

Dentro do escopo:
- Cadastro e ciclo de vida de processos de importação (Uso e Consumo, Industrialização).
- Motor de cálculo parametrizável (CIF, impostos, TCIF, transportes, armazenagens, despachante, frete).
- Versionamento de cálculos, simulação de cenários e histórico.
- Parâmetros com vigência (taxas, alíquotas, valores por transportadora/despachante/terminal).
- Provisões (mensal, por IP, por tipo) e exportação Excel.
- Dashboard, controle de acesso por perfil e auditoria.

Fora do escopo inicial (roadmap):
- Integração automática com TecWinWeb, ERP e PTAX/BCB.
- Registro de valores realizados (previsto × realizado).
- Workflow de aprovação de provisão.
- Detalhamento por item/NCM (adições).

## 2. Partes interessadas e perfis

| Perfil | Responsabilidades no sistema |
|--------|------------------------------|
| PCM | Cadastra e calcula importações, atualiza parâmetros operacionais, simula, consulta e emite relatórios |
| Financeiro | Consulta provisões, gera relatórios, acompanha custos, fecha a competência mensal |
| Administrador | Gerencia usuários e perfis, configura o sistema, mantém fórmulas e regras |
| Fiscal/Tributário (stakeholder) | Valida alíquotas e bases de cálculo dos impostos. Recomenda-se ter um perfil de consulta/validação |
| Auditoria interna (stakeholder) | Consulta trilha de auditoria (somente leitura) |

### 2.1 Matriz de permissões

Legenda: C = criar, L = ler, A = alterar, E = excluir/cancelar, X = executar

| Recurso | PCM | Financeiro | Admin |
|---------|-----|------------|-------|
| Importações | C L A E | L | L |
| Calcular / recalcular | X | – | – |
| Simular cenários | X | X | – |
| Histórico de cálculos | L | L | L |
| Parâmetros operacionais (taxas, transportadoras, despachantes, terminais) | C L A | L | C L A |
| Alíquotas de impostos | C L A | L | C L A |
| Fórmulas e regras de cálculo | L | L | C L A (com aprovação) |
| Provisões e relatórios | L X | L X | L |
| Fechamento da despesa do processo (`importacao:editar`) | X | – | – |
| Fechamento / reabertura de competência | – | X | X (reabertura) |
| Dashboard | L | L | L |
| Usuários e perfis | – | – | C L A E |
| Auditoria | L (próprios processos) | L | L |

As permissões devem ser granulares (ex.: `importacao:editar`, `parametro:alterar`), não codificadas por perfil. Assim os perfis podem ser recombinados sem alterar código.

## 3. Glossário

| Termo | Definição |
|-------|-----------|
| IP | Identificador da importação provisionada. Número livre (sem formato fiscal) que identifica a provisão do processo; no lugar da declaração aduaneira, que não é usada porque a provisão acontece antes dela. O significado de IP foi inferido e deve ser confirmado |
| CIF | Cost, Insurance and Freight. Aqui é o valor aduaneiro em R$ (Invoice + Frete), base de cálculo configurável. Não inclui a Taxa Siscomex |
| TCIF | Taxa de Controle de Incentivos Fiscais (SUFRAMA) |
| Taxa de liberação | Despesa de liberação da carga, informada em cada processo (varia por agente e por processo). Aparece separada do frete internacional |
| Suspensão (II/IPI) | Condição em que o Imposto de Importação ou o IPI não é pago. Controlada por parâmetro e, por padrão, vale para todos os tipos |
| Fechamento da despesa | Ação sobre um processo calculado: o PCM informa o valor e o número da fatura e o processo passa a FECHADO. Vale por processo e não é o fechamento de competência (mensal, do Financeiro, previsto para a R1) |
| Competência | Mês em que o valor entra na provisão financeira |
| Parâmetro com vigência | Valor válido de uma data inicial até uma data final, sem sobrescrever o histórico |
| Memória de cálculo | Registro de fórmula, variáveis e resultado de cada componente |

## 4. Regras de negócio

| ID | Regra |
|----|-------|
| RN01 | Conversão cambial: valor em BRL = valor na moeda × taxa informada no processo (Taxa USD, Taxa CNY). BRL tem taxa 1. Toda moeda usada no processo exige taxa. |
| RN02 | CIF = Invoice (BRL) + Frete (BRL), igual ao valor aduaneiro da DI. A Taxa Siscomex não entra no CIF nem na base de II, IPI, PIS e COFINS; entra só na base do ICMS. A fórmula é configurável e versionada. |
| RN03 | Alíquotas (II, IPI, PIS, COFINS, ICMS e outros) vêm de tabela parametrizada por tipo de importação, com origem "manual" ou "TecWin". Podem ser sobrescritas no processo, com justificativa obrigatória. O ICMS só se aplica a Uso e Consumo; Industrialização e Adicionar Ativo têm alíquota de ICMS 0. |
| RN04 | A ordem e a base de cálculo dos impostos seguem o pipeline definido no doc 04 e devem ser validadas pelo Fiscal antes do go-live. |
| RN05 | TCIF = R$ 45,00 × quantidade de itens + R$ 250,00 por IP (Lei 13.451/2017, art. 8º, § 2º; cada parcela é limitada a 1,5% do valor da mercadoria, limite ainda não aplicado). O valor de R$ 245,00 do levantamento inicial não tem respaldo legal e foi corrigido. |
| RN06 | Competência: se o dia da data da IP for maior que 15, o valor é provisionado no mês seguinte; senão, no mês da data da IP. O dia de corte é parametrizável e a regra é configurável por componente (hoje aplica-se à TCIF). |
| RN07 | Transporte local = valor por container × qtd. containers + 0,06% × valor da carga. Valores por transportadora, parametrizáveis. |
| RN09 | Armazenagem marítima, 1º período = percentual × CIF (0,92% no Chibatão e na Superterminais; 0,2% na Santos Brasil) + serviços portuários do terminal. No Chibatão (R$ 1.444,76) e na Superterminais (R$ 1.730,49) são valores fixos por processo, itemizados em seis parâmetros e sem multiplicar por container; na Santos Brasil são por container. Na Santos Brasil o total é dividido por 0,8575 (impostos embutidos). Períodos seguintes não entram na provisão. Percentuais, serviços e valor mínimo são parametrizáveis por terminal. |
| RN10 | Armazenagem aérea = 1,65% × CIF + maior valor entre (peso bruto × tarifa por kg) e o mínimo de R$ 20,41. Tarifa por kg: 0,25 em Manaus (0,0612 em São Paulo), parametrizável por terminal. O valor informado manualmente no processo prevalece sobre o cálculo. |
| RN11 | Despachante: R$ 715,00 por IP (Industrialização) e R$ 900,00 por IP (Uso e Consumo e Adicionar Ativo). Parametrizável por despachante e tipo. |
| RN12 | Frete internacional (componente de desembolso) = Frete (BRL). A Taxa de liberação é outro componente, com o valor informado em cada processo (campo valor_taxa_liberacao), pois varia por processo. |
| RN13 | Cada cálculo gera uma versão imutável. Só uma versão é a vigente por processo. Versões anteriores ficam no histórico. |
| RN14 | O cálculo usa os parâmetros vigentes na data de referência e grava um snapshot deles. Recalcular um processo antigo não muda a versão anterior. |
| RN15 | Simulações não alteram a versão vigente nem a provisão. |
| RN16 | Processos cancelados saem da provisão e mantêm o histórico. O cancelamento exige motivo. |
| RN17 | Competência fechada pelo Financeiro bloqueia alterações que afetem aquele mês. Reabertura só por perfil autorizado, com motivo e auditoria. |
| RN18 | Valores monetários usam aritmética decimal (nunca ponto flutuante). Cada componente é arredondado em 2 casas, meia para cima. A regra deve ser confirmada contra as planilhas atuais. |
| RN19 | O número da IP é único quando informado. É texto livre (até 30 caracteres), sem validação de formato fiscal. |
| RN21 | II e IPI são suspensos (não pagos) por padrão, controlados pelos parâmetros ii_suspenso e ipi_suspenso (1 = suspenso, 0 = cobra), com exceção possível por tipo de importação e vigência. Suspenso, o valor é 0,00 e o ICMS não os inclui na base. A memória de cálculo marca o item como suspenso. |
| RN22 | A Taxa Siscomex é um componente do grupo de impostos e compõe a provisão. O valor fica fora do CIF e é somado só na base do ICMS (RN02). Se o processo não informar o valor, o sistema calcula pela tabela oficial (valor por DI + faixas por adição, adições estimadas por qtd_itens); valor informado maior que zero prevalece (doc 04). |
| RN23 | Fechamento da despesa (por processo): só processo CALCULADO e sem recálculo pendente pode ser fechado. O fechamento exige o valor realizado de cada item que compõe a despesa (zero ou mais, 2 casas, todos os itens do cálculo vigente que compõem a provisão), com total maior que zero, e o número da fatura (texto, até 60 caracteres, sem espaços nas pontas). O valor da fatura do processo é a soma dos itens. Registra data/hora e usuário. Processo FECHADO não pode ser editado, recalculado nem cancelado e continua somando na provisão. A regra é garantida também por constraint no banco. Não substitui o fechamento de competência (RN17, R1). |
| RN20 | Cada componente indica se compõe o total de desembolso provisionado. Bases de cálculo, como o CIF, não somam no total, para evitar dupla contagem (o frete, por exemplo, entra no CIF e também no componente Frete Internacional). |

## 5. Requisitos funcionais

### Importações
- RF01: Cadastrar processo com os dados de entrada (IP, data da IP, tipo, invoice e moeda, frete e moeda, itens, containers, taxas USD/CNY, Siscomex, pesos, observações).
- RF02: Permitir processo sem IP (previsão antecipada), usando data prevista para competência.
- RF03: Editar processo nos status permitidos, com controle de concorrência (versão otimista).
- RF04: Consultar com filtros (período, tipo, status, IP, transportadora, despachante) e paginação.
- RF05: Cancelar processo com motivo.
- RF05a: Fechar a despesa do processo calculado informando valor e número da fatura (RN23).
- RF06: Vincular transportadora, despachante, terminal e modal (marítimo/aéreo).

### Cálculo
- RF07: Calcular e recalcular processo, gerando nova versão com memória de cálculo.
- RF08: Exibir memória de cálculo por componente (fórmula, variáveis, resultado, competência).
- RF09: Simular cenários alterando taxas de câmbio, alíquotas e parâmetros, sem efeito na provisão.
- RF10: Comparar versões e cenários lado a lado.
- RF11: Recalcular em lote os processos abertos após mudança de parâmetro, com pré-visualização do impacto.

### Parâmetros
- RF12: Manter parâmetros gerais com vigência (TCIF, percentuais, dia de corte etc.).
- RF13: Manter alíquotas de impostos por tipo de importação, com origem e vigência.
- RF14: Manter transportadoras (valor por container, percentuais), despachantes (honorários por tipo) e terminais (tabelas de armazenagem).
- RF15: Manter componentes de custo e fórmulas (Admin), com validação, teste e publicação versionada.
- RF16: Cadastrar novos impostos/componentes ("outros impostos parametrizáveis").

### Financeiro
- RF17: Provisão mensal consolidada (competência × componente).
- RF18: Provisão por IP/processo.
- RF19: Provisão por tipo de importação.
- RF20: Exportar relatórios para Excel (.xlsx) com filtros aplicados e data/usuário de emissão.
- RF21: Fechar e reabrir competência mensal (snapshot da provisão no fechamento).

### Dashboard
- RF22: Importações por mês, valor provisionado, valor por tipo, evolução mensal e indicadores (ticket médio, % de impostos sobre o CIF, custo por container).

### Administração e auditoria
- RF23: Gerir usuários, perfis e permissões (preferencialmente integrado ao AD/Entra ID).
- RF24: Registrar auditoria de toda criação, alteração e exclusão (quem, quando, antes/depois, origem).
- RF25: Consultar trilha de auditoria por entidade, usuário e período.
- RF26: Configurações do sistema (moedas, tipos de importação, dia de corte, arredondamento).

## 6. Requisitos não funcionais

| ID | Categoria | Requisito |
|----|-----------|-----------|
| RNF01 | Usabilidade | Interface web responsiva (desktop prioritário, tablet funcional), em pt-BR, formatos BRL e datas dd/mm/aaaa |
| RNF02 | Acessibilidade | Seguir WCAG 2.1 AA como referência (navegação por teclado, contraste, rótulos). A conformidade exige teste manual |
| RNF03 | Segurança | SSO corporativo (OIDC), RBAC por permissão, HTTPS, OWASP ASVS nível 2 como referência |
| RNF04 | Auditoria | Trilha imutável (append-only), retenção mínima de 5 anos (alinhar com Compliance) |
| RNF05 | Precisão | `NUMERIC` no banco e `Decimal` no backend. Nenhum cálculo monetário em float |
| RNF06 | Desempenho | Cálculo de um processo < 1 s; relatório mensal < 5 s para 12 meses de dados |
| RNF07 | Disponibilidade | Horário comercial, 99,5%. Backup diário + PITR. RPO ≤ 24 h, RTO ≤ 4 h |
| RNF08 | Escalabilidade | Monolito modular com fronteiras claras, stateless, horizontalmente escalável |
| RNF09 | Integração | API REST documentada (OpenAPI). Adaptadores isolados para TecWin, ERP e PTAX |
| RNF10 | Manutenibilidade | Cobertura de testes ≥ 90% no motor de cálculo, ≥ 70% no geral. Lint e tipagem no CI |
| RNF11 | Observabilidade | Logs estruturados com correlation-id, métricas e alertas de erro |
| RNF12 | LGPD | Dados pessoais mínimos (apenas usuários). Base legal: execução de contrato/legítimo interesse |

## 7. Pontos em aberto (validar com o negócio antes do desenvolvimento)

1. Siscomex no CIF: resolvido. Conferido com a DI do IMP-00010, o CIF é o valor aduaneiro sem a Taxa Siscomex, que passou a entrar só na base do ICMS (RN02).
2. Seguro internacional: não está nos dados de entrada. Deve ser incluído?
3. Modal: a armazenagem depende de marítimo × aéreo, mas o modal não está nos dados de entrada. Proposta: incluir.
4. "Valor da carga" (transportes): é o CIF em BRL, a invoice em BRL ou outro valor?
5. Dia 15: "após o dia 15" significa dia ≥ 16? A regra vale só para a TCIF ou para outros componentes?
6. Composição do total provisionado: o valor da invoice (pagamento ao fornecedor via câmbio) entra na provisão ou só custos e impostos? O frete é pago pela empresa em todos os Incoterms?
7. Armazenagem marítima: há períodos adicionais, valor mínimo, valores fixos (Chibatão)? Como estimar a quantidade de períodos?
8. Armazenagem aérea: fórmula a detalhar.
9. Benefícios ZFM: como TCIF e Chibatão indicam operação em Manaus, os tratamentos de II/IPI/PIS/COFINS/ICMS diferem entre Industrialização e Uso e Consumo. Confirmar a tabela de alíquotas efetivas por tipo.
10. Alíquotas por NCM: hoje há uma alíquota por processo? Com itens de NCMs diferentes, será necessário modelar adições/itens (previsto no modelo como opcional).
11. IP: resolvida por interpretação. IP foi tratada como o identificador livre da importação provisionada, sem declaração aduaneira. Confirmar o significado com o usuário.
12. Reforma Tributária (CBS/IBS): definir com o Fiscal como e quando provisionar os novos tributos (o sistema já suporta novos impostos parametrizáveis).
13. Taxa de liberação: resolvida. O valor é variável e informado em cada processo.
14. Data de referência dos parâmetros: data do cálculo, data da IP ou data prevista de chegada?
