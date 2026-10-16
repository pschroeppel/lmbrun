import pickle
import os
import copy
import re
import yaml
from . import utils

_user_default_config_path = os.path.join(os.path.dirname(__file__), 'user_conf.yaml')
_did_print_user_default_config_path = False


def print_user_default_config_path():
    global _did_print_user_default_config_path
    if not _did_print_user_default_config_path:
        print("Using default config values from: %s" % _user_default_config_path)
        _did_print_user_default_config_path = True


def get_default_format():
    print_user_default_config_path()

    with open(_user_default_config_path, 'r') as user_default_config_file:
        user_default_config = yaml.safe_load(user_default_config_file)
        return user_default_config['config_format']


_TARGET_LIST = [
    "local",
    "torque",
    "ssh",
    "slurm",
]


_system_config_path = os.path.join(os.path.dirname(__file__), 'system_conf.yaml')


def _load_system_config():
    if not os.path.isfile(_system_config_path):
        return {}

    with open(_system_config_path, 'r') as system_config_file:
        return yaml.safe_load(system_config_file) or {}


_system_config = _load_system_config()
_slurm_system_config = _system_config.get('slurm') or {}
_torque_system_config = _system_config.get('torque') or {}

_NODE_NAME_LIST = _torque_system_config.get('nodes') or []

_PROP_LIST = _torque_system_config.get('properties') or []

_QUEUE_LIST = _torque_system_config.get('queues') or []

_MAIL_NOTIFICATIONS_LIST = ["n", "p", "a", "b", "e", "f"]

_TORQUE_LOGIN_HOST = _torque_system_config.get('login_host')
_TORQUE_JOB_ID_REGEX = _torque_system_config.get('job_id_regex')
_TORQUE_DEFAULT_GPU_QUEUE = _torque_system_config.get('default_gpu_queue')
_TORQUE_DEFAULT_CPU_QUEUE = _torque_system_config.get('default_cpu_queue')


_SLURM_PARTITION_LIST = _slurm_system_config.get('partitions') or []

_SLURM_GRES_LIST = _slurm_system_config.get('gres') or []

_SLURM_GPU_TYPES_LIST = _slurm_system_config.get('gpu_types') or []

_SLURM_LOGIN_HOST = _slurm_system_config.get('login_host')


def check_system_config_value(value, name):
    if value is None:
        raise RuntimeError("%s is not set. Copy %s to %s and fill in the values for your system." % (
            name, os.path.join(os.path.dirname(__file__), '_system_conf.yaml'), _system_config_path))


