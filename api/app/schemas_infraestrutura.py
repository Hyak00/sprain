from pydantic import BaseModel, ConfigDict, Field


class VeiculoDimensoes(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    altura_m: float = Field(gt=0, le=10)
    largura_m: float = Field(gt=0, le=10)
    comprimento_m: float = Field(gt=0, le=100)
    peso_total_t: float = Field(gt=0, le=300, description="Peso com carga, em toneladas")
    eixos: int = Field(ge=2, le=15)
