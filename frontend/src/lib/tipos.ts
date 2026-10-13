// Contratos da API (espelham os schemas do backend). Decimais chegam como string.

export type Decimal = string;
export type Id = string;

export interface Perfil {
  id: Id;
  codigo: string;
  nome: string;
}

export interface Usuario {
  id: Id;
  nome: string;
  email: string;
  ativo: boolean;
  ultimo_acesso: string | null;
  perfis: Perfil[];
}

export interface Sessao {
  token: string;
  expira_em_segundos: number;
  usuario: Usuario;
  permissoes: string[];
}

export interface TipoImportacao {
  id: Id;
  codigo: string;
  nome: string;
  ativo?: boolean;
}

export interface RefNome {
  id: Id;
  nome: string;
}

export interface Transportadora extends RefNome {
  cnpj: string | null;
  tipo_servico: "LOCAL" | "SECUNDARIO" | "AMBOS";
  ativo: boolean;
}

export interface Despachante extends RefNome {
  cnpj: string | null;
  ativo: boolean;
}

export interface Terminal extends RefNome {
  modal: "MARITIMO" | "AEREO";
  ativo: boolean;
}

export type StatusImportacao = "RASCUNHO" | "CALCULADO" | "CANCELADO";

export interface ImportacaoEntrada {
  tipo_declaracao: "DI" | "DUIMP";
  numero_declaracao: string | null;
  data_declaracao: string | null;
  data_prevista: string | null;
  tipo_importacao_id: Id;
  modal: "MARITIMO" | "AEREO";
  valor_invoice: Decimal;
  moeda_invoice: string;
  valor_frete: Decimal;
  moeda_frete: string;
  qtd_itens: number;
  qtd_containers: number;
  taxa_usd: Decimal | null;
  taxa_cny: Decimal | null;
  valor_siscomex: Decimal;
  peso_bruto_kg: Decimal;
  peso_liquido_kg: Decimal;
  valor_armazenagem_aerea: Decimal;
  transportadora_local_id: Id | null;
  transportadora_secundaria_id: Id | null;
  despachante_id: Id | null;
  terminal_id: Id | null;
  observacoes: string | null;
}

export interface CalculoItem {
  componente_codigo: string;
  componente_nome: string;
  natureza: "BASE" | "IMPOSTO" | "TAXA" | "LOGISTICA" | "SERVICO";
  expressao: string;
  formula_versao: number | null;
  valor: Decimal;
  competencia: string;
  compoe_provisao: boolean;
  ordem: number;
  memoria: {
    expressao: string;
    formula_versao: number | null;
    variaveis: Record<string, string>;
    origens: Record<string, string>;
  };
}

export interface Calculo {
  id: Id;
  numero_versao: number;
  vigente: boolean;
  data_parametros: string;
  data_referencia: string;
  motivo: string;
  total_provisionado: Decimal;
  hash_integridade: string;
  calculado_em: string;
  calculado_por_nome: string | null;
  itens: CalculoItem[];
}

export interface Importacao extends ImportacaoEntrada {
  id: Id;
  numero_processo: string;
  status: StatusImportacao;
  calculo_desatualizado: boolean;
  motivo_cancelamento: string | null;
  versao: number;
  criado_em: string;
  atualizado_em: string;
  tipo_importacao: TipoImportacao;
  transportadora_local: RefNome | null;
  transportadora_secundaria: RefNome | null;
  despachante: RefNome | null;
  terminal: RefNome | null;
  calculo_vigente: Calculo | null;
}

export interface ImportacaoResumo {
  id: Id;
  numero_processo: string;
  tipo_declaracao: string;
  numero_declaracao: string | null;
  data_referencia: string | null;
  data_declaracao: string | null;
  tipo_importacao: TipoImportacao;
  modal: string;
  status: StatusImportacao;
  calculo_desatualizado: boolean;
  total_provisionado: Decimal | null;
  atualizado_em: string;
}

export interface Pagina<T> {
  itens: T[];
  total: number;
  pagina: number;
  tamanho: number;
}

export interface Previa {
  itens: CalculoItem[];
  total_provisionado: Decimal;
  total_anterior: Decimal | null;
  diferencas: Record<string, { anterior: Decimal | null; novo: Decimal; diferenca: Decimal }>;
  variaveis_base: Record<string, string>;
  exige_motivo: boolean;
}

export interface LinhaProvisao {
  chave: string;
  rotulo: string;
  natureza?: string;
  numero_declaracao?: string | null;
  data_referencia?: string | null;
  tipo_codigo?: string;
  tipo_nome?: string;
  valores: Record<string, Decimal>;
  total: Decimal;
}

export interface Provisao {
  competencias: string[];
  linhas: LinhaProvisao[];
  totais: Record<string, Decimal>;
  total: Decimal;
}

export interface Dashboard {
  competencia_atual: string;
  kpis: {
    provisao_mes_atual: Decimal;
    provisao_proximo_mes: Decimal;
    processos_ativos: number;
    rascunhos: number;
    desatualizados: number;
  };
  serie: { competencia: string; por_tipo: Record<string, Decimal>; total: Decimal }[];
  importacoes_por_mes: { mes: string; quantidade: number }[];
  por_tipo: { codigo: string; nome: string; valor: Decimal }[];
  composicao: { natureza: string; valor: Decimal }[];
}

export interface Vigencia {
  id: Id;
  valor: Decimal;
  vigencia_inicio: string;
  vigencia_fim: string | null;
  justificativa: string;
  criado_por_nome: string | null;
  criado_em: string;
  vigente: boolean;
}

export interface Parametro {
  id: Id;
  chave: string;
  descricao: string;
  tipo_valor: "MONETARIO" | "PERCENTUAL" | "INTEIRO";
  escopo: string;
  grupo: string;
  valores: {
    escopo_ref_id: Id | null;
    escopo_ref_nome: string;
    vigente: Vigencia | null;
    historico: Vigencia[];
  }[];
}

export interface TabelaAliquotas {
  tipos: TipoImportacao[];
  linhas: {
    imposto: { id: Id; codigo: string; nome: string };
    por_tipo: Record<Id, { vigente: Vigencia | null; historico: Vigencia[]; origem: string | null }>;
  }[];
}

export interface ComponenteCusto {
  id: Id;
  codigo: string;
  nome: string;
  natureza: string;
  compoe_provisao: boolean;
  regra_competencia: string;
  ordem: number;
  ativo: boolean;
  formula: { id: Id; versao: number; expressao: string; vigencia_inicio: string } | null;
}

export interface RegistroAuditoria {
  id: number;
  tabela: string;
  registro_id: string;
  acao: "INSERT" | "UPDATE" | "DELETE";
  campos_alterados: string[] | null;
  dados_antes: Record<string, unknown> | null;
  dados_depois: Record<string, unknown> | null;
  usuario_nome: string;
  ocorrido_em: string;
}
