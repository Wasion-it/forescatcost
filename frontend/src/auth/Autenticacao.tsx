import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, sessao } from "../lib/api";
import type { Sessao, Usuario } from "../lib/tipos";

interface EstadoAuth {
  usuario: Usuario | null;
  permissoes: Set<string>;
  carregando: boolean;
  entrar: (email: string, senha: string) => Promise<void>;
  sair: () => void;
  pode: (permissao: string) => boolean;
}

const Contexto = createContext<EstadoAuth | null>(null);

export function ProvedorAutenticacao({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [permissoes, setPermissoes] = useState<Set<string>>(new Set());
  const [carregando, setCarregando] = useState(Boolean(sessao.token()));

  const sair = useCallback(() => {
    sessao.limpar();
    setUsuario(null);
    setPermissoes(new Set());
  }, []);

  useEffect(() => {
    sessao.aoExpirar(sair);
    if (!sessao.token()) return;
    api
      .get<{ usuario: Usuario; permissoes: string[] }>("/auth/me")
      .then((r) => {
        setUsuario(r.usuario);
        setPermissoes(new Set(r.permissoes));
      })
      .catch(sair)
      .finally(() => setCarregando(false));
  }, [sair]);

  const entrar = useCallback(async (email: string, senha: string) => {
    const r = await api.post<Sessao>("/auth/login", { email, senha });
    sessao.salvar(r.token);
    setUsuario(r.usuario);
    setPermissoes(new Set(r.permissoes));
  }, []);

  const valor = useMemo<EstadoAuth>(
    () => ({ usuario, permissoes, carregando, entrar, sair, pode: (p) => permissoes.has(p) }),
    [usuario, permissoes, carregando, entrar, sair],
  );
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useAuth(): EstadoAuth {
  const ctx = useContext(Contexto);
  if (!ctx) throw new Error("useAuth fora do ProvedorAutenticacao");
  return ctx;
}

export const PERM = {
  importacaoLer: "importacao:ler",
  importacaoEditar: "importacao:editar",
  calcular: "calculo:executar",
  parametroLer: "parametro:ler",
  parametroEditar: "parametro:editar",
  cadastroEditar: "cadastro:editar",
  provisaoLer: "provisao:ler",
  auditoriaLer: "auditoria:ler",
  usuarioGerir: "usuario:gerir",
} as const;
