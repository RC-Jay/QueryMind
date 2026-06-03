declare module "plotly.js-dist-min" {
  export function newPlot(
    root: HTMLElement,
    data: unknown[],
    layout?: Record<string, unknown>,
    config?: Record<string, unknown>
  ): Promise<void>;
  export function purge(root: HTMLElement): void;
  export function downloadImage(
    root: HTMLElement,
    options: { format: string; filename: string; width: number; height: number }
  ): Promise<void>;
}
