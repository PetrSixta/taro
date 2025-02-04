import os

import sys

import taro
from taro import util, paths, cfgfile
from taro.jobs.persistence import PersistenceDisabledError
from taroapp import cmd, cli


def main_cli():
    main(None)


def main(args):
    """Taro CLI app main function.

    Note: Configuration is setup before execution of all commands although not all commands require it.
          This practice increases safety (in regards with future extensions) and consistency.
          Performance impact is expected to be negligible.

    :param args: CLI arguments
    """
    if not args and not len(sys.argv) > 1:
        args = taro.cfg.default_action.split(" ")
    taro.auto_init()
    args_parsed = cli.parse_args(args)

    if args_parsed.no_color or 'NO_COLOR' in os.environ or 'TARO_NO_COLOR' in os.environ:
        os.environ['PROMPT_TOOLKIT_COLOR_DEPTH'] = 'DEPTH_1_BIT'

    if args_parsed.action == 'config':
        run_config(args_parsed)
    else:
        init_taro(args_parsed)
        run_command(args_parsed)


def run_config(args):
    if args.config_action == cli.ACTION_CONFIG_SHOW:
        if getattr(args, 'def_config', False):
            util.print_file(paths.default_config_file_path())
        else:
            util.print_file(paths.lookup_config_file())
    elif args.config_action == cli.ACTION_CONFIG_CREATE:
        cfgfile.copy_default_file_to_search_path(args.overwrite)
    elif args.config_action == cli.ACTION_CONFIG_RESET:
        cfgfile.copy_default_file_to_search_path(True)

def init_taro(args):
    """Initialize taro according to provided CLI arguments

    :param args: CLI arguments
    """
    config_vars = util.split_params(args.set) if args.set else {}  # Config variables and override values

    if getattr(args, 'config', None):
        taro.load_config(args.config, **config_vars)
    elif getattr(args, 'def_config', False):
        taro.load_defaults(**config_vars)
    elif getattr(args, 'min_config', False):
        taro.setup(**config_vars)
    else:
        taro.load_config(**config_vars)


def run_command(args_ns):
    try:
        cmd.run(args_ns)
    except PersistenceDisabledError:
        print('This command cannot be executed with disabled persistence. Enable persistence in config file first.',
              file=sys.stderr)
    finally:
        taro.close()
