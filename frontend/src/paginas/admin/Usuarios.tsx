import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AvisoErro, Cabecalho, Carregando, Dialogo, Notificacao } from "../../componentes/comuns";
import { api } from "../../lib/api";
import { dataHora } from "../../lib/formato";
import type { Perfil, Usuario } from "../../lib/tipos";

interface Edicao {
  id?: string;
  nome: string;
  email: string;
  senha: string;
  ativo: boolean;
  perfis: string[];
}

export function Usuarios() {
  const [editando, setEditando] = useState<Edicao | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const usuarios = useQuery({ queryKey: ["usuarios"], queryFn: () => api.get<Usuario[]>("/usuarios") });

  if (usuarios.isLoading) return <Carregando />;
  if (usuarios.error || !usuarios.data) return <AvisoErro erro={usuarios.error} />;

  return (
    <>
      <Cabecalho
        titulo="Usuários"
        descricao="Acesso por perfil. Usuários não são excluídos: desative para revogar o acesso e manter o histórico."
        acoes={
          <button className="botao botao-primario" onClick={() => setEditando({ nome: "", email: "", senha: "", ativo: true, perfis: [] })}>
            Adicionar usuário
          </button>
        }
      />
      <section className="painel">
        <table className="tabela">
          <thead>
            <tr>
              <th scope="col">Nome</th>
              <th scope="col">E-mail</th>
              <th scope="col">Perfis</th>
              <th scope="col">Último acesso</th>
              <th scope="col">Situação</th>
              <th scope="col">
                <span className="sr-only">Ações</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {usuarios.data.map((u) => (
              <tr key={u.id}>
                <td>
                  <strong>{u.nome}</strong>
                </td>
                <td>{u.email}</td>
                <td>{u.perfis.map((p) => p.nome).join(", ")}</td>
                <td>{dataHora(u.ultimo_acesso)}</td>
                <td>
                  <span className={`status ${u.ativo ? "status-calculado" : "status-cancelado"}`}>{u.ativo ? "Ativo" : "Inativo"}</span>
                </td>
                <td className="num">
                  <button
                    className="botao botao-pequeno"
                    onClick={() => setEditando({ id: u.id, nome: u.nome, email: u.email, senha: "", ativo: u.ativo, perfis: u.perfis.map((p) => p.codigo) })}
                  >
                    Editar<span className="sr-only"> {u.nome}</span>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {editando && (
        <DialogoUsuario
          inicial={editando}
          aoFechar={() => setEditando(null)}
          aoSalvar={() => {
            setEditando(null);
            setAviso("Usuário salvo.");
          }}
        />
      )}
      <Notificacao texto={aviso} aoSumir={() => setAviso(null)} />
    </>
  );
}

function DialogoUsuario({ inicial, aoFechar, aoSalvar }: { inicial: Edicao; aoFechar: () => void; aoSalvar: () => void }) {
  const cliente = useQueryClient();
  const [u, setU] = useState(inicial);
  const perfis = useQuery({ queryKey: ["perfis"], queryFn: () => api.get<Perfil[]>("/perfis") });
  const salvar = useMutation({
    mutationFn: () => {
      const { id, ...corpo } = u;
      const envio = { ...corpo, senha: corpo.senha || null };
      return id ? api.put(`/usuarios/${id}`, envio) : api.post("/usuarios", envio);
    },
    onSuccess: () => {
      cliente.invalidateQueries({ queryKey: ["usuarios"] });
      aoSalvar();
    },
  });
  const novo = !inicial.id;
  const valido = u.nome.trim().length >= 3 && u.email.includes("@") && u.perfis.length > 0 && (!novo || u.senha.length >= 10);

  return (
    <Dialogo
      aberto
      titulo={novo ? "Adicionar usuário" : `Editar ${inicial.nome}`}
      aoFechar={aoFechar}
      rodape={
        <>
          <button className="botao botao-texto" onClick={aoFechar}>
            Cancelar
          </button>
          <button className="botao botao-primario" disabled={!valido || salvar.isPending} onClick={() => salvar.mutate()}>
            Salvar
          </button>
        </>
      }
    >
      <div className="campo">
        <label htmlFor="u-nome">Nome</label>
        <input id="u-nome" className="entrada" value={u.nome} onChange={(e) => setU({ ...u, nome: e.target.value })} />
      </div>
      <div className="campo">
        <label htmlFor="u-email">E-mail</label>
        <input id="u-email" type="email" className="entrada" value={u.email} onChange={(e) => setU({ ...u, email: e.target.value })} />
      </div>
      <div className="campo">
        <label htmlFor="u-senha">{novo ? "Senha inicial" : "Nova senha (opcional)"}</label>
        <input id="u-senha" type="password" autoComplete="new-password" className="entrada" value={u.senha} onChange={(e) => setU({ ...u, senha: e.target.value })} />
        <span className="ajuda">Mínimo de 10 caracteres.</span>
      </div>
      <fieldset className="grupo-opcoes">
        <legend>Perfis</legend>
        {perfis.data?.map((p) => (
          <label className="caixa" key={p.id}>
            <input
              type="checkbox"
              checked={u.perfis.includes(p.codigo)}
              onChange={(e) =>
                setU({ ...u, perfis: e.target.checked ? [...u.perfis, p.codigo] : u.perfis.filter((c) => c !== p.codigo) })
              }
            />{" "}
            {p.nome}
          </label>
        ))}
      </fieldset>
      <label className="caixa">
        <input type="checkbox" checked={u.ativo} onChange={(e) => setU({ ...u, ativo: e.target.checked })} /> Acesso ativo
      </label>
      <AvisoErro erro={salvar.error} />
    </Dialogo>
  );
}