class RunConfig:
    def __init__(self, run_commands=None, pre_commands=None, init_default=False):
        self._run_commands = None
        self._pre_commands = None

        if init_default:
            print_user_default_config_path()
            with open(_user_default_config_path, 'r') as user_default_config_file:
                user_default_config = yaml.safe_load(user_default_config_file)
                if 'run_commands' in user_default_config and user_default_config['run_commands'] is not None:
                    self.set_run_commands(user_default_config['run_commands'])
                if 'pre_commands' in user_default_config and user_default_config['pre_commands'] is not None:
                    self.set_pre_commands(user_default_config['pre_commands'])

        if run_commands is not None:
            self.set_run_commands(run_commands)

        if pre_commands is not None:
            self.set_pre_commands(pre_commands)

        self.meta = MetaConfig(init_default=init_default)
        self.target = TargetConfig(init_default=init_default)
        self.jobs = JobsConfig()

    @property
    def run_commands(self):
        return self._run_commands

    def set_run_commands(self, value):
        if isinstance(value, list) and len(value) > 0:
            run_commands = [str(x).strip() for x in value]
            run_commands = [x for x in run_commands if x != '']
            if len(run_commands) > 0:
                self._run_commands = run_commands
            else:
                self._run_commands = None
        elif isinstance(value, str):
            self.set_run_commands(value.split(';'))
        else:
            self._run_commands = None

    def set_run_commands_from_file(self, file_path):
        with open(file_path, 'r') as file:
            self._run_commands = [line for line in file.read().split('\n') if line != '']

    def get_run_commands(self, insert_placeholders=True, rel_paths=False, delimiter='\n', job_num=None):

        run_commands = self._run_commands.copy()

        if run_commands is None:
            return "" if delimiter is not None else []

        if rel_paths:
            for command_idx, run_command in enumerate(run_commands):
                run_command_words = run_command.split(' ')
                for word_idx, run_command_word in enumerate(run_command_words):
                    common_prefix = os.path.commonprefix([run_command_word, self.meta.git_path])
                    if common_prefix == self.meta.git_path:
                        run_command_word = os.path.relpath(run_command_word, self.meta.git_path)
                        run_command_words[word_idx] = run_command_word
                run_command = ' '.join(run_command_words)
                run_commands[command_idx] = run_command

        if insert_placeholders:
            logdir = self._get_logdir()

            for command_idx, run_command in enumerate(run_commands):
                splits = run_command.split("%LOGDIR%")  # %LOGDIR% is a special placeholder
                run_commands[command_idx] = logdir.join(splits)

            comment = self.meta.comment if self.meta.comment is not None else ''

            for command_idx, run_command in enumerate(run_commands):
                splits = run_command.split("%COMMENT%")  # %COMMENT% is a special placeholder
                run_commands[command_idx] = comment.join(splits)

            if self.meta.run_id is None:
                run_id = ''
            else:
                if self.meta.number_of_runs is not None and self.meta.number_of_runs > 1 and self.meta._run_id_with_repetition is None:
                    run_id = self.meta.run_id + "_[REPETITION_NUM]"  # add placeholder for the repetition number that will be added later
                else:
                    run_id = self.meta.run_id

            for command_idx, run_command in enumerate(run_commands):
                splits = run_command.split("%RUNID%")  # %RUNID% is a special placeholder
                run_commands[command_idx] = run_id.join(splits)
                
            if job_num is not None:
                for command_idx, run_command in enumerate(run_commands):
                    splits = run_command.split("%SEED%")  # %SEED% is a special placeholder
                    seed_base = self.meta.seed_base
                    cur_seed = seed_base + job_num if self.meta.increment_seed else seed_base
                    run_commands[command_idx] = str(cur_seed).join(splits)

        return delimiter.join(run_commands) if delimiter is not None else run_commands
    
    def convert_run_commands_to_rel_paths(self):
        if self._run_commands is None:
            return
        
        for command_idx, run_command in enumerate(self._run_commands):
            run_command_words = run_command.split(' ')
            for word_idx, run_command_word in enumerate(run_command_words):
                
                subcommand_words = run_command_word.split('=')
                for subcommand_idx, subcommand_word in enumerate(subcommand_words):
                    common_prefix = os.path.commonprefix([subcommand_word, self.meta.git_path])
                    if common_prefix == self.meta.git_path:
                        subcommand_word = os.path.relpath(subcommand_word, self.meta.git_path)
                        subcommand_words[subcommand_idx] = subcommand_word
                run_command_word = '='.join(subcommand_words)
                run_command_words[word_idx] = run_command_word
                    
            run_command = ' '.join(run_command_words)
            self._run_commands[command_idx] = run_command

    @property
    def pre_commands(self):
        return self._pre_commands

    def set_pre_commands(self, value):
        if isinstance(value, list) and len(value) > 0:
            pre_commands = [str(x).strip() for x in value]
            pre_commands = [x for x in pre_commands if x != '']
            if len(pre_commands) > 0:
                self._pre_commands = pre_commands
            else:
                self._pre_commands = None
        elif isinstance(value, str):
            self.set_pre_commands(value.split(';'))
        else:
            self._pre_commands = None

    def set_pre_commands_from_file(self, file_path):
        with open(file_path, 'r') as file:
            self._pre_commands = [line for line in file.read().split('\n') if line != '']

    def get_pre_commands(self, insert_placeholders=True, rel_paths=False, delimiter='\n', job_num=None):

        if self._pre_commands is None:
            return "" if delimiter is not None else []

        pre_commands = self._pre_commands.copy()

        if rel_paths:
            for command_idx, pre_command in enumerate(pre_commands):
                pre_command_words = pre_command.split(' ')
                for word_idx, pre_command_word in enumerate(pre_command_words):
                    common_prefix = os.path.commonprefix([pre_command_word, self.meta.git_path])
                    if common_prefix == self.meta.git_path:
                        pre_command_word = os.path.relpath(pre_command_word, self.meta.git_path)
                        pre_command_words[word_idx] = pre_command_word
                pre_command = ' '.join(pre_command_words)
                pre_commands[command_idx] = pre_command

        if insert_placeholders:
            logdir = self._get_logdir()

            for command_idx, pre_command in enumerate(pre_commands):
                splits = pre_command.split("%LOGDIR%")  # %LOGDIR% is a special placeholder
                pre_commands[command_idx] = logdir.join(splits)

            comment = self.meta.comment if self.meta.comment is not None else ''

            for command_idx, pre_command in enumerate(pre_commands):
                splits = pre_command.split("%COMMENT%")  # %COMMENT% is a special placeholder
                pre_commands[command_idx] = comment.join(splits)

            if self.meta.run_id is None:
                run_id = ''
            else:
                if self.meta.number_of_runs is not None and self.meta.number_of_runs > 1 and self.meta._run_id_with_repetition is None:
                    run_id = self.meta.run_id + "_[REPETITION_NUM]"  # add placeholder for the repetition number that will be added later
                else:
                    run_id = self.meta.run_id

            for command_idx, pre_command in enumerate(pre_commands):
                splits = pre_command.split("%RUNID%")  # %RUNID% is a special placeholder
                pre_commands[command_idx] = run_id.join(splits)
                
            if job_num is not None:
                for command_idx, pre_command in enumerate(pre_commands):
                    splits = pre_command.split("%SEED%")
                    seed_base = self.meta.seed_base
                    cur_seed = seed_base + job_num if self.meta.increment_seed else seed_base
                    pre_commands[command_idx] = str(cur_seed).join(splits)

        return delimiter.join(pre_commands) if delimiter is not None else pre_commands
    
    def convert_pre_commands_to_rel_paths(self):
        if self._pre_commands is None:
            return
        
        for command_idx, pre_command in enumerate(self._pre_commands):
            pre_command_words = pre_command.split(' ')
            for word_idx, pre_command_word in enumerate(pre_command_words):
                
                subcommand_words = pre_command_word.split('=')
                for subcommand_idx, subcommand_word in enumerate(subcommand_words):
                    common_prefix = os.path.commonprefix([subcommand_word, self.meta.git_path])
                    if common_prefix == self.meta.git_path:
                        subcommand_word = os.path.relpath(subcommand_word, self.meta.git_path)
                        subcommand_words[subcommand_idx] = subcommand_word
                pre_command_word = '='.join(subcommand_words)
                pre_command_words[word_idx] = pre_command_word
                
            pre_command = ' '.join(pre_command_words)
            self._pre_commands[command_idx] = pre_command

    def update_from(self, run_config):
        self.meta.update_from(run_config.meta)
        self.target.update_from(run_config.target)
        self.jobs.update_from(run_config.jobs)

        self._run_commands = run_config.run_commands if run_config.run_commands is not None else self._run_commands
        self._pre_commands = run_config.pre_commands if run_config.pre_commands is not None else self._pre_commands

    def copy(self):
        return copy.deepcopy(self)

    def to_dict(self, general_only=False):
        meta_dict = self.meta.to_dict(general_only=general_only)
        target_dict = self.target.to_dict(general_only=general_only)

        config_dict = {'meta': meta_dict,
                       'target': target_dict,
                       'run_commands': self._run_commands,
                       'pre_commands': self._pre_commands}

        if not general_only:
            config_dict['jobs'] = self.jobs.to_dict()

        return config_dict

    def write_yaml(self, path, general_only=False):
        data = self.to_dict(general_only=general_only)
        data['format'] = 'single_run'
        with open(path, 'w') as yamlfile:
            yaml.dump(data, yamlfile, default_flow_style=False)

    def write(self, path):
        with open(path, 'wb') as file:
            pickle.dump(self, file)

    def _get_logdir(self):
        if self.meta.run_path is None and self.meta.run_base_path is not None:
            logdir = self.meta.run_base_path + '/[RUN_ID]'
        else:
            logdir = self.meta.run_path

        return logdir


