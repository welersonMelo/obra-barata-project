import { useMemo, useState } from "react";

import {
  analyzeIfc,
  createProject as createProjectRequest,
  fetchSupplierPrices,
  listProjects,
  login as loginRequest,
  updateProject as updateProjectRequest,
  uploadIfc,
} from "./api/client";
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
  ProjectCreateInput,
  ProjectUpdateInput,
  Screen,
  SetupTab,
  User,
} from "./types";
import { filterRemovedMaterials, updateMaterialOffer } from "./utils/materials";

function messageFromError(error: unknown): string {
  return error instanceof Error ? error.message : "Nao foi possivel concluir a operacao.";
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

function nextScreenForProject(project: Project): Screen {
  if (project.status === "precificado") return "resumo";
  if (project.status === "rascunho") return "setup";
  return "compras";
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
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

  function upsertProject(savedProject: Project) {
    setProjects((current) => {
      const exists = current.some((project) => project.id === savedProject.id);
      if (exists) {
        return current.map((project) => (project.id === savedProject.id ? savedProject : project));
      }
      return [savedProject, ...current];
    });
  }

  async function persistProjectUpdate(
    projectId: string,
    updates: ProjectUpdateInput,
  ): Promise<Project> {
    const savedProject = await updateProjectRequest(projectId, updates);
    upsertProject(savedProject);
    return savedProject;
  }

  async function handleLogin(username: string, password: string) {
    setBusy("Entrando");
    setError(null);
    try {
      const loggedUser = await loginRequest(username, password);
      const savedProjects = await listProjects();
      setUser(loggedUser);
      setProjects(savedProjects);
      setActiveProjectId(null);
      setScreen("projects");
      setSetupTab("upload");
    } catch (err) {
      setError(messageFromError(err));
    } finally {
      setBusy(null);
    }
  }

  async function createNewProject(data: ProjectCreateInput) {
    setBusy("Criando projeto");
    setError(null);
    try {
      const project = await createProjectRequest(data);
      upsertProject(project);
      setActiveProjectId(project.id);
      setScreen("setup");
      setSetupTab("upload");
    } catch (err) {
      setError(messageFromError(err));
      throw err;
    } finally {
      setBusy(null);
    }
  }

  function openProject(projectId: string) {
    const project = projects.find((item) => item.id === projectId);
    if (!project) return;
    setActiveProjectId(projectId);
    setScreen(nextScreenForProject(project));
    setSetupTab(project.materialList ? "review" : "upload");
    setError(null);
  }

  async function handleUploadIfc(file: File) {
    if (!activeProject) return;
    setBusy("Enviando arquivo IFC");
    setError(null);
    try {
      const upload = await uploadIfc(file);
      await persistProjectUpdate(activeProject.id, {
        upload,
        status: "ifc_enviado",
        materialList: null,
        pricedList: null,
        removedMaterialIds: [],
      });
    } catch (err) {
      setError(messageFromError(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleAnalyzeIfc() {
    if (!activeProject?.upload) return;
    const projectSnapshot = activeProject;
    setBusy("Analisando modelo IFC");
    setError(null);
    try {
      const materialList = await analyzeIfc(projectSnapshot.upload.ifc_id);
      await persistProjectUpdate(projectSnapshot.id, {
        materialList: withProjectDefaults(materialList, projectSnapshot),
        pricedList: null,
        status: "analisado",
        removedMaterialIds: [],
      });
      setSetupTab("review");
    } catch (err) {
      setError(messageFromError(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleFetchPrices() {
    if (!activeProject?.materialList) return;
    const projectSnapshot = activeProject;
    setBusy("Buscando fornecedores e precos");
    setError(null);
    try {
      const sourceList = withProjectDefaults(
        filterRemovedMaterials(projectSnapshot.materialList, projectSnapshot.removedMaterialIds),
        projectSnapshot,
      );
      const pricedList = await fetchSupplierPrices(sourceList);
      await persistProjectUpdate(projectSnapshot.id, {
        pricedList,
        status: "precificado",
      });
      setScreen("resumo");
    } catch (err) {
      setError(messageFromError(err));
    } finally {
      setBusy(null);
    }
  }

  async function toggleRemovedMaterial(id: string) {
    if (!activeProject) return;
    const exists = activeProject.removedMaterialIds.includes(id);
    const removedMaterialIds = exists
      ? activeProject.removedMaterialIds.filter((item) => item !== id)
      : [...activeProject.removedMaterialIds, id];
    setError(null);
    try {
      await persistProjectUpdate(activeProject.id, { removedMaterialIds });
    } catch (err) {
      setError(messageFromError(err));
    }
  }

  async function selectOffer(area: string, materialName: string, offer: OfertaFornecedor) {
    if (!activeProject?.pricedList) return;
    const pricedList = updateMaterialOffer(activeProject.pricedList, area, materialName, offer);
    setError(null);
    try {
      await persistProjectUpdate(activeProject.id, { pricedList });
    } catch (err) {
      setError(messageFromError(err));
    }
  }

  if (!user) {
    return <LoginView busy={busy} error={error} onLogin={handleLogin} />;
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
          setError(null);
        }}
      />

      {screen === "projects" ? (
        <ProjectsView
          projects={projects}
          busy={busy}
          error={error}
          onCreate={createNewProject}
          onOpen={openProject}
        />
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
