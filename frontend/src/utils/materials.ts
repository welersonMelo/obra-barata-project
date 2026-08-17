import type {
  AreaMateriaisObra,
  ListaMateriaisObra,
  MaterialObra,
  OfertaFornecedor,
  PaymentMode,
  Project,
  ProjectStatus,
} from "../types";

export function currency(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value);
}

export function numberText(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(value);
}

export function statusLabel(status: ProjectStatus): string {
  const labels: Record<ProjectStatus, string> = {
    rascunho: "Rascunho",
    ifc_enviado: "IFC enviado",
    analisado: "Análise concluída",
    precificado: "Preços consultados",
  };
  return labels[status];
}

export function materialId(area: string, material: MaterialObra): string {
  return `${area}::${material.nome}::${material.medida}`;
}

export function activeMaterialList(project: Project): ListaMateriaisObra | null {
  return project.pricedList ?? project.materialList;
}

export function filterRemovedMaterials(
  list: ListaMateriaisObra,
  removedIds: string[],
): ListaMateriaisObra {
  const removed = new Set(removedIds);
  return {
    ...list,
    areas: list.areas.map((area) => ({
      ...area,
      materiais: area.materiais.filter(
        (material) => !removed.has(materialId(area.area, material)),
      ),
    })),
  };
}

export function flattenMaterials(list: ListaMateriaisObra | null): Array<{
  area: string;
  material: MaterialObra;
}> {
  if (!list) return [];
  return list.areas.flatMap((area) =>
    area.materiais.map((material) => ({ area: area.area, material })),
  );
}

export function materialQuantityText(material: MaterialObra): string {
  const quantity = numberText(material.quantidade);
  return material.quantidade == null ? material.medida || "-" : `${quantity} ${material.medida}`;
}

export function bestOffer(material: MaterialObra): OfertaFornecedor | null {
  if (material.lista_fornecedores.length > 0) {
    const byFornecedor = material.lista_fornecedores.find(
      (offer) => offer.fornecedor === material.fornecedor,
    );
    return byFornecedor ?? material.lista_fornecedores[0];
  }
  if (!material.fornecedor) return null;
  return {
    fornecedor: material.fornecedor,
    descricao: material.descricao,
    marca: null,
    unidade: material.medida,
    quantidade: material.quantidade,
    valor_unitario: material.valor_unitario,
    valor_total: material.valor_total,
    preco_a_vista: material.preco_a_vista,
    preco_a_prazo: material.preco_a_prazo,
    num_parcelas: material.num_parcelas,
    frete: material.frete,
    disponibilidade: null,
    data_consulta: null,
    link_produto: null,
  };
}

export function materialTotal(material: MaterialObra, mode: PaymentMode): number {
  if (mode === "avista") {
    return material.preco_a_vista ?? material.valor_total ?? 0;
  }
  return material.preco_a_prazo ?? material.valor_total ?? 0;
}

export function listTotal(list: ListaMateriaisObra | null, mode: PaymentMode): number {
  return flattenMaterials(list).reduce(
    (total, item) => total + materialTotal(item.material, mode),
    0,
  );
}

export function categoryRows(list: ListaMateriaisObra | null, mode: PaymentMode) {
  if (!list) return [];
  return list.areas
    .map((area) => {
      const total = area.materiais.reduce(
        (sum, material) => sum + materialTotal(material, mode),
        0,
      );
      const suppliers = Array.from(
        new Set(area.materiais.map((m) => m.fornecedor).filter(Boolean)),
      );
      return {
        area: area.area,
        itens: area.materiais.length,
        total,
        fornecedores: suppliers.join(", ") || "-",
      };
    })
    .filter((row) => row.itens > 0);
}

export function pricedAreaCount(list: ListaMateriaisObra | null): number {
  if (!list) return 0;
  return list.areas.filter((area) => area.materiais.some((m) => materialTotal(m, "avista") > 0))
    .length;
}

export function supplierCount(list: ListaMateriaisObra | null): number {
  return new Set(flattenMaterials(list).map((item) => item.material.fornecedor).filter(Boolean))
    .size;
}

export function withAreaMaterials(
  list: ListaMateriaisObra,
  mapper: (area: AreaMateriaisObra) => AreaMateriaisObra,
): ListaMateriaisObra {
  return { ...list, areas: list.areas.map(mapper) };
}

export function updateMaterialOffer(
  list: ListaMateriaisObra,
  areaName: string,
  materialName: string,
  offer: OfertaFornecedor,
): ListaMateriaisObra {
  return withAreaMaterials(list, (area) => {
    if (area.area !== areaName) return area;
    return {
      ...area,
      materiais: area.materiais.map((material) => {
        if (material.nome !== materialName) return material;
        return {
          ...material,
          fornecedor: offer.fornecedor,
          valor_unitario: offer.valor_unitario,
          valor_total: offer.valor_total,
          preco_a_vista: offer.preco_a_vista,
          preco_a_prazo: offer.preco_a_prazo,
          num_parcelas: offer.num_parcelas,
          frete: offer.frete,
        };
      }),
    };
  });
}
