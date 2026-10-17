from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict, Any
from app.schemas_infraestrutura import VeiculoDimensoes

class ParametrosDecisaoEconomica(BaseModel):
    custo_por_km: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False,
                                           description="Custo por distancia incluindo combustivel; excluir custos horarios informados separadamente.")
    custo_por_km_sem_combustivel: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False,
        description="Outros custos por distancia; usado apenas quando custo_por_km total nao foi informado.")
    consumo_km_l: float = Field(default=3.0, ge=0.5, le=20.0, allow_inf_nan=False)
    preco_diesel_litro: float = Field(default=6.20, ge=1.0, allow_inf_nan=False)
    custo_hora_veiculo: float = Field(default=50.0, ge=0.0, allow_inf_nan=False)
    custo_hora_motorista: float = Field(default=35.0, ge=0.0, allow_inf_nan=False)
    valor_frete: float = Field(default=600.0, ge=0.0, allow_inf_nan=False)
    valor_carga: float = Field(default=25000.0, ge=0.0, allow_inf_nan=False,
                               description="Valor informativo; nao e tratado como prejuizo por bloqueio.")
    prejuizo_por_bloqueio_brl: Optional[float] = Field(default=None, ge=0.0, allow_inf_nan=False,
        description="Perda hipotetica por bloqueio; so entra no custo se houver probabilidade calibrada.")
    multa_por_hora_atraso: float = Field(default=150.0, ge=0.0, allow_inf_nan=False)
    janela_limite_min: float = Field(default=45.0, ge=1.0, allow_inf_nan=False)
    tempo_espera_min: Optional[float] = Field(default=None, ge=0.0, allow_inf_nan=False,
        description="Tempo de espera informado pelo cliente para comparar aguardar e desviar.")

    @model_validator(mode="after")
    def validar_custo_por_km(self):
        if self.custo_por_km is not None and self.custo_por_km_sem_combustivel is not None:
            raise ValueError("Informe custo_por_km total ou custo_por_km_sem_combustivel, nao ambos.")
        return self

class DecisaoEconomicaRequest(BaseModel):
    id_veiculo: Optional[str] = None
    dimensoes: Optional[VeiculoDimensoes] = None
    tenant_id: str = "demo_corp"
    origem_lat: float = Field(..., ge=-90, le=90)
    origem_lon: float = Field(..., ge=-180, le=180)
    destino_lat: float = Field(..., ge=-90, le=90)
    destino_lon: float = Field(..., ge=-180, le=180)
    precipitacao_mm: float = Field(default=60.0, ge=0.0, le=250.0)
    parametros: ParametrosDecisaoEconomica = ParametrosDecisaoEconomica()
