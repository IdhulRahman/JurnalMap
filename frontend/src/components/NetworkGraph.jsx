import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import * as d3 from "d3";
import { Loader2, Network as NetworkIcon, RefreshCw, AlertTriangle } from "lucide-react";
import { api } from "@/services/api";
import { toast } from "sonner";
import { useT } from "@/lib/useT";

/**
 * Network Graph — replaces OutlierMap in Tab Baca.
 *
 * Auto-loads when the list of ready docs changes. Nodes = documents, edges =
 * composite similarity > 0.7. Isolated nodes (max_edge_score < 0.4) are
 * flagged as "Potensial tidak relevan" and rendered with a warning ring.
 */
export default function NetworkGraph({ projectId, docs }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedEdge, setSelectedEdge] = useState(null);
  const svgRef = useRef(null);
  const nav = useNavigate();
  const params = useParams();
  const pid = projectId || params?.id;
  const { t } = useT();

  const readyDocs = useMemo(
    () => (docs || []).filter((d) => d.status === "ready"),
    [docs],
  );

  const load = async () => {
    if (readyDocs.length < 2) {
      setData(null);
      return;
    }
    setLoading(true);
    try {
      const r = await api.network(pid);
      setData(r);
    } catch (e) {
      toast.error(t("network.errLoad"));
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh when the ready-docs set changes
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid, readyDocs.map((d) => d.id).join(",")]);

  // D3 force-directed graph render
  useEffect(() => {
    if (!data || !svgRef.current) return undefined;
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    const width = svgRef.current.clientWidth;
    const height = 460;

    const nodes = data.nodes.map((n) => ({ ...n }));
    const edges = data.edges.map((e) => ({ ...e }));

    const link = svg.append("g")
      .selectAll("line")
      .data(edges)
      .join("line")
      .attr("stroke", (d) => (d.strength === "kuat" ? "#10b981" : "#f59e0b"))
      .attr("stroke-width", (d) => (d.strength === "kuat" ? 3 : 1.8))
      .attr("stroke-opacity", (d) => (d.strength === "kuat" ? 0.8 : 0.6))
      .attr("stroke-dasharray", (d) => (d.strength === "sedang" ? "5,5" : "none"))
      .attr("data-testid", (d) => `net-edge-${d.source}-${d.target}`)
      .style("cursor", "pointer")
      .on("mouseenter", (_, d) => setSelectedEdge(d))
      .on("mouseleave", () => setSelectedEdge(null))
      .on("click", (_, d) => setSelectedEdge(d));

    const nodeG = svg.append("g")
      .selectAll("g")
      .data(nodes)
      .join("g")
      .attr("data-testid", (d) => `net-node-${d.id}`)
      .style("cursor", "pointer")
      .on("click", (_, d) => nav(`/project/${pid}/doc/${d.id}`));

    nodeG.append("circle")
      .attr("r", 14)
      .attr("fill", (d) => (d.isolated ? "#dc2626" : "var(--jm-text)"))
      .attr("fill-opacity", 0.95)
      .attr("stroke", (d) => (d.isolated ? "#fca5a5" : "var(--jm-border-2)"))
      .attr("stroke-width", (d) => (d.isolated ? 3 : 2));

    nodeG.append("title").text((d) => `${d.title}\n${d.isolated ? "Potensial tidak relevan" : ""}`);

    nodeG.append("text")
      .attr("x", 18)
      .attr("y", 4)
      .attr("font-size", 11)
      .attr("font-family", "IBM Plex Sans, system-ui, sans-serif")
      .attr("font-weight", 600)
      .attr("fill", "currentColor")
      .attr("class", "text-[color:var(--jm-text)]")
      .text((d) => (d.title.length > 34 ? `${d.title.slice(0, 32)}…` : d.title));

    const sim = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(edges).id((d) => d.id).distance((d) => 220 * (1 - d.weight * 0.4)))
      .force("charge", d3.forceManyBody().strength(-360))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collide", d3.forceCollide(46))
      .on("tick", () => {
        link
          .attr("x1", (d) => d.source.x)
          .attr("y1", (d) => d.source.y)
          .attr("x2", (d) => d.target.x)
          .attr("y2", (d) => d.target.y);
        nodeG.attr("transform", (d) => `translate(${d.x},${d.y})`);
      });

    return () => sim.stop();
  }, [data, nav, pid]);

  return (
    <section
      data-testid="network-section"
      className="rounded-xl bg-[var(--jm-surface)] border-2 border-[var(--jm-border-2)] p-5"
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)]">
          <NetworkIcon className="w-3.5 h-3.5" /> {t("network.title")}
        </div>
        <div className="flex items-center gap-2">
          {data?.embedding_backend && (
            <span
              data-testid="network-backend"
              className="hidden sm:inline text-[10px] uppercase tracking-[0.18em] text-[color:var(--jm-text-3)] font-ui"
              title={data.embedding_backend}
            >
              {data.embedding_backend.split(" ")[0]}
            </span>
          )}
          <button
            data-testid="network-refresh"
            onClick={load}
            className="text-xs flex items-center gap-1.5 px-2.5 py-1.5 rounded hover:bg-[color:var(--jm-sidebar)] text-[color:var(--jm-text-2)] font-ui"
          >
            <RefreshCw className="w-3 h-3" /> {t("network.refresh")}
          </button>
        </div>
      </div>

      {readyDocs.length < 2 ? (
        <div className="h-[320px] flex items-center justify-center text-[color:var(--jm-text-3)] font-ui text-sm text-center px-6">
          {t("network.needTwo")}
        </div>
      ) : loading || !data ? (
        <div className="h-[320px] flex items-center justify-center text-[color:var(--jm-text-3)] font-ui text-sm">
          <Loader2 className="w-4 h-4 animate-spin mr-2" /> {t("network.building")}
        </div>
      ) : (
        <div className="relative">
          <svg
            ref={svgRef}
            data-testid="network-svg"
            width="100%"
            height={460}
            className="overflow-visible text-[color:var(--jm-text)]"
          />
          {selectedEdge && (
            <div
              data-testid="network-edge-tip"
              className="absolute bottom-3 right-3 max-w-sm rounded-lg border-2 border-[var(--jm-border-2)] bg-[var(--jm-surface)] p-3 shadow-lg text-xs font-ui"
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                  {t("network.edgeInfo")}
                </span>
                <button
                  data-testid="network-edge-close"
                  onClick={() => setSelectedEdge(null)}
                  className="text-[color:var(--jm-text-3)] hover:text-[color:var(--jm-text)]"
                >
                  ×
                </button>
              </div>
              <div className="text-[11px] text-[color:var(--jm-text-2)] leading-relaxed">
                <div>
                  <span className="font-semibold">Kategori:</span>{" "}
                  <span className={selectedEdge.strength === "kuat" ? "text-emerald-500 font-semibold" : "text-amber-500 font-semibold"}>
                    {selectedEdge.strength === "kuat" ? "Kuat" : "Sedang"}
                  </span>
                </div>
                <div>
                  <span className="font-semibold">Composite:</span>{" "}
                  {(selectedEdge.weight * 100).toFixed(0)}%
                </div>
                <div>
                  <span className="font-semibold">Semantic:</span>{" "}
                  {(selectedEdge.semantic * 100).toFixed(0)}%
                  {" · "}
                  <span className="font-semibold">Keyword:</span>{" "}
                  {(selectedEdge.keyword * 100).toFixed(0)}%
                  {" · "}
                  <span className="font-semibold">Topic:</span>{" "}
                  {(selectedEdge.topic * 100).toFixed(0)}%
                </div>
                {selectedEdge.shared_keywords?.length > 0 && (
                  <div className="mt-1.5">
                    <span className="font-semibold">Overlap:</span>{" "}
                    <span className="text-[color:var(--jm-text)]">
                      {selectedEdge.shared_keywords.join(", ")}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
          <div
            data-testid="network-summary"
            className="mt-3 pt-3 border-t-2 border-[var(--jm-border-2)] text-sm font-reading text-[color:var(--jm-text-2)] flex items-start gap-2"
          >
            {data.nodes.some((n) => n.isolated) && (
              <AlertTriangle className="w-4 h-4 text-[color:var(--jm-low-fg)] shrink-0 mt-0.5" />
            )}
            <span>{data.summary}</span>
          </div>
        </div>
      )}
    </section>
  );
}
