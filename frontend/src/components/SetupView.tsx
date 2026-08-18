import { ChangeEvent, useMemo, useState } from "react";
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
  activeMaterialList,
  filterRemovedMaterials,
  flattenMaterials,
  materialId,
  materialQuantityText,
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
}: SetupViewProps) {
  const [file, setFile] = useState<File | null>(null);
  const materialList = activeMaterialList(project);
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
                      <dd>{materialQuantityText(material)}</dd>
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