class MetaConfig:
    def __init__(self, init_default=False):
        self._output_base_path = None
        self.user_name = None
        self.is_test = None
        self.comment = None
        self.number_of_runs = None  # number of runs (with identical parameters)

        self.run_name = None
        self._git_path = None  # path to .git of the project
        self.git_remote_url = None  # url of the git remote repository where the commit should be pushed to

        self._run_id = None
        self._run_id_with_repetition = None
        self.run_base_path = None
        self.run_path = None
        self.git_tag = None
        
        self.increment_seed = None
        self.seed_base = None

        # if you add a new attribute here, make sure to also add it in from_dict()

        if init_default:
            self.init_default()

    def init_default(self):
        print_user_default_config_path()
        with open(_user_default_config_path, 'r') as user_default_config_file:
            user_default_config = yaml.safe_load(user_default_config_file)

            if 'meta' in user_default_config:
                self.from_dict(user_default_config['meta'])

    @property
    def output_base_path(self):
        return self._output_base_path

    @output_base_path.setter
    def output_base_path(self, value):
        if value.endswith('/'):
            value = value[:-1]  # remove trailing slash

        self._output_base_path = value

    @property
    def base_dir(self):
        return os.path.split(self.output_base_path)[1]

    @property
    def git_path(self):
        return self._git_path

    @git_path.setter
    def git_path(self, value):
        parent, child = os.path.split(value)
        if child == '.git': 
            self._git_path = parent
        else:
            self._git_path = value

    @property
    def data_path(self):
        if self.is_test:
            return os.path.join(self.output_base_path, 'test')
        else:
            return os.path.join(self.output_base_path, 'data')
        
    @property
    def run_id(self):
        return self._run_id_with_repetition if self._run_id_with_repetition is not None else self._run_id
    
    @property
    def base_run_id(self):
        return self._run_id
    
    @property
    def run_id_with_repetition(self):
        return self._run_id_with_repetition
    
    @run_id.setter
    def run_id(self, value):
        self._run_id = value
        
    @run_id_with_repetition.setter
    def run_id_with_repetition(self, value):
        self._run_id_with_repetition = value

    def to_dict(self, general_only=False):
        out_dict = vars(self).copy()
        out_dict['git_path'] = out_dict.pop('_git_path')
        out_dict['output_base_path'] = out_dict.pop('_output_base_path')
        out_dict['run_id'] = out_dict.pop('_run_id')
        out_dict['run_id_with_repetition'] = out_dict.pop('_run_id_with_repetition')

        if general_only:
            out_dict.pop('run_id', None)
            out_dict.pop('run_id_with_repetition', None)
            out_dict.pop('run_base_path', None)
            out_dict.pop('run_path', None)
            out_dict.pop('git_tag', None)

        return out_dict

    def from_dict(self, config_dict, general_only=False):
        if 'output_base_path' in config_dict and config_dict['output_base_path'] is not None:
            self.output_base_path = str(config_dict['output_base_path'])

        if 'user_name' in config_dict and config_dict['user_name'] is not None:
            self.user_name = str(config_dict['user_name'])

        if 'is_test' in config_dict and config_dict['is_test'] is not None:
            self.is_test = bool(config_dict['is_test'])

        if 'comment' in config_dict and config_dict['comment'] is not None:
            self.comment = str(config_dict['comment'])

        if 'number_of_runs' in config_dict and config_dict['number_of_runs'] is not None:
            self.number_of_runs = int(config_dict['number_of_runs'])

        if 'run_name' in config_dict and config_dict['run_name'] is not None:
            self.run_name = str(config_dict['run_name'])

        if 'git_path' in config_dict and config_dict['git_path'] is not None:
            self.git_path = str(config_dict['git_path'])

        if 'git_remote_url' in config_dict and config_dict['git_remote_url'] is not None:
            self.git_remote_url = str(config_dict['git_remote_url'])
            
        if 'increment_seed' in config_dict and config_dict['increment_seed'] is not None:
            self.increment_seed = bool(config_dict['increment_seed'])
            
        if 'seed_base' in config_dict and config_dict['seed_base'] is not None:
            self.seed_base = int(config_dict['seed_base'])

        if not general_only:
            if 'run_id' in config_dict and config_dict['run_id'] is not None:
                self._run_id = str(config_dict['run_id'])

            if 'run_id_with_repetition' in config_dict and config_dict['run_id_with_repetition'] is not None:
                self._run_id_with_repetition = str(config_dict['run_id_with_repetition'])

            if 'run_base_path' in config_dict and config_dict['run_base_path'] is not None:
                self.run_base_path = str(config_dict['run_base_path'])

            if 'run_path' in config_dict and config_dict['run_path'] is not None:
                self.run_path = str(config_dict['run_path'])

            if 'git_tag' in config_dict and config_dict['git_tag'] is not None:
                self.git_tag = str(config_dict['git_tag'])

    def update_from(self, meta_config):
        self.from_dict(meta_config.to_dict())


