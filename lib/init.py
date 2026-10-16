import os
import datetime
import csv
from . import utils
from .config import RunConfig
from .config_readers import init_from_config
from . import prompt


def init(config_path, run_command, do_prompt, do_comment_prompt):
    # Parameter search chain:  passed parameter > config file parameters > default parameter > assertion error

    assert (config_path is not None or run_command is not None) and (config_path is None or run_command is None)
    assert not (do_prompt and do_comment_prompt)

    if config_path is not None:
        run_config = init_from_config(config_path)

        if do_prompt:
            prompt.meta_prompt(run_config)

        if do_comment_prompt:
            prompt.comment_only_prompt(run_config)

    elif run_command is not None:
        run_config = init_from_run_command(run_command)
        prompt.meta_prompt(run_config)
        run_config.convert_run_commands_to_rel_paths()
        run_config.convert_pre_commands_to_rel_paths()

    if not os.path.exists(run_config.meta.output_base_path):
        print("\tSkipping run, because output base path does not exist.")
        return None

    init_run_id(run_config)
    init_dirs(run_config)
    create_git_tag(run_config)

    if do_prompt:
        prompt.run_prompt(run_config)
        prompt.target_prompt(run_config)
        
    log_run(run_config)
    
    repetition_configs = init_run_repetitions(run_config)

    print()
    print("Run:")

    if len(repetition_configs) == 1:
        repetition_config = repetition_configs[0]
        init_jobs(repetition_config)
        
        print("\tRun id: %s" % repetition_config.meta.run_id)
        print("\tRun path: %s" % repetition_config.meta.run_path)
        print("\tJob path: %s" % repetition_config.jobs.dir)
        print("\tGit tag: %s" % run_config.meta.git_tag)
        print()
        
        yield repetition_config
    else:
        print("\tRun id: %s" % run_config.meta.base_run_id)
        print("\tRun base path: %s" % run_config.meta.run_base_path)
        print("\tGit tag: %s" % run_config.meta.git_tag)
        
        for rep_ctr, repetition_config in enumerate(repetition_configs):
            print()
            print("Repetition #%d:" % (rep_ctr + 1))
            print("\tRun id for repetition #%d: %s" % (rep_ctr + 1, repetition_config.meta.run_id))
            print("\tRun path for repetition #%d: %s" % (rep_ctr + 1, repetition_config.meta.run_path))

            init_jobs(repetition_config)
            print("\tJob path for repetition #%d: %s" % (rep_ctr + 1, repetition_config.jobs.dir))
            print()

            yield repetition_config


def init_from_run_command(run_command):
    if ';' in run_command:
        raise NotImplementedError('Handling of ";" in the run commands is currently not supported.')

    # Expand paths in the run command to absolute paths and then use this to find the parent git repository:
    run_command_words = run_command.split(' ')
    for word_idx, run_command_word in enumerate(run_command_words):
        
        sub_run_command_words = run_command_word.split('=')
        for sub_run_command_word_idx, sub_run_command_word in enumerate(sub_run_command_words):
            sub_run_command_word = os.path.expanduser(sub_run_command_word)
            if os.path.exists(sub_run_command_word):
                sub_run_command_words[sub_run_command_word_idx] = os.path.realpath(sub_run_command_word)
        run_command_word = '='.join(sub_run_command_words)

        run_command_words[word_idx] = run_command_word

    run_command = ' '.join(run_command_words)
    run_config = RunConfig(run_commands=run_command, pre_commands=None, init_default=True)

    # apply some heuristics to find the git path from the run commands:
    args = run_command.split(' ')

    if args[0] == 'python' or args[0] == 'python3':
        args = args[1:] + [args[0]]

    for arg in args:
        git_dir = utils.find_git(arg)
        if git_dir is not None:
            run_config.meta.git_path = git_dir
            run_config.meta.run_name = os.path.split(git_dir)[1]
            break

    return run_config


def init_run_id(config):
    run_dir_prefix = ("t_" if config.meta.is_test else "") + config.meta.run_name

    run_id = utils.get_next_dir(config.meta.data_path, run_dir_prefix)
    config.meta.run_id = run_id
    config.meta.run_base_path = os.path.join(config.meta.data_path, config.meta.base_run_id)


