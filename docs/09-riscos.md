# 09. Riscos do Projeto

Escala: P = probabilidade, I = impacto (B baixo, M médio, A alto).

| ID | Risco | P | I | Mitigação | Responsável |
|----|-------|---|---|-----------|-------------|
| R01 | Regras de cálculo incompletas ou ambíguas (valor da carga, armazenagem, Siscomex no CIF, dia 15) | A | A | Fase 0 dedicada, lista de pontos em aberto com dono e prazo, golden cases assinados pelo PCM | PO |
| R02 | Planilhas atuais contêm erros e o sistema "replica o erro" ou diverge sem explicação | M | A | Período paralelo com relatório de divergências, decisão documentada sobre qual valor está correto | PCM + Fiscal |
| R03 | Tributação da ZFM e benefícios por tipo de importação mal parametrizados | M | A | Validação formal das alíquotas efetivas pelo Fiscal, override por processo com justificativa | Fiscal |
| R04 | Reforma Tributária (CBS/IBS e transição de PIS/COFINS/ICMS) muda bases e tributos durante o projeto | A | M | Impostos e fórmulas parametrizáveis com vigência, item de backlog dedicado (B34), acompanhamento com o Fiscal | Fiscal + PO |
| R05 | Mudança no formato ou no momento da declaração aduaneira real não afeta a provisão, que usa a IP | A | M | IP em texto livre (`numero_ip`), sem máscara fiscal; competência baseada em data configurável (`data_ip` ou data prevista) | Arquiteto |
| R06 | Flexibilidade excessiva de fórmulas gera erros e perda de controle | M | A | Avaliador restrito, testes obrigatórios na publicação, aprovação por 4 olhos, versionamento | Admin + Arquiteto |
| R07 | Erros de arredondamento ou uso de float | M | M | `Decimal`/`NUMERIC` ponta a ponta, serialização como string, testes de propriedade | Tech lead |
| R08 | Baixa adoção: usuários continuam na planilha | M | A | Usuários-chave no desenvolvimento, UX focada em velocidade (colar do Excel, valores padrão), desligamento formal da planilha após o aceite | Patrocinador |
| R09 | Dependência de pessoas-chave do PCM que detêm o conhecimento das planilhas | A | M | Documentar regras (doc 04), sessões gravadas, golden cases versionados no repositório | PO |
| R10 | Integração TecWinWeb sem API disponível ou com restrições de licença | M | M | Entrada manual no MVP, adaptador isolado, verificar contrato/licença cedo | TI |
| R11 | Integração com ERP mais complexa que o previsto | M | M | Deixar para R3, contrato de interface definido cedo, filas/arquivos como alternativa | TI |
| R12 | Alteração de dados de mês já reportado ao Financeiro | M | A | Fechamento de competência (R1). No MVP: export mensal arquivado como evidência + auditoria | Financeiro |
| R13 | Segurança: acesso indevido a dados financeiros | B | A | SSO, RBAC granular, auditoria, revisões de acesso periódicas, OWASP no CI | Segurança da Informação |
| R14 | Escopo crescendo (dashboard, BI, ERP) antes do MVP estabilizar | A | M | MVP com critério de saída claro, backlog priorizado com o patrocinador, change control | PO |
| R15 | Disponibilidade limitada dos usuários de negócio para homologação | M | M | Agenda de homologação acordada no kick-off, sprints com demo quinzenal | Patrocinador |
| R16 | Time com pouca experiência em FastAPI/React | M | M | Templates e padrões no início (B01), revisão de código, pareamento, ADRs | Tech lead |
| R17 | Câmbio informado manualmente errado (ex.: troca USD/CNY) | M | M | Validação de faixa contra a última cotação conhecida (alerta se variar mais de X%), PTAX automático em R2 | PO |
