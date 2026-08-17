import { useMemo, useState } from "react";
import { ExternalLink, Loader2, Search, ShoppingCart } from "lucide-react";

import type { Project, OfertaFornecedor } from "../types";
import {
  activeMaterialList,
  bestOffer,
  currency,
  filterRemovedMaterials,
  flattenMaterials,
  materialQuantityText,
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
                  <span className="tag tag-neutral">{material.perfil_produto ?? project.finishProfile}</span>
                </div>

                {offers.length > 0 ? (
                  <div className="offer-grid">
                    {offers.map((offer) => {
                      const active = selected?.fornecedor === offer.fornecedor && selected?.descricao === offer.descricao;
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
                            <strong>{currency(offer.valor_unitario)}</strong>
                            <small>{offer.unidade || material.medida}</small>
                          </span>
                          <span className="offer-bottom">
                            <small>{offer.disponibilidade || "Sem disponibilidade"}</small>
                            <strong>{currency(offer.valor_total ?? offer.preco_a_vista)}</strong>
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
                  <span>{currency(selected?.valor_total ?? selected?.preco_a_vista)}</span>
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
    </main>
  );
}
