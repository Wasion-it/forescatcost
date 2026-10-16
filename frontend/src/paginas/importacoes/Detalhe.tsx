import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { PERM, useAuth } from "../../auth/Autenticacao";
import { AvisoErro, Cabecalho, Carregando, Dialogo, Notificacao, Status } from "../../componentes/comuns";
import { api, ErroApi } from "../../lib/api";
import {
  diferencaProvisao,
  validarFechamento,
  type DespesaInformada,
  type ResultadoFechamento,
} from "../../lib/fechamento";
import { brl, data, dataHora, decimal2, mesLongo } from "../../lib/formato";
import type { Calculo, Importacao, Previa, RegistroAuditoria } from "../../lib/tipos";
import { FitaCalculo } from "./FitaCalculo";

type Resumo = Omit<Calculo, "itens">;

export function DetalheImportacao() {
  const { id } = useParams();
  const { pode } = useAuth();
  const cliente = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [versaoSelecionada, setVersaoSelecionada] = useState<string | null>(null);
  const [calculando, setCalculando] = useState(false);
  const [cancelando, setCancelando] = useState(false);
  const [fechando, setFechando] = useState(false);
  const [animar, setAnimar] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  const imp = useQuery({ queryKey: ["importacao", id], queryFn: () => api.get<Importacao>(`/importacoes/${id}`) });
  const versoes = useQuery({
    queryKey: ["importacao", id, "versoes"],
    queryFn: () => api.get<Resumo[]>(`/importacoes/${id}/calculos`),
  });
  const versao = useQuery({
    queryKey: ["calculo", versaoSelecionada],
    queryFn: () => api.get<Calculo>(`/importacoes/${id}/calculos/${versaoSelecionada}`),
    enabled: Boolean(versaoSelecionada),
  });

  useEffect(() => {
    if (params.get("calcular") === "1" && imp.data && imp.data.status !== "CANCELADO" && imp.data.status !== "FECHADO") {
      setCalculando(true);
      setParams({}, { replace: true });
    }
  }, [params, imp.data, setParams]);

  function aoCalcular() {
    setCalculando(false);
    setVersaoSelecionada(null);
    setAnimar(true);
    setAviso("Cálculo registrado. A provisão já considera a nova versão.");
    cliente.invalidateQueries({ queryKey: ["importacao", id] });
    cliente.invalidateQueries({ queryKey: ["importacoes"] });
  }

  if (imp.isLoading) return <Carregando />;
  if (imp.error || !imp.data) return <AvisoErro erro={imp.error} />;
  const i = imp.data;
  const calculoExibido = versaoSelecionada ? versao.data : i.calculo_vigente;
  // Mês da IP (ou data prevista); componentes com outra competência são sinalizados na fita
  const competenciaPrincipal = calculoExibido ? `${calculoExibido.data_referencia.slice(0, 7)}-01` : "";
  const cancelado = i.status === "CANCELADO";
  const fechado = i.status === "FECHADO";
  const podeFechar = pode(PERM.importacaoEditar) && i.status === "CALCULADO" && !i.calculo_desatualizado;

  return (
    <>
      <Cabecalho
        titulo={
          <span className="titulo-processo">
            {i.numero_processo}
            <Status status={i.status} desatualizado={i.calculo_desatualizado} />
          </span>
        }
        descricao={
          <>
            {i.numero_ip ? `IP ${i.numero_ip}` : "IP ainda não gerada"}
            {", "}
            {i.tipo_importacao.nome}, {i.modal === "MARITIMO" ? "marítimo" : "aéreo"}
          </>
        }
        acoes={
          !cancelado &&
          !fechado && (
            <>
              {pode(PERM.importacaoEditar) && (
                <>
                  <button className="botao botao-perigo" onClick={() => setCancelando(true)}>
                    Cancelar processo
                  </button>
                  <Link to={`/importacoes/${i.id}/editar`} className="botao">
                    Editar
                  </Link>
                </>
              )}
              {podeFechar && (
                <button className="botao" onClick={() => setFechando(true)}>
                  Fechar despesa
                </button>
              )}
              {pode(PERM.calcular) && (
                <button className="botao botao-primario" onClick={() => setCalculando(true)}>
                  {i.calculo_vigente ? "Recalcular" : "Calcular"}
                </button>
              )}
            </>
          )
        }
      />

      {cancelado && (
        <div className="aviso aviso-erro bloco">
          <p>
            Processo cancelado: <strong>{i.motivo_cancelamento}</strong>. Ele não entra na provisão, mas o histórico fica
            disponível.
          </p>
        </div>
      )}
      {i.calculo_desatualizado && !cancelado && (
        <div className="aviso aviso-atencao bloco">
          <p>Os dados do processo mudaram depois do último cálculo. Recalcule para atualizar a provisão.</p>
        </div>
      )}

      <div className="detalhe">
        <section className="painel" aria-labelledby="t-fita">
          <div className="painel-topo">
            <div>
              <h2 id="t-fita">Fita de cálculo</h2>
              {calculoExibido && (
                <p className="suave">
                  Versão {calculoExibido.numero_versao}
                  {!calculoExibido.vigente && " (histórica)"}, calculada em {dataHora(calculoExibido.calculado_em)} por{" "}
                  {calculoExibido.calculado_por_nome}. Competência principal: {mesLongo(competenciaPrincipal)}.
                </p>
              )}
            </div>
            {versaoSelecionada && (
              <button className="botao botao-pequeno" onClick={() => setVersaoSelecionada(null)}>
                Voltar à versão vigente
              </button>
            )}
          </div>
          {calculoExibido ? (
            <FitaCalculo
              calculo={calculoExibido}
              competenciaPrincipal={competenciaPrincipal}
              animar={animar && !versaoSelecionada}
              // O realizado pertence ao cálculo vigente; versões históricas têm outros itens
              realizado={
                fechado && calculoExibido.vigente
                  ? Object.fromEntries(i.despesas_fechadas.map((d) => [d.componente_codigo, d.valor]))
                  : undefined
              }
            />
          ) : versaoSelecionada ? (
            <Carregando />
          ) : (
            <div className="vazio">
              <p>Este processo ainda não foi calculado.</p>
              {pode(PERM.calcular) && !cancelado && !fechado && (
                <button className="botao botao-primario" onClick={() => setCalculando(true)}>
                  Calcular agora
                </button>
              )}
            </div>
          )}
        </section>

        <aside className="detalhe-lateral">
          {fechado && (
            <section className="painel" aria-labelledby="t-fechamento">
              <div className="painel-topo">
                <h2 id="t-fechamento">Fechamento da despesa</h2>
                <Status status="FECHADO" />
              </div>
              <dl className="manifesto">
                <Dado rotulo="Número da fatura" valor={i.numero_fatura ?? "–"} />
                <Dado rotulo="Total realizado" valor={brl(i.valor_fatura)} />
                {i.calculo_vigente && i.valor_fatura && (
                  <Dado
                    rotulo="Diferença para a provisão"
                    valor={formatarDiferenca(diferencaProvisao(i.calculo_vigente.total_provisionado, i.valor_fatura))}
                  />
                )}
                <Dado rotulo="Fechada em" valor={dataHora(i.fechado_em)} />
                <Dado rotulo="Fechada por" valor={i.fechado_por_nome ?? "–"} />
              </dl>

            </section>
          )}

          <section className="painel" aria-labelledby="t-dados">
            <div className="painel-topo">
              <h2 id="t-dados">Dados do processo</h2>
            </div>
            <dl className="manifesto">
              <Dado rotulo="Data da IP" valor={data(i.data_ip)} />
              <Dado rotulo="Data prevista" valor={data(i.data_prevista)} />
              <Dado rotulo="Invoice" valor={`${i.moeda_invoice} ${decimal2(i.valor_invoice)}`} />
              <Dado rotulo="Frete internacional" valor={`${i.moeda_frete} ${decimal2(i.valor_frete)}`} />
              <Dado rotulo="Taxa de liberação" valor={brl(i.valor_taxa_liberacao)} />
              <Dado rotulo="Taxa USD" valor={i.taxa_usd ? Number(i.taxa_usd).toLocaleString("pt-BR", { maximumFractionDigits: 6 }) : "–"} />
              <Dado rotulo="Taxa CNY" valor={i.taxa_cny ? Number(i.taxa_cny).toLocaleString("pt-BR", { maximumFractionDigits: 6 }) : "–"} />
              <Dado
                rotulo="Taxa Siscomex"
                valor={Number(i.valor_siscomex) > 0 ? `${brl(i.valor_siscomex)} (informada)` : "Calculada pelo sistema"}
              />
              <Dado rotulo="Itens / containers" valor={`${i.qtd_itens} / ${i.qtd_containers}`} />
              <Dado rotulo="Peso bruto / líquido" valor={`${Number(i.peso_bruto_kg).toLocaleString("pt-BR")} / ${Number(i.peso_liquido_kg).toLocaleString("pt-BR")} kg`} />
              <Dado rotulo="Transportadora local" valor={i.transportadora_local?.nome ?? "Valores padrão"} />
              <Dado rotulo="Despachante" valor={i.despachante?.nome ?? "–"} />
              <Dado rotulo="Terminal" valor={i.terminal?.nome ?? "Valores padrão"} />
            </dl>
            {i.observacoes && <p className="observacoes">{i.observacoes}</p>}
          </section>

          <PainelHistorico
            id={i.id}
            versoes={versoes.data}
            versaoSelecionada={versaoSelecionada}
            comAlteracoes={pode(PERM.auditoriaLer)}
            aoEscolher={(v) => {
              setAnimar(false);
              setVersaoSelecionada(v.vigente ? null : v.id);
            }}
          />
        </aside>
      </div>

      {calculando && <DialogoCalculo importacao={i} aoFechar={() => setCalculando(false)} aoConcluir={aoCalcular} />}
      {cancelando && (
        <DialogoCancelamento
          importacao={i}
          aoFechar={() => setCancelando(false)}
          aoConcluir={() => {
            setCancelando(false);
            setAviso("Processo cancelado e retirado da provisão.");
            cliente.invalidateQueries({ queryKey: ["importacao", id] });
            cliente.invalidateQueries({ queryKey: ["importacoes"] });
          }}
        />
      )}
      {fechando && (
        <DialogoFechamento
          importacao={i}
          aoFechar={() => setFechando(false)}
          aoConcluir={() => {
            setFechando(false);
            setAviso("Despesa fechada.");
            cliente.invalidateQueries({ queryKey: ["importacao", id] });
            cliente.invalidateQueries({ queryKey: ["auditoria", "importacao", id] });
            cliente.invalidateQueries({ queryKey: ["importacoes"] });
          }}
        />
      )}
      <Notificacao texto={aviso} aoSumir={() => setAviso(null)} />
    </>
  );
}

