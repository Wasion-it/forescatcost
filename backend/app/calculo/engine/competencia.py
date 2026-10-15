"""Regras de competência (mês em que o valor entra na provisão)."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from dateutil.relativedelta import relativedelta


class RegraCompetencia(StrEnum):
    MES_REFERENCIA = "MES_REFERENCIA"
    """Mês da data da IP (ou da data prevista, se ainda não houver IP)."""
    CORTE_DIA = "CORTE_DIA"
    """Se o dia for maior que o dia de corte, provisiona no mês seguinte."""


def competencia(data_ref: date, regra: RegraCompetencia, dia_corte: int = 15) -> date:
    """Retorna o primeiro dia do mês de competência."""
    inicio_mes = data_ref.replace(day=1)
    if regra is RegraCompetencia.CORTE_DIA and data_ref.day > dia_corte:
        return inicio_mes + relativedelta(months=1)
    return inicio_mes
