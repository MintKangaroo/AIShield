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
    description: "빠른 단일 스텝 그래디언트 공격",
    norm: "linf",
    iterative: false,
    randomStart: false,
  },
  bim: {
    label: "BIM",
    description: "랜덤 시작 없는 반복 공격",
    norm: "linf",
    iterative: true,
    randomStart: false,
  },
  pgd: {
    label: "PGD",
    description: "랜덤 시작이 있는 반복 투영 공격",
    norm: "linf",
    iterative: true,
    randomStart: true,
  },
  deepfool: {
    label: "DeepFool",
    description: "적응 스텝의 L2 경계 공격",
    norm: "l2",
    iterative: true,
    randomStart: false,
  },
  cw: {
    label: "CW",
    description: "L2 마진 최적화 공격",
    norm: "l2",
    iterative: true,
    randomStart: false,
  },
  autoattack: {
    label: "AutoAttack",
    description: "결정론적 FGSM/BIM/PGD 앙상블",
    norm: "linf",
    iterative: true,
    randomStart: false,
  },
  apgd: {
    label: "APGD",
    description: "경계 auto-PGD 호환 어댑터",
    norm: "linf",
    iterative: true,
    randomStart: false,
  },
  fab: {
    label: "FAB",
    description: "경계 fast adaptive boundary 어댑터",
    norm: "linf",
    iterative: true,
    randomStart: false,
  },
  square: {
    label: "Square",
    description: "경계 질의 제한 탐색 어댑터",
    norm: "linf",
    iterative: true,
    randomStart: false,
  },
};

export const attackAlgorithms = Object.keys(attackProfiles) as AttackAlgorithm[];

/** Curve endpoints only accept algorithms with a monotone epsilon sweep. */
export const curveAlgorithms = ["pgd", "apgd", "fab", "square"] as const;