def init_dirs(config):
    os.makedirs(config.meta.data_path, exist_ok=True)
    utils.wait_dir_exists(config.meta.data_path)

    os.makedirs(config.meta.run_base_path, exist_ok=False)
    utils.wait_dir_exists(config.meta.run_base_path)


def create_git_tag(config):
    git_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'create_git_tag.sh')
    git_path = config.meta.git_path
    git_tag = config.meta.git_tag = "lmbrun_" + config.meta.base_dir + "_" + config.meta.base_run_id
    git_remote_url = config.meta.git_remote_url
    git_message = "Run with id {} at location {}.".format(config.meta.base_run_id, config.meta.output_base_path)

    if git_remote_url is None:
        run_str = "{} {} {} '{}'".format(git_script, git_path, git_tag, git_message)
    else:
        run_str = "{} {} {} '{}' {}".format(git_script, git_path, git_tag, git_message, git_remote_url)

    utils.run_in_shell(run_str)

    with open(os.path.join(config.meta.run_base_path, 'git_repository'), 'w') as f:
        if git_remote_url is not None:
            f.write(git_remote_url)
        else:
            f.write('file:///{}'.format(git_path))
    with open(os.path.join(config.meta.run_base_path, 'git_tag'), 'w') as f:
        f.write(git_tag)


def get_log_data(config):
    log_data = []

    log_data.append(config.meta.run_id)
    log_data.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    log_data.append(config.get_pre_commands(insert_placeholders=True, delimiter='; '))
    log_data.append(config.get_run_commands(insert_placeholders=True, delimiter='; '))
    log_data.append(config.meta.comment if config.meta.comment else "")
    log_data.append(config.meta.git_path)
    log_data.append(config.meta.git_tag)
    log_data.append(config.meta.git_remote_url)

    return log_data


def write_comment(config):
    comment_file_name = 'comment'
    with open(os.path.join(config.meta.run_base_path, comment_file_name), 'w') as f:
        f.write(config.meta.comment if config.meta.comment is not None else "")


def log_run(config):
    config_file_name = 'run_config.yaml'
    config.write_yaml(os.path.join(config.meta.run_base_path, config_file_name), general_only=True)

    write_comment(config)

    log_file_name = "tests_log.csv" if config.meta.is_test else "main_log.csv"
    log_file_path = os.path.join(config.meta.output_base_path, log_file_name)

    log_data = get_log_data(config)

    existing_logs = []
    if os.path.isfile(log_file_path):
        with open(log_file_path, 'r') as log_file:
            reader = csv.reader(log_file)
            existing_logs.extend(reader)

    append = True
    for idx, existing_log in enumerate(existing_logs):
        if existing_log[0] == log_data[0]:  # overwrite
            existing_logs[idx] = log_data
            append = False
            break

    if append:
        with open(log_file_path, 'a') as log_file:
            writer = csv.writer(log_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(log_data)
    else:
        with open(log_file_path, 'w') as log_file:
            writer = csv.writer(log_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            for log in existing_logs:
                writer.writerow(log)


def init_run_repetitions(config):
    configs = []

    for run_num in range(config.meta.number_of_runs):

        repetition_config = config.copy()

        if config.meta.number_of_runs == 1:
            run_path = os.path.join(config.meta.run_base_path, config.meta.run_id)
            run_id_with_repetition = config.meta.run_id
        else:
            run_path = os.path.join(config.meta.run_base_path, config.meta.run_id + "_" + str(run_num).zfill(2))
            run_id_with_repetition = config.meta.run_id + "_" + str(run_num).zfill(2)

        os.makedirs(run_path, exist_ok=False)
        utils.wait_dir_exists(run_path)

        repetition_config.meta.run_path = run_path
        repetition_config.meta.run_id_with_repetition = run_id_with_repetition
        repetition_config.meta.number_of_runs = 1

        configs.append(repetition_config)

    return configs


def init_jobs(config):
    config.jobs.name = config.meta.run_id
    config.jobs.dir = os.path.join(config.meta.run_path, 'jobs')

    os.makedirs(config.jobs.dir)
    utils.wait_dir_exists(config.jobs.dir)

    open(config.jobs.current_file, 'a')
    open(config.jobs.queued_file, 'a')
