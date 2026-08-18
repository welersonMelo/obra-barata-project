import { ChangeEvent, KeyboardEvent, useEffect, useMemo, useState } from "react";
import {
  Check,
  FileArchive,
  FileSearch,
  Loader2,
  RefreshCw,
  Trash2,
  Upload,
} from "lucide-react";

import type { Project, SetupTab } from "../types";
import {
  filterRemovedMaterials,
  flattenMaterials,
  materialId,
} from "../utils/materials";

interface SetupViewProps {
  project: Project;
  setupTab: SetupTab;
  busy: string | null;
  error: string | null;
  onSetupTab: (tab: SetupTab) => void;
  onUploadIfc: (file: File) => Promise<void>;
  onAnalyzeIfc: () => Promise<void>;
  onToggleRemovedMaterial: (materialId: string) => Promise<void>;
  onUpdateMaterialQuantity: (materialId: string, quantity: number | null) => Promise<void>;
}

export function SetupView({
  project,
  setupTab,
  busy,
  error,
  onSetupTab,
  onUploadIfc,
  onAnalyzeIfc,
  onToggleRemovedMaterial,
  onUpdateMaterialQuantity,
}: SetupViewProps) {
  const [file, setFile] = useState<File | null>(null);
  const materialList = project.materialList ?? project.pricedList;
  const visibleList = useMemo(
    () => (materialList ? filterRemovedMaterials(materialList, project.removedMaterialIds) : null),
    [materialList, project.removedMaterialIds],
  );
  const materials = flattenMaterials(materialList);
  const visibleMaterials = flattenMaterials(visibleList);

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
  }

  return (
    <main className="page shell">
      <section className="page-head">
        <div>
          <p className="kicker">Configuração</p>
          <h1>IFC & revisão da IA</h1>
        </div>
        <div className="segmented">
          <button
            type="button"
            className={setupTab === "upload" ? "active" : ""}
            onClick={() => onSetupTab("upload")}
          >
            Upload
          </button>
          <button
            type="button"
            className={setupTab === "review" ? "active" : ""}
            onClick={() => onSetupTab("review")}
            disabled={!materialList}
          >
            Revisão
          </button>
        </div>
      </section>

      {error ? <div className="alert error">{error}</div> : null}
      {busy ? (
        <div className="alert busy">
          <Loader2 size={16} className="spin" />
          {busy}
        </div>
      ) : null}

      {setupTab === "upload" ? (
        <section className="setup-grid">
          <div className="card blueprint upload-card">
            <i className="corner tl" />
            <i className="corner tr" />
            <i className="corner bl" />
            <i className="corner br" />
            <div className="upload-drop">
              <FileArchive size={28} />
              <div>
                <strong>{file?.name ?? project.upload?.filename ?? "Arquivo IFC"}</strong>
                <span>{file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : "Selecione um .ifc"}</span>
              </div>
              <label className="btn btn-secondary file-button">
                <Upload size={16} />
                Escolher
                <input type="file" accept=".ifc,.ifczip" onChange={selectFile} />
              </label>
            </div>
            <div className="button-row">
              <button
                className="btn btn-primary"
                type="button"
                disabled={!file || Boolean(busy)}
                onClick={() => file && onUploadIfc(file)}
              >
                <Upload size={16} />
                Enviar IFC
              </button>
              <button
                className="btn btn-secondary"
                type="button"
                disabled={!project.upload || Boolean(busy)}
                onClick={onAnalyzeIfc}
              >
                <FileSearch size={16} />
                Analisar IFC
              </button>
            </div>
          </div>

          <div className="card blueprint details-card">
            <i className="corner tl" />
            <i className="corner tr" />
            <i className="corner bl" />
            <i className="corner br" />
            <h2>{project.name}</h2>
            <dl className="details-list">
              <div>
                <dt>Tipo</dt>
                <dd>{project.type}</dd>
              </div>
              <div>
                <dt>Área</dt>
                <dd>{project.areaBuilt || "-"}</dd>
              </div>
              <div>
                <dt>Perfil</dt>
                <dd>{project.finishProfile}</dd>
              </div>
              <div>
                <dt>Endereço</dt>
                <dd>{project.address || "-"}</dd>
              </div>
              <div>
                <dt>Schema IFC</dt>
                <dd>{project.upload?.schema ?? "-"}</dd>
              </div>
            </dl>
          </div>

          <div className="metric-grid wide">
            <Metric label="Pavimentos" value={project.upload?.pavimentos.length ?? 0} />
            <Metric label="Materiais lidos" value={project.upload?.materiais.length ?? 0} />
            <Metric label="Materiais de compra" value={visibleMaterials.length} />
          </div>

          <section className="pipeline wide">
            <Step n="1" title="Upload IFC" done={Boolean(project.upload)} />
            <Step n="2" title="Análise de materiais" done={Boolean(project.materialList)} />
            <Step n="3" title="Pesquisa de preços" done={Boolean(project.pricedList)} />
          </section>
        </section>
      ) : (
        <section className="review-list">
          <div className="card blueprint review-summary">
            <i className="corner tl" />
            <i className="corner tr" />
            <i className="corner bl" />
            <i className="corner br" />
            <strong>{visibleMaterials.length} materiais ativos</strong>
            <span>{project.removedMaterialIds.length} removidos nesta revisão</span>
          </div>

          {materials.map(({ area, material }) => {
            const id = materialId(area, material);
            const removed = project.removedMaterialIds.includes(id);
            return (
              <article key={id} className={`card blueprint material-review ${removed ? "muted" : ""}`}>
                <i className="corner tl" />
                <i className="corner tr" />
                <i className="corner bl" />
                <i className="corner br" />
                <div>
                  <div className="row-wrap">
                    <h3>{material.nome}</h3>
                    <span className="tag tag-neutral">{area}</span>
                    <span className="tag tag-outline">{material.origem ?? "sem origem"}</span>
                    {material.nivel_confianca != null ? (
                      <span className="tag tag-accent">{material.nivel_confianca}%</span>
                    ) : null}
                  </div>
                  <p>{material.descricao || material.justificativa || "Sem descrição."}</p>
                  <dl className="inline-facts">
                    <div>
                      <dt>Quantidade</dt>
                      <dd>
                        <QuantityEditor
                          materialId={id}
                          quantity={material.quantidade}
                          measure={material.medida}
                          disabled={Boolean(busy) || removed}
                          onSave={onUpdateMaterialQuantity}
                        />
                      </dd>
                    </div>
                    <div>
                      <dt>Perfil</dt>
                      <dd>{material.perfil_produto ?? project.finishProfile}</dd>
                    </div>
                  </dl>
                </div>
                <button
                  className={`btn ${removed ? "btn-secondary" : "btn-ghost"}`}
                  type="button"
                  onClick={() => onToggleRemovedMaterial(id)}
                >
                  {removed ? <RefreshCw size={16} /> : <Trash2 size={16} />}
                  {removed ? "Restaurar" : "Remover"}
                </button>
              </article>
            );
          })}
        </section>
      )}
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="blueprint metric">
      <i className="corner tl" />
      <i className="corner tr" />
      <i className="corner bl" />
      <i className="corner br" />
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function quantityDraft(value: number | null): string {
  return value == null ? "" : String(value).replace(".", ",");
}

function parseQuantityDraft(value: string): { valid: true; quantity: number | null } | { valid: false } {
  const trimmed = value.trim();
  if (!trimmed) return { valid: true, quantity: null };

  const normalized = trimmed.replace(",", ".");
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed) || parsed < 0) return { valid: false };
  return { valid: true, quantity: parsed };
}