function formatarDiferenca(d: number): string {
  return `${d > 0 ? "+" : ""}${brl(d)}`;
}

function Dado({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div>
      <dt>{rotulo}</dt>
      <dd>{valor}</dd>
    </div>
  );
}

function DialogoCalculo({ importacao, aoFechar, aoConcluir }: { importacao: Importacao; aoFechar: () => void; aoConcluir: () => void }) {
  const [motivo, setMotivo] = useState("");
  const previa = useQuery({
    queryKey: ["previa", importacao.id, importacao.versao],
    queryFn: () => api.post<Previa>(`/importacoes/${importacao.id}/calculos/previa`),
    gcTime: 0,
    retry: false,
  });
  const registrar = useMutation({
    mutationFn: () => api.post<Calculo>(`/importacoes/${importacao.id}/calculos`, { motivo: motivo || null }),
    onSuccess: aoConcluir,
  });
  const exigeMotivo = previa.data?.exige_motivo ?? false;
  const alterados = previa.data
    ? previa.data.itens.filter((it) => it.compoe_provisao && Number(previa.data!.diferencas[it.componente_codigo]?.diferenca ?? 0) !== 0)
    : [];

  return (
    <Dialogo
      aberto
      titulo={exigeMotivo ? "Recalcular processo" : "Calcular processo"}
      aoFechar={aoFechar}
      rodape={
        <>
          <button className="botao botao-texto" onClick={aoFechar}>
            Cancelar
          </button>
          <button
            className="botao botao-primario"
            disabled={!previa.data || registrar.isPending || (exigeMotivo && motivo.trim().length < 5)}
            onClick={() => registrar.mutate()}
          >
            {registrar.isPending ? "Registrando…" : "Registrar cálculo"}
          </button>
        </>
      }
    >
      {previa.isLoading && <Carregando texto="Calculando com os parâmetros vigentes…" />}
      <AvisoErro erro={previa.error} titulo="Não foi possível calcular" />
      {previa.data && (
        <>
          <div className="comparacao">
            <div>
              <span className="suave">Versão atual</span>
              <strong className="num">{brl(previa.data.total_anterior)}</strong>
            </div>
            <div>
              <span className="suave">Novo cálculo</span>
              <strong className="num valor-provisionado">{brl(previa.data.total_provisionado)}</strong>
            </div>
          </div>
          {exigeMotivo && (
            <>
              {alterados.length > 0 ? (
                <table className="tabela tabela-compacta">
                  <caption className="sr-only">Componentes que mudam</caption>
                  <thead>
                    <tr>
                      <th scope="col">Componente</th>
                      <th scope="col" className="num">
                        Diferença
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {alterados.map((it) => {
                      const d = Number(previa.data!.diferencas[it.componente_codigo].diferenca);
                      return (
                        <tr key={it.componente_codigo}>
                          <td>{it.componente_nome}</td>
                          <td className="num">
                            {d > 0 ? "+" : ""}
                            {brl(d)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              ) : (
                <p className="suave">Nenhum componente muda em relação à versão atual.</p>
              )}
              <div className="campo">
                <label htmlFor="motivo">Motivo do recálculo</label>
                <input id="motivo" className="entrada" value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ex.: atualização da PTAX" maxLength={300} />
                <span className="ajuda">Fica registrado no histórico de versões.</span>
              </div>
            </>
          )}
        </>
      )}
      <AvisoErro erro={registrar.error} />
    </Dialogo>
  );
}

function DialogoCancelamento({ importacao, aoFechar, aoConcluir }: { importacao: Importacao; aoFechar: () => void; aoConcluir: () => void }) {
  const [motivo, setMotivo] = useState("");
  const cancelar = useMutation({
    mutationFn: () => api.post(`/importacoes/${importacao.id}/cancelar`, { motivo }),
    onSuccess: aoConcluir,
  });
  return (
    <Dialogo
      aberto
      titulo={`Cancelar ${importacao.numero_processo}`}
      aoFechar={aoFechar}
      rodape={
        <>
          <button className="botao botao-texto" onClick={aoFechar}>
            Manter processo
          </button>
          <button className="botao botao-perigo" disabled={motivo.trim().length < 5 || cancelar.isPending} onClick={() => cancelar.mutate()}>
            Cancelar processo
          </button>
        </>
      }
    >
      <p>O processo sai da provisão e não poderá mais ser editado ou calculado. O histórico continua disponível.</p>
      <div className="campo">
        <label htmlFor="motivo-cancelamento">Motivo</label>
        <input id="motivo-cancelamento" className="entrada" value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={300} />
      </div>
      <AvisoErro erro={cancelar.error} />
    </Dialogo>
  );
}

function DialogoFechamento({ importacao, aoFechar, aoConcluir }: { importacao: Importacao; aoFechar: () => void; aoConcluir: () => void }) {
  // Cada item que compõe a despesa recebe o valor realizado (a fatura de cada despesa é individual)
  const itens = (importacao.calculo_vigente?.itens ?? []).filter((it) => it.compoe_provisao);
  const codigos = itens.map((it) => it.componente_codigo);
  const [numero, setNumero] = useState("");
  const [textos, setTextos] = useState<Record<string, string>>({});
  const [erros, setErros] = useState<ResultadoFechamento["erros"]>({ itens: {} });
  const fechar = useMutation({
    mutationFn: (corpo: { numero_fatura: string; despesas: DespesaInformada[] }) =>
      api.post<Importacao>(`/importacoes/${importacao.id}/fechar`, { versao: importacao.versao, ...corpo }),
    onSuccess: aoConcluir,
  });

  const provisionado = importacao.calculo_vigente?.total_provisionado ?? "0";
  const { total } = validarFechamento(numero, textos, codigos);
  const informou = codigos.some((c) => (textos[c] ?? "").trim() !== "");
  const errosServidor = fechar.error instanceof ErroApi ? fechar.error.campos : {};
  const erroNumero = erros.numero ?? errosServidor.numero_fatura;
  // Erro do número aparece junto do campo; o aviso geral cobre o restante (409, itens faltando, regras de negócio)
  const soNumero = Object.keys(errosServidor).length > 0 && Object.keys(errosServidor).every((k) => k === "numero_fatura");
  const erroGeral = soNumero ? null : fechar.error;

  function enviar(e: FormEvent) {
    e.preventDefault();
    const r = validarFechamento(numero, textos, codigos);
    setErros(r.erros);
    if (!r.despesas || r.erros.numero) return;
    fechar.mutate({ numero_fatura: numero.trim(), despesas: r.despesas });
  }

  return (
    <Dialogo
      aberto
      titulo={`Fechar despesa de ${importacao.numero_processo}`}
      aoFechar={aoFechar}
      rodape={
        <>
          <button type="button" className="botao botao-texto" onClick={aoFechar}>
            Cancelar
          </button>
          <button type="submit" form="form-fechamento" className="botao botao-primario" disabled={fechar.isPending}>
            {fechar.isPending ? "Fechando…" : "Fechar despesa"}
          </button>
        </>
      }
    >
      <form id="form-fechamento" className="form-dialogo" onSubmit={enviar} noValidate>
        <p>
          Informe o valor realizado de cada item da despesa. Depois de fechado, o processo não pode ser editado,
          recalculado nem cancelado.
        </p>
        <div className="campo">
          <label htmlFor="fatura-numero">Número da fatura</label>
          <input
            id="fatura-numero"
            className="entrada"
            value={numero}
            onChange={(e) => {
              setNumero(e.target.value);
              setErros(({ numero: _, ...resto }) => resto);
            }}
            maxLength={60}
            aria-invalid={Boolean(erroNumero)}
            aria-describedby={erroNumero ? "fatura-numero-erro" : undefined}
          />
          {erroNumero && (
            <span className="erro-campo" id="fatura-numero-erro">
              {erroNumero}
            </span>
          )}
        </div>
        <table className="tabela tabela-compacta">
          <caption className="sr-only">Valor realizado de cada item da despesa</caption>
          <thead>
            <tr>
              <th scope="col">Item</th>
              <th scope="col" className="num">
                Provisionado
              </th>
              <th scope="col" className="num">
                Realizado (R$)
              </th>
            </tr>
          </thead>
          <tbody>
            {itens.map((it) => {
              const codigo = it.componente_codigo;
              const erro = erros.itens[codigo];
              return (
                <tr key={codigo}>
                  <td>
                    <label htmlFor={`despesa-${codigo}`}>{it.componente_nome}</label>
                  </td>
                  <td className="num">{brl(it.valor)}</td>
                  <td>
                    <input
                      id={`despesa-${codigo}`}
                      className="entrada num"
                      inputMode="decimal"
                      value={textos[codigo] ?? ""}
                      onChange={(e) => {
                        setTextos((atual) => ({ ...atual, [codigo]: e.target.value }));
                        setErros(({ itens: antigos, ...resto }) => {
                          const { [codigo]: _, ...itensRestantes } = antigos;
                          return { ...resto, itens: itensRestantes, total: undefined };
                        });
                      }}
                      aria-invalid={Boolean(erro)}
                      aria-describedby={erro ? `despesa-${codigo}-erro` : undefined}
                    />
                    {erro && (
                      <span className="erro-campo" id={`despesa-${codigo}-erro`}>
                        {erro}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {erros.total && (
          <span className="erro-campo" role="alert">
            {erros.total}
          </span>
        )}
        <div className="comparacao comparacao-tres" aria-live="polite">
          <div>
            <span className="suave">Provisionado</span>
            <strong className="num">{brl(provisionado)}</strong>
          </div>
          <div>
            <span className="suave">Realizado</span>
            <strong className="num">{informou ? brl(total) : "–"}</strong>
          </div>
          <div>
            <span className="suave">Diferença</span>
            <strong className="num">{informou ? formatarDiferenca(diferencaProvisao(provisionado, total)) : "–"}</strong>
          </div>
        </div>
        <AvisoErro erro={erroGeral} />
      </form>
    </Dialogo>
  );
}

const ROTULOS_CAMPOS: Record<string, string> = {
  taxa_usd: "taxa USD", taxa_cny: "taxa CNY", valor_invoice: "invoice", valor_frete: "frete",
  qtd_itens: "itens", qtd_containers: "containers", observacoes: "observações", status: "situação",
  calculo_desatualizado: "indicador de recálculo", numero_ip: "número da IP", data_ip: "data da IP",
  data_prevista: "data prevista", motivo_cancelamento: "motivo do cancelamento",
  valor_taxa_liberacao: "taxa de liberação", valor_siscomex: "taxa Siscomex", valor_fatura: "valor da fatura",
  numero_fatura: "número da fatura", fechado_em: "data do fechamento", fechado_por: "responsável pelo fechamento",
  // Nomes de colunas anteriores, para o histórico de auditoria de processos antigos
  numero_declaracao: "número da IP", data_declaracao: "data da IP", tipo_declaracao: "tipo de declaração",
  transportadora_secundaria_id: "transportadora secundária",
};

type AbaHistorico = "versoes" | "alteracoes";

/**
 * Versões do cálculo e alterações do processo em um só painel com abas.
 * As listas rolam dentro do painel, então a coluna lateral não cresce com o histórico.
 */
function PainelHistorico({
  id,
  versoes,
  versaoSelecionada,
  comAlteracoes,
  aoEscolher,
}: {
  id: string;
  versoes: Resumo[] | undefined;
  versaoSelecionada: string | null;
  comAlteracoes: boolean;
  aoEscolher: (v: Resumo) => void;
}) {
  const [aba, setAba] = useState<AbaHistorico>("versoes");
  const alteracoes = useQuery({
    queryKey: ["auditoria", "importacao", id],
    queryFn: () => api.get<{ itens: RegistroAuditoria[] }>(`/auditoria?tabela=importacao&registro_id=${id}&tamanho=20`),
    enabled: comAlteracoes,
  });

  const abas: { id: AbaHistorico; rotulo: string; total: number | null }[] = [
    { id: "versoes", rotulo: "Versões", total: versoes?.length ?? null },
    ...(comAlteracoes ? [{ id: "alteracoes" as const, rotulo: "Alterações", total: alteracoes.data?.itens.length ?? null }] : []),
  ];

  // Setas esquerda/direita, Home e End trocam de aba (padrão WAI-ARIA para abas)
  function aoTeclar(e: KeyboardEvent<HTMLDivElement>) {
    const atual = abas.findIndex((a) => a.id === aba);
    let alvo = atual;
    if (e.key === "ArrowRight") alvo = (atual + 1) % abas.length;
    else if (e.key === "ArrowLeft") alvo = (atual - 1 + abas.length) % abas.length;
    else if (e.key === "Home") alvo = 0;
    else if (e.key === "End") alvo = abas.length - 1;
    else return;
    e.preventDefault();
    setAba(abas[alvo].id);
    document.getElementById(`aba-${abas[alvo].id}`)?.focus();
  }

  return (
    <section className="painel" aria-labelledby="t-historico">
      <div className="painel-topo painel-topo-abas">
        <h2 id="t-historico" className="sr-only">
          Histórico do processo
        </h2>
        <div className="abas" role="tablist" aria-labelledby="t-historico" onKeyDown={aoTeclar}>
          {abas.map((a) => (
            <button
              key={a.id}
              id={`aba-${a.id}`}
              type="button"
              role="tab"
              className="aba"
              aria-selected={aba === a.id}
              aria-controls={`painel-${a.id}`}
              tabIndex={aba === a.id ? 0 : -1}
              onClick={() => setAba(a.id)}
            >
              {a.rotulo}
              {a.total !== null && <span className="aba-contagem">{a.total}</span>}
            </button>
          ))}
        </div>
      </div>

      {aba === "versoes" && (
        <div id="painel-versoes" role="tabpanel" aria-labelledby="aba-versoes" tabIndex={0} className="historico-rolagem">
          {versoes?.length ? (
            <ol className="versoes">
              {versoes.map((v) => {
                const ativa = versaoSelecionada ? v.id === versaoSelecionada : v.vigente;
                return (
                  <li key={v.id}>
                    <button className="versao" aria-current={ativa ? "true" : undefined} onClick={() => aoEscolher(v)}>
                      <span className="versao-topo">
                        <strong>
                          v{v.numero_versao}
                          {v.vigente && <span className="versao-selo">vigente</span>}
                        </strong>
                        <span className="num">{brl(v.total_provisionado)}</span>
                      </span>
                      <span className="suave">
                        {dataHora(v.calculado_em)}, {v.calculado_por_nome}
                      </span>
                      <span className="versao-motivo" title={v.motivo}>
                        {v.motivo}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          ) : (
            <p className="painel-corpo suave">Nenhuma versão registrada.</p>
          )}
        </div>
      )}

      {aba === "alteracoes" && (
        <div id="painel-alteracoes" role="tabpanel" aria-labelledby="aba-alteracoes" tabIndex={0} className="historico-rolagem">
          {alteracoes.data?.itens.length ? (
            <ol className="linha-tempo">
              {alteracoes.data.itens.map((a) => (
                <li key={a.id}>
                  <span className="suave">
                    {dataHora(a.ocorrido_em)}, {a.usuario_nome}
                  </span>
                  <span>
                    {a.acao === "INSERT"
                      ? "Cadastrou o processo"
                      : a.campos_alterados?.includes("numero_fatura")
                        ? "Fechou a despesa"
                        : `Alterou ${(a.campos_alterados ?? []).map((c) => ROTULOS_CAMPOS[c] ?? c.replace(/_/g, " ")).join(", ")}`}
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="painel-corpo suave">{alteracoes.isLoading ? "Carregando…" : "Nenhuma alteração registrada."}</p>
          )}
        </div>
      )}
    </section>
  );
}
