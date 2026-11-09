import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { PERM, useAuth } from "../../auth/Autenticacao";
import { AvisoErro, Cabecalho, Carregando, Dialogo, Notificacao, Status } from "../../componentes/comuns";
import { api, baixar, ErroApi } from "../../lib/api";
import { MARGEM_PROVISAO_PCT } from "../../lib/margem";
import { diferencaProvisao, validarFechamentoItem, type ResultadoFechamento } from "../../lib/fechamento";
import { brl, data, dataHora, decimal2, mesLongo, paraDecimal } from "../../lib/formato";
import type { Calculo, CalculoItem, DespesaFechada, Importacao, Previa, RegistroAuditoria } from "../../lib/tipos";
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
  const [fechando, setFechando] = useState<CalculoItem | null>(null);
  const [animar, setAnimar] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const [exportando, setExportando] = useState(false);
  const [erroExport, setErroExport] = useState<unknown>(null);

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

  async function exportar() {
    if (!imp.data?.calculo_vigente) return;
    setExportando(true);
    setErroExport(null);
    try {
      const { numero_processo, calculo_vigente } = imp.data;
      await baixar(`/importacoes/${id}/excel`, `provisao-${numero_processo}-v${calculo_vigente.numero_versao}.xlsx`);
      setAviso("Planilha exportada.");
    } catch (e) {
      setErroExport(e);
    } finally {
      setExportando(false);
    }
  }

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
  // Com algum item fechado, o cálculo vigente fica congelado: sem editar, recalcular ou cancelar
  const temFechamento = i.despesas_fechadas.length > 0;
  const congelado = cancelado || fechado || temFechamento;
  const podeFechar =
    pode(PERM.importacaoEditar) && i.status === "CALCULADO" && !i.calculo_desatualizado && Boolean(i.calculo_vigente);

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
          <>
            {!congelado && pode(PERM.importacaoEditar) && (
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
              <button
                className="botao"
                onClick={() => {
                  const painel = document.getElementById("painel-fechamento");
                  painel?.scrollIntoView({ behavior: "smooth", block: "start" });
                  painel?.focus({ preventScroll: true });
                }}
              >
                Fechar despesas
              </button>
            )}
            {i.calculo_vigente && (
              <button
                className="botao"
                onClick={exportar}
                disabled={exportando}
                title={`Itens da despesa com o provisionado e o provisionado + ${MARGEM_PROVISAO_PCT}%`}
              >
                {exportando ? "Exportando…" : "Exportar Excel"}
              </button>
            )}
            {!congelado && pode(PERM.calcular) && (
              <button className="botao botao-primario" onClick={() => setCalculando(true)}>
                {i.calculo_vigente ? "Recalcular" : "Calcular"}
              </button>
            )}
          </>
        }
      />

      <AvisoErro erro={erroExport} titulo="Não foi possível exportar a planilha" />
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
                temFechamento && calculoExibido.vigente
                  ? Object.fromEntries(i.despesas_fechadas.map((d) => [d.componente_codigo, d.valor]))
                  : undefined
              }
            />
          ) : versaoSelecionada ? (
            <Carregando />
          ) : (
            <div className="vazio">
              <p>Este processo ainda não foi calculado.</p>
              {pode(PERM.calcular) && !congelado && (
                <button className="botao botao-primario" onClick={() => setCalculando(true)}>
                  Calcular agora
                </button>
              )}
            </div>
          )}
        </section>

        <aside className="detalhe-lateral">
          {i.calculo_vigente && (fechado || temFechamento || i.status === "CALCULADO") && (
            <PainelFechamento importacao={i} podeFechar={podeFechar} aoFechar={setFechando} />
          )}

          <section className="painel" aria-labelledby="t-dados">
            <div className="painel-topo">
              <h2 id="t-dados">Dados do processo</h2>
            </div>
            <dl className="manifesto">
              <Dado rotulo="Número da invoice" valor={i.numero_invoice ?? "–"} />
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
        <DialogoFechamentoItem
          importacao={i}
          item={fechando}
          aoFechar={() => setFechando(null)}
          aoConcluir={(atualizado) => {
            setFechando(null);
            setAviso(
              atualizado.status === "FECHADO"
                ? `Fatura de ${fechando.componente_nome} registrada. Todas as despesas do processo estão fechadas.`
                : `Fatura de ${fechando.componente_nome} registrada.`,
            );
            cliente.setQueryData(["importacao", id], atualizado);
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

/**
 * Itens da despesa do processo, cada um fechado com a própria fatura quando ela chega.
 * O processo fica "Fechado" junto com o último item.
 */
function PainelFechamento({
  importacao: i,
  podeFechar,
  aoFechar,
}: {
  importacao: Importacao;
  podeFechar: boolean;
  aoFechar: (item: CalculoItem) => void;
}) {
  const itens = (i.calculo_vigente?.itens ?? []).filter((it) => it.compoe_provisao);
  const porCodigo = new Map<string, DespesaFechada>(i.despesas_fechadas.map((d) => [d.componente_codigo, d]));
  const fechados = itens.filter((it) => porCodigo.has(it.componente_codigo)).length;
  const fechado = i.status === "FECHADO";
  // Processos fechados antes do fechamento por item têm só o total e um número de fatura
  const legado = fechado && i.despesas_fechadas.length === 0;
  const realizado = i.despesas_fechadas.reduce((s, d) => s + Number(d.valor), 0);

  return (
    <section className="painel" aria-labelledby="t-fechamento" id="painel-fechamento" tabIndex={-1}>
      <div className="painel-topo">
        <h2 id="t-fechamento">Fechamento da despesa</h2>
        {fechado ? (
          <Status status="FECHADO" />
        ) : (
          <span className="suave">
            {fechados} de {itens.length} {itens.length === 1 ? "fechado" : "fechados"}
          </span>
        )}
      </div>

      {!legado && (
        <ul className="despesas">
          {itens.map((it) => {
            const d = porCodigo.get(it.componente_codigo);
            return (
              <li key={it.componente_codigo} className={d ? "despesa-fechada" : undefined}>
                <span className="despesa-nome">
                  <strong>{it.componente_nome}</strong>
                  <span className="suave">
                    {d
                      ? `Fatura ${d.numero_fatura}, ${dataHora(d.fechado_em)}${d.fechado_por_nome ? `, ${d.fechado_por_nome}` : ""}`
                      : `Provisionado ${brl(it.valor)}`}
                  </span>
                </span>
                {d ? (
                  <span className="despesa-valor">
                    <span className="num">{brl(d.valor)}</span>
                    <span className="suave num">{formatarDiferenca(diferencaProvisao(it.valor, d.valor))}</span>
                  </span>
                ) : podeFechar ? (
                  <button
                    type="button"
                    className="botao botao-pequeno"
                    onClick={() => aoFechar(it)}
                    aria-label={`Fechar ${it.componente_nome}`}
                  >
                    Fechar
                  </button>
                ) : (
                  <span className="suave">Pendente</span>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {fechado ? (
        <dl className="manifesto">
          {legado && <Dado rotulo="Número da fatura" valor={i.numero_fatura ?? "–"} />}
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
      ) : fechados > 0 ? (
        <>
          <dl className="manifesto">
            <Dado rotulo="Realizado até agora" valor={brl(realizado)} />
          </dl>
          <p className="painel-corpo suave despesas-nota">
            Com despesa fechada, o processo não pode mais ser editado, recalculado nem cancelado.
          </p>
        </>
      ) : (
        <p className="painel-corpo suave despesas-nota">
          {i.calculo_desatualizado
            ? "Recalcule o processo para fechar as despesas."
            : "Feche cada item quando a fatura dele chegar. O processo fica fechado junto com o último."}
        </p>
      )}
    </section>
  );
}

function DialogoFechamentoItem({
  importacao,
  item,
  aoFechar,
  aoConcluir,
}: {
  importacao: Importacao;
  item: CalculoItem;
  aoFechar: () => void;
  aoConcluir: (atualizado: Importacao) => void;
}) {
  const [numero, setNumero] = useState("");
  const [valorTexto, setValorTexto] = useState("");
  const [erros, setErros] = useState<ResultadoFechamento["erros"]>({});
  const fechar = useMutation({
    mutationFn: (corpo: { numero_fatura: string; valor: string }) =>
      api.post<Importacao>(
        `/importacoes/${importacao.id}/despesas/${encodeURIComponent(item.componente_codigo)}/fechar`,
        { versao: importacao.versao, ...corpo },
      ),
    onSuccess: aoConcluir,
  });

  const pendentes = (importacao.calculo_vigente?.itens ?? []).filter(
    (it) => it.compoe_provisao && !importacao.despesas_fechadas.some((d) => d.componente_codigo === it.componente_codigo),
  );
  const ultimo = pendentes.length === 1;
  const primeiro = importacao.despesas_fechadas.length === 0;
  let valorDigitado: string | null = null;
  try {
    valorDigitado = paraDecimal(valorTexto);
  } catch {
    valorDigitado = null;
  }
  const errosServidor = fechar.error instanceof ErroApi ? fechar.error.campos : {};
  const erroNumero = erros.numero ?? errosServidor.numero_fatura;
  const erroValor = erros.valor ?? errosServidor.valor;
  // Erros de campo aparecem junto do campo; o aviso geral cobre o restante (409, regras de negócio)
  const soCampos =
    Object.keys(errosServidor).length > 0 && Object.keys(errosServidor).every((k) => k === "numero_fatura" || k === "valor");
  const erroGeral = soCampos ? null : fechar.error;

  function enviar(e: FormEvent) {
    e.preventDefault();
    const r = validarFechamentoItem(numero, valorTexto);
    setErros(r.erros);
    if (r.erros.numero || r.valor === null) return;
    fechar.mutate({ numero_fatura: numero.trim(), valor: r.valor });
  }

  return (
    <Dialogo
      aberto
      titulo={`Fechar ${item.componente_nome}`}
      aoFechar={aoFechar}
      rodape={
        <>
          <button type="button" className="botao botao-texto" onClick={aoFechar}>
            Cancelar
          </button>
          <button type="submit" form="form-fechamento" className="botao botao-primario" disabled={fechar.isPending}>
            {fechar.isPending ? "Fechando…" : `Fechar ${item.componente_nome}`}
          </button>
        </>
      }
    >
      <form id="form-fechamento" className="form-dialogo" onSubmit={enviar} noValidate>
        <p>
          Informe a fatura de {item.componente_nome} do processo {importacao.numero_processo}.
          {ultimo
            ? " É o último item pendente: a despesa do processo fica fechada."
            : primeiro
              ? " Depois do primeiro fechamento, o processo não pode mais ser editado, recalculado nem cancelado."
              : null}
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
        <div className="campo">
          <label htmlFor="fatura-valor">Valor da fatura (R$)</label>
          <input
            id="fatura-valor"
            className="entrada num"
            inputMode="decimal"
            value={valorTexto}
            onChange={(e) => {
              setValorTexto(e.target.value);
              setErros(({ valor: _, ...resto }) => resto);
            }}
            aria-invalid={Boolean(erroValor)}
            aria-describedby={erroValor ? "fatura-valor-erro" : undefined}
          />
          {erroValor && (
            <span className="erro-campo" id="fatura-valor-erro">
              {erroValor}
            </span>
          )}
        </div>
        <div className="comparacao comparacao-tres" aria-live="polite">
          <div>
            <span className="suave">Provisionado</span>
            <strong className="num">{brl(item.valor)}</strong>
          </div>
          <div>
            <span className="suave">Fatura</span>
            <strong className="num">{valorDigitado !== null ? brl(valorDigitado) : "–"}</strong>
          </div>
          <div>
            <span className="suave">Diferença</span>
            <strong className="num">
              {valorDigitado !== null ? formatarDiferenca(diferencaProvisao(item.valor, valorDigitado)) : "–"}
            </strong>
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
  calculo_desatualizado: "indicador de recálculo", numero_ip: "número da IP", numero_invoice: "número da invoice", data_ip: "data da IP",
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
                      : a.campos_alterados?.includes("valor_fatura")
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
