# Architecture of Taro

## Components

### Configuration File

Config file [taro.yaml](../taro/config/taro.yaml) is shared with all other [components](#components).

### Package jobs

This is the main component of taro. This package provides functionality for executing and managing jobs.

#### Main parts

##### Module [runner](../taro/jobs/runner.py)

This module runs jobs and controls their execution.

##### Module [managed](../taro/jobs/managed.py)

Creates an infrastructure for managing and monitoring jobs from plugins and external applications.

##### Database accessed by [db](../taro/jobs/db) module

This is where data about finished jobs is stored.

#### Log file

Executions of all jobs are logged into a single log file (if enabled).

#### Plugin infrastructure

Job execution can be extended by self-discoverable plugins.

### Package [client](../taro/client)

Client connects to running job instances for requesting data or sending commands.

### Package [listening](../taro/listening)

Contains server components which receive events from running job instances. These components are used for monitoring.