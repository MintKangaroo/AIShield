# Roadmap

1. **Foundation** — API/package structure, dashboard shell, Compose, quality gates, reproducibility
   policy, and experiment result schema.
2. **Registry** — MNIST/CIFAR-10 adapters, a small CNN, torchvision adapters, checksums, split and
   seed records, and model evaluation API.
3. **Clean baseline** — accuracy, loss, confusion matrix, per-class precision/recall, latency,
   artifacts, and same-seed rerun checks.
4. **FGSM** — bounded untargeted attack first, gradient validation, comparison artifacts, paired
   clean/robust metrics, and algorithm documentation.
5. **PGD** — validated epsilon/alpha/iteration parameters, random starts, L-infinity bounds,
   strength curves, and FGSM comparison.
6. **Additional attacks** — BIM, DeepFool, Carlini-Wagner, and an AutoAttack adapter behind the
   common attack interface, each with independent numerical tests.
7. **Defense evaluation** — adversarial training, TRADES adapter, preprocessing baseline,
   transferability, adaptive reevaluation, and gradient-masking checks.
8. **Robustness score** — a documented versioned formula with all raw metric inputs retained.
9. **Dashboard** — experiment/model comparisons, parameters, curves, samples, matrices, defense
   comparisons, and export.
10. **LLM security design** — interfaces and roadmap only, with execution and metrics separated from
    image-model evaluation.

Each milestone is committed independently after its tests and static checks pass.
