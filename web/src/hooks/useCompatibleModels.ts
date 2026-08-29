import { useEffect, useMemo, useState } from "react";

import type { DatasetRecord, ModelVersionRecord } from "../types";

/** Models whose input channels and class count match the selected dataset. */
export function useCompatibleModels(
  datasets: DatasetRecord[],
  models: ModelVersionRecord[],
  datasetId: string,
) {
  const dataset = datasets.find((item) => item.id === datasetId);
  return useMemo(
    () =>
      models.filter(
        (model) =>
          dataset !== undefined &&
          model.input_channels === dataset.input_shape[0] &&
          model.num_classes === dataset.num_classes,
      ),
    [dataset, models],
  );
}

/**
 * Hold a model selection that always stays inside the compatible set, falling back
 * to the first compatible model whenever the dataset selection changes.
 */
export function useModelSelection(compatibleModels: ModelVersionRecord[]) {
  const [modelId, setModelId] = useState(compatibleModels[0]?.id ?? "");

  useEffect(() => {
    if (!compatibleModels.some((model) => model.id === modelId)) {
      setModelId(compatibleModels[0]?.id ?? "");
    }
  }, [compatibleModels, modelId]);

  return [modelId, setModelId] as const;
}

/** Parse the optional "sample cap" text field into the API's nullable integer. */
export function parseSampleCap(value: string): number | null {
  return value.trim() ? Number(value) : null;
}
