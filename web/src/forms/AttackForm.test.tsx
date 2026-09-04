import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { makeDataset, makeModel } from "../test/fixtures";
import type { AttackRequest } from "../types";
import { AttackForm } from "./AttackForm";

function setup(onSubmit = vi.fn<(payload: AttackRequest) => Promise<void>>()) {
  onSubmit.mockResolvedValue(undefined);
  render(
    <AttackForm
      busy={false}
      datasets={[makeDataset()]}
      models={[makeModel()]}
      onCancel={vi.fn()}
      onSubmit={onSubmit}
    />,
  );
  return onSubmit;
}

/** Pick an algorithm from the picker group, anchored so "PGD" never matches "APGD". */
async function selectAlgorithm(label: string) {
  const picker = screen.getByRole("group", { name: "공격 알고리즘" });
  await userEvent.click(within(picker).getByRole("button", { name: new RegExp(`^${label}`) }));
}

function submitButton() {
  return screen.getByRole("button", { name: /실행$/ });
}

describe("AttackForm", () => {
  it("submits FGSM as a single step with no random start", async () => {
    const onSubmit = setup();

    await userEvent.click(submitButton());

    const payload = onSubmit.mock.calls[0][0];
    expect(payload.algorithm).toBe("fgsm");
    expect(payload.iterations).toBeUndefined();
    expect(payload.random_start).toBeUndefined();
    expect(payload.step_size).toBeUndefined();
    expect(payload.epsilon).toBeCloseTo(8 / 255);
  });

  it("submits PGD with a random start and a bounded step", async () => {
    const onSubmit = setup();

    await selectAlgorithm("PGD");
    await userEvent.click(submitButton());

    const payload = onSubmit.mock.calls[0][0];
    expect(payload.algorithm).toBe("pgd");
    expect(payload.random_start).toBe(true);
    expect(payload.norm).toBe("linf");
    expect(payload.step_size).toBeLessThanOrEqual(payload.epsilon);
  });

  it("submits BIM without a random start", async () => {
    const onSubmit = setup();

    await selectAlgorithm("BIM");
    await userEvent.click(submitButton());

    expect(onSubmit.mock.calls[0][0].random_start).toBe(false);
  });

  it("switches DeepFool to the L2 norm the server requires", async () => {
    const onSubmit = setup();

    await selectAlgorithm("DeepFool");
    await userEvent.click(submitButton());

    expect(onSubmit.mock.calls[0][0].norm).toBe("l2");
  });

  it("submits APGD as a bounded L-infinity attack without a random start", async () => {
    const onSubmit = setup();

    await selectAlgorithm("APGD");
    await userEvent.click(submitButton());

    const payload = onSubmit.mock.calls[0][0];
    expect(payload.algorithm).toBe("apgd");
    expect(payload.norm).toBe("linf");
    expect(payload.random_start).toBe(false);
  });

  it("keeps the step size at or below epsilon for a very small bound", async () => {
    const onSubmit = setup();

    await selectAlgorithm("PGD");
    const epsilon = screen.getByLabelText("엡실론 / 255");
    await userEvent.clear(epsilon);
    await userEvent.type(epsilon, "1");
    await userEvent.click(submitButton());

    const payload = onSubmit.mock.calls[0][0];
    expect(payload.step_size).toBeLessThanOrEqual(payload.epsilon);
  });

  it("disables the iteration field for a single-step attack", () => {
    setup();

    expect(screen.getByLabelText("반복 횟수")).toBeDisabled();
  });

  it("treats a blank sample cap as the whole split", async () => {
    const onSubmit = setup();

    await userEvent.clear(screen.getByLabelText("샘플 상한"));
    await userEvent.click(submitButton());

    expect(onSubmit.mock.calls[0][0].max_samples).toBeNull();
  });

  it("warns when no compatible model exists for the dataset", () => {
    render(
      <AttackForm
        busy={false}
        datasets={[makeDataset({ input_shape: [3, 32, 32] })]}
        models={[makeModel({ input_channels: 1 })]}
        onCancel={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByText(/호환되는 모델이 적재되지 않았습니다/)).toBeInTheDocument();
  });
});
