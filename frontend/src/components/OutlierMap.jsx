import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import * as d3 from "d3";
import { Loader2, Compass, RefreshCw } from "lucide-react";
import { api } from "@/services/api";
import { toast } from "sonner";
import { useT } from "@/lib/useT";

export default function OutlierMap({ projectId, docs }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const svgRef = useRef(null);
  const nav = useNavigate();
  const params = useParams();
  const pid = projectId || params?.id;
  const { t } = useT();

  const load = async () => {
    if (!docs || docs.filter((d) => d.status === "ready").length === 0) {
      setData(null);
      return;
    }
    setLoading(true);
    try {
      const r = await api.outliers(projectId);
      setData(r);
    } catch {
      toast.error("Gagal menghitung outlier");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [projectId, docs.filter((d) => d.status === "ready").length, docs.map((d) => d.id).join(",")]);

  // D3 render
  useEffect(() => {
    if (!data || !svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const width = svgRef.current.clientWidth;
    const height = 360;
    const margin = { top: 24, right: 24, bottom: 36, left: 48 };

    const xScale = d3
      .scaleLinear()
      .domain([0, 1])
      .range([margin.left, width - margin.right]);
    const yScale = d3
      .scaleLinear()
      .domain([0, 1])
      .range([height - margin.bottom, margin.top]);

    // axes
    svg
      .append("g")
      .attr("transform", `translate(0,${height - margin.bottom})`)
      .call(d3.axisBottom(xScale).ticks(5).tickFormat(d3.format(".1f")))
      .selectAll("text")
      .attr("class", "text-[10px]")
      .attr("fill", "#868e96");
    svg
      .append("g")
      .attr("transform", `translate(${margin.left},0)`)
      .call(d3.axisLeft(yScale).ticks(5).tickFormat(d3.format(".1f")))
      .selectAll("text")
      .attr("class", "text-[10px]")
      .attr("fill", "#868e96");

    // axis labels
    svg
      .append("text")
      .attr("x", width / 2)
      .attr("y", height - 6)
      .attr("text-anchor", "middle")
      .attr("font-size", 10)
      .attr("letter-spacing", "0.18em")
      .attr("text-transform", "uppercase")
      .attr("fill", "#868e96")
      .text(t("outlier.xLabel"));
    svg
      .append("text")
      .attr("transform", `translate(12,${height / 2}) rotate(-90)`)
      .attr("text-anchor", "middle")
      .attr("font-size", 10)
      .attr("letter-spacing", "0.18em")
      .attr("text-transform", "uppercase")
      .attr("fill", "#868e96")
      .text(t("outlier.yLabel"));

    // dots
    const tooltip = d3.select(svgRef.current.parentNode).select(".jm-tooltip");

    svg
      .append("g")
      .selectAll("circle")
      .data(data.points)
      .join("circle")
      .attr("cx", (d) => xScale(d.x))
      .attr("cy", (d) => yScale(d.y))
      .attr("r", 9)
      .attr("fill", (d) => (d.is_outlier ? "#dc2626" : "#1a1d20"))
      .attr("fill-opacity", 0.85)
      .attr("stroke", "white")
      .attr("stroke-width", 2)
      .attr("data-testid", (d) => `outlier-point-${d.document_id}`)
      .style("cursor", "pointer")
      .on("mouseenter", function (e, d) {
        d3.select(this).transition().duration(150).attr("r", 12);
        const kw = (d.keywords || []).slice(0, 6);
        tooltip
          .style("opacity", 1)
          .style("left", `${e.offsetX + 12}px`)
          .style("top", `${e.offsetY + 12}px`)
          .html(
            `<div class="font-ui text-xs font-semibold text-[color:var(--jm-text)] max-w-[260px] leading-tight">${d.title}</div>
             <div class="text-[10px] text-[color:var(--jm-text-3)] mt-1">Kemiripan: ${(d.similarity_to_centroid * 100).toFixed(1)}%</div>
             ${kw.length ? `<div class="mt-1.5 flex flex-wrap gap-1 max-w-[260px]">${kw.map((k) => `<span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[color:var(--jm-sidebar)] text-[color:var(--jm-text-2)]">${k}</span>`).join("")}</div>` : ""}
             ${d.is_outlier ? '<div class="text-[10px] text-[color:var(--jm-low-fg)] font-semibold mt-1.5">OUTLIER — periksa relevansi</div>' : ""}
             <div class="text-[10px] text-[color:var(--jm-text-3)] mt-1.5 italic">Klik untuk buka jurnal →</div>`,
          );
      })
      .on("mousemove", function (e) {
        tooltip.style("left", `${e.offsetX + 12}px`).style("top", `${e.offsetY + 12}px`);
      })
      .on("mouseleave", function () {
        d3.select(this).transition().duration(150).attr("r", 9);
        tooltip.style("opacity", 0);
      })
      .on("click", function (e, d) {
        nav(`/project/${pid}/doc/${d.document_id}`);
      });
  }, [data, nav, pid]);

  return (
    <section
      data-testid="outlier-section"
      className="rounded-xl bg-white border border-[color:var(--jm-border)] p-5"
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)]">
          <Compass className="w-3.5 h-3.5" /> Peta Outlier Proyek
        </div>
        <button
          data-testid="outlier-refresh"
          onClick={load}
          className="text-xs flex items-center gap-1.5 px-2.5 py-1.5 rounded hover:bg-[color:var(--jm-sidebar)] text-[color:var(--jm-text-2)] font-ui"
        >
          <RefreshCw className="w-3 h-3" /> Hitung ulang
        </button>
      </div>

      {!data || loading ? (
        <div className="h-[360px] flex items-center justify-center text-[color:var(--jm-text-3)] font-ui text-sm">
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin mr-2" /> Menghitung…
            </>
          ) : (
            "Unggah minimal 2 jurnal yang sudah selesai diproses untuk melihat peta outlier."
          )}
        </div>
      ) : (
        <div className="relative">
          <svg
            ref={svgRef}
            data-testid="outlier-svg"
            width="100%"
            height={360}
            className="overflow-visible"
          />
          <div
            className="jm-tooltip absolute pointer-events-none bg-white border border-[color:var(--jm-border)] shadow-md rounded-md p-2.5 text-xs"
            style={{ opacity: 0, transition: "opacity 120ms" }}
          />
          <div
            data-testid="outlier-summary"
            className="mt-3 pt-3 border-t border-[color:var(--jm-border)] text-sm font-reading text-[color:var(--jm-text-2)]"
          >
            {data.summary}
          </div>
        </div>
      )}
    </section>
  );
}
