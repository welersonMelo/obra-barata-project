import { useMemo, useState } from "react";
import { Calculator, ExternalLink, Loader2, Search, ShoppingCart, X } from "lucide-react";

import type { MaterialObra, OfertaFornecedor, Project } from "../types";
import {
  activeMaterialList,
  bestOffer,
  currency,
  filterRemovedMaterials,
  flattenMaterials,
  materialTotal,
  materialQuantityText,
  numberText,
  offerPurchaseQuantity,
  offerTotalForMaterial,
} from "../utils/materials";

interface PricingViewProps {
  project: Project;
  busy: string | null;
  error: string | null;
  onFetchPrices: () => Promise<void>;
  onSelectOffer: (area: string, materialName: string, offer: OfertaFornecedor) => void;
}

export function PricingView({
  project,
  busy,
  error,
  onFetchPrices,
  onSelectOffer,
}: PricingViewProps) {
  const [memorial, setMemorial] = useState<{ area: string; material: MaterialObra } | null>(
    null,
  );
  const list = useMemo(() => {
    const source = activeMaterialList(project);
    return source ? filterRemovedMaterials(source, project.removedMaterialIds) : null;
  }, [project]);
  const [selectedArea, setSelectedArea] = useState<string | null>(null);
  const areas = list?.areas.filter((area) => area.materiais.length > 0) ?? [];
  const activeArea = selectedArea ?? areas[0]?.area ?? null;
  const materials = flattenMaterials(list).filter((item) => !activeArea || item.area === activeArea);

  if (!project.materialList) {
    return (
      <main className="page shell">
        <section className="empty-state blueprint">
          <i className="corner tl" />
          <i className="corner tr" />
          <i className="corner bl" />
          <i className="corner br" />
          <ShoppingCart size={32} />
          <h2>Execute a análise IFC</h2>
        </section>
      </main>
    );
  }

  return (
    <main className="page pricing-layout">
      <aside className="category-sidebar">
        <p>Categorias</p>
        {areas.map((area) => (
          <button
            key={area.area}
            type="button"
            className={area.area === activeArea ? "active" : ""}
            onClick={() => setSelectedArea(area.area)}
          >
            <span />
            <strong>{area.area}</strong>
            <small>{area.materiais.length}</small>
          </button>
        ))}
      </aside>

      <section className="pricing-main">
        <div className="page-head">
          <div>
            <p className="kicker">{activeArea ?? "Materiais"}</p>
            <h1>{materials.length} materiais</h1>
          </div>
          <button
            className="btn btn-primary blueprint"
            type="button"
            disabled={Boolean(busy)}
            onClick={onFetchPrices}
          >
            <i className="corner tl" />
            <i className="corner tr" />
            <i className="corner bl" />
            <i className="corner br" />
            {busy ? <Loader2 size={16} className="spin" /> : <Search size={16} />}
            Buscar fornecedores
          </button>
        </div>

        {error ? <div className="alert error">{error}</div> : null}
        {busy ? (
          <div className="alert busy">
            <Loader2 size={16} className="spin" />
            {busy}
          </div>
        ) : null}

        <div className="material-list">
          {materials.map(({ area, material }) => {
            const selected = bestOffer(material);
            const offers = material.lista_fornecedores;
            return (
              <article key={`${area}-${material.nome}`} className="card blueprint material-card">
                <i className="corner tl" />
                <i className="corner tr" />
                <i className="corner bl" />
                <i className="corner br" />
                <div className="material-head">
                  <div>
                    <h2>{material.nome}</h2>
                    <span>Quantidade: {materialQuantityText(material)}</span>
                  </div>
                  <div className="material-actions">
                    <button
                      type="button"
                      className="icon-button"
                      title="Abrir memorial de calculo"
                      aria-label={`Abrir memorial de calculo de ${material.nome}`}
                      onClick={() => setMemorial({ area, material })}
                    >
                      <Calculator size={17} />
                    </button>
                    <span className="tag tag-neutral">
                      {material.perfil_produto ?? project.finishProfile}
                    </span>
                  </div>
                </div>

                {offers.length > 0 ? (
                  <div className="offer-grid">
                    {offers.map((offer) => {
                      const active = selected?.fornecedor === offer.fornecedor && selected?.descricao === offer.descricao;
                      const purchaseQuantity = offerPurchaseQuantity(material, offer);
                      const total = offerTotalForMaterial(material, offer, "avista");
                      return (
                        <button
                          key={`${offer.fornecedor}-${offer.descricao}-${offer.valor_total}`}
                          type="button"
                          className={`offer-card ${active ? "active" : ""}`}
                          onClick={() => onSelectOffer(area, material.nome, offer)}
                        >
                          <span className="offer-top">
                            <strong>{offer.fornecedor}</strong>
                            <i />
                          </span>
                          <span className="offer-desc">{offer.descricao || "Oferta sem descrição"}</span>
                          <span className="offer-price">
                            <small>Unitario</small>
                            <strong>{currency(offer.valor_unitario)}</strong>
                            <em>{offer.unidade || material.medida}</em>
                          </span>
                          <span className="offer-total">
                            <small>
                              Total{purchaseQuantity ? ` (${numberText(purchaseQuantity)} un.)` : ""}
                            </small>
                            <strong>{currency(total)}</strong>
                          </span>
                          <span className="offer-bottom">
                            <small>{offer.disponibilidade || "Sem disponibilidade"}</small>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div className="no-offers">Sem fornecedores consultados para este material.</div>
                )}

                <div className="selected-offer">
                  <span>
                    Selecionado: <strong>{selected?.fornecedor || "-"}</strong>
                  </span>
                  <span>{currency(materialTotal(material, "avista"))}</span>
                  {selected?.link_produto ? (
                    <a href={selected.link_produto} target="_blank" rel="noreferrer" className="btn btn-ghost">
                      <ExternalLink size={16} />
                      Abrir
                    </a>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      </section>
      {memorial ? (
        <CalculationMemorial
          area={memorial.area}
          material={memorial.material}
          onClose={() => setMemorial(null)}
        />
      ) : null}
    </main>
  );
}

function CalculationMemorial({
  area,
  material,
  onClose,
}: {
  area: string;
  material: MaterialObra;
  onClose: () => void;
}) {
  const selected = bestOffer(material);
  const total = selected ? offerTotalForMaterial(material, selected, "avista") : material.valor_total;
  const unitPrice = selected?.valor_unitario ?? material.valor_unitario;
  const purchaseQuantity = selected ? offerPurchaseQuantity(material, selected) : material.quantidade;
  const unit = selected?.unidade ?? material.medida;

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-panel blueprint"
        role="dialog"
        aria-modal="true"
        aria-labelledby="calculation-memorial-title"
        onClick={(event) => event.stopPropagation()}
      >
        <i className="corner tl" />
        <i className="corner tr" />
        <i className="corner bl" />
        <i className="corner br" />

        <header className="modal-head">
          <div>
            <p className="kicker">{area}</p>
            <h2 id="calculation-memorial-title">Memorial de calculo</h2>
          </div>
          <button
            type="button"
            className="icon-button"
            title="Fechar"
            aria-label="Fechar memorial de calculo"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>

        <div className="memorial-summary">
          <strong>{material.nome}</strong>
          <span>{material.descricao || "Sem descricao informada."}</span>
        </div>

        <dl className="memorial-grid">
          <MemorialFact label="Quantidade de projeto" value={materialQuantityText(material)} />
          <MemorialFact label="Unidade comercial" value={unit || "-"} />
          <MemorialFact label="Quantidade de compra" value={numberText(purchaseQuantity)} />
          <MemorialFact label="Preco unitario" value={currency(unitPrice)} />
          <MemorialFact label="Total calculado" value={currency(total)} />
          <MemorialFact label="Fornecedor selecionado" value={selected?.fornecedor || "-"} />
          <MemorialFact label="Origem" value={material.origem || "-"} />
          <MemorialFact
            label="Confianca"
            value={material.nivel_confianca == null ? "-" : `${material.nivel_confianca}%`}
          />
        </dl>

        <section className="memorial-section">
          <h3>Justificativa</h3>
          <p>{material.justificativa || "O backend nao retornou justificativa para este item."}</p>
        </section>

        <section className="memorial-section">
          <h3>Formula de preco</h3>
          <p>
            {unitPrice != null && purchaseQuantity != null
              ? `${currency(unitPrice)} x ${numberText(purchaseQuantity)} = ${currency(total)}`
              : "Nao ha preco e quantidade comercial suficientes para montar a formula."}
          </p>
        </section>

        <section className="memorial-section">
          <h3>Referencias IFC</h3>
          {material.referencias_ifc.length > 0 ? (
            <div className="reference-list">
              {material.referencias_ifc.map((reference) => (
                <span key={reference}>{reference}</span>
              ))}
            </div>
          ) : (
            <p>Nenhuma referencia IFC foi retornada para este material.</p>
          )}
        </section>
      </section>
    </div>
  );
}

function MemorialFact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
