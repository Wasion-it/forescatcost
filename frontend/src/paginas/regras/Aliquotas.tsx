import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { PERM, useAuth } from "../../auth/Autenticacao";
import { AvisoErro, Cabecalho, Carregando, Dialogo, Notificacao } from "../../componentes/comuns";
import { api } from "../../lib/api";
import { data, percentual, percentualParaFracao } from "../../lib/formato";
import type { TabelaAliquotas, TipoImportacao } from "../../lib/tipos";

interface Alvo {
  imposto: TabelaAliquotas["linhas"][number]["imposto"];
  tipo: TipoImportacao;
  atual: string | null;
}

export function Aliquotas() {
  const { pode } = useAuth();
  const [alvo, setAlvo] = useState<Alvo | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const r = useQuery({ queryKey: ["aliquotas"], queryFn: () => api.get<TabelaAliquotas>("/aliquotas") });

  if (r.isLoading) return <Carregando />;
  if (r.error || !r.data) return <AvisoErro erro={r.error} />;

  return (
    <>
      <Cabecalho
        titulo="Alíquotas"
        descricao="Percentuais por imposto e tipo de importação. Hoje são informados manualmente a partir do TecWinWeb."
      />
      <div className="aviso aviso-atencao bloco">
        <p>Os valores da carga inicial são exemplos. Substitua pelos percentuais validados pelo Fiscal antes de usar em produção.</p>
      </div>
      <section className="painel">
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr>
                <th scope="col">Imposto</th>
                {r.data.tipos.map((t) => (
                  <th scope="col" className="num" key={t.id}>
                    {t.nome}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {r.data.linhas.map((ln) => (
                <tr key={ln.imposto.id}>
                  <th scope="row" className="celula-imposto">
                    <strong>{ln.imposto.codigo}</strong>
                    <span className="suave">{ln.imposto.nome}</span>
                  </th>
                  {r.data!.tipos.map((t) => {
                    const c = ln.por_tipo[t.id];
                    return (
                      <td className="num" key={t.id}>
                        <span className="aliquota-valor">{c?.vigente ? percentual(c.vigente.valor, 4) : "–"}</span>
                        <span className="ajuda-linha">
                          {c?.vigente ? `desde ${data(c.vigente.vigencia_inicio)}, ${c.origem === "TECWIN" ? "TecWin" : "manual"}` : "sem vigência"}
                        </span>
                        {pode(PERM.parametroEditar) && (
                          <button
                            className="botao botao-texto botao-pequeno"
                            onClick={() => setAlvo({ imposto: ln.imposto, tipo: t, atual: c?.vigente?.valor ?? null })}
                          >
                            Alterar<span className="sr-only">
                              {" "}
                              {ln.imposto.codigo} para {t.nome}
                            </span>
                          </button>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {alvo && (
        <DialogoAliquota
          alvo={alvo}
          aoFechar={() => setAlvo(null)}
          aoSalvar={() => {
            setAlvo(null);
            setAviso("Nova alíquota registrada.");
          }}
        />
      )}
      <Notificacao texto={aviso} aoSumir={() => setAviso(null)} />
    </>
  );
}

function DialogoAliquota({ alvo, aoFechar, aoSalvar }: { alvo: Alvo; aoFechar: () => void; aoSalvar: () => void }) {
  const cliente = useQueryClient();
  const amanha = new Date(Date.now() + 86_400_000).toISOString().slice(0, 10);
  const [valor, setValor] = useState("");
  const [inicio, setInicio] = useState(amanha);
  const [origem, setOrigem] = useState<"MANUAL" | "TECWIN">("TECWIN");
  const [justificativa, setJustificativa] = useState("");
  const [erroLocal, setErroLocal] = useState<string | null>(null);
  const salvar = useMutation({
    mutationFn: (corpo: object) => api.post("/aliquotas/vigencias", corpo),
    onSuccess: () => {
      cliente.invalidateQueries({ queryKey: ["aliquotas"] });
      aoSalvar();
    },
  });

  function enviar() {
    setErroLocal(null);
    try {
      const percentualFracao = percentualParaFracao(valor);
      if (percentualFracao === null) throw new Error();
      salvar.mutate({
        imposto_id: alvo.imposto.id,
        tipo_importacao_id: alvo.tipo.id,
        percentual: percentualFracao,
        vigencia_inicio: inicio,
        origem,
        justificativa,
      });
    } catch {
      setErroLocal("Informe um percentual válido.");
    }
  }

  return (
    <Dialogo
      aberto
      titulo={`${alvo.imposto.codigo} para ${alvo.tipo.nome}`}
      aoFechar={aoFechar}
      rodape={
        <>
          <button className="botao botao-texto" onClick={aoFechar}>
            Cancelar
          </button>
          <button className="botao botao-primario" disabled={!valor || justificativa.trim().length < 5 || salvar.isPending} onClick={enviar}>
            Registrar alíquota
          </button>
        </>
      }
    >
      <p className="suave">Alíquota atual: {alvo.atual ? percentual(alvo.atual, 4) : "nenhuma"}</p>
      <div className="grade-campos">
        <div className="campo">
          <label htmlFor="a-valor">Nova alíquota (%)</label>
          <input id="a-valor" className="entrada num" inputMode="decimal" value={valor} onChange={(e) => setValor(e.target.value)} placeholder="18" />
        </div>
        <div className="campo">
          <label htmlFor="a-inicio">Vale a partir de</label>
          <input id="a-inicio" type="date" className="entrada" value={inicio} onChange={(e) => setInicio(e.target.value)} />
        </div>
        <div className="campo">
          <label htmlFor="a-origem">Origem</label>
          <select id="a-origem" className="entrada" value={origem} onChange={(e) => setOrigem(e.target.value as "MANUAL" | "TECWIN")}>
            <option value="TECWIN">Consulta ao TecWinWeb</option>
            <option value="MANUAL">Informada pelo Fiscal</option>
          </select>
        </div>
      </div>
      <div className="campo">
        <label htmlFor="a-just">Justificativa</label>
        <input id="a-just" className="entrada" value={justificativa} onChange={(e) => setJustificativa(e.target.value)} maxLength={300} />
      </div>
      {erroLocal && (
        <div className="aviso aviso-erro" role="alert">
          {erroLocal}
        </div>
      )}
      <AvisoErro erro={salvar.error} />
    </Dialogo>
  );
}
