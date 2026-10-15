import { useEffect, useRef, type ReactNode } from "react";
import { ErroApi } from "../lib/api";
import type { StatusImportacao } from "../lib/tipos";

export function Cabecalho({ titulo, descricao, acoes }: { titulo: ReactNode; descricao?: ReactNode; acoes?: ReactNode }) {
  return (
    <header className="cabecalho">
      <div>
        <h1>{titulo}</h1>
        {descricao && <p>{descricao}</p>}
      </div>
      {acoes && <div className="acoes">{acoes}</div>}
    </header>
  );
}

const ROTULO_STATUS: Record<string, string> = {
  RASCUNHO: "Rascunho",
  CALCULADO: "Calculado",
  FECHADO: "Fechado",
  CANCELADO: "Cancelado",
  DESATUALIZADO: "Recálculo pendente",
};

export function Status({ status, desatualizado }: { status: StatusImportacao; desatualizado?: boolean }) {
  const chave = status === "CALCULADO" && desatualizado ? "DESATUALIZADO" : status;
  return (
    <span
      className={`status status-${chave.toLowerCase()}`}
      title={chave === "DESATUALIZADO" ? "Dados alterados depois do último cálculo" : undefined}
    >
      {ROTULO_STATUS[chave]}
    </span>
  );
}

export function AvisoErro({ erro, titulo }: { erro: unknown; titulo?: string }) {
  if (!erro) return null;
  const e = erro instanceof ErroApi ? erro : null;
  const mensagem = e?.message ?? (erro instanceof Error ? erro.message : "Erro inesperado.");
  return (
    <div className="aviso aviso-erro" role="alert">
      <div>
        <strong>{titulo ?? mensagem}</strong>
        {titulo && <p>{mensagem}</p>}
        {e && e.problemas.length > 0 && (
          <ul>
            {e.problemas.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function Carregando({ texto = "Carregando…" }: { texto?: string }) {
  return (
    <p className="carregando" role="status">
      {texto}
    </p>
  );
}

interface DialogoProps {
  aberto: boolean;
  titulo: string;
  aoFechar: () => void;
  children: ReactNode;
  rodape: ReactNode;
}

/** Diálogo modal nativo (foco preso, Esc fecha). */
export function Dialogo({ aberto, titulo, aoFechar, children, rodape }: DialogoProps) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (aberto && !d.open) d.showModal();
    if (!aberto && d.open) d.close();
  }, [aberto]);
  return (
    <dialog ref={ref} className="dialogo" aria-labelledby="dialogo-titulo" onClose={aoFechar}>
      <div className="painel-topo">
        <h2 id="dialogo-titulo">{titulo}</h2>
      </div>
      <div className="dialogo-corpo">{children}</div>
      <div className="dialogo-rodape">{rodape}</div>
    </dialog>
  );
}

export function Notificacao({ texto, aoSumir }: { texto: string | null; aoSumir: () => void }) {
  useEffect(() => {
    if (!texto) return;
    const t = setTimeout(aoSumir, 4000);
    return () => clearTimeout(t);
  }, [texto, aoSumir]);
  if (!texto) return null;
  return (
    <div className="notificacao" role="status" aria-live="polite">
      {texto}
    </div>
  );
}

export function Paginacao({
  pagina,
  tamanho,
  total,
  aoMudar,
}: {
  pagina: number;
  tamanho: number;
  total: number;
  aoMudar: (p: number) => void;
}) {
  const paginas = Math.max(1, Math.ceil(total / tamanho));
  const inicio = total === 0 ? 0 : (pagina - 1) * tamanho + 1;
  const fim = Math.min(total, pagina * tamanho);
  return (
    <nav className="paginacao" aria-label="Paginação">
      <span>
        {inicio}–{fim} de {total}
      </span>
      <span className="acoes">
        <button className="botao botao-pequeno" disabled={pagina <= 1} onClick={() => aoMudar(pagina - 1)}>
          Anterior
        </button>
        <button className="botao botao-pequeno" disabled={pagina >= paginas} onClick={() => aoMudar(pagina + 1)}>
          Próxima
        </button>
      </span>
    </nav>
  );
}
