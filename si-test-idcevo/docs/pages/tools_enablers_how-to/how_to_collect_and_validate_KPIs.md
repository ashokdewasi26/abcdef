# How to collect and validate KPIs

We have in place a way to collect metric based on DLT markers that we call "Generic DLT KPIs".
This was created to be easy configurable and scalable.
All the markers will be collected based after a single reboot.

## Easy way to collect a new KPI - Generic DLT KPIs

There are 3 main files to configure this new metric, you can follow the guidelines on the top of each file on how to add a new entry:
- Main KPI config file, which is ECU-dependant: [idcevo_kpi_metrics_config.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/idcevo_kpi_metrics_config.py) or [rse26_kpi_metrics_config.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/rse26_kpi_metrics_config.py) or [cde_kpi_metrics_config.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/cde_kpi_metrics_config.py);
- [KPI threshold requirement (kpi_threshold_config.py)](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/kpi_threshold_config.py).
- [Metrics naming dict](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/__init__.py)

**This last file** is used as a centralized way to define the name of the new metric on a class variable (MetricsOutputName) to be reused on the other two files.

The next sections explain in more detail the flow of the metric collection.

## Easy way to test a new KPI - Generic DLT KPIs

If you changed the files mentioned in the previous point and have opened a PR, now you are ready to test!

