export type PerfilProduto = "Baixo custo" | "Medio custo" | "Alto custo";

export type OrigemMaterial = "ifc" | "ia" | "usuario" | "fornecedor" | "template";

export interface OfertaFornecedor {
  fornecedor: string;
  descricao: string | null;
  marca: string | null;
  unidade: string | null;
  quantidade: number | null;
  valor_unitario: number | null;
  valor_total: number | null;
  preco_a_vista: number | null;
  preco_a_prazo: number | null;
  num_parcelas: number | null;
  frete: number | null;
  disponibilidade: string | null;
  data_consulta: string | null;
  link_produto: string | null;
}

export interface MaterialObra {
  nome: string;
  descricao: string;
  quantidade: number | null;
  medida: string;
  fornecedor: string;
  lista_fornecedores: OfertaFornecedor[];
  valor_unitario: number | null;
  valor_total: number | null;
  preco_a_vista: number | null;
  preco_a_prazo: number | null;
  num_parcelas: number | null;
  frete: number | null;
  perfil_produto: PerfilProduto | null;
  origem: OrigemMaterial | null;
  justificativa: string | null;
  nivel_confianca: number | null;
  referencias_ifc: string[];
}

export interface AreaMateriaisObra {
  area: string;
  materiais: MaterialObra[];
}

export interface ListaMateriaisObra {
  obra: string | null;
  responsavel: string | null;
  data: string | null;
  moeda: string;
  observacoes: string | null;
  areas: AreaMateriaisObra[];
}

export interface IfcUploadResponse {
  ifc_id: string;
  filename: string;
  schema: string;
  pavimentos: string[];
  areas: Record<string, Record<string, unknown>>;
  materiais: string[];
  camadas_material: Record<string, unknown>[];
}

export type ProjectStatus =
  | "rascunho"
  | "ifc_enviado"
  | "analisado"
  | "precificado";

export interface Project {
  id: string;
  name: string;
  type: string;
  address: string;
  areaBuilt: string;
  finishProfile: PerfilProduto;
  status: ProjectStatus;
  createdAt: string;
  updatedAt: string;
  upload: IfcUploadResponse | null;
  materialList: ListaMateriaisObra | null;
  pricedList: ListaMateriaisObra | null;
  removedMaterialIds: string[];
}

export interface User {
  id: string;
  username: string;
}

export interface ProjectCreateInput {
  name: string;
  type: string;
  address: string;
  areaBuilt: string;
  finishProfile: PerfilProduto;
}

export type ProjectUpdateInput = Partial<
  Pick<
    Project,
    | "name"
    | "type"
    | "address"
    | "areaBuilt"
    | "finishProfile"
    | "status"
    | "upload"
    | "materialList"
    | "pricedList"
    | "removedMaterialIds"
  >
>;

export type Screen = "projects" | "setup" | "compras" | "resumo";
export type SetupTab = "upload" | "review";
export type PaymentMode = "avista" | "aprazo";

export interface ApiErrorInfo {
  message: string;
  status?: number;
}