class TargetConfig:
    def __init__(self, init_default=False):
        self._which = None
        self.torque = TorqueConfig(init_default=False)
        self.ssh = SSHConfig(init_default=False)
        self.slurm = SlurmConfig(init_default=False)

        if init_default:
            self.init_default()

    def init_default(self):
        with open(_user_default_config_path, 'r') as user_default_config_file:
            user_default_config = yaml.safe_load(user_default_config_file)
            if 'target' in user_default_config:
                self.from_dict(user_default_config['target'])

    @property
    def which(self):
        return self._which

    @which.setter
    def which(self, value):
        value = value.lower()
        assert value in _TARGET_LIST, "Valid arguments for the target are: {}.".format(str(_TARGET_LIST))
        self._which = value

    def to_dict(self, general_only=False):
        out_dict = {
            'which': self.which,
            'torque': self.torque.to_dict(general_only=general_only),
            'slurm': self.slurm.to_dict(general_only=general_only),
            'ssh': self.ssh.to_dict(general_only=general_only),
        }
        return out_dict

    def from_dict(self, config_dict):
        if 'which' in config_dict and config_dict['which'] is not None:
            self.which = str(config_dict['which'])
        if 'torque' in config_dict and config_dict['torque'] is not None:
            self.torque.from_dict(config_dict['torque'])
        if 'ssh' in config_dict and config_dict['ssh'] is not None:
            self.ssh.from_dict(config_dict['ssh'])
        if 'slurm' in config_dict and config_dict['slurm'] is not None:
            self.slurm.from_dict(config_dict['slurm'])

    def update_from(self, target_config):
        self.from_dict(target_config.to_dict())


