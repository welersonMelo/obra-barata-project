"""Pydantic contracts for the construction material planning flow."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AreaObra(StrEnum):
    """Purchase categories used to organize construction materials."""

    FUNDACAO = "Fundacao"
    ESTRUTURA = "Estrutura"
    ALVENARIA = "Alvenaria"
    COBERTURA = "Cobertura"
    ESQUADRIAS = "Esquadrias"
    PORTAS_JANELAS = "Portas e janelas"
    INSTALACOES_HIDRAULICAS = "Instalacoes hidraulicas"
    INSTALACOES_ELETRICAS = "Instalacoes eletricas"
    REVESTIMENTOS = "Revestimentos"
    REVESTIMENTOS_INTERNOS = "Revestimentos internos"
    REVESTIMENTOS_EXTERNOS = "Revestimentos externos"
    PISOS_REVESTIMENTOS_CERAMICOS = "Pisos e revestimentos ceramicos"
    LOUCAS_METAIS = "Loucas e metais"
    PINTURA = "Pintura"
    GESSO_FORROS = "Gesso e forros"
    VIDROS = "Vidros"
    IMPERMEABILIZACAO = "Impermeabilizacao"
    AREA_EXTERNA_PAISAGISMO = "Area externa e paisagismo"
    FERRAGENS_FIXADORES = "Ferragens e fixadores"
    MATERIAIS_COMPLEMENTARES = "Materiais complementares"


class PerfilProduto(StrEnum):
    """Price/search profile selected for a material."""

    BAIXO_CUSTO = "Baixo custo"
    MEDIO_CUSTO = "Medio custo"
    ALTO_CUSTO = "Alto custo"


class OrigemMaterial(StrEnum):
    """Where a material entry came from in the IFC-to-purchase flow."""

    IFC = "ifc"
    IA = "ia"
    USUARIO = "usuario"
    FORNECEDOR = "fornecedor"
    TEMPLATE = "template"


class OfertaFornecedor(BaseModel):
    """A supplier option found for a material."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"additionalProperties": False},
    )

    fornecedor: str = Field(default="", description="Supplier name.")
    descricao: str | None = Field(default=None, description="Product description.")
    marca: str | None = Field(default=None, description="Product brand.")
    unidade: str | None = Field(default=None, description="Commercial unit.")
    quantidade: float | None = Field(default=None, ge=0)
    valor_unitario: float | None = Field(default=None, ge=0)
    valor_total: float | None = Field(default=None, ge=0)
    preco_a_vista: float | None = Field(default=None, ge=0)
    preco_a_prazo: float | None = Field(default=None, ge=0)
    num_parcelas: int | None = Field(default=None, ge=1)
    frete: float | None = Field(default=None, ge=0)
    disponibilidade: str | None = None
    data_consulta: str | None = None
    link_produto: str | None = None


class MaterialObra(BaseModel):
    """A material item used from IFC extraction through final purchase planning."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"additionalProperties": False},
    )

    nome: str = Field(min_length=1)
    descricao: str = ""
    quantidade: float | None = Field(default=None, ge=0)
    medida: str = Field(default="", description="Unit of measure, e.g. m3 or saco 50 kg.")
    fornecedor: str = ""
    lista_fornecedores: list[OfertaFornecedor] = Field(
        default_factory=list,
        description="Supplier options found for this material.",
    )
    valor_unitario: float | None = Field(default=None, ge=0)
    valor_total: float | None = Field(default=None, ge=0)
    preco_a_vista: float | None = Field(default=None, ge=0)
    preco_a_prazo: float | None = Field(default=None, ge=0)
    num_parcelas: int | None = Field(default=None, ge=1)
    frete: float | None = Field(default=None, ge=0)

    perfil_produto: PerfilProduto | None = None
    origem: OrigemMaterial | None = None
    justificativa: str | None = None
    nivel_confianca: int | None = Field(default=None, ge=0, le=100)
    referencias_ifc: list[str] = Field(default_factory=list)

    @field_validator("lista_fornecedores", mode="before")
    @classmethod
    def normalizar_lista_fornecedores(cls, value):
        if value in (None, ""):
            return []
        if isinstance(value, dict):
            return list(value.values())
        return value

    @model_validator(mode="after")
    def calcular_valor_total_quando_possivel(self) -> "MaterialObra":
        if (
            self.valor_total is None
            and self.quantidade is not None
            and self.valor_unitario is not None
        ):
            self.valor_total = self.quantidade * self.valor_unitario
        return self


class AreaMateriaisObra(BaseModel):
    """A purchase category and its materials."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"additionalProperties": False},
    )

    area: str
    materiais: list[MaterialObra] = Field(default_factory=list)


class ListaMateriaisObra(BaseModel):
    """Base communication model for the material list after IFC processing."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"additionalProperties": False},
    )

    obra: str | None = None
    responsavel: str | None = None
    data: str | None = None
    moeda: str = "BRL"
    observacoes: str | None = None
    areas: list[AreaMateriaisObra] = Field(default_factory=list)

    @field_validator("moeda")
    @classmethod
    def normalizar_moeda(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3:
            raise ValueError("moeda deve usar codigo ISO 4217 com 3 letras, exemplo: BRL")
        return normalized

    @property
    def materiais(self) -> list[MaterialObra]:
        """Flattened material list across all areas."""

        return [material for area in self.areas for material in area.materiais]

    @property
    def total_geral(self) -> float | None:
        """Sum known material totals, returning None when no total is available."""

        totais = [
            material.valor_total
            for material in self.materiais
            if material.valor_total is not None
        ]
        if not totais:
            return None
        return sum(totais)

    @property
    def total_a_vista(self) -> float | None:
        totais = [
            material.preco_a_vista
            for material in self.materiais
            if material.preco_a_vista is not None
        ]
        if not totais:
            return None
        return sum(totais)

    @property
    def total_a_prazo(self) -> float | None:
        totais = [
            material.preco_a_prazo
            for material in self.materiais
            if material.preco_a_prazo is not None
        ]
        if not totais:
            return None
        return sum(totais)
