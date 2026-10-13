import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { Despachante, Terminal, TipoImportacao, Transportadora } from "./tipos";

const LONGO = 5 * 60 * 1000;

export const useTipos = () =>
  useQuery({ queryKey: ["tipos"], queryFn: () => api.get<TipoImportacao[]>("/tipos-importacao"), staleTime: LONGO });

export const useTransportadoras = (incluirInativos = false) =>
  useQuery({
    queryKey: ["transportadoras", incluirInativos],
    queryFn: () => api.get<Transportadora[]>(`/transportadoras?incluir_inativos=${incluirInativos}`),
    staleTime: LONGO,
  });

export const useDespachantes = (incluirInativos = false) =>
  useQuery({
    queryKey: ["despachantes", incluirInativos],
    queryFn: () => api.get<Despachante[]>(`/despachantes?incluir_inativos=${incluirInativos}`),
    staleTime: LONGO,
  });

export const useTerminais = (incluirInativos = false) =>
  useQuery({
    queryKey: ["terminais", incluirInativos],
    queryFn: () => api.get<Terminal[]>(`/terminais?incluir_inativos=${incluirInativos}`),
    staleTime: LONGO,
  });