class TorqueConfig:
    def __init__(self, init_default=False):
        self.user_name = None
        self._hostlist = None  # list of strings
        self.ppn = None  # int
        self.gpus = None  # int
        self.mem = None  # string, format '10gb'
        self.nodes = None  # int
        self.walltime = None  # string, format '24:00:00'
        self.job_chain_length = None  # int
        self._properties = None  # list of strings
        self._mail_notifications = None  # list of strings of len 1
        self._queue = None  # string

        # if you add a new attribute here, make sure to also add it in from_dict()

        if init_default:
            self.init_default()

    def init_default(self):
        with open(_user_default_config_path, 'r') as user_default_config_file:
            user_default_config = yaml.safe_load(user_default_config_file)
            if 'torque' in user_default_config:
                self.from_dict(user_default_config['torque'])

    @property
    def hostlist(self):
        return self._hostlist

    @hostlist.setter
    def hostlist(self, value):
        if isinstance(value, list) and len(value) > 0:
            hostlist = [str(host).strip() for host in value]
            hostlist = [host for host in hostlist if not utils.is_int(host)]
            hostlist = [host for host in hostlist if host in _NODE_NAME_LIST]
            if len(hostlist) > 0:
                self._hostlist = hostlist
            else:
                self._hostlist = None
        elif isinstance(value, str):
            self.hostlist = re.findall(r"\w+", value)  # call setter again
        else:
            self._hostlist = None

    @property
    def properties(self):
        return self._properties

    @properties.setter
    def properties(self, value):
        if isinstance(value, list) and len(value) > 0:
            properties = [str(prop).strip() for prop in value]
            properties = [prop for prop in properties if not utils.is_int(prop)]
            properties = [prop for prop in properties if prop in _PROP_LIST]
            if len(properties) > 0:
                self._properties = properties
            else:
                self._properties = None
        elif isinstance(value, str):
            self.properties = re.findall(r"\w+", value)  # call setter again
        else:
            self._properties = None

    @property
    def mail_notifications(self):
        return self._mail_notifications

    @mail_notifications.setter
    def mail_notifications(self, value):
        if isinstance(value, list) and len(value) > 0:
            mail_notifications = [str(notification).strip() for notification in value]
            mail_notifications = [notification for notification in mail_notifications if not utils.is_int(notification)]
            mail_notifications = [notification for notification in mail_notifications if notification in _MAIL_NOTIFICATIONS_LIST]
            if len(mail_notifications) > 0:
                self._mail_notifications = mail_notifications
            else:
                self._mail_notifications = None
        elif isinstance(value, str):
            list_from_str = re.findall(r"\w+", value)

            if len(list_from_str) == 1:
                list_from_str = list(list_from_str[0])  # take the only str from the list and create new list by splitting it into characters

            self.mail_notifications = list_from_str  # call setter again
        else:
            self._mail_notifications = None

    @property
    def queue(self):
        return self._queue

    @queue.setter
    def queue(self, value):
        if value in _QUEUE_LIST:
            self._queue = value
        else:
            self._queue = None

    def to_dict(self, general_only=False):
        out_dict = vars(self).copy()
        out_dict['hostlist'] = out_dict.pop('_hostlist')
        out_dict['properties'] = out_dict.pop('_properties')
        out_dict['mail_notifications'] = out_dict.pop('_mail_notifications')
        out_dict['queue'] = out_dict.pop('_queue')
        return out_dict

    def from_dict(self, config_dict):
        if 'user_name' in config_dict and config_dict['user_name'] is not None:
            self.user_name = str(config_dict['user_name'])

        if 'hostlist' in config_dict and config_dict['hostlist'] is not None and config_dict['hostlist'] != []:
            self.hostlist = config_dict['hostlist']

        if 'ppn' in config_dict and config_dict['ppn'] is not None:
            self.ppn = int(config_dict['ppn'])

        if 'gpus' in config_dict and config_dict['gpus'] is not None:
            self.gpus = int(config_dict['gpus'])

        if 'mem' in config_dict and config_dict['mem'] is not None:
            self.mem = str(config_dict['mem'])

        if 'nodes' in config_dict and config_dict['nodes'] is not None:
            self.nodes = int(config_dict['nodes'])

        if 'walltime' in config_dict and config_dict['walltime'] is not None:
            self.walltime = str(config_dict['walltime'])

        if 'job_chain_length' in config_dict and config_dict['job_chain_length'] is not None:
            self.job_chain_length = int(config_dict['job_chain_length'])

        if 'properties' in config_dict and config_dict['properties'] is not None and config_dict['properties'] != []:
            self.properties = config_dict['properties']

        if 'mail_notifications' in config_dict and config_dict['mail_notifications'] is not None and config_dict['mail_notifications'] != []:
            self.mail_notifications = config_dict['mail_notifications']

        if 'queue' in config_dict and config_dict['queue'] is not None:
            self.queue = config_dict['queue']

    def update_from(self, torque_config):
        self.from_dict(torque_config.to_dict())