function sameQuantity(left: number | null, right: number | null): boolean {
  if (left == null || right == null) return left == null && right == null;
  return Math.abs(left - right) < 0.000001;
}

function QuantityEditor({
  materialId,
  quantity,
  measure,
  disabled,
  onSave,
}: {
  materialId: string;
  quantity: number | null;
  measure: string;
  disabled: boolean;
  onSave: (materialId: string, quantity: number | null) => Promise<void>;
}) {
  const [draft, setDraft] = useState(quantityDraft(quantity));
  const [saving, setSaving] = useState(false);
  const parsed = parseQuantityDraft(draft);
  const parsedQuantity = parsed.valid ? parsed.quantity : null;
  const unchanged = parsed.valid && sameQuantity(parsedQuantity, quantity);

  useEffect(() => {
    setDraft(quantityDraft(quantity));
  }, [quantity]);

  async function saveQuantity() {
    if (!parsed.valid || unchanged || disabled || saving) return;
    setSaving(true);
    try {
      await onSave(materialId, parsed.quantity);
    } finally {
      setSaving(false);
    }
  }

  function saveOnEnter(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      void saveQuantity();
    }
  }

  return (
    <div className="quantity-editor">
      <input
        className={`input quantity-input ${parsed.valid ? "" : "invalid"}`}
        value={draft}
        inputMode="decimal"
        disabled={disabled || saving}
        aria-label="Quantidade do material"
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={saveOnEnter}
      />
      <span>{measure || "-"}</span>
      <button
        className="btn btn-secondary quantity-save"
        type="button"
        disabled={disabled || saving || !parsed.valid || unchanged}
        onClick={saveQuantity}
      >
        {saving ? <Loader2 size={15} className="spin" /> : <Check size={15} />}
        Salvar
      </button>
    </div>
  );
}

function Step({ n, title, done }: { n: string; title: string; done: boolean }) {
  return (
    <div className={`blueprint step ${done ? "done" : ""}`}>
      <i className="corner tl" />
      <i className="corner tr" />
      <i className="corner bl" />
      <i className="corner br" />
      <span>{done ? <Check size={16} /> : n}</span>
      <strong>{title}</strong>
    </div>
  );
}
