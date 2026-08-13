import { toPng } from "html-to-image";

export type PngRenderer = (
  node: HTMLElement,
  options?: Parameters<typeof toPng>[1],
) => Promise<string>;

function waitForPaint(): Promise<void> {
  return new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  });
}

export async function exportReportAsPng(
  reportElement: HTMLElement,
  filenameBase: string,
  renderer: PngRenderer = toPng,
): Promise<void> {
  const previousExportState = reportElement.dataset.exporting;
  reportElement.dataset.exporting = "true";

  try {
    await document.fonts.ready;
    await waitForPaint();

    const width = Math.ceil(reportElement.scrollWidth);
    const height = Math.ceil(reportElement.scrollHeight);
    const dataUrl = await renderer(reportElement, {
      backgroundColor: getComputedStyle(reportElement).backgroundColor,
      cacheBust: true,
      height,
      pixelRatio: 2,
      width,
    });

    const downloadLink = document.createElement("a");
    downloadLink.download = `${filenameBase}.png`;
    downloadLink.href = dataUrl;
    downloadLink.click();
  } finally {
    if (previousExportState === undefined) {
      delete reportElement.dataset.exporting;
    } else {
      reportElement.dataset.exporting = previousExportState;
    }
  }
}
