"""Motor de cálculo (domínio puro)."""

from .avaliador import ErroFormula, avaliar, compilar, variaveis_referenciadas
from .competencia import RegraCompetencia, competencia
from .pipeline import (
    Componente,
    Entradas,
    ErroCalculo,
    ResultadoCalculo,
    ResultadoComponente,
    calcular,
)

__all__ = [
    "Componente",
    "Entradas",
    "ErroCalculo",
    "ErroFormula",
    "RegraCompetencia",
    "ResultadoCalculo",
    "ResultadoComponente",
    "avaliar",
    "calcular",
    "compilar",
    "competencia",
    "variaveis_referenciadas",
]
