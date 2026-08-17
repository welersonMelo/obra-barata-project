import type { PerfilProduto, Project } from "../types";

export function createProject(input?: Partial<Project>): Project {
  const now = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    name: input?.name?.trim() || "Nova obra",
    type: input?.type?.trim() || "Residencial",
    address: input?.address?.trim() || "",
    areaBuilt: input?.areaBuilt?.trim() || "",
    finishProfile: (input?.finishProfile as PerfilProduto | undefined) ?? "Medio custo",
    status: "rascunho",
    createdAt: now,
    updatedAt: now,
    upload: null,
    materialList: null,
    pricedList: null,
    removedMaterialIds: [],
  };
}

export function touchProject(project: Project, updates: Partial<Project>): Project {
  return {
    ...project,
    ...updates,
    updatedAt: new Date().toISOString(),
  };
}
