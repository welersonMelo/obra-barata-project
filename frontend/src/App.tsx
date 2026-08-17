import { useMemo, useState } from "react";

import { analyzeIfc, fetchSupplierPrices, uploadIfc } from "./api/client";
import { Header } from "./components/Header";
import { LoginView } from "./components/LoginView";
import { PricingView } from "./components/PricingView";
import { ProjectsView } from "./components/ProjectsView";
import { SetupView } from "./components/SetupView";
import { SummaryView } from "./components/SummaryView";
import type {
  ListaMateriaisObra,
  OfertaFornecedor,
  PaymentMode,
  Project,
  Screen,
  SetupTab,
} from "./types";
import { filterRemovedMaterials, updateMaterialOffer } from "./utils/materials";
import { createProject, touchProject } from "./utils/projects";

function messageFromError(error: unknown): string {
  return error instanceof Error ? error.message : "Não foi possível concluir a operação.";
}

function withProjectDefaults(list: ListaMateriaisObra, project: Project): ListaMateriaisObra {
  return {
    ...list,
    obra: list.obra ?? project.name,
    areas: list.areas.map((area) => ({
      ...area,
      materiais: area.materiais.map((material) => ({
        ...material,
        perfil_produto: material.perfil_produto ?? project.finishProfile,
      })),
    })),
  };
}

export default function App() {
  const [user, setUser] = useState<string | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [screen, setScreen] = useState<Screen>("projects");
  const [setupTab, setSetupTab] = useState<SetupTab>("upload");
  const [paymentMode, setPaymentMode] = useState<PaymentMode>("avista");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activeProject = useMemo(
    () => projects.find((project) => project.id === activeProjectId) ?? null,
    [projects, activeProjectId],
  );

  function replaceProject(projectId: string, updater: (project: Project) => Project) {
    setProjects((current) =>
      current.map((project) => (project.id === projectId ? updater(project) : project)),
    );
  }

  function createNewProject(data: Parameters<typeof createProject>[0]) {
    const project = createProject(data);
    setProjects((current) => [project, ...current]);
    setActiveProjectId(project.id);
    setScreen("setup");
    setSetupTab("upload");
  }

  function openProject(projectId: string) {
    const project = projects.find((item) => item.id === projectId);
    if (!project) return;
    setActiveProjectId(projectId);
    setScreen(project.status === "precificado" ? "resumo" : project.status === "rascunho" ? "setup" : "compras");
    setSetupTab(project.materialList ? "review" : "upload");
  }

  async function handleUploadIfc(file: File) {
    if (!activeProject) return;
    setBusy("Enviando arquivo IFC");
    setError(null);
    try {
      const upload = await uploadIfc(file);
      replaceProject(activeProject.id, (project) =>
        touchProject(project, {
          upload,
          status: "ifc_enviado",
          pricedList: null,
        }),
      );
    } catch (err) {
      setError(messageFromError(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleAnalyzeIfc() {
    if (!activeProject?.upload) return;
    setBusy("Analisando modelo IFC");
    setError(null);
    try {
      const materialList = await analyzeIfc(activeProject.upload.ifc_id);
      replaceProject(activeProject.id, (project) =>
        touchProject(project, {
          materialList: withProjectDefaults(materialList, project),
          pricedList: null,
          status: "analisado",
          removedMaterialIds: [],
        }),
      );
      setSetupTab("review");
    } catch (err) {
      setError(messageFromError(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleFetchPrices() {
    if (!activeProject?.materialList) return;
    setBusy("Buscando fornecedores e preços");
    setError(null);
    try {
      const sourceList = withProjectDefaults(
        filterRemovedMaterials(activeProject.materialList, activeProject.removedMaterialIds),
        activeProject,
      );
      const pricedList = await fetchSupplierPrices(sourceList);
      replaceProject(activeProject.id, (project) =>
        touchProject(project, {
          pricedList,
          status: "precificado",
        }),
      );
      setScreen("resumo");
    } catch (err) {
      setError(messageFromError(err));
    } finally {
      setBusy(null);
    }
  }

  function toggleRemovedMaterial(id: string) {
    if (!activeProject) return;
    replaceProject(activeProject.id, (project) => {
      const exists = project.removedMaterialIds.includes(id);
      return touchProject(project, {
        removedMaterialIds: exists
          ? project.removedMaterialIds.filter((item) => item !== id)
          : [...project.removedMaterialIds, id],
      });
    });
  }

  function selectOffer(area: string, materialName: string, offer: OfertaFornecedor) {
    if (!activeProject?.pricedList) return;
    replaceProject(activeProject.id, (project) =>
      touchProject(project, {
        pricedList: project.pricedList
          ? updateMaterialOffer(project.pricedList, area, materialName, offer)
          : project.pricedList,
      }),
    );
  }

  if (!user) {
    return <LoginView onLogin={setUser} />;
  }

  return (
    <div className="app">
      <Header
        project={activeProject}
        screen={screen}
        onProjects={() => setScreen("projects")}
        onScreen={setScreen}
        onLogout={() => {
          setUser(null);
          setProjects([]);
          setActiveProjectId(null);
          setScreen("projects");
        }}
      />

      {screen === "projects" ? (
        <ProjectsView projects={projects} onCreate={createNewProject} onOpen={openProject} />
      ) : activeProject && screen === "setup" ? (
        <SetupView
          project={activeProject}
          setupTab={setupTab}
          busy={busy}
          error={error}
          onSetupTab={setSetupTab}
          onUploadIfc={handleUploadIfc}
          onAnalyzeIfc={handleAnalyzeIfc}
          onToggleRemovedMaterial={toggleRemovedMaterial}
        />
      ) : activeProject && screen === "compras" ? (
        <PricingView
          project={activeProject}
          busy={busy}
          error={error}
          onFetchPrices={handleFetchPrices}
          onSelectOffer={selectOffer}
        />
      ) : activeProject && screen === "resumo" ? (
        <SummaryView
          project={activeProject}
          paymentMode={paymentMode}
          onPaymentMode={setPaymentMode}
        />
      ) : null}
    </div>
  );
}
