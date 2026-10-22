"""Carga inicial: perfis, cadastros, parâmetros, alíquotas de EXEMPLO e fórmulas v1.

Uso:
    python -m app.seed              # dados base
    python -m app.seed --exemplos   # dados base + processos de exemplo

As alíquotas e alguns valores são ilustrativos e precisam ser validados pelo Fiscal.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculo.formulas_padrao import COMPONENTES_PADRAO
from app.core.db import SessionLocal, definir_usuario_sessao
from app.core.deps import Permissoes as P
from app.core.security import gerar_hash_senha
from app.models import (
    Aliquota,
    ComponenteCusto,
    Despachante,
    Formula,
    Imposto,
    Moeda,
    Parametro,
    ParametroValor,
    Perfil,
    Permissao,
    Terminal,
    TipoImportacao,
    Transportadora,
    Usuario,
)

D = Decimal
INICIO = date(2026, 1, 1)
EXEMPLO = "Valor de exemplo da carga inicial. Validar com PCM/Fiscal."
JUSTIFICATIVA_SISCOMEX = "Portaria ME 4.131/2021 (vigente desde jun/2021)"
JUSTIFICATIVA_TCIF = "Lei 13.451/2017, art. 8º, § 2º: R$ 250,00 por PLI e R$ 45,00 por mercadoria"
JUSTIFICATIVAS = {"tcif_valor_ip": JUSTIFICATIVA_TCIF, "tcif_valor_item": JUSTIFICATIVA_TCIF}

TERMINAIS = {
    "Chibatão": "MARITIMO",
    "Superterminais": "MARITIMO",
    "Santos Brasil": "MARITIMO",
    "TECA Aeroporto Eduardo Gomes": "AEREO",
}

# Tarifas de armazenagem por terminal, da planilha "Cálculo Armazenagem BR260630-C".
# (terminal, chave do parâmetro, valor, justificativa). Os demais valores usam o padrão.
PLANILHA = "Planilha Cálculo Armazenagem BR260630-C"
# Serviços portuários fixos por processo (aba Custos Marítimos): não multiplicam por container.
SERVICOS_PORTUARIOS = {
    "Chibatão": {
        "arm_mar_pesagem": "130.02", "arm_mar_infra": "570.66", "arm_mar_isps": "99.68",
        "arm_mar_seguro": "97.65", "arm_mar_inspecao": "469.53", "arm_mar_servicos_adm": "77.22",
    },
    "Superterminais": {
        "arm_mar_pesagem": "160.28", "arm_mar_infra": "715.36", "arm_mar_isps": "122.12",
        "arm_mar_seguro": "97.65", "arm_mar_inspecao": "584.70", "arm_mar_servicos_adm": "50.38",
    },
}  # fmt: skip
ARMAZENAGEM_TERMINAL = [
    (terminal, chave, D(valor), f"{PLANILHA}, aba Custos Marítimos: serviços portuários {terminal}")
    for terminal, servicos in SERVICOS_PORTUARIOS.items()
    for chave, valor in servicos.items()
] + [
    ("Santos Brasil", "arm_mar_pct_periodo1", D("0.002"),
     f"{PLANILHA}: armazenagem 1º período de 0,2% do CIF, antes do gross-up de impostos"),
    ("Santos Brasil", "arm_mar_taxas_container", D("1023.02"),
     f"{PLANILHA}: scanner 198 + remoção ao costado 655 + reembolso Embraport 32,72 "
     "+ processamento eletrônico 32,50 + cadastro de BL 52,40 (2 linhas), antes do gross-up"),
    ("Santos Brasil", "arm_mar_pct_impostos", D("0.1425"),
     f"{PLANILHA}: tarifas divididas por 0,8575 (PIS/COFINS + ISS embutidos)"),
]  # fmt: skip
for _chave in ("arm_aer_pct", "arm_aer_taxa_kg", "arm_aer_minimo_peso"):
    JUSTIFICATIVAS[_chave] = f"{PLANILHA}, aba Custos Aéreos (Manaus)"

PERMISSOES = {
    P.IMPORTACAO_LER: "Consultar importações",
    P.IMPORTACAO_EDITAR: "Cadastrar, editar e cancelar importações",
    P.CALCULO_EXECUTAR: "Calcular e recalcular processos",
    P.PARAMETRO_LER: "Consultar parâmetros e alíquotas",
    P.PARAMETRO_EDITAR: "Alterar parâmetros e alíquotas",
    P.CADASTRO_EDITAR: "Manter transportadoras, despachantes e terminais",
    P.PROVISAO_LER: "Consultar provisões, dashboard e exportar",
    P.AUDITORIA_LER: "Consultar a trilha de auditoria",
    P.USUARIO_GERIR: "Gerir usuários e perfis",
}

PERFIS = {
    "PCM": ("PCM", [
        P.IMPORTACAO_LER, P.IMPORTACAO_EDITAR, P.CALCULO_EXECUTAR, P.PARAMETRO_LER,
        P.PARAMETRO_EDITAR, P.CADASTRO_EDITAR, P.PROVISAO_LER, P.AUDITORIA_LER,
    ]),
    "FINANCEIRO": ("Financeiro", [P.IMPORTACAO_LER, P.PARAMETRO_LER, P.PROVISAO_LER, P.AUDITORIA_LER]),
    "ADMIN": ("Administrador", [
        P.IMPORTACAO_LER, P.PARAMETRO_LER, P.PARAMETRO_EDITAR, P.CADASTRO_EDITAR,
        P.PROVISAO_LER, P.AUDITORIA_LER, P.USUARIO_GERIR,
    ]),
}  # fmt: skip

NATUREZA = {
    "CIF": "BASE", "II": "IMPOSTO", "IPI": "IMPOSTO", "PIS": "IMPOSTO", "COFINS": "IMPOSTO",
    "TAXA_SISCOMEX": "IMPOSTO", "ICMS": "IMPOSTO", "TCIF": "TAXA", "TRANSP_LOCAL": "LOGISTICA",
    "ARM_MARITIMA": "LOGISTICA", "ARM_AEREA": "LOGISTICA", "DESPACHANTE": "SERVICO",
    "FRETE_INTL": "LOGISTICA", "TAXA_LIBERACAO": "TAXA",
}  # fmt: skip

# chave: (descrição, tipo, escopo, grupo, valor padrão ou None)
PARAMETROS = {
    "competencia_dia_corte": ("Dia de corte da competência (TCIF)", "INTEIRO", "GLOBAL", "Competência", D(15)),
    "tcif_valor_item": ("TCIF por item", "MONETARIO", "GLOBAL", "TCIF", D(45)),
    "tcif_valor_ip": ("TCIF por IP", "MONETARIO", "GLOBAL", "TCIF", D(250)),
    "siscomex_registro": ("Siscomex, valor por DI/Duimp", "MONETARIO", "GLOBAL", "Siscomex", D("115.67")),
    "siscomex_adicao_faixa1": ("Siscomex por adição, da 1ª à 2ª", "MONETARIO", "GLOBAL", "Siscomex", D("38.56")),
    "siscomex_adicao_faixa2": ("Siscomex por adição, da 3ª à 5ª", "MONETARIO", "GLOBAL", "Siscomex", D("30.85")),
    "siscomex_adicao_faixa3": ("Siscomex por adição, da 6ª à 10ª", "MONETARIO", "GLOBAL", "Siscomex", D("23.14")),
    "siscomex_adicao_faixa4": ("Siscomex por adição, da 11ª à 20ª", "MONETARIO", "GLOBAL", "Siscomex", D("15.42")),
    "siscomex_adicao_faixa5": ("Siscomex por adição, da 21ª à 50ª", "MONETARIO", "GLOBAL", "Siscomex", D("7.71")),
    "siscomex_adicao_faixa6": ("Siscomex por adição, da 51ª em diante", "MONETARIO", "GLOBAL", "Siscomex", D("3.86")),
    "ii_suspenso": ("Imposto de Importação suspenso (não paga)", "BOOLEANO", "TIPO_IMPORTACAO", "Impostos", D(1)),
    "ipi_suspenso": ("IPI suspenso (não paga)", "BOOLEANO", "TIPO_IMPORTACAO", "Impostos", D(1)),
    "tl_valor_container": ("Transporte local por container", "MONETARIO", "TRANSP_LOCAL", "Transporte local", D(1500)),
    "tl_percentual": ("Transporte local sobre o valor da carga", "PERCENTUAL", "TRANSP_LOCAL", "Transporte local", D("0.0006")),
    "arm_mar_pct_periodo1": ("Armazenagem marítima, 1º período, sobre o CIF", "PERCENTUAL", "TERMINAL", "Armazenagem", D("0.0092")),
    "arm_mar_minimo": ("Armazenagem marítima, valor mínimo", "MONETARIO", "TERMINAL", "Armazenagem", D(0)),
    "arm_mar_taxas_container": ("Armazenagem marítima, serviços portuários por container", "MONETARIO", "TERMINAL", "Armazenagem", D(0)),
    "arm_mar_pesagem": ("Armazenagem marítima, pesagem de container (fixo)", "MONETARIO", "TERMINAL", "Armazenagem", D(0)),
    "arm_mar_infra": ("Armazenagem marítima, infraestrutura portuária (fixo)", "MONETARIO", "TERMINAL", "Armazenagem", D(0)),
    "arm_mar_isps": ("Armazenagem marítima, ISPS Code (fixo)", "MONETARIO", "TERMINAL", "Armazenagem", D(0)),
    "arm_mar_seguro": ("Armazenagem marítima, seguro (fixo)", "MONETARIO", "TERMINAL", "Armazenagem", D(0)),
    "arm_mar_inspecao": ("Armazenagem marítima, inspeção não invasiva (fixo)", "MONETARIO", "TERMINAL", "Armazenagem", D(0)),
    "arm_mar_servicos_adm": ("Armazenagem marítima, serviços administrativos (fixo)", "MONETARIO", "TERMINAL", "Armazenagem", D(0)),
    "arm_mar_pct_impostos": ("Armazenagem marítima, impostos embutidos nas tarifas (PIS/COFINS + ISS)", "PERCENTUAL", "TERMINAL", "Armazenagem", D(0)),
    "arm_aer_pct": ("Armazenagem aérea, percentual sobre o CIF", "PERCENTUAL", "TERMINAL", "Armazenagem", D("0.0165")),
    "arm_aer_taxa_kg": ("Armazenagem aérea, tarifa por kg de peso bruto", "MONETARIO", "TERMINAL", "Armazenagem", D("0.25")),
    "arm_aer_minimo_peso": ("Armazenagem aérea, mínimo da tarifa de peso", "MONETARIO", "TERMINAL", "Armazenagem", D("20.41")),
    "despachante_honorario_ip": ("Honorário do despachante por IP", "MONETARIO", "TIPO_IMPORTACAO", "Despachante", None),
}  # fmt: skip

ALIQUOTAS = {
    "USO_CONSUMO": {
        "II": "0.14",
        "IPI": "0.10",
        "PIS": "0.021",
        "COFINS": "0.0965",
        "ICMS": "0.20",
    },
    "INDUSTRIALIZACAO": {"II": "0.0168", "IPI": "0", "PIS": "0", "COFINS": "0", "ICMS": "0"},
}
# Adicionar Ativo: alíquotas de exemplo iguais às de Uso e Consumo (validar com o Fiscal), mas sem
# ICMS. Só Uso e Consumo recolhe ICMS; Industrialização e Adicionar Ativo ficam com 0.
ALIQUOTAS["ADICIONAR_ATIVO"] = {**ALIQUOTAS["USO_CONSUMO"], "ICMS": "0"}

IMPOSTOS = {
    "II": "Imposto de Importação",
    "IPI": "Imposto sobre Produtos Industrializados",
    "PIS": "PIS-Importação",
    "COFINS": "COFINS-Importação",
    "ICMS": "ICMS",
}

SENHA_PADRAO = os.environ.get("SEED_SENHA", "Forecast@2026!")


def seed_base(db: Session) -> None:
    if db.scalar(select(Perfil.id).limit(1)):
        print("Dados base já carregados; nada a fazer.")
        return

    permissoes = {c: Permissao(codigo=c, descricao=d) for c, d in PERMISSOES.items()}
    db.add_all(permissoes.values())
    perfis = {}
    for codigo, (nome, lista) in PERFIS.items():
        perfis[codigo] = Perfil(codigo=codigo, nome=nome, permissoes=[permissoes[p] for p in lista])
    db.add_all(perfis.values())
    db.flush()

    hash_senha = gerar_hash_senha(SENHA_PADRAO)
    for email, nome, perfil in [
        ("admin@forecast.local", "Administrador do Sistema", "ADMIN"),
        ("pcm@forecast.local", "Analista PCM", "PCM"),
        ("financeiro@forecast.local", "Analista Financeiro", "FINANCEIRO"),
    ]:
        db.add(Usuario(email=email, nome=nome, senha_hash=hash_senha, perfis=[perfis[perfil]]))

    for codigo, nome, simbolo in [
        ("BRL", "Real", "R$"),
        ("USD", "Dólar americano", "US$"),
        ("CNY", "Yuan chinês", "¥"),
    ]:
        db.add(Moeda(codigo=codigo, nome=nome, simbolo=simbolo))
    tipos = {
        "USO_CONSUMO": TipoImportacao(codigo="USO_CONSUMO", nome="Uso e Consumo"),
        "INDUSTRIALIZACAO": TipoImportacao(codigo="INDUSTRIALIZACAO", nome="Industrialização"),
        "ADICIONAR_ATIVO": TipoImportacao(codigo="ADICIONAR_ATIVO", nome="Adicionar Ativo"),
    }
    db.add_all(tipos.values())

    terminais = {
        nome: Terminal(nome=nome, modal=modal) for nome, modal in TERMINAIS.items()
    }
    db.add_all([
        Transportadora(nome="Rodo Norte Logística", tipo_servico="LOCAL"),
        Transportadora(nome="Amazon Cargo Transportes", tipo_servico="LOCAL"),
        Despachante(nome="Despachos Manaus Assessoria"),
        Despachante(nome="Aduana Norte Comissária"),
        *terminais.values(),
    ])  # fmt: skip
    db.flush()

    for chave, (descricao, tipo, escopo, grupo, padrao) in PARAMETROS.items():
        p = Parametro(chave=chave, descricao=descricao, tipo_valor=tipo, escopo=escopo, grupo=grupo)
        db.add(p)
        db.flush()
        if padrao is not None:
            justificativa = JUSTIFICATIVAS.get(
                chave, JUSTIFICATIVA_SISCOMEX if chave.startswith("siscomex_") else EXEMPLO
            )
            db.add(
                ParametroValor(
                    parametro_id=p.id, valor=padrao, vigencia_inicio=INICIO,
                    justificativa=justificativa,
                )
            )  # fmt: skip
        if chave == "despachante_honorario_ip":
            for codigo, valor in [
                ("INDUSTRIALIZACAO", D(715)), ("USO_CONSUMO", D(900)), ("ADICIONAR_ATIVO", D(900)),
            ]:
                db.add(ParametroValor(
                    parametro_id=p.id, escopo_ref_id=tipos[codigo].id, valor=valor,
                    vigencia_inicio=INICIO, justificativa="Valores informados pelo PCM",
                ))  # fmt: skip
        for terminal, chave_param, valor, justificativa in ARMAZENAGEM_TERMINAL:
            if chave_param == chave:
                db.add(ParametroValor(
                    parametro_id=p.id, escopo_ref_id=terminais[terminal].id, valor=valor,
                    vigencia_inicio=INICIO, justificativa=justificativa,
                ))  # fmt: skip

    impostos = {}
    for codigo, nome in IMPOSTOS.items():
        impostos[codigo] = Imposto(codigo=codigo, nome=nome)
    db.add_all(impostos.values())
    db.flush()
    for tipo_codigo, aliquotas in ALIQUOTAS.items():
        for imposto, valor in aliquotas.items():
            db.add(Aliquota(
                imposto_id=impostos[imposto].id, tipo_importacao_id=tipos[tipo_codigo].id,
                percentual=D(valor), vigencia_inicio=INICIO, justificativa=EXEMPLO,
            ))  # fmt: skip

    for comp in COMPONENTES_PADRAO:
        orm = ComponenteCusto(
            codigo=comp.codigo, nome=comp.nome, natureza=NATUREZA[comp.codigo],
            compoe_provisao=comp.compoe_provisao, regra_competencia=comp.regra_competencia.value,
            ordem=comp.ordem,
        )  # fmt: skip
        db.add(orm)
        db.flush()
        db.add(Formula(
            componente_id=orm.id, versao=1, expressao=comp.expressao,
            status="PUBLICADA", vigencia_inicio=INICIO,
        ))  # fmt: skip
    db.flush()
    print("Dados base carregados.")


def seed_exemplos(db: Session) -> None:
    from app.modules.calculo import service as calculo
    from app.modules.importacoes import service as importacoes
    from app.modules.importacoes.schemas import (
        DespesaFechamento,
        FechamentoDespesa,
        ImportacaoEntrada,
    )

    if db.scalar(select(ComponenteCusto.id).limit(1)) is None:
        raise RuntimeError("Carregue os dados base antes dos exemplos")
    from app.models import Importacao

    if db.scalar(select(Importacao.id).limit(1)):
        print("Já existem processos; exemplos não carregados.")
        return

    pcm = db.scalar(select(Usuario).where(Usuario.email == "pcm@forecast.local"))
    definir_usuario_sessao(db, pcm.id, "seed-exemplos")
    tipo = {t.codigo: t.id for t in db.scalars(select(TipoImportacao))}
    transp = {t.nome: t.id for t in db.scalars(select(Transportadora))}
    desp = {d.nome: d.id for d in db.scalars(select(Despachante))}
    term = {t.nome: t.id for t in db.scalars(select(Terminal))}

    def base(**kw):
        padrao = dict(
            modal="MARITIMO", moeda_invoice="USD", moeda_frete="USD",
            taxa_usd=D("5.4210"), taxa_cny=D("0.7512"),
            transportadora_local_id=transp["Rodo Norte Logística"],
            despachante_id=desp["Despachos Manaus Assessoria"], terminal_id=term["Chibatão"],
        )  # fmt: skip
        padrao.update(kw)
        return ImportacaoEntrada(**padrao)

    exemplos = [
        (base(numero_ip="IP-26-0001", data_ip=date(2026, 8, 5),
              tipo_importacao_id=tipo["INDUSTRIALIZACAO"], valor_invoice=D("182000"), valor_frete=D("6400"),
              qtd_itens=14, qtd_containers=2, peso_bruto_kg=D("18400"), peso_liquido_kg=D("17100"),
              valor_taxa_liberacao=D(350), observacoes="Placas eletrônicas para linha de montagem"),
         "calcular_e_fechar"),
        (base(numero_ip="IP-26-0002", data_ip=date(2026, 8, 21),
              tipo_importacao_id=tipo["USO_CONSUMO"], valor_invoice=D("38500"), valor_frete=D("2900"),
              qtd_itens=6, qtd_containers=1, peso_bruto_kg=D("4200"), peso_liquido_kg=D("3900"),
              valor_taxa_liberacao=D(420), observacoes="Peças de manutenção"), "calcular"),
        (base(numero_ip="IP-26-0003", data_ip=date(2026, 9, 9),
              tipo_importacao_id=tipo["INDUSTRIALIZACAO"], moeda_invoice="CNY", valor_invoice=D("1450000"),
              valor_frete=D("8200"), qtd_itens=32, qtd_containers=4, peso_bruto_kg=D("52000"),
              peso_liquido_kg=D("49800"), valor_taxa_liberacao=D(280), observacoes="Componentes plásticos injetados"), "calcular"),
        (base(numero_ip="IP-26-0004", data_ip=date(2026, 9, 18),
              tipo_importacao_id=tipo["USO_CONSUMO"], modal="AEREO", valor_invoice=D("12800"),
              valor_frete=D("1650"), qtd_itens=3, qtd_containers=0, peso_bruto_kg=D("380"),
              peso_liquido_kg=D("340"),
              terminal_id=term["TECA Aeroporto Eduardo Gomes"], valor_taxa_liberacao=D(510),
              observacoes="Ferramental urgente"), "calcular"),
        (base(numero_ip="IP-26-0005", data_ip=date(2026, 10, 2),
              tipo_importacao_id=tipo["INDUSTRIALIZACAO"], valor_invoice=D("265000"), valor_frete=D("9800"),
              qtd_itens=21, qtd_containers=3, peso_bruto_kg=D("31000"), peso_liquido_kg=D("29400"),
              transportadora_local_id=transp["Amazon Cargo Transportes"],
              valor_taxa_liberacao=D(390)), "calcular"),
        (base(numero_ip="IP-26-0006", data_ip=date(2026, 10, 21),
              tipo_importacao_id=tipo["ADICIONAR_ATIVO"], valor_invoice=D("76000"), valor_frete=D("4100"),
              qtd_itens=5, qtd_containers=1, peso_bruto_kg=D("8300"), peso_liquido_kg=D("7900"),
              valor_taxa_liberacao=D(350), observacoes="Máquina para adicionar ao ativo imobilizado"),
         "calcular"),
        (base(numero_ip="IP-26-0007", data_ip=date(2026, 10, 16),
              tipo_importacao_id=tipo["INDUSTRIALIZACAO"], moeda_invoice="CNY", valor_invoice=D("980000"),
              valor_frete=D("7100"), qtd_itens=18, qtd_containers=3, peso_bruto_kg=D("27600"),
              peso_liquido_kg=D("26000"), despachante_id=desp["Aduana Norte Comissária"],
              observacoes="IP após o dia 15: TCIF vai para novembro"), "calcular_e_editar"),
        (base(data_prevista=date(2026, 11, 10), tipo_importacao_id=tipo["USO_CONSUMO"],
              valor_invoice=D("54000"), valor_frete=D("3300"), qtd_itens=9, qtd_containers=1,
              peso_bruto_kg=D("6100"), peso_liquido_kg=D("5700"),
              observacoes="Embarque previsto, IP ainda não gerada"), "calcular"),
        (base(data_prevista=date(2026, 12, 3), tipo_importacao_id=tipo["INDUSTRIALIZACAO"],
              valor_invoice=D("310000"), valor_frete=D("11200"), qtd_itens=25, qtd_containers=4,
              peso_bruto_kg=D("40100"), peso_liquido_kg=D("38200")), "rascunho"),
        (base(numero_ip="IP-26-0008", data_ip=date(2026, 9, 30),
              tipo_importacao_id=tipo["USO_CONSUMO"], valor_invoice=D("9900"), valor_frete=D("1200"),
              qtd_itens=2, qtd_containers=1, peso_bruto_kg=D("900"), peso_liquido_kg=D("820")), "cancelar"),
    ]  # fmt: skip

    for dados, acao in exemplos:
        imp = importacoes.criar(db, dados, pcm)
        if acao == "rascunho":
            continue
        if acao == "cancelar":
            importacoes.cancelar(db, imp, "Pedido cancelado pelo fornecedor")
            continue
        vigente = calculo.registrar(db, imp, None, pcm)
        if acao == "calcular_e_editar":
            imp.taxa_cny = D("0.7598")
            imp.calculo_desatualizado = True
            db.flush()
        if acao == "calcular_e_fechar":
            db.refresh(imp)
            # Realizado = provisionado em cada item, com R$ 120,50 a mais no último
            itens = [i for i in vigente.itens if i.compoe_provisao]
            despesas = [
                DespesaFechamento(
                    componente_codigo=i.componente_codigo,
                    valor=i.valor + (D("120.50") if i is itens[-1] else D(0)),
                )
                for i in itens
            ]
            importacoes.fechar(
                db,
                imp,
                FechamentoDespesa(
                    versao=imp.versao, numero_fatura="FT-2026/0412", despesas=despesas
                ),
                pcm,
            )
    print(f"{len(exemplos)} processos de exemplo carregados.")


def main() -> None:
    with SessionLocal() as db:
        seed_base(db)
        db.commit()
        if "--exemplos" in sys.argv:
            seed_exemplos(db)
            db.commit()
    print("Usuários: admin@, pcm@ e financeiro@forecast.local (senha definida em SEED_SENHA).")


if __name__ == "__main__":
    main()
