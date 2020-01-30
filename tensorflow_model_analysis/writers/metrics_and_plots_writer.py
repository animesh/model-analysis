# Lint as: python3
# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Metrics and plots writer."""

from __future__ import absolute_import
from __future__ import division
# Standard __future__ imports
from __future__ import print_function

from typing import Dict, List, Text

import apache_beam as beam
from tensorflow_model_analysis import constants
from tensorflow_model_analysis import types
from tensorflow_model_analysis.evaluators import evaluator
from tensorflow_model_analysis.writers import metrics_and_plots_serialization
from tensorflow_model_analysis.writers import writer


def MetricsAndPlotsWriter(
    output_paths: Dict[Text, Text],
    add_metrics_callbacks: List[types.AddMetricsCallbackType]) -> writer.Writer:
  """Returns metrics and plots writer.

  Args:
    output_paths: Output paths keyed by output key (e.g. 'metrics', 'plots').
    add_metrics_callbacks: Optional list of metric callbacks (if used).
  """
  return writer.Writer(
      stage_name='WriteMetricsAndPlots',
      ptransform=_WriteMetricsAndPlots(  # pylint: disable=no-value-for-parameter
          output_paths=output_paths,
          add_metrics_callbacks=add_metrics_callbacks))


@beam.ptransform_fn
@beam.typehints.with_input_types(evaluator.Evaluation)
@beam.typehints.with_output_types(beam.pvalue.PDone)
def _WriteMetricsAndPlots(
    evaluation: evaluator.Evaluation, output_paths: Dict[Text, Text],
    add_metrics_callbacks: List[types.AddMetricsCallbackType]):
  """PTransform to write metrics and plots."""

  metrics = evaluation[constants.METRICS_KEY]
  plots = evaluation[constants.PLOTS_KEY]

  metrics, plots = ((metrics, plots)
                    | 'SerializeMetricsAndPlots' >>
                    metrics_and_plots_serialization.SerializeMetricsAndPlots(
                        add_metrics_callbacks=add_metrics_callbacks))

  if constants.METRICS_KEY in output_paths:
    # We only use a single shard here because metrics are usually single values,
    # so even with 1M slices and a handful of metrics the size requirements will
    # only be a few hundred MB.
    _ = metrics | 'WriteMetrics' >> beam.io.WriteToTFRecord(
        file_path_prefix=output_paths[constants.METRICS_KEY],
        shard_name_template='')

  if constants.PLOTS_KEY in output_paths:
    # We only use a single shard here because we are assuming that plots will
    # not be enabled when millions of slices are in use. By default plots are
    # stored with 1K thresholds with each plot entry taking up to 7 fields
    # (tp, fp, ... recall) so if this assumption is false the output can end up
    # in the hundreds of GB.
    _ = plots | 'WritePlots' >> beam.io.WriteToTFRecord(
        file_path_prefix=output_paths[constants.PLOTS_KEY],
        shard_name_template='')

  return beam.pvalue.PDone(metrics.pipeline)