To do that you simply need to comment on you PR "check-all".
This comment will trigger a verification job that in the end should publish the new metric to this dashboard:
[KPI dashboard for verification run](https://mgu-gen22-si-metrics.bmwgroup.net/grafana/d/oXi3zG9Vz/idcevo-generic-performance-kpis?orgId=1&var-kpi_name=All&var-job_name=ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SI-staging&var-build_id=All)
You should expect a new panel with the name of your KPI to show up.

## How to collect KPIs - Generic DLT KPIs

The steps to perform the collection of a new KPI metric are:

1. Create a new entry with all the parameters (check the instructions on the file) in the 'GENERIC_DLT_KPI_CONFIG' dict on: [idcevo_kpi_metrics_config.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/idcevo_kpi_metrics_config.py) or [rse26_kpi_metrics_config.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/rse26_kpi_metrics_config.py) or [cde_kpi_metrics_config.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/cde_kpi_metrics_config.py);

2. If all the metrics are correctly collected the test reports green: [Test ticket - Collect all KPIs from GENERIC_DLT_KPI_CONFIG](https://jira.cc.bmwgroup.net/browse/IDCEVODEV-22247);

3. All the collected metrics are available in the 'test_idcevo.log' on the job artifacts at "test-artifacts/results/" - search for "INFO  [METRIC_STRUCTURED] key=". Here is the [performance-job-history](https://cc-ci.bmwgroup.net/zuul/t/idcevo/builds?job_name=ta-idcevo-hw-mtf3-flash-and-validate-idcevo-SI-performance&project=idcevo/si-test-idcevo);

4. All the metrics collected are available in the output file 'metric.json' located on the job artifacts at "test-artifacts/results/extracted_files/";

5. All the collected metrics are also available in the output file 'generic_dlt_kpis.csv' located on the job artifacts at "test-artifacts/results/extracted_files/";

6. All these metrics are also uploaded to influxDB, this can be confirmed by looking into the file 'metrics_evo.txt' on the root of the job artifacts;

7. These metrics will be available at the grafana dashboard: [IDCEvo - Generic Performance KPIs](https://mgu-gen22-si-metrics.bmwgroup.net/grafana/d/oXi3zG9Vz/idc-evo-generic-performance-kpis?orgId=1).

These steps consist on a new approach to extract KPIs from DLT based on a single reboot.

### Collect multi marker KPIs - Generic DLT KPIs

This was created to fill the need to compute the difference between two markers. So for this we can define which markers we want to use.

The steps to perform the collection of a new multi markerKPI metric are:

1. Ensure start and end marker are being collected in 'GENERIC_DLT_KPI_CONFIG' dict on: [idcevo_kpi_metrics_config.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/idcevo_kpi_metrics_config.py) or [rse26_kpi_metrics_config.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/rse26_kpi_metrics_config.py) or [cde_kpi_metrics_config.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/cde_kpi_metrics_config.py);

2. Create a new entry with all the parameters (check the instructions on the file) in the 'GENERIC_MULTI_MARKERS_KPI_CONFIG' dict on: [idcevo_kpi_metrics_config.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/idcevo_kpi_metrics_config.py) or [rse26_kpi_metrics_config.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/rse26_kpi_metrics_config.py) or [cde_kpi_metrics_config.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/cde_kpi_metrics_config.py);

3. The remaining steps are the same as the Generic DLT KPIs section, so please check the steps 2. to 6. of the above section"

## Where to configure tests pass fail thresholds

This is essentially an agreed place where to place all these values and how to organize them: [kpi_threshold_config](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/kpi_threshold_config.py).

### SI tests with configurable pass fail threshold

The intention of this feature is to allow us, in an easy way, to change a target KPI threshold in a configuration file where all tests in which we have to measure a KPI must read the pass/fail value from that configuration file.

To use this feature, the following guidelines must be used:

- You need to add the target, branch and the new kpi (taget name, branch name and threshold) to the following file within our repository: **si-test-idcevo/si_test_idcevo/si_test_config/[kpi_threshold_config.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/kpi_threshold_config.py#L14)**
- Within the file mentioned above, we created a nested dictionary (**ECU_SPECIFIC_KPI**) with this structure:

```
ECU_SPECIFIC_KPI = {
    "target_name_1": {
        "master": {
            "kpi_name_1": kpi_threshold_1,
            "kpi_name_2": kpi_threshold_2,
            ...
            "kpi_name_n": kpi_threshold_n,
        },
        ...
        "branch_name_n": {
            "kpi_name_1": kpi_threshold_1,
            "kpi_name_2": kpi_threshold_2,
            ...
            "kpi_name_n": kpi_threshold_n,
        },
    },
    ...
    "target_name_n": {
        "master": {
            "kpi_name_1": kpi_threshold_1,
            "kpi_name_2": kpi_threshold_2,
            ...
            "kpi_name_n": kpi_threshold_n
        },
    },
    "default_target": {
        "default_branch": {
            "default_kpi_threshold": 0.0,
        },
    },
}
```

- Basically, this python dictionary will be used to search for the desired target, "target_name_n" which must be the same as defined in: **target.options.target**. For each target, we assume that the main branch that should be configured by default is **master**, but it is also possible to configure different threshold values for each branch with the same KPI. Then, the name you specified for "kpi_name_n" must match exactly what is defined in the test file at: si_test_idcevo/si_test_package_performance/systemtests, otherwise the default values will be used for that KPI.

NOTE: In the repository: **si-test-idcevo/si_test_idcevo/si_test_helpers/[kpi_handlers.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_helpers/kpi_handlers.py#L14)** the helper function, **get_specific_kpi_threshold**, is implemented and is responsible for obtaining the "kpi_threshold_n" for the desired KPI, kpi_name_n.

## How to validate KPI metrics against thresholds

Before implementing a new KPI validation it is assumed that the KPI metrics to validate was already collected (probably using the Generic DLT KPIs)

The recommended usage is to have a defined threshold in [kpi_threshold_config](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/kpi_threshold_config.py) (see section: [SI tests with configurable pass/fail threshold](https://cc-github.bmwgroup.net/pages/idcevo/si-test-idcevo/pages/tools_enablers_how-to/how_to_collect_and_validate_KPIs.html#si-tests-with-configurable-pass-fail-threshold))

As a good practice we suggest the KPI threshold name to be the same as the KPI metric name: see ([example_metric_name](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/kpi_metrics_config.py#L41)) and ([example_threshold_name](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_config/kpi_threshold_config.py#L16))

To perform the validation there is no automatic mechanism, meaning a pass/fail test (probably a post test) should be added to validate the KPI metrics against the KPI threshold/requirement, like this:
[validate_kpi_tests.py](https://cc-github.bmwgroup.net/idcevo/si-test-idcevo/blob/master/si_test_idcevo/si_test_package_performance/posttests/validate_kpi_tests.py)

## How to publish new metrics on Grafana using MetricLogger

[MetricLogger](https://cc-github.bmwgroup.net/node0/mtee_core/blob/master/mtee/metric/metric_logger.py) is a thin wrapper to logging module. It publishes metrics through loggers.

MetricLogger defines two loggers:``METRIC`` and ``METRIC_STRUCTURED``. ``METRIC`` logger shows human-readable messages for each metric in log output. ``METRIC_STRUCTURED`` logger shows machine-readable messages with json format for each metric in log output.

All the messages related to ``METRIC_STRUCTURED`` will be collected automatically and saved in ``metrics.json``. Then by using [MetricCollectorLogMetrics](https://cc-github.bmwgroup.net/software-factory/validation-python-metrics-collector/blob/master/metric_collector/collectors/log_metrics.py) plugin, all the metrics that are in metrics.json will be published on InfluxDB and consequently to Grafana.

However to save any metric in this file, there are some requirements to meet:
    1. The data to publish needs to be a dictionary
    2. Must have the key "name"

Example:
```
from mtee.metric import MetricLogger
metric_logger = MetricLogger()

metric_logger.publish(
    {
        "name": name,
        "kpi_name": kpi_name,
        "value": value,
    }
)
```