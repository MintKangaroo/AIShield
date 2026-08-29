import { describe, expect, it } from "vitest";

import { attackAlgorithms, attackProfiles, curveAlgorithms } from "./attacks";

describe("attack profiles", () => {
  it("covers exactly the algorithms the API accepts", () => {
    expect([...attackAlgorithms].sort()).toEqual(
      ["apgd", "autoattack", "bim", "cw", "deepfool", "fab", "fgsm", "pgd", "square"].sort(),
    );
  });

  it("keeps FGSM single-step, which the server contract requires", () => {
    expect(attackProfiles.fgsm.iterative).toBe(false);
    expect(attackProfiles.fgsm.randomStart).toBe(false);
  });

  it("only randomizes the start for PGD", () => {
    const randomized = attackAlgorithms.filter((item) => attackProfiles[item].randomStart);
    expect(randomized).toEqual(["pgd"]);
  });

  it("marks exactly DeepFool and CW as L2 attacks", () => {
    const l2 = attackAlgorithms.filter((item) => attackProfiles[item].norm === "l2");
    expect(l2.sort()).toEqual(["cw", "deepfool"]);
  });

  it("restricts strength curves to monotone L-infinity sweeps", () => {
    for (const algorithm of curveAlgorithms) {
      expect(attackProfiles[algorithm].norm).toBe("linf");
    }
  });
});
