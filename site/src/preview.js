// Размеры — внешний прямоугольник превью, включая рамку.
export function placePreview(rect, viewport, image = { width: 300, height: 360 }) {
  if (!(image.width > 0 && image.height > 0)) return null;
  const margin = 16;
  const gap = 12;
  const { width: vw, height: vh } = viewport;
  if (rect.bottom <= margin || rect.top >= vh - margin ||
    rect.right <= margin || rect.left >= vw - margin) return null;
  const right = Math.max(margin, rect.right + gap);
  const bottom = Math.max(margin, rect.bottom + gap);
  const regions = [
    { side: "right", left: right, top: margin, width: vw - margin - right, height: vh - 2 * margin },
    { side: "left", left: margin, top: margin, width: Math.min(vw - margin, rect.left - gap) - margin, height: vh - 2 * margin },
    { side: "below", left: margin, top: bottom, width: vw - 2 * margin, height: vh - margin - bottom },
    { side: "above", left: margin, top: margin, width: vw - 2 * margin, height: Math.min(vh - margin, rect.top - gap) - margin },
  ].filter((region) => region.width >= 180 && region.height >= 62);
  const side = regions.find((region) => region.side === "right" || region.side === "left");
  const region = side || regions.sort((a, b) => b.height - a.height)[0];
  if (!region) return null;
  // Масштабируем изображение целиком; по одному пикселю рамки с каждой стороны.
  const scale = Math.min((Math.min(300, region.width) - 2) / image.width,
    (Math.min(362, region.height) - 2) / image.height);
  const width = image.width * scale + 2;
  const height = image.height * scale + 2;
  const clamp = (value, min, max) => Math.max(min, Math.min(value, max));
  if (region.side === "right" || region.side === "left") {
    return {
      left: region.side === "right" ? region.left : region.left + region.width - width,
      top: clamp(rect.top, margin, vh - margin - height), width, height,
    };
  }
  return {
    left: clamp(rect.left, margin, vw - margin - width),
    top: region.side === "below" ? region.top : region.top + region.height - height,
    width, height,
  };
}
