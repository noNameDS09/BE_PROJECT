import { Component, Suspense, lazy, type ReactNode } from "react";
import type { PlotlyFigure } from "../api/types";
import { Skeleton } from "./Feedback";

const PlotlyInner = lazy(() => import("./PlotlyInner"));

class ChartBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return <div className="small faint">Chart could not be rendered: {this.state.error.message}</div>;
    }
    return this.props.children;
  }
}

/** Renders a backend Plotly spec ({data, layout}). plotly.js loads on first use. */
export function PlotlyChart({ figure, height }: { figure: PlotlyFigure; height?: number }) {
  const h = height ?? (typeof figure.layout?.height === "number" ? (figure.layout.height as number) : 280);
  return (
    <ChartBoundary>
      <Suspense fallback={<Skeleton height={h} />}>
        <PlotlyInner figure={figure} height={height} />
      </Suspense>
    </ChartBoundary>
  );
}
