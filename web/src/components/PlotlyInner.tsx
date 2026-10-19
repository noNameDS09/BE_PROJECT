/**
 * The actual Plotly renderer. Imported only through React.lazy (see PlotlyChart.tsx) so the
 * ~4.5 MB plotly.js bundle stays out of the main chunk.
 */
import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";
import { useMemo } from "react";
import type { PlotlyFigure } from "../api/types";
import { useThemeVersion } from "../lib/theme";

const Plot = createPlotlyComponent(Plotly);

type Obj = Record<string, unknown>;

function isObj(v: unknown): v is Obj {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** Deep merge where `over` wins (arrays are replaced, not merged). */
function merge(base: Obj, over: Obj): Obj {
  const out: Obj = { ...base };
  for (const [k, v] of Object.entries(over)) {
    const b = out[k];
    out[k] = isObj(b) && isObj(v) ? merge(b, v) : v;
  }
  return out;
}

function cssVar(name: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

export interface PlotlyInnerProps {
  figure: PlotlyFigure;
  height?: number;
}

export default function PlotlyInner({ figure, height }: PlotlyInnerProps) {
  const themeVersion = useThemeVersion();

  const layout = useMemo(() => {
    const text = cssVar("--text-muted", "#52525b");
    const grid = cssVar("--border", "#e4e4e7");
    const font = cssVar("--font", "system-ui, sans-serif");
    const axis = { gridcolor: grid, zerolinecolor: grid, linecolor: grid, tickfont: { color: text }, title: { font: { color: text } } };
    const themed: Obj = {
      autosize: true,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: font, size: 12, color: text },
      margin: { t: 24, r: 16, b: 40, l: 56 },
      xaxis: axis,
      yaxis: axis,
      yaxis2: axis,
      legend: { orientation: "h", y: -0.2, font: { color: text } },
      hoverlabel: { font: { family: font } },
    };
    const merged = merge(themed, figure.layout ?? {});
    // Keep a transparent background so the chart sits on the card in both themes.
    merged.paper_bgcolor = "rgba(0,0,0,0)";
    merged.plot_bgcolor = "rgba(0,0,0,0)";
    if (height) merged.height = height;
    if (!isObj(figure.layout) || !("yaxis2" in figure.layout)) delete merged.yaxis2;
    return merged;
    // themeVersion re-reads the CSS variables after a theme switch.
  }, [figure.layout, height, themeVersion]);

  const h = typeof layout.height === "number" ? layout.height : 280;

  return (
    <Plot
      data={figure.data}
      layout={layout}
      config={{ displaylogo: false, responsive: true, modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"] }}
      useResizeHandler
      style={{ width: "100%", height: h }}
    />
  );
}
