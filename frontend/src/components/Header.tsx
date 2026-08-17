import { ArrowLeft, Building2, LogOut } from "lucide-react";

import type { Screen, Project } from "../types";

interface HeaderProps {
  project: Project | null;
  screen: Screen;
  onProjects: () => void;
  onScreen: (screen: Screen) => void;
  onLogout: () => void;
}

const tabs: Array<{ id: Screen; label: string }> = [
  { id: "setup", label: "Configuração" },
  { id: "compras", label: "Compras & Preços" },
  { id: "resumo", label: "Resumo Financeiro" },
];

export function Header({ project, screen, onProjects, onScreen, onLogout }: HeaderProps) {
  const inProject = project && screen !== "projects";

  return (
    <header className="app-header">
      <button className="brand" type="button" onClick={onProjects}>
        <span className="brand-mark">OB</span>
        <span>Obra Barata</span>
      </button>

      {inProject ? (
        <div className="project-header">
          <span className="header-divider" />
          <Building2 size={18} />
          <div className="project-title">
            <span>Projeto</span>
            <strong>{project.name}</strong>
          </div>
          <nav className="tabs" aria-label="Navegação do projeto">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={`tab ${screen === tab.id ? "active" : ""}`}
                onClick={() => onScreen(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </nav>
          <button className="btn btn-ghost header-action" type="button" onClick={onProjects}>
            <ArrowLeft size={16} />
            Todos os projetos
          </button>
        </div>
      ) : (
        <button className="btn btn-ghost header-action" type="button" onClick={onLogout}>
          <LogOut size={16} />
          Sair
        </button>
      )}
    </header>
  );
}
