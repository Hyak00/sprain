from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from pydantic import model_validator
from datetime import datetime, timezone
from app.schemas_infraestrutura import VeiculoDimensoes

class CustosCaminhao(BaseModel):
    """Premissas informadas, nunca inferidas do peso ou do modelo do veiculo."""
    custo_por_km: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    custo_hora_motorista: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    custo_operacional_veiculo_hora: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    custo_atraso_hora: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    prejuizo_potencial_alagamento: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)

class VeiculoCreate(BaseModel):
    tenant_id: str = "demo_corp"
    id_veiculo: str
    placa: str
    modelo: str
    tipo_veiculo: str = "VUC"
    lat_atual: Optional[float] = None
    lon_atual: Optional[float] = None
    dimensoes: Optional[VeiculoDimensoes] = None
    custos_operacionais: Optional[CustosCaminhao] = None

class OperacaoCreate(BaseModel):
    tenant_id: str = "demo_corp"
    id_operacao: str
    id_veiculo: Optional[str] = None
    origem_nome: str
    origem_lat: float = Field(..., ge=-90, le=90)
    origem_lon: float = Field(..., ge=-180, le=180)
    destino_nome: str
    destino_lat: float = Field(..., ge=-90, le=90)
    destino_lon: float = Field(..., ge=-180, le=180)
    janela_inicio: str
    janela_fim: str
    dimensoes: Optional[VeiculoDimensoes] = None
    custos_operacionais: Optional[CustosCaminhao] = None

    @model_validator(mode='after')
    def validar_janela(self):
        valores=[]
        for campo in ('janela_inicio','janela_fim'):
            texto=getattr(self,campo)
            if not texto:
                valores.append(None)
                continue
            valor=datetime.fromisoformat(texto.replace('Z','+00:00'))
            if valor.tzinfo:
                valor=valor.astimezone(timezone.utc).replace(tzinfo=None)
            setattr(self,campo,valor.isoformat())
            valores.append(valor)
        if all(valores) and valores[1]<=valores[0]:
            raise ValueError('Fim da janela deve ser posterior ao inicio.')
        return self

class ParametrosFinanceiros(BaseModel):
    custo_por_km: float = 4.50
    custo_hora_motorista: float = 35.00
    custo_operacional_veiculo_hora: float = 50.00
    custo_atraso_hora: float = 120.00
    prejuizo_potencial_alagamento: float = 0.00

class SimulacaoB2BRequest(BaseModel):
    tenant_id: str = "demo_corp"
    precipitacao_mm: float = Field(..., ge=0.0, le=250.0)
    parametros_custo: ParametrosFinanceiros = ParametrosFinanceiros()

class AlertaRapidoCreate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    nivel: str = Field(..., pattern="^(VERDE|AMARELO|LARANJA|VERMELHO)$")
    corporacao: str = Field(default="DEFESA_CIVIL")
    observacao: Optional[str] = None

class OcorrenciaTextoCreate(BaseModel):
    texto: str
    fonte: str = "OPERACIONAL"

class ResumoEstatisticas(BaseModel):
    total_trechos: int
    criticos: int
    altos: int
    medios: int
    baixos: int
    ivi_medio: float
    trechos_interditados: int

class WebhookAlertaRequest(BaseModel):
    webhook_url: str
    id_operacao: str
    tenant_id: str = "demo_corp"

class PlanejamentoD1Request(BaseModel):
    data_alvo: str
    previsao_chuva_mm: float
    fator_severidade: float = 1.0
    tenant_id: str = "demo_corp"
