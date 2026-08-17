import type { IfcUploadResponse, ListaMateriaisObra } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function parseApiError(response: Response): Promise<Error> {
  let message = `Erro ${response.status}`;
  try {
    const payload = await response.json();
    if (typeof payload?.detail === "string") {
      message = payload.detail;
    }
  } catch {
    message = response.statusText || message;
  }
  return Object.assign(new Error(message), { status: response.status });
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    throw await parseApiError(response);
  }
  return response.json() as Promise<T>;
}

export async function uploadIfc(file: File): Promise<IfcUploadResponse> {
  const body = new FormData();
  body.append("file", file);
  return requestJson<IfcUploadResponse>("/upload_ifc", {
    method: "POST",
    body,
  });
}

export async function analyzeIfc(ifcId: string): Promise<ListaMateriaisObra> {
  return requestJson<ListaMateriaisObra>("/analisar_ifc", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ifc_id: ifcId }),
  });
}

export async function fetchSupplierPrices(
  materialList: ListaMateriaisObra,
  maxOffers = 3,
): Promise<ListaMateriaisObra> {
  const params = new URLSearchParams({
    max_materials: String(maxOffers),
    use_serper_fallback: "false",
  });
  return requestJson<ListaMateriaisObra>(`/buscar_fornecedores?${params}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(materialList),
  });
}
