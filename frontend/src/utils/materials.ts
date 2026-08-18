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

function normalizeMeasureText(value: string | null | undefined): string {
  return (value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\u00b2/g, "2")
    .replace(/,/g, ".")
    .toLowerCase();
}

function hasPackageWord(measure: string | null | undefined): boolean {
  return /\b(saco|sacos|lata|latas|caixa|caixas|cx|pacote|pacotes|rolo|rolos|fardo|fardos|galao|galoes|balde|baldes)\b/.test(
    normalizeMeasureText(measure),
  );
}

function parseAmountUnit(value: string | null | undefined): {
  amount: number | null;
  family: string | null;
} {
  const text = normalizeMeasureText(value);
  const amountPatterns: Array<[RegExp, string]> = [
    [/(\d+(?:\.\d+)?)\s*(?:metros?\s*quadrados?|m2)\b/, "m2"],
    [/(\d+(?:\.\d+)?)\s*(?:metros?\s*cubicos?|m3)\b/, "m3"],
    [/(\d+(?:\.\d+)?)\s*(?:mililitros?|ml)\b/, "ml"],
    [/(\d+(?:\.\d+)?)\s*(?:litros?|lts?|lt|l)\b/, "l"],
    [/(\d+(?:\.\d+)?)\s*(?:quilogramas?|quilos?|kilos?|kg)\b/, "kg"],
    [/(\d+(?:\.\d+)?)\s*(?:gramas?|g)\b/, "g"],
    [/(\d+(?:\.\d+)?)\s*(?:metros?|m)\b/, "m"],
    [/(\d+(?:\.\d+)?)\s*(?:unidades?|und|un)\b/, "un"],
  ];

  for (const [pattern, family] of amountPatterns) {
    const match = text.match(pattern);
    if (match) return { amount: Number(match[1]), family };
  }

  const unitPatterns: Array<[RegExp, string]> = [
    [/\b(?:metros?\s*quadrados?|m2)\b/, "m2"],
    [/\b(?:metros?\s*cubicos?|m3)\b/, "m3"],
    [/\b(?:mililitros?|ml)\b/, "ml"],
    [/\b(?:litros?|lts?|lt|l)\b/, "l"],
    [/\b(?:quilogramas?|quilos?|kilos?|kg)\b/, "kg"],
    [/\b(?:gramas?|g)\b/, "g"],
    [/\b(?:metros?|m)\b/, "m"],
    [/\b(?:unidades?|und|un)\b/, "un"],
  ];

  for (const [pattern, family] of unitPatterns) {
    if (pattern.test(text)) return { amount: 1, family };
  }

  return { amount: null, family: null };
}

function almostEqual(left: number | null, right: number | null): boolean {
  if (left == null || right == null) return false;
  return Math.abs(left - right) < 0.01;
}

function roundMoney(value: number): number {
  return Math.round(value * 100) / 100;
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

export function offerPurchaseQuantity(
  material: MaterialObra,
  offer: OfertaFornecedor,
): number | null {
  const materialQuantity = material.quantidade;
  if (materialQuantity == null || materialQuantity <= 0) {
    return offer.quantidade ?? null;
  }

  const materialUnit = parseAmountUnit(material.medida);
  const offerUnit = parseAmountUnit(`${offer.unidade ?? ""} ${offer.descricao ?? ""}`);
  const materialIsPackageQuantity = hasPackageWord(material.medida);

  if (materialIsPackageQuantity) {
    const hasCompatibleUnit =
      !materialUnit.family ||
      !offerUnit.family ||
      materialUnit.family === offerUnit.family;
    const hasCompatiblePackageSize =
      materialUnit.amount == null ||
      offerUnit.amount == null ||
      almostEqual(materialUnit.amount, offerUnit.amount);

    if (hasCompatibleUnit && hasCompatiblePackageSize) {
      return materialQuantity;
    }
  }

  if (
    materialUnit.family &&
    offerUnit.family &&
    materialUnit.family === offerUnit.family &&
    offerUnit.amount
  ) {
    return Math.ceil(materialQuantity / offerUnit.amount);
  }

  return offer.quantidade ?? (materialIsPackageQuantity ? materialQuantity : null);
}

function offerExplicitTotal(offer: OfertaFornecedor, mode: PaymentMode): number | null {
  if (mode === "avista") return offer.preco_a_vista ?? offer.valor_total;
  return offer.preco_a_prazo ?? offer.valor_total;
}

export function offerTotalForMaterial(
  material: MaterialObra,
  offer: OfertaFornecedor,
  mode: PaymentMode = "avista",
): number | null {
  const explicitTotal = offerExplicitTotal(offer, mode);
  const purchaseQuantity = offerPurchaseQuantity(material, offer);

  if (offer.valor_unitario != null && purchaseQuantity != null && purchaseQuantity > 0) {
    const computedTotal = roundMoney(offer.valor_unitario * purchaseQuantity);
    if (explicitTotal == null) return computedTotal;
    if (purchaseQuantity > 1 && almostEqual(explicitTotal, offer.valor_unitario)) {
      return computedTotal;
    }
    if (purchaseQuantity > 1 && explicitTotal < offer.valor_unitario) {
      return computedTotal;
    }
  }

  return explicitTotal;
}

export function materialTotal(material: MaterialObra, mode: PaymentMode): number {
  const selectedOffer = bestOffer(material);
  if (selectedOffer) {
    return offerTotalForMaterial(material, selectedOffer, mode) ?? 0;
  }

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
        const totalAvista = offerTotalForMaterial(material, offer, "avista");
        const totalAprazo = offerTotalForMaterial(material, offer, "aprazo");
        return {
          ...material,
          fornecedor: offer.fornecedor,
          valor_unitario: offer.valor_unitario,
          valor_total: totalAvista ?? totalAprazo ?? offer.valor_total,
          preco_a_vista: totalAvista ?? offer.preco_a_vista,
          preco_a_prazo: totalAprazo ?? offer.preco_a_prazo,
          num_parcelas: offer.num_parcelas,
          frete: offer.frete,
        };
      }),
    };
  });
}

export function updateMaterialQuantity(
  list: ListaMateriaisObra,
  targetMaterialId: string,
  quantity: number | null,
): ListaMateriaisObra {
  return withAreaMaterials(list, (area) => ({
    ...area,
    materiais: area.materiais.map((material) =>
      materialId(area.area, material) === targetMaterialId
        ? {
            ...material,
            quantidade: quantity,
          }
        : material,
    ),
  }));
}
