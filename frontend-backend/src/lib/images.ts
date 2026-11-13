// Real field photos — the same Unsplash photos the old agri-fusion-bd site
// uses in its cards (src/lib/images.ts there). Remote Unsplash URLs, so no
// binary files need to be committed to the repo; images load lazily.
// Pattern (from the old site): <img src={photo} loading="lazy" />
// with object-fit: cover — full-bleed card headers, or small thumbnails.

const U = (id: string, width = 900) =>
  `https://images.unsplash.com/${id}?auto=format&fit=crop&w=${width}&q=78`

export const farmPhotos = {
  farmer: U('photo-1558289282-647de9fdf608'),
  rice: U('photo-1558289282-647de9fdf608'),
  wheat: U('photo-1779043151848-784c1bc6c780'),
  greenField: U('photo-1592982537447-7440770cbfc9'),
  irrigation: U('photo-1777058019395-8b455056f99c'),
  watering: U('photo-1722286092981-daad28048013'),
  pest: U('photo-1774427477281-9d4faf8d19d1'),
  storm: U('photo-1643918031463-7d04999e4c8c'),
  specialist: U('photo-1779043151848-784c1bc6c780'),
  aerial: U('photo-1524486361537-8ad15938e1a3'),
}

/** Pick a photo for a crop name (English or Bangla), like the old site. */
export function cropPhoto(crop = ''): string {
  const value = crop.toLowerCase()
  if (value.includes('rice') || value.includes('paddy') || value.includes('ধান') || value.includes('aman')) return farmPhotos.rice
  if (value.includes('wheat') || value.includes('গম')) return farmPhotos.wheat
  if (value.includes('vegetable') || value.includes('সবজি') || value.includes('chili')) return farmPhotos.greenField
  if (value.includes('jute') || value.includes('পাট')) return farmPhotos.greenField
  if (value.includes('mustard') || value.includes('সরিষা')) return farmPhotos.greenField
  if (value.includes('mung') || value.includes('মুগ') || value.includes('lentil') || value.includes('মসুর')) return farmPhotos.greenField
  return farmPhotos.greenField
}

/** Cycle the three rotation photos, like the old site. */
export function rotationPhoto(index: number): string {
  return [farmPhotos.rice, farmPhotos.greenField, farmPhotos.wheat][index % 3]
}

/** A photo for a field — by its crop when known, else by its position. */
export function fieldPhoto(cropName = '', index = 0): string {
  if (cropName) return cropPhoto(cropName)
  return [farmPhotos.rice, farmPhotos.greenField, farmPhotos.wheat][index % 3]
}
