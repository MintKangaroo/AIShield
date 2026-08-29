"""Serializable descriptions of the work a background job performs.

A closure cannot cross a process boundary. Describing a job as data instead of
as a callable is what lets the same task be executed by the in-process worker or
by a separate worker process reading from a shared queue, without the two paths
diverging.
"""

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, TypeAdapter

from aishield.registry.contracts import RegistryModel
from aishield.training.contracts import TrainingConfig


class TaskKind(StrEnum):
    """Work a background worker knows how to execute."""

    TRAINING = "training"


class TrainingTask(RegistryModel):
    """Train a copy of a registered model with bounded adversarial examples."""

    kind: Literal[TaskKind.TRAINING] = TaskKind.TRAINING
    model_version_id: UUID
    dataset_id: UUID
    config: TrainingConfig


#: Discriminated on ``kind`` so a worker can reject unknown work rather than guess.
TaskDescriptor = Annotated[TrainingTask, Field(discriminator="kind")]

task_adapter: TypeAdapter[TaskDescriptor] = TypeAdapter(TrainingTask)
