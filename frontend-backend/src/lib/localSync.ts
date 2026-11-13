import type { Field } from './types'
import { createField } from './api'
import { deleteLocalField } from './geo'

/** Push a field that only exists in this browser into Django, then remove the
 *  on-device copy. Used by the "Save to my account" actions. */
export async function saveLocalFieldToAccount(field: Field): Promise<Field> {
  const created = await createField({
    name: field.name,
    geometry: field.geometry,
    areaHa: field.areaHa,
    irrigation: field.irrigation,
    soilType: field.soilType,
    priorities: field.priorities,
    currentCycleCrops: field.currentCycleCrops,
    recentCycleCrops: field.recentCycleCrops,
  })
  deleteLocalField(field.id)
  return created
}
