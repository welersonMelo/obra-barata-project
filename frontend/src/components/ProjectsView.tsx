import { FormEvent, useState } from "react";
import { FolderOpen, Plus, Upload } from "lucide-react";

import type { PerfilProduto, Project } from "../types";
import { currency, listTotal, statusLabel } from "../utils/materials";

interface ProjectsViewProps {
  projects: Project[];
  busy: string | null;
  error: string | null;
  onCreate: (data: {
    name: string;
    type: string;
    address: string;
    areaBuilt: string;
    finishProfile: PerfilProduto;
  }) => Promise<void>;
  onOpen: (projectId: string) => void;
}

export function ProjectsView({ projects, busy, error, onCreate, onOpen }: ProjectsViewProps) {
  const [showForm, setShowForm] = useState(projects.length === 0);
  const [name, setName] = useState("");
  const [type, setType] = useState("Residencial");
  const [address, setAddress] = useState("");
  const [areaBuilt, setAreaBuilt] = useState("");
  const [finishProfile, setFinishProfile] = useState<PerfilProduto>("Medio custo");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    try {
      await onCreate({ name, type, address, areaBuilt, finishProfile });
      setName("");
      setAddress("");
      setAreaBuilt("");
      setShowForm(false);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="page shell">
      <section className="page-head">
        <div>
          <p className="kicker">Projetos</p>
          <h1>Escolha uma obra</h1>
        </div>
        <button className="btn btn-primary blueprint" type="button" onClick={() => setShowForm(true)}>
          <i className="corner tl" />
          <i className="corner tr" />
          <i className="corner bl" />
          <i className="corner br" />
          <Plus size={16} />
          Novo projeto
        </button>
      </section>

      {error ? <div className="alert error">{error}</div> : null}
      {busy ? <div className="alert busy">{busy}</div> : null}

      {showForm ? (
        <form className="card blueprint project-form" onSubmit={submit}>
          <i className="corner tl" />
          <i className="corner tr" />
          <i className="corner bl" />
          <i className="corner br" />
          <label className="field">
            <span>Nome da obra</span>
            <input
              className="input"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Residência, reforma ou lote"
              required
            />
          </label>
          <label className="field">
            <span>Tipo</span>
            <input className="input" value={type} onChange={(event) => setType(event.target.value)} />
          </label>
          <label className="field">
            <span>Área construída</span>
            <input
              className="input"
              value={areaBuilt}
              onChange={(event) => setAreaBuilt(event.target.value)}
              placeholder="120 m²"
            />
          </label>
          <label className="field wide">
            <span>Endereço</span>
            <input
              className="input"
              value={address}
              onChange={(event) => setAddress(event.target.value)}
              placeholder="Cidade, bairro ou obra"
            />
          </label>
          <label className="field wide">
            <span>Perfil de acabamento</span>
            <select
              className="input"
              value={finishProfile}
              onChange={(event) => setFinishProfile(event.target.value as PerfilProduto)}
            >
              <option>Baixo custo</option>
              <option>Medio custo</option>
              <option>Alto custo</option>
            </select>
          </label>
          <div className="form-actions">
            <button className="btn btn-secondary" type="button" onClick={() => setShowForm(false)}>
              Cancelar
            </button>
            <button className="btn btn-primary" type="submit" disabled={submitting}>
              <Upload size={16} />
              {submitting ? "Criando" : "Criar"}
            </button>
          </div>
        </form>
      ) : null}

      {projects.length === 0 && !showForm ? (
        <section className="empty-state blueprint">
          <i className="corner tl" />
          <i className="corner tr" />
          <i className="corner bl" />
          <i className="corner br" />
          <FolderOpen size={32} />
          <h2>Nenhum projeto aberto</h2>
          <button className="btn btn-primary" type="button" onClick={() => setShowForm(true)}>
            <Plus size={16} />
            Novo projeto
          </button>
        </section>
      ) : null}

      <section className="project-grid">
        {projects.map((project) => (
          <button
            key={project.id}
            type="button"
            className="card blueprint project-card"
            onClick={() => onOpen(project.id)}
          >
            <i className="corner tl" />
            <i className="corner tr" />
            <i className="corner bl" />
            <i className="corner br" />
            <span className="card-kicker">{project.type}</span>
            <strong>{project.name}</strong>
            <div className="project-card-grid">
              <span>
                <small>Área</small>
                {project.areaBuilt || "-"}
              </span>
              <span>
                <small>Orçamento</small>
                {currency(listTotal(project.pricedList, "avista"))}
              </span>
            </div>
            <div className="card-footer">
              <span className="tag tag-neutral">{statusLabel(project.status)}</span>
              <span>{new Date(project.updatedAt).toLocaleDateString("pt-BR")}</span>
            </div>
          </button>
        ))}
      </section>
    </main>
  );
}