class SSHConfig:
    def __init__(self, init_default=False):
        self._connect_string = None

        # if you add a new attribute here, make sure to also add it in from_dict()

        if init_default:
            self.init_default()

    @property
    def connect_string(self):
        return self._connect_string

    @connect_string.setter
    def connect_string(self, value):
        self._connect_string = value.strip()

    def init_default(self):
        with open(_user_default_config_path, 'r') as user_default_config_file:
            user_default_config = yaml.safe_load(user_default_config_file)
            if 'ssh' in user_default_config:
                self.from_dict(user_default_config['ssh'])

    def to_dict(self, general_only=False):
        out_dict = vars(self).copy()
        out_dict['connect_string'] = out_dict.pop('_connect_string')
        return out_dict

    def from_dict(self, config_dict):
        if 'connect_string' in config_dict and config_dict['connect_string'] is not None:
            self.connect_string = str(config_dict['connect_string'])

    def update_from(self, ssh_config):
        self.from_dict(ssh_config.to_dict())
        
        
class SlurmConfig:
    def __init__(self, init_default=False):
        self.user_name = None
        self._partitions = None  # list of strings
        self.num_gpus = None  # int
        self._gpu_type = None  # string
        self.cpus_per_gpu = None  # int
        self.mem = None  # string, format '10gb'
        self.walltime_hrs = None  # string, format 24
        self.signal_str = None  # string, format: see sbatch manpage for --signal parameter (e.g. B:TERM@600)
        self._additional_gres = None  # list of strings
        self._nodelist = None  # list of strings
        self._exclude_nodelist = None  # list of strings
        self.nice = None  # int, higher values mean lower priority
        self.job_chain_length = None  # int

        # if you add a new attribute here, make sure to also add it in from_dict()

        if init_default:
            self.init_default()

    def init_default(self):
        with open(_user_default_config_path, 'r') as user_default_config_file:
            user_default_config = yaml.safe_load(user_default_config_file)
            if 'slurm' in user_default_config:
                self.from_dict(user_default_config['slurm'])

    @property
    def partitions(self):
        return self._partitions

    @partitions.setter
    def partitions(self, value):
        if isinstance(value, list) and len(value) > 0:
            partitions = [str(partition).strip() for partition in value]
            partitions = [partition for partition in partitions if not utils.is_int(partition)]
            partitions = [partition for partition in partitions if partition in _SLURM_PARTITION_LIST]
            if len(partitions) > 0:
                self._partitions = partitions
            else:
                self._partitions = None
        elif isinstance(value, str):
            self.partitions = re.findall(r"[\w-]+", value)  # call setter again
        else:
            self._partitions = None

    @property
    def additional_gres(self):
        return self._additional_gres

    @additional_gres.setter
    def additional_gres(self, value):
        if isinstance(value, list) and len(value) > 0:
            additional_gres = [str(gres).strip() for gres in value]
            additional_gres = [gres for gres in additional_gres if utils.is_int(gres.split(':')[1])]
            additional_gres = [gres for gres in additional_gres if gres.split(':')[0] in _SLURM_GRES_LIST]
            if len(additional_gres) > 0:
                self._additional_gres = additional_gres
            else:
                self._additional_gres = None
        elif isinstance(value, str):
            self.additional_gres = re.findall(r"\b\w+:\d+\b", value)  # matches all key:count pairs and calls setter again
        else:
            self._additional_gres = None

    @property
    def gpu_type(self):
        return self._gpu_type

    @gpu_type.setter
    def gpu_type(self, value):
        if value in _SLURM_GPU_TYPES_LIST:
            self._gpu_type = value
        else:
            self._gpu_type = None

    @property
    def nodelist(self):
        return self._nodelist

    @nodelist.setter
    def nodelist(self, value):
        if isinstance(value, list) and len(value) > 0:
            nodelist = [str(node).strip() for node in value]
            nodelist = [node for node in nodelist if not utils.is_int(node)]
            nodelist = [node for node in nodelist if node != '']
            if len(nodelist) > 0:
                self._nodelist = nodelist
            else:
                self._nodelist = None
        elif isinstance(value, str):
            self.nodelist = re.findall(r"[\w-]+", value)  # call setter again
        else:
            self._nodelist = None

    @property
    def exclude_nodelist(self):
        return self._exclude_nodelist

    @exclude_nodelist.setter
    def exclude_nodelist(self, value):
        if isinstance(value, list) and len(value) > 0:
            exclude_nodelist = [str(node).strip() for node in value]
            exclude_nodelist = [node for node in exclude_nodelist if not utils.is_int(node)]
            exclude_nodelist = [node for node in exclude_nodelist if node != '']
            if len(exclude_nodelist) > 0:
                self._exclude_nodelist = exclude_nodelist
            else:
                self._exclude_nodelist = None
        elif isinstance(value, str):
            self.exclude_nodelist = re.findall(r"[\w-]+", value)  # call setter again
        else:
            self._exclude_nodelist = None

    def to_dict(self, general_only=False):
        out_dict = vars(self).copy()
        out_dict['partitions'] = out_dict.pop('_partitions')
        out_dict['additional_gres'] = out_dict.pop('_additional_gres')
        out_dict['gpu_type'] = out_dict.pop('_gpu_type')
        out_dict['nodelist'] = out_dict.pop('_nodelist')
        out_dict['exclude_nodelist'] = out_dict.pop('_exclude_nodelist')
        return out_dict

    def from_dict(self, config_dict):
        if 'user_name' in config_dict and config_dict['user_name'] is not None:
            self.user_name = str(config_dict['user_name'])

        if 'partitions' in config_dict and config_dict['partitions'] is not None and config_dict['partitions'] != []:
            self.partitions = config_dict['partitions']

        if 'num_gpus' in config_dict and config_dict['num_gpus'] is not None:
            self.num_gpus = int(config_dict['num_gpus'])

        if 'gpu_type' in config_dict and config_dict['gpu_type'] is not None:
            self.gpu_type = config_dict['gpu_type']

        if 'cpus_per_gpu' in config_dict and config_dict['cpus_per_gpu'] is not None:
            self.cpus_per_gpu = int(config_dict['cpus_per_gpu'])

        if 'mem' in config_dict and config_dict['mem'] is not None:
            self.mem = str(config_dict['mem'])

        if 'walltime_hrs' in config_dict and config_dict['walltime_hrs'] is not None:
            self.walltime_hrs = str(config_dict['walltime_hrs'])
            
        if 'signal_str' in config_dict and config_dict['signal_str'] is not None:
            self.signal_str = str(config_dict['signal_str'])

        if 'additional_gres' in config_dict and config_dict['additional_gres'] is not None and config_dict['additional_gres'] != []:
            self.additional_gres = config_dict['additional_gres']

        if 'nodelist' in config_dict and config_dict['nodelist'] is not None and config_dict['nodelist'] != []:
            self.nodelist = config_dict['nodelist']

        if 'exclude_nodelist' in config_dict and config_dict['exclude_nodelist'] is not None and config_dict['exclude_nodelist'] != []:
            self.exclude_nodelist = config_dict['exclude_nodelist']

        if 'nice' in config_dict and config_dict['nice'] is not None:
            self.nice = int(config_dict['nice'])

        if 'job_chain_length' in config_dict and config_dict['job_chain_length'] is not None:
            self.job_chain_length = int(config_dict['job_chain_length'])

    def update_from(self, slurm_config):
        self.from_dict(slurm_config.to_dict())


class JobsConfig:
    def __init__(self):
        self.name = None
        self.dir = None

        # if you add a new attribute here, make sure to also add it in from_dict()

    @property
    def current_file(self):
        return os.path.join(self.dir, 'current')

    @property
    def queued_file(self):
        return os.path.join(self.dir, 'queue')

    def to_dict(self):
        out_dict = vars(self).copy()
        return out_dict

    def from_dict(self, config_dict):
        if 'name' in config_dict and config_dict['name'] is not None:
            self.name = str(config_dict['name'])

        if 'dir' in config_dict and config_dict['dir'] is not None:
            self.dir = str(config_dict['dir'])

    def update_from(self, jobs_config):
        self.from_dict(jobs_config.to_dict())
