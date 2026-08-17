import { Download, FileText } from "lucide-react";

import type { PaymentMode, Project } from "../types";
import {
  categoryRows,
  currency,
  filterRemovedMaterials,
  flattenMaterials,
  listTotal,
  pricedAreaCount,
  supplierCount,
} from "../utils/materials";

interface SummaryViewProps {
  project: Project;
  paymentMode: PaymentMode;
  onPaymentMode: (mode: PaymentMode) => void;
}

export function SummaryView({ project, paymentMode, onPaymentMode }: SummaryViewProps) {
  const list = project.pricedList
    ? filterRemovedMaterials(project.pricedList, project.removedMaterialIds)
    : null;
  const totalAvista = listTotal(list, "avista");
  const totalAprazo = listTotal(list, "aprazo");
  const economia = Math.max(totalAprazo - totalAvista, 0);
  const rows = categoryRows(list, paymentMode);
  const max = Math.max(...rows.map((row) => row.total), 1);
  const total = paymentMode === "avista" ? totalAvista : totalAprazo;

  function exportCsv() {
    if (!list) return;
    const header = "Categoria;Material;Fornecedor;Quantidade;Unidade;Valor total";
    const lines = flattenMaterials(list).map(({ area, material }) =>
      [
        area,
        material.nome,
        material.fornecedor,
        material.quantidade ?? "",
        material.medida,
        material.valor_total ?? material.preco_a_vista ?? "",
      ].join(";"),
    );
    const blob = new Blob([[header, ...lines].join("\n")], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${project.name.replace(/\s+/g, "_")}_fornecedores.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="page shell">
      <section className="page-head">
        <div>
          <p className="kicker">Resumo financeiro</p>
          <h1>{project.name}</h1>
        </div>
        <div className="segmented">
          <button
            type="button"
            className={paymentMode === "avista" ? "active" : ""}
            onClick={() => onPaymentMode("avista")}
          >
            À vista
          </button>
          <button
            type="button"
            className={paymentMode === "aprazo" ? "active" : ""}
            onClick={() => onPaymentMode("aprazo")}
          >
            A prazo
          </button>
        </div>
      </section>

      {!list ? (
        <section className="empty-state blueprint">
          <i className="corner tl" />
          <i className="corner tr" />
          <i className="corner bl" />
          <i className="corner br" />
          <FileText size={32} />
          <h2>Busque fornecedores</h2>
        </section>
      ) : (
        <>
          <section className="summary-kpis">
            <div className="total-card">
              <small>Total à vista</small>
              <strong>{currency(totalAvista)}</strong>
            </div>
            <div className="card blueprint summary-card">
              <i className="corner tl" />
              <i className="corner tr" />
              <i className="corner bl" />
              <i className="corner br" />
              <small>Total a prazo</small>
              <strong>{currency(totalAprazo)}</strong>
            </div>
            <div className="blueprint economy-card">
              <i className="corner tl" />
              <i className="corner tr" />
              <i className="corner bl" />
              <i className="corner br" />
              <small>Diferença</small>
              <strong>{currency(economia)}</strong>
            </div>
          </section>

          <section className="metric-grid">
            <Metric value={pricedAreaCount(list)} label="categorias com preço" />
            <Metric value={flattenMaterials(list).length} label="materiais ativos" />
            <Metric value={supplierCount(list)} label="fornecedores" />
          </section>

          <section className="card blueprint summary-table-card">
            <i className="corner tl" />
            <i className="corner tr" />
            <i className="corner bl" />
            <i className="corner br" />
            <h2>Custo por categoria</h2>
            <table className="table">
              <thead>
                <tr>
                  <th>Categoria</th>
                  <th>Participação</th>
                  <th>Fornecedor</th>
                  <th className="right">Custo</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.area}>
                    <td>
                      <strong>{row.area}</strong>
                      <small>{row.itens} itens</small>
                    </td>
                    <td>
                      <span className="bar">
                        <i style={{ width: `${Math.round((row.total / max) * 100)}%` }} />
                      </span>
                    </td>
                    <td>{row.fornecedores}</td>
                    <td className="right">{currency(row.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <footer>
              <strong>Total</strong>
              <strong>{currency(total)}</strong>
            </footer>
          </section>

          <div className="button-row">
            <button className="btn btn-primary" type="button" onClick={exportCsv}>
              <Download size={16} />
              Exportar CSV
            </button>
          </div>
        </>
      )}
    </main>
  );
}

function Metric({ value, label }: { value: number; label: string }) {
  return (
    <div className="card blueprint metric compact">
      <i className="corner tl" />
      <i className="corner tr" />
      <i className="corner bl" />
      <i className="corner br" />
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}
