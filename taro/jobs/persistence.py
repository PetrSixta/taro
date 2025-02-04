import importlib
import pkgutil
import sys
from enum import Enum

import taro.jobs.db
from taro import cfg
from taro import paths
from taro import util
from taro.jobs.execution import ExecutionState


def is_enabled():
    return cfg.persistence_enabled


def _load_persistence(type_):
    if not cfg.persistence_enabled:
        return NoPersistence()

    for finder, name, is_pkg in pkgutil.iter_modules(taro.jobs.db.__path__, taro.jobs.db.__name__ + "."):
        if name == taro.jobs.db.__name__ + "." + type_:
            db_module = importlib.import_module(name)
            return db_module.create_persistence()

    raise PersistenceNotFoundError(taro.jobs.db.__name__ + "." + type_)


class PersistenceHolder(dict):

    def __missing__(self, key):
        self.close()

        new_instance = _load_persistence(key)
        self[key] = new_instance
        return new_instance

    def close(self):
        for instance in self.values():
            instance.close()
        self.clear()


_persistence = PersistenceHolder()


def _instance():
    return _persistence[cfg.persistence_type]


class SortCriteria(Enum):
    CREATED = 1
    FINISHED = 2
    TIME = 3


def read_jobs(*, id_=None, sort=SortCriteria.CREATED, asc=False, limit=-1, last=False):
    return _instance().read_jobs(id_=id_, sort=sort, asc=asc, limit=limit, last=last)


def num_of_job(id_):
    return len(_instance().read_jobs(id_=id_, sort=SortCriteria.CREATED, asc=False, limit=-1, last=False))


def store_job(job_info):
    _instance().store_job(job_info)
    clean_up()


def remove_job(id_):
    _instance().remove_job(id_=id_)


def clean_up():
    try:
        max_age = util.parse_iso8601_duration(cfg.persistence_max_age) if cfg.persistence_max_age else None
    except ValueError:
        sys.stderr.write("Invalid max_age in " + str(paths.lookup_config_file()) + "\n")
        return
    _instance().clean_up(cfg.persistence_max_records, max_age)


def close():
    _persistence.close()


def _sort_key(sort: SortCriteria):
    def key(j):
        if sort == SortCriteria.CREATED:
            return j.lifecycle.changed(ExecutionState.CREATED)
        if sort == SortCriteria.FINISHED:
            return j.lifecycle.execution_finished()
        if sort == SortCriteria.TIME:
            return j.lifecycle.execution_time()
        raise ValueError(sort)

    return key


class NoPersistence:

    def read_jobs(self, *, id_=None, sort, asc, limit):
        raise PersistenceDisabledError()

    def store_job(self, job_info):
        raise PersistenceDisabledError()

    def remove_job(self, id_):
        raise PersistenceDisabledError()

    def clean_up(self):
        raise PersistenceDisabledError()

    def close(self):
        pass


class PersistenceError(Exception):
    pass


class PersistenceNotFoundError(PersistenceError):

    def __init__(self, module_):
        super().__init__(f'Cannot find persistence module {module_}. Ensure the module is installed '
                         f'or check that persistence type value in the config is correct.')


class PersistenceDisabledError(PersistenceError):

    def __init__(self):
        super().__init__('Executed logic depends on data persistence; however, persistence is disabled in the config.')
