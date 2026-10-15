import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { PERM, useAuth } from "../../auth/Autenticacao";
import { AvisoErro, Cabecalho, Carregando, Dialogo, Notificacao } from "../../componentes/comuns";
import { api } from "../../lib/api";
import { useDespachantes, useTerminais, useTransportadoras } from "../../lib/consultas";

type Aba = "transportadoras" | "despachantes" | "terminais";

const ABAS: { id: Aba; rotulo: string; singular: string }[] = [
  { id: "transportadoras", rotulo: "Transportadoras", singular: "transportadora" },
  { id: "despachantes", rotulo: "Despachantes", singular: "despachante" },
  { id: "terminais", rotulo: "Terminais", singular: "terminal" },
];

const MODAL: Record<string, string> = { MARITIMO: "Marítimo", AEREO: "Aéreo" };

interface Registro {
  id?: string;
  nome: string;
  cnpj?: string | null;
  ativo: boolean;
  tipo_servico?: string;
  modal?: string;
}

export function Cadastros() {
  const { pode } = useAuth();
  const [params, setParams] = useSearchParams();
  const aba = (params.get("aba") as Aba) ?? "transportadoras";
  const [editando, setEditando] = useState<Registro | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const transp = useTransportadoras(true);
  const desp = useDespachantes(true);
  const term = useTerminais(true);
  const consulta = { transportadoras: transp, despachantes: desp, terminais: term }[aba];
  const info = ABAS.find((a) => a.id === aba)!;
  const podeEditar = pode(PERM.cadastroEditar);

  const novo: Registro =
    aba === "transportadoras"
      ? { nome: "", cnpj: "", ativo: true, tipo_servico: "LOCAL" }
      : aba === "terminais"
        ? { nome: "", ativo: true, modal: "MARITIMO" }
        : { nome: "", cnpj: "", ativo: true };

  return (
    <>
      <Cabecalho
        titulo="Parceiros e terminais"
        descricao="Transportadoras, despachantes e terminais vinculados aos processos. Os valores de cada um ficam em Parâmetros."
        acoes={
          podeEditar && (
            <button className="botao botao-primario" onClick={() => setEditando(novo)}>
              Adicionar {info.singular}
            </button>
          )
        }
      />
      <section className="painel">
        <div className="filtros">
          <div className="alternador" role="group" aria-label="Tipo de cadastro">
            {ABAS.map((a) => (
              <button key={a.id} type="button" aria-pressed={a.id === aba} onClick={() => setParams({ aba: a.id })}>
                {a.rotulo}
              </button>
            ))}
          </div>
        </div>
        {consulta.isLoading && <Carregando />}
        <AvisoErro erro={consulta.error} />
        {consulta.data && (
          <table className="tabela">
            <thead>
              <tr>
                <th scope="col">Nome</th>
                <th scope="col">{aba === "terminais" ? "Modal" : "CNPJ"}</th>
                <th scope="col">Situação</th>
                <th scope="col">
                  <span className="sr-only">Ações</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {(consulta.data as Registro[]).map((r) => (
                <tr key={r.id}>
                  <td>
                    <strong>{r.nome}</strong>
                  </td>
                  <td>{aba === "terminais" ? MODAL[r.modal ?? ""] : r.cnpj || <span className="suave">não informado</span>}</td>
                  <td>
                    <span className={`status ${r.ativo ? "status-calculado" : "status-rascunho"}`}>{r.ativo ? "Ativo" : "Inativo"}</span>
                  </td>
                  <td className="num">
                    {podeEditar && (
                      <button className="botao botao-pequeno" onClick={() => setEditando(r)}>
                        Editar<span className="sr-only"> {r.nome}</span>
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      {editando && (
        <DialogoCadastro
          aba={aba}
          singular={info.singular}
          registro={editando}
          aoFechar={() => setEditando(null)}
          aoSalvar={() => {
            setEditando(null);
            setAviso("Cadastro salvo.");
          }}
        />
      )}
      <Notificacao texto={aviso} aoSumir={() => setAviso(null)} />
    </>
  );
}

function DialogoCadastro({
  aba,
  singular,
  registro,
  aoFechar,
  aoSalvar,
}: {
  aba: Aba;
  singular: string;
  registro: Registro;
  aoFechar: () => void;
  aoSalvar: () => void;
}) {
  const cliente = useQueryClient();
  const [r, setR] = useState<Registro>(registro);
  const salvar = useMutation({
    mutationFn: () => {
      const { id, ...corpo } = r;
      if (corpo.cnpj === "") corpo.cnpj = null;
      return id ? api.put(`/${aba}/${id}`, corpo) : api.post(`/${aba}`, corpo);
    },
    onSuccess: () => {
      cliente.invalidateQueries({ queryKey: [aba] });
      aoSalvar();
    },
  });

  return (
    <Dialogo
      aberto
      titulo={registro.id ? `Editar ${singular}` : `Adicionar ${singular}`}
      aoFechar={aoFechar}
      rodape={
        <>
          <button className="botao botao-texto" onClick={aoFechar}>
            Cancelar
          </button>
          <button className="botao botao-primario" disabled={r.nome.trim().length < 2 || salvar.isPending} onClick={() => salvar.mutate()}>
            Salvar
          </button>
        </>
      }
    >
      <div className="campo">
        <label htmlFor="c-nome">Nome</label>
        <input id="c-nome" className="entrada" value={r.nome} onChange={(e) => setR({ ...r, nome: e.target.value })} maxLength={120} />
      </div>
      {aba !== "terminais" && (
        <div className="campo">
          <label htmlFor="c-cnpj">CNPJ</label>
          <input id="c-cnpj" className="entrada" value={r.cnpj ?? ""} onChange={(e) => setR({ ...r, cnpj: e.target.value })} placeholder="00.000.000/0000-00" />
        </div>
      )}
      {aba === "terminais" && (
        <div className="campo">
          <label htmlFor="c-modal">Modal</label>
          <select id="c-modal" className="entrada" value={r.modal} onChange={(e) => setR({ ...r, modal: e.target.value })}>
            <option value="MARITIMO">Marítimo</option>
            <option value="AEREO">Aéreo</option>
          </select>
        </div>
      )}
      <label className="caixa">
        <input type="checkbox" checked={r.ativo} onChange={(e) => setR({ ...r, ativo: e.target.checked })} /> Ativo para novos processos
      </label>
      <AvisoErro erro={salvar.error} />
    </Dialogo>
  );
}
