// Cliente HTTP mínimo. Erros seguem Problem Details (title, detail, problemas) ou o
// formato de validação do FastAPI (detail: [{loc, msg}]).

const BASE = "/api/v1";
const CHAVE_TOKEN = "forecast.token";

export class ErroApi extends Error {
  status: number;
  problemas: string[];
  campos: Record<string, string>;

  constructor(status: number, mensagem: string, problemas: string[] = [], campos: Record<string, string> = {}) {
    super(mensagem);
    this.status = status;
    this.problemas = problemas;
    this.campos = campos;
  }
}

let aoExpirar: (() => void) | null = null;

export const sessao = {
  token: () => sessionStorage.getItem(CHAVE_TOKEN),
  salvar: (token: string) => sessionStorage.setItem(CHAVE_TOKEN, token),
  limpar: () => sessionStorage.removeItem(CHAVE_TOKEN),
  aoExpirar: (fn: () => void) => {
    aoExpirar = fn;
  },
};

type ItemValidacao = { loc: (string | number)[]; msg: string };

function traduzirValidacao(itens: ItemValidacao[]): { problemas: string[]; campos: Record<string, string> } {
  const campos: Record<string, string> = {};
  const problemas: string[] = [];
  for (const item of itens) {
    const msg = item.msg.replace(/^Value error, /, "");
    const campo = item.loc.filter((p) => p !== "body").join(".");
    if (campo) campos[campo] = msg;
    for (const parte of msg.split("; ")) problemas.push(parte);
  }
  return { problemas, campos };
}

async function erroDaResposta(resp: Response): Promise<ErroApi> {
  let corpo: unknown = null;
  try {
    corpo = await resp.json();
  } catch {
    /* corpo vazio */
  }
  const c = corpo as { detail?: unknown; problemas?: string[]; title?: string } | null;
  if (resp.status === 422 && Array.isArray(c?.detail)) {
    const { problemas, campos } = traduzirValidacao(c.detail as ItemValidacao[]);
    return new ErroApi(422, "Revise os campos destacados.", problemas, campos);
  }
  const mensagem =
    typeof c?.detail === "string" ? c.detail : resp.status >= 500 ? "O servidor não respondeu como esperado. Tente de novo em instantes." : "Não foi possível concluir a operação.";
  return new ErroApi(resp.status, mensagem, c?.problemas ?? []);
}

async function requisicao<T>(metodo: string, caminho: string, corpo?: unknown): Promise<T> {
  const token = sessao.token();
  const resp = await fetch(`${BASE}${caminho}`, {
    method: metodo,
    headers: {
      ...(corpo !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: corpo !== undefined ? JSON.stringify(corpo) : undefined,
  });
  if (resp.status === 401 && token) {
    sessao.limpar();
    aoExpirar?.();
  }
  if (!resp.ok) throw await erroDaResposta(resp);
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  get: <T>(caminho: string) => requisicao<T>("GET", caminho),
  post: <T>(caminho: string, corpo: unknown = {}) => requisicao<T>("POST", caminho, corpo),
  put: <T>(caminho: string, corpo: unknown) => requisicao<T>("PUT", caminho, corpo),
};

/** Baixa um arquivo autenticado (ex.: Excel) e dispara o download no navegador. */
export async function baixar(caminho: string, nomePadrao: string): Promise<void> {
  const token = sessao.token();
  const resp = await fetch(`${BASE}${caminho}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) throw await erroDaResposta(resp);
  const blob = await resp.blob();
  const disposicao = resp.headers.get("Content-Disposition") ?? "";
  const nome = /filename="([^"]+)"/.exec(disposicao)?.[1] ?? nomePadrao;
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nome;
  link.click();
  URL.revokeObjectURL(url);
}

export function query(params: Record<string, string | number | null | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined && v !== "") p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}
