import logging
from collections.abc import Iterable

from taro import cfg, util, paths
from taro.cfg import LogMode

LOG_MODE = 'log.mode'
LOG_STDOUT_LEVEL = 'log.stdout.level'
LOG_FILE_LEVEL = 'log.file.level'
LOG_FILE_PATH = 'log.file.path'
PERSISTENCE_ENABLED = 'persistence.enabled'
PERSISTENCE_TYPE = 'persistence.type'
PERSISTENCE_MAX_AGE = 'persistence.max_age'
PERSISTENCE_MAX_RECORDS = 'persistence.max_records'
PERSISTENCE_DATABASE = 'persistence.database'
PLUGINS = 'plugins'
DEFAULT_ACTION = 'default_action'

log = logging.getLogger(__name__)


def load(config=None):
    config_path = util.expand_user(config) if config else paths.lookup_config_file()
    cns = util.read_yaml_file(config_path)
    log.debug("event=[config_file_loaded] path=[%s] content=[%s]", config_path, cns)

    cfg.log_mode = LogMode.from_value(cns.get(LOG_MODE, default=cfg.log_mode))
    cfg.log_stdout_level = cns.get(LOG_STDOUT_LEVEL, default=cfg.log_stdout_level, type_=str).lower()
    cfg.log_file_level = cns.get(LOG_FILE_LEVEL, default=cfg.log_file_level, type_=str).lower()
    cfg.log_file_path = cns.get(LOG_FILE_PATH, default=cfg.log_file_path, type_=str)

    cfg.persistence_enabled = cns.get(PERSISTENCE_ENABLED, default=cfg.persistence_enabled, type_=bool)
    cfg.persistence_type = cns.get(PERSISTENCE_TYPE, default=cfg.persistence_type, type_=str)
    cfg.persistence_max_age = cns.get(PERSISTENCE_MAX_AGE, default=cfg.persistence_max_age, type_=str).upper()
    cfg.persistence_max_records = cns.get(PERSISTENCE_MAX_RECORDS, default=cfg.persistence_max_records, type_=int)
    cfg.persistence_database = cns.get(PERSISTENCE_DATABASE, default=cfg.persistence_database, type_=str)

    cfg.default_action = cns.get(DEFAULT_ACTION, default=cfg.default_action, type_=str)

    plugins = cns.get(PLUGINS)
    if isinstance(plugins, str):
        cfg.plugins = (plugins,)
    elif isinstance(plugins, Iterable):
        cfg.plugins = tuple(plugins)


def copy_default_file_to_search_path(overwrite: bool):
    cfg_to_copy = paths.default_config_file_path()
    # Copy to first dir in search path
    copy_to = paths.config_file_search_path(exclude_cwd=True)[0] / paths.CONFIG_FILE
    util.copy_resource(cfg_to_copy, copy_to, overwrite)
