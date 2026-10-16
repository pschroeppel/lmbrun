import yaml

from . import utils
from .config import RunConfig, get_default_format


def init_from_config(config_path):
    if utils.get_extension(config_path) == '.yaml':
        return init_from_yaml(config_path)

    # add more config file types here if needed


def init_from_yaml(yaml_path):
    with open(yaml_path, 'r') as yaml_file:
        config_dict = yaml.safe_load(yaml_file)

        config_dict_format = config_dict['format'] if 'format' in config_dict else get_default_format()

        if config_dict_format == 'default':
            return init_from_dict_default_format(config_dict)


def init_from_dict_default_format(config_dict):
    run_commands = config_dict['run_commands']
    pre_commands = config_dict['pre_commands'] if 'pre_commands' in config_dict else None
    run_config = RunConfig(run_commands=run_commands, pre_commands=pre_commands, init_default=True)

    if 'meta' in config_dict:
        run_config.meta.from_dict(config_dict['meta'], general_only=True)
    if 'target' in config_dict:
        run_config.target.from_dict(config_dict['target'])

    return run_config
