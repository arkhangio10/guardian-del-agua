/** Approximate area of a WGS84 bbox in km², using cos(lat) compensation. */
export function bboxAreaKm2(bbox: number[] | undefined | null): number | null {
  if (!bbox || bbox.length !== 4) return null;
  const [lonMin, latMin, lonMax, latMax] = bbox;
  const latCenter = (latMin + latMax) / 2;
  const kmPerDegLon = 111.32 * Math.cos((latCenter * Math.PI) / 180);
  const kmPerDegLat = 110.57;
  const dLon = Math.max(0, lonMax - lonMin);
  const dLat = Math.max(0, latMax - latMin);
  const area = dLon * kmPerDegLon * dLat * kmPerDegLat;
  return Math.round(area);
}

/** Centroid of a bbox as [lon, lat]. */
export function bboxCentroid(bbox: number[] | undefined | null): [number, number] | null {
  if (!bbox || bbox.length !== 4) return null;
  return [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2];
}

/** Approximate side lengths of bbox in km, [width, height]. */
export function bboxSidesKm(bbox: number[] | undefined | null): [number, number] | null {
  if (!bbox || bbox.length !== 4) return null;
  const [lonMin, latMin, lonMax, latMax] = bbox;
  const latCenter = (latMin + latMax) / 2;
  const kmPerDegLon = 111.32 * Math.cos((latCenter * Math.PI) / 180);
  const kmPerDegLat = 110.57;
  return [
    Math.round((lonMax - lonMin) * kmPerDegLon),
    Math.round((latMax - latMin) * kmPerDegLat),
  ];
}
