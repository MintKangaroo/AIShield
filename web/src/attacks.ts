import type { AttackAlgorithm } from "./types";

interface AlgorithmProfile {
  label: string;
  description: string;
  norm: "linf" | "l2";
  iterative: boolean;
  randomStart: boolean;
}

/**
 * Client-side mirror of the server's `AttackConfig` validator, so the dashboard
 * cannot submit a configuration the API contract would reject.
 */
export const attackProfiles: Record<AttackAlgorithm, AlgorithmProfile> = {
  fgsm: {
    label: "FGSM",
    description: "Fast single-step gradient attack",
    norm: "linf",
    iterative: false,
    randomStart: false,
  },
  bim: {
    label: "BIM",
    description: "Iterative attack without random start",
    norm: "linf",
    iterative: true,
    randomStart: false,
  },
  pgd: {
    label: "PGD",
    description: "Iterative projected attack with random start",
    norm: "linf",
    iterative: true,
    randomStart: true,
  },
  deepfool: {
    label: "DeepFool",
    description: "L2 boundary attack with adaptive steps",
    norm: "l2",
    iterative: true,
    randomStart: false,
  },
  cw: {
    label: "CW",
    description: "L2 margin optimization attack",
    norm: "l2",
    iterative: true,
    randomStart: false,
  },
  autoattack: {
    label: "AutoAttack",
    description: "Deterministic FGSM/BIM/PGD ensemble",
    norm: "linf",
    iterative: true,
    randomStart: false,
  },
  apgd: {
    label: "APGD",
    description: "Bounded auto-PGD compatibility adapter",
    norm: "linf",
    iterative: true,
    randomStart: false,
  },
  fab: {
    label: "FAB",
    description: "Bounded fast adaptive boundary adapter",
    norm: "linf",
    iterative: true,
    randomStart: false,
  },
  square: {
    label: "Square",
    description: "Bounded query-limited search adapter",
    norm: "linf",
    iterative: true,
    randomStart: false,
  },
};

export const attackAlgorithms = Object.keys(attackProfiles) as AttackAlgorithm[];

/** Curve endpoints only accept algorithms with a monotone epsilon sweep. */
export const curveAlgorithms = ["pgd", "apgd", "fab", "square"] as const;
