import os, re, sys, time

from prompt_toolkit import prompt
from prompt_toolkit.validation import Validator, ValidationError
from prompt_toolkit.completion import WordCompleter, PathCompleter
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from . import utils
from .config import _NODE_NAME_LIST, _PROP_LIST, _QUEUE_LIST, _MAIL_NOTIFICATIONS_LIST, _TARGET_LIST
from .config import _SLURM_PARTITION_LIST, _SLURM_GPU_TYPES_LIST, _SLURM_GRES_LIST

# heavily based on tfrun (from Benjamin Ummenhofer)


def target_prompt(config):
    print('Enter target:')

    target_questions = (
        enter_which_target,
    )

    question_idx = 0
    lines_per_question = []
    while question_idx < len(target_questions):
        try:
            terminal_lines_used = target_questions[question_idx](config)
            if terminal_lines_used is None:
                terminal_lines_used = 1
            lines_per_question.append(terminal_lines_used)
            question_idx += 1

            if question_idx >= len(target_questions):
                lines_per_question[-1] = 0
                # give user 1 sec to react after the last question
                print('.' * 10, flush=True, end='\r')
                for i in range(10):
                    time.sleep(0.1);
                    print(' ', flush=True, end='')
                print()

        except KeyboardInterrupt as e:
            question_idx -= 1

            if question_idx < 0:
                print('cancelled')
                sys.exit(0)
            else:
                CLEAR_SCREEN_BELOW_CURSOR = '\x1b[0J'
                CURSOR_UP_ONE = '\x1b[1A'
                ERASE_LINE = '\x1b[2K'
                for i in range(lines_per_question.pop()):
                    print(CURSOR_UP_ONE, end='')
                print(CURSOR_UP_ONE + CLEAR_SCREEN_BELOW_CURSOR + ERASE_LINE, end='\r')

    which_prompt = globals()[config.target.which + "_prompt"]
    which_prompt(config)


def local_prompt(config):
    pass


def ssh_prompt(config):
    print('Enter ssh parameters:')

    ssh_questions = (
        enter_connect_string,
    )

    question_idx = 0
    lines_per_question = []
    while question_idx < len(ssh_questions):
        try:
            terminal_lines_used = ssh_questions[question_idx](config)
            if terminal_lines_used is None:
                terminal_lines_used = 1
            lines_per_question.append(terminal_lines_used)
            question_idx += 1

            if question_idx >= len(ssh_questions):
                lines_per_question[-1] = 0
                # give user 1 sec to react after the last question
                print('.' * 10, flush=True, end='\r')
                for i in range(10):
                    time.sleep(0.1);
                    print(' ', flush=True, end='')
                print()

        except KeyboardInterrupt as e:
            question_idx -= 1

            if question_idx < 0:
                print('cancelled')
                sys.exit(0)
            else:
                CLEAR_SCREEN_BELOW_CURSOR = '\x1b[0J'
                CURSOR_UP_ONE = '\x1b[1A'
                ERASE_LINE = '\x1b[2K'
                for i in range(lines_per_question.pop()):
                    print(CURSOR_UP_ONE, end='')
                print(CURSOR_UP_ONE + CLEAR_SCREEN_BELOW_CURSOR + ERASE_LINE, end='\r')


def torque_prompt(config):
    print('Enter torque parameters:')

    target_questions = (  # if you change sth here, make sure to adapt the question_idx constants below!
        enter_torque_user_name,
        enter_nodes,
        enter_ppn,
        enter_gpus,
        enter_properties,
        enter_mem,
        enter_walltime,
        enter_hostlist,
        enter_mail_notifications,
        enter_queue,
        enter_job_chain_length,
    )

    enter_properties_index = 4
    enter_hostlist_index = 7

    question_idx = 0
    lines_per_question = []
    while question_idx < len(target_questions):
        try:
            terminal_lines_used = target_questions[question_idx](config)
            if terminal_lines_used is None:
                terminal_lines_used = 1
            if question_idx == enter_hostlist_index or question_idx == enter_properties_index:
                terminal_lines_used += 1
            lines_per_question.append(terminal_lines_used)
            question_idx += 1

            if question_idx >= len(target_questions):
                lines_per_question[-1] = 0
                # give user 1 sec to react after the last question
                print('.' * 10, flush=True, end='\r')
                for i in range(10):
                    time.sleep(0.1);
                    print(' ', flush=True, end='')
                print()

        except KeyboardInterrupt as e:
            question_idx -= 1

            if question_idx < 0:
                print('cancelled')
                sys.exit(0)
            else:
                CLEAR_SCREEN_BELOW_CURSOR = '\x1b[0J'
                CURSOR_UP_ONE = '\x1b[1A'
                ERASE_LINE = '\x1b[2K'
                for i in range(lines_per_question.pop()):
                    print(CURSOR_UP_ONE, end='')
                print(CURSOR_UP_ONE + CLEAR_SCREEN_BELOW_CURSOR + ERASE_LINE, end='\r')
                
                
def slurm_prompt(config):
    print('Enter SLURM parameters:')

    target_questions = (  # if you change sth here, make sure to adapt the question_idx constants below!
        enter_slurm_user_name,
        enter_slurm_partitions,
        enter_slurm_num_gpus,
        enter_slurm_gpu_type,
        enter_slurm_cpus_per_gpu,
        enter_slurm_mem,
        enter_slurm_walltime_hrs,
        enter_slurm_signal_str,
        enter_slurm_additional_gres,
        enter_slurm_nodelist,
        enter_slurm_exclude_nodelist,
        enter_slurm_nice,
        enter_slurm_job_chain_length,
    )

    enter_partitions_index = 1
    enter_gpu_type_index = 3
    enter_additional_gres_index = 8
    enter_nodelist_index = 9
    enter_exclude_nodelist_index = 10

    question_idx = 0
    lines_per_question = []
    while question_idx < len(target_questions):
        try:
            terminal_lines_used = target_questions[question_idx](config)
            if terminal_lines_used is None:
                terminal_lines_used = 1
            if question_idx == enter_additional_gres_index or question_idx == enter_partitions_index or question_idx == enter_gpu_type_index or question_idx == enter_nodelist_index or question_idx == enter_exclude_nodelist_index:
                terminal_lines_used += 1
            lines_per_question.append(terminal_lines_used)
            question_idx += 1

            if question_idx >= len(target_questions):
                lines_per_question[-1] = 0
                # give user 1 sec to react after the last question
                print('.' * 10, flush=True, end='\r')
                for i in range(10):
                    time.sleep(0.1);
                    print(' ', flush=True, end='')
                print()

        except KeyboardInterrupt as e:
            question_idx -= 1

            if question_idx < 0:
                print('cancelled')
                sys.exit(0)
            else:
                CLEAR_SCREEN_BELOW_CURSOR = '\x1b[0J'
                CURSOR_UP_ONE = '\x1b[1A'
                ERASE_LINE = '\x1b[2K'
                for i in range(lines_per_question.pop()):
                    print(CURSOR_UP_ONE, end='')
                print(CURSOR_UP_ONE + CLEAR_SCREEN_BELOW_CURSOR + ERASE_LINE, end='\r')


def run_prompt(config):

    pre_commands_empty = (len(config.get_pre_commands(delimiter=None)) == 0)

    print()
    if not pre_commands_empty:
        print('Current pre-run commands (called from git root):\n%s' % config.get_pre_commands())
        print()
        print('Enter new pre-run commands: ')
    else:
        print('Enter pre-run commands:')

    done = False
    while not done:
        try:
            done = True
            asked = False
            enter_pre_commands(config)
            asked = True

            # give user 1 sec to react after the last question
            print('.' * 10, flush=True, end='\r')
            for i in range(10):
                time.sleep(0.1);
                print(' ', flush=True, end='')
            print()

        except KeyboardInterrupt as e:
            done = False

            if not asked:
                print('cancelled')
                sys.exit(0)
            else:
                asked = False
                CLEAR_SCREEN_BELOW_CURSOR = '\x1b[0J'
                ERASE_LINE = '\x1b[2K'
                print(CLEAR_SCREEN_BELOW_CURSOR + ERASE_LINE, end='\r')
                print()
                print('Enter new pre-run commands: ')

    run_commands_empty = (len(config.get_run_commands(delimiter=None)) == 0)

    print()
    if not run_commands_empty:
        print('Current run commands (called from git root):\n%s' % config.get_run_commands())
        print()
        print('Enter new run commands: ')
    else:
        print('Enter run commands:')

    done = False
    while not done:
        try:
            done = True
            asked = False
            enter_run_commands(config)
            asked = True

            # give user 1 sec to react after the last question
            print('.' * 10, flush=True, end='\r')
            for i in range(10):
                time.sleep(0.1);
                print(' ', flush=True, end='')
            print()

        except KeyboardInterrupt as e:
            done = False

            if not asked:
                print('cancelled')
                sys.exit(0)
            else:
                asked = False
                CLEAR_SCREEN_BELOW_CURSOR = '\x1b[0J'
                ERASE_LINE = '\x1b[2K'
                print(CLEAR_SCREEN_BELOW_CURSOR + ERASE_LINE, end='\r')
                print()
                print('Enter new run commands: ')


def meta_prompt(config):
    print('Enter meta parameters:')

    meta_questions = (
        enter_user_name,
        enter_run_name,
        enter_git_path,
        enter_git_remote_url,
        enter_output_base_path,
        enter_is_test,
        enter_number_of_runs,
        enter_increment_seed,
        enter_seed_base,
        enter_comment,
    )

    question_idx = 0
    lines_per_question = []
    while question_idx < len(meta_questions):
        try:
            terminal_lines_used = meta_questions[question_idx](config)
            if terminal_lines_used is None:
                terminal_lines_used = 1
            lines_per_question.append(terminal_lines_used)
            question_idx += 1

            if question_idx >= len(meta_questions):
                lines_per_question[-1] = 0
                # give user 1 sec to react after the last question
                print('.' * 10, flush=True, end='\r')
                for i in range(10):
                    time.sleep(0.1);
                    print(' ', flush=True, end='')
                print()

        except KeyboardInterrupt as e:
            question_idx -= 1

            if question_idx < 0:
                print('cancelled')
                sys.exit(0)
            else:
                CLEAR_SCREEN_BELOW_CURSOR = '\x1b[0J'
                CURSOR_UP_ONE = '\x1b[1A'
                ERASE_LINE = '\x1b[2K'
                for i in range(lines_per_question.pop()):
                    print(CURSOR_UP_ONE, end='')
                print(CURSOR_UP_ONE + CLEAR_SCREEN_BELOW_CURSOR + ERASE_LINE, end='\r')


def comment_only_prompt(config):
    print('Enter comment:')

    comment_question = (
        enter_comment,
    )

    question_idx = 0
    lines_per_question = []
    while question_idx < len(comment_question):
        try:
            terminal_lines_used = comment_question[question_idx](config)
            if terminal_lines_used is None:
                terminal_lines_used = 1
            lines_per_question.append(terminal_lines_used)
            question_idx += 1

            if question_idx >= len(comment_question):
                lines_per_question[-1] = 0
                # give user 1 sec to react after the last question
                print('.' * 10, flush=True, end='\r')
                for i in range(10):
                    time.sleep(0.1);
                    print(' ', flush=True, end='')
                print()

        except KeyboardInterrupt as e:
            question_idx -= 1

            if question_idx < 0:
                print('cancelled')
                sys.exit(0)
            else:
                CLEAR_SCREEN_BELOW_CURSOR = '\x1b[0J'
                CURSOR_UP_ONE = '\x1b[1A'
                ERASE_LINE = '\x1b[2K'
                for i in range(lines_per_question.pop()):
                    print(CURSOR_UP_ONE, end='')
                print(CURSOR_UP_ONE + CLEAR_SCREEN_BELOW_CURSOR + ERASE_LINE, end='\r')


def continue_prompt(config):
    enter_git_tag(config)
    print()
    run_prompt(config)
    print()
    target_prompt(config)


# GENERAL PROMPT SETUP #

default_style = Style.from_dict({
    'question': 'bg:#ansidarkgray #ansilightgray',
    'bottombar': '#ffffff bg:#333333',
})


class NumberValidator(Validator):
    def __init__(self, allow_empty=False):
        # allow_empty=True is for optional settings, where an empty input means 'not set'
        self.allow_empty = allow_empty

    def validate(self, document):
        text = document.text

        if not text and not self.allow_empty:
            raise ValidationError(message='This input must not be empty', cursor_position=0)

        if text and not text.isdigit():
            i = 0

            # Get index of fist non numeric character.
            # We want to move the cursor here.
            for i, c in enumerate(text):
                if not c.isdigit():
                    break

            raise ValidationError(message='This input contains non-numeric characters',
                                  cursor_position=i)


def _first_non_digit_index(text):
    # Get index of first non numeric character, so that we can move the cursor there if the unit
    # is wrong. If the text is all digits, this is the end of the text, i.e. where the unit is missing.
    i = 0
    while i < len(text) and text[i].isdigit():
        i += 1
    return i


class MemValidator(Validator):
    def validate(self, document):
        text = document.text

        if not text:
            raise ValidationError(message='This input must not be empty', cursor_position=0)

        # a valid value is a number directly followed by a unit, e.g. 4200mb
        if re.match(r'\d+(mb|gb)\Z', text) is None:
            raise ValidationError(
                message='This input is not a valid memory value. It must be a number directly followed by a unit (mb or gb), e.g. 4200mb. No white space!',
                cursor_position=_first_non_digit_index(text))


class SlurmMemValidator(Validator):
    def validate(self, document):
        text = document.text

        if not text:
            raise ValidationError(message='This input must not be empty', cursor_position=0)

        # a valid value is a number directly followed by a unit, e.g. 64G
        if re.match(r'\d+[KMGT]\Z', text, re.IGNORECASE) is None:
            raise ValidationError(
                message='This input is not a valid memory value. It must be a number directly followed by a unit (K, M, G or T), e.g. 64G. No white space!',
                cursor_position=_first_non_digit_index(text))


class FileExistsOrEmptyValidator(Validator):
    def validate(self, document):
        text = document.text
        if text and not os.path.isfile(text):
            raise ValidationError(message='Input is not an existing file', cursor_position=len(text) - 1)


def myprompt(question, *args, toolbarmsg="", **kwargs):
    def get_message():
        return [('class:question', '{:>23}'.format(question)), ('', ' ')]

    return prompt(*args,
                  vi_mode=True,
                  style=default_style,
                  message=get_message,
                  bottom_toolbar=[('class:bottombar', toolbarmsg)],
                  **kwargs)


def myprompt_number(question, *args, min_value=0, max_value=1000, delta=1, toolbarmsg="", **kwargs):
    def get_message():
        return [('class:question', '{:>23}'.format(question)), ('', ' ')]

    bindings = KeyBindings()

    def change_number(event, delta):
        text = event.cli.current_buffer.document.text
        match = re.match(r'(-?\d+)\s*(\D*)\s*\Z', text)
        if match:
            number = int(match.group(1))
            old_number = number
            number += delta
            unit = match.group(2)
            if number < min_value:
                number = min_value
            elif number > max_value:
                number = max_value
            if number != old_number and number >= min_value and number <= max_value:
                event.cli.current_buffer.reset()
                event.cli.current_buffer.insert_text(str(number) + unit)

    @bindings.add_binding('up')
    def inc_buffer(event):
        change_number(event, delta)

    @bindings.add_binding('down')
    def dec_buffer(event):
        change_number(event, -delta)

    return prompt(*args,
                  vi_mode=True,
                  style=default_style,
                  message=get_message,
                  bottom_toolbar=[('class:bottombar', toolbarmsg)],
                  key_bindings=bindings,
                  **kwargs)


# TARGET PROMPT QUESTIONS #

def enter_which_target(config):
    default_value = config.target.which if config.target.which is not None else ""

    out = myprompt("target:",
                   toolbarmsg="select target; tab gives autocomplete",
                   default=default_value,
                   completer=WordCompleter(_TARGET_LIST)).strip()

    config.target.which = out


def enter_connect_string(config):
    default_value = config.target.ssh.connect_string if config.target.ssh.connect_string is not None else ''

    out = myprompt("connect string:",
                   toolbarmsg="used to submit command via ssh ; vim mode on, use ESC-d-d to delete complete line",
                   default=default_value).strip()

    if out is not None and out != '':
        config.target.ssh.connect_string = out
    else:
        print("Connect string must be set.")
        enter_connect_string(config)


def enter_torque_user_name(config):
    default_value = config.target.torque.user_name if config.target.torque.user_name is not None else ''

    out = myprompt("user_name:",
                   toolbarmsg="used to log in at torque ; vim mode on, use ESC-d-d to delete complete line",
                   default=default_value).strip()

    if out is not None and out != '':
        config.target.torque.user_name = out
    else:
        print("User name must be set.")
        enter_torque_user_name(config)


def enter_slurm_user_name(config):
    default_value = config.target.slurm.user_name if config.target.slurm.user_name is not None else ''

    out = myprompt("user_name:",
                   toolbarmsg="used to log in at SLURM ; vim mode on, use ESC-d-d to delete complete line",
                   default=default_value).strip()

    if out is not None and out != '':
        config.target.slurm.user_name = out
    else:
        print("User name must be set.")
        enter_slurm_user_name(config)


def enter_slurm_partitions(config):
    has_partitions = config.target.slurm.partitions is not None and len(config.target.slurm.partitions) > 0
    default_value = ', '.join(config.target.slurm.partitions) if has_partitions else ""

    out = myprompt("partitions:",
                   toolbarmsg="(optional) insert partitions separated by space, tab gives autocomplete",
                   default=default_value,
                   completer=WordCompleter(_SLURM_PARTITION_LIST)).strip()
    config.target.slurm.partitions = out
    print('{:>23} {}'.format('Partitions set to:', config.target.slurm.partitions))


def enter_slurm_additional_gres(config):
    has_additional_gres = config.target.slurm.additional_gres is not None and len(config.target.slurm.additional_gres) > 0
    default_value = ', '.join(config.target.slurm.additional_gres) if has_additional_gres else ""

    out = myprompt("additional gres:",
                   toolbarmsg="(optional) insert additional gres (format key:count) separated by space, tab gives autocomplete",
                   default=default_value,
                   completer=WordCompleter(_SLURM_GRES_LIST)).strip()
    config.target.slurm.additional_gres = out
    print('{:>23} {}'.format('Additional gres set to:', config.target.slurm.additional_gres))


def enter_hostlist(config):
    has_hostlist = config.target.torque.hostlist is not None and len(config.target.torque.hostlist) > 0
    default_value = ', '.join(config.target.torque.hostlist) if has_hostlist else ""

    out = myprompt("hostlist:",
                   toolbarmsg="(optional) insert hosts separated by space, tab gives autocomplete",
                   default=default_value,
                   completer=WordCompleter(_NODE_NAME_LIST)).strip()
    config.target.torque.hostlist = out
    print('{:>23} {}'.format('Hostlist set to:', config.target.torque.hostlist))


def enter_ppn(config):
    default_value = str(config.target.torque.ppn)
    config.target.torque.ppn = int(myprompt_number("ppn:", min_value=1, default=default_value, validator=NumberValidator()))


def enter_slurm_cpus_per_gpu(config):
    default_value = str(config.target.slurm.cpus_per_gpu)
    config.target.slurm.cpus_per_gpu = int(myprompt_number("cpus per gpu:", min_value=1, default=default_value, validator=NumberValidator()))


def enter_nodes(config):
    default_value = str(config.target.torque.nodes)
    config.target.torque.nodes = int(myprompt_number("nodes:", min_value=1, default=default_value, validator=NumberValidator()))


def enter_gpus(config):
    default_value = str(config.target.torque.gpus)
    config.target.torque.gpus = int(myprompt_number("gpus:", default=default_value, validator=NumberValidator()))


def enter_slurm_num_gpus(config):
    default_value = str(config.target.slurm.num_gpus)
    config.target.slurm.num_gpus = int(myprompt_number("num gpus:", default=default_value, validator=NumberValidator()))


def enter_mem(config):
    default_value = config.target.torque.mem
    config.target.torque.mem = myprompt_number("mem:",
                                               toolbarmsg="number directly followed by a unit (mb or gb), e.g. 4200mb; no white space",
                                               min_value=1,
                                               default=default_value,
                                               validator=MemValidator())


def enter_slurm_mem(config):
    default_value = config.target.slurm.mem
    config.target.slurm.mem = myprompt_number("mem:",
                                              toolbarmsg="number directly followed by a unit (K, M, G or T), e.g. 64G; no white space",
                                              min_value=1,
                                              default=default_value,
                                              validator=SlurmMemValidator())


def enter_properties(config):
    has_properties = config.target.torque.properties is not None and len(config.target.torque.properties) > 0
    default_value = ', '.join(config.target.torque.properties) if has_properties else ""

    out = myprompt("properties:",
                   toolbarmsg="(optional) insert properties separated by space, tab gives autocomplete",
                   default=default_value,
                   completer=WordCompleter(_PROP_LIST)).strip()
    config.target.torque.properties = out
    print('{:>23} {}'.format('Properties set to:', config.target.torque.properties))


def enter_mail_notifications(config):
    has_mail_notifications = config.target.torque.mail_notifications is not None and len(config.target.torque.mail_notifications) > 0
    default_value = ', '.join(config.target.torque.mail_notifications) if has_mail_notifications else ""

    out = myprompt("mail notifications:",
                   toolbarmsg="(optional) insert mail notification options separated by space, tab gives autocomplete",
                   default=default_value,
                   completer=WordCompleter(_MAIL_NOTIFICATIONS_LIST)).strip()
    config.target.torque.mail_notifications = out
    print('{:>23} {}'.format('Mail notifications set to:', config.target.torque.mail_notifications))


def enter_slurm_gpu_type(config):
    default_value = config.target.slurm.gpu_type if config.target.slurm.gpu_type is not None else ""

    out = myprompt("gpu type:",
                   toolbarmsg="(optional) insert gpu type (one value only); tab gives autocomplete",
                   default=default_value,
                   completer=WordCompleter(_SLURM_GPU_TYPES_LIST)).strip()
    config.target.slurm.gpu_type = out
    print('{:>23} {}'.format('GPU type set to:', config.target.slurm.gpu_type))


def enter_queue(config):
    default_value = config.target.torque.queue if config.target.torque.queue is not None else ""

    out = myprompt("queue:",
                   toolbarmsg="(optional) insert queue (one value only); if empty, job will be assigned to default-gpu/cpu automatically; tab gives autocomplete",
                   default=default_value,
                   completer=WordCompleter(_QUEUE_LIST)).strip()
    config.target.torque.queue = out
    print('{:>23} {}'.format('Queue set to:', config.target.torque.queue))


def enter_walltime(config):
    match = re.match(r'(\d+):\d\d:\d\d', config.target.torque.walltime)
    if match:
        default_value = match.group(1)
    else:
        default_value = "24"
    wallh = int(myprompt_number("walltime hours:", default=default_value, validator=NumberValidator()))
    config.target.torque.walltime = "{0}:00:00".format(wallh)


def enter_slurm_walltime_hrs(config):
    default_value = str(config.target.slurm.walltime_hrs)
    config.target.slurm.walltime_hrs = int(myprompt_number("walltime hours:", default=default_value, validator=NumberValidator()))


def enter_slurm_signal_str(config):
    default_value = config.target.slurm.signal_str if config.target.slurm.signal_str is not None else ''

    out = myprompt("signal_str:",
                   toolbarmsg="(optional) will be passed to sbatch via --signal; format [{R|B}:]<sig_num>[@sig_time]; vim mode on, use ESC-d-d to delete complete line",
                   default=default_value).strip()

    config.target.slurm.signal_str = out if out != '' else None


def enter_job_chain_length(config):
    default_value = str(config.target.torque.job_chain_length)
    config.target.torque.job_chain_length = int(myprompt_number("job chain length:",
                                                          toolbarmsg='number of jobs that will be created [last question!]',
                                                          min_value=1,
                                                          default=default_value,
                                                          validator=NumberValidator()))


def enter_slurm_nodelist(config):
    has_nodelist = config.target.slurm.nodelist is not None and len(config.target.slurm.nodelist) > 0
    default_value = ', '.join(config.target.slurm.nodelist) if has_nodelist else ""

    out = myprompt("nodelist:",
                   toolbarmsg="(optional) insert node names separated by comma or space; vim mode on, use ESC-d-d to delete complete line",
                   default=default_value).strip()
    config.target.slurm.nodelist = out
    print('{:>23} {}'.format('Nodelist set to:', config.target.slurm.nodelist))


def enter_slurm_exclude_nodelist(config):
    has_exclude_nodelist = config.target.slurm.exclude_nodelist is not None and len(config.target.slurm.exclude_nodelist) > 0
    default_value = ', '.join(config.target.slurm.exclude_nodelist) if has_exclude_nodelist else ""

    out = myprompt("exclude nodelist:",
                   toolbarmsg="(optional) insert node names to exclude separated by comma or space; vim mode on, use ESC-d-d to delete complete line",
                   default=default_value).strip()
    config.target.slurm.exclude_nodelist = out
    print('{:>23} {}'.format('Exclude nodelist set to:', config.target.slurm.exclude_nodelist))


def enter_slurm_nice(config):
    default_value = str(config.target.slurm.nice) if config.target.slurm.nice is not None else ""

    out = myprompt("nice:",
                   toolbarmsg="(optional) will be passed to sbatch via --nice; higher values mean lower priority; leave empty to not set it",
                   default=default_value,
                   validator=NumberValidator(allow_empty=True)).strip()
    config.target.slurm.nice = int(out) if out != '' else None


def enter_slurm_job_chain_length(config):
    default_value = str(config.target.slurm.job_chain_length)
    config.target.slurm.job_chain_length = int(myprompt_number("job chain length:",
                                                          toolbarmsg='number of jobs that will be created [last question!]',
                                                          min_value=1,
                                                          default=default_value,
                                                          validator=NumberValidator()))


# RUN PARAMETER QUESTIONS #

def enter_pre_commands(config):
    default_value = config.get_pre_commands(insert_placeholders=False, delimiter='; ')

    out = myprompt("pre-run commands:",
                   toolbarmsg="use ';' to separate commands; use %LOGDIR% placeholder; vim mode on; ESC-d-d to delete line",
                   default=default_value,
                   completer=PathCompleter()).strip()

    out = [x.strip() for x in out.split(';')]
    out = list(filter(lambda x: x != '', out))
    config.set_pre_commands(out)

    pre_commands_empty = (len(config.get_pre_commands(delimiter=None)) == 0)
    if not pre_commands_empty:
        print()
        print('Pre-run commands changed to (called from git root):\n%s' % config.get_pre_commands(insert_placeholders=True, delimiter='\n'))


def enter_run_commands(config):
    default_value = config.get_run_commands(insert_placeholders=False, delimiter='; ')

    out = myprompt("run commands:",
                   toolbarmsg="use ';' to separate commands; use %LOGDIR% placeholder; vim mode on; ESC-d-d to delete line",
                   default=default_value,
                   completer=PathCompleter()).strip()

    out = [x.strip() for x in out.split(';')]
    out = list(filter(lambda x: x != '', out))
    config.set_run_commands(out)

    run_commands_empty = (len(config.get_run_commands(delimiter=None)) == 0)
    if not run_commands_empty:
        print()
        print('Run commands changed to (called from git root):\n%s' % config.get_run_commands(insert_placeholders=True, delimiter='\n'))


# META QUESTIONS #

def enter_use_pdb(config):
    default_value = str(config.meta.use_pdb)
    config.meta.use_pdb = utils.str2bool(myprompt("use pdb: ", default=default_value))


def enter_output_base_path(config):
    default_value = config.meta.output_base_path if config.meta.output_base_path is not None else ''

    out = myprompt("output base_path:",
                   toolbarmsg="base path for outputs; vim mode on, use ESC-d-d to delete complete line",
                   default=default_value,
                   completer=PathCompleter()).strip()

    if out is not None and out != '':
        config.meta.output_base_path = out
    else:
        print("Output base path must be set.")
        enter_output_base_path(config)


def enter_user_name(config):
    default_value = config.meta.user_name if config.meta.user_name is not None else ''

    out = myprompt("user_name:",
                   toolbarmsg="vim mode on, use ESC-d-d to delete complete line",
                   default=default_value).strip()

    if out is not None and out != '':
        config.meta.user_name = out
    else:
        print("User name must be set.")
        enter_user_name(config)


def enter_is_test(config):
    default_value = str(config.meta.is_test)
    config.meta.is_test = utils.str2bool(myprompt("is_test: ", default=default_value))
    
    
def enter_increment_seed(config):
    default_value = str(config.meta.increment_seed)
    config.meta.increment_seed = utils.str2bool(myprompt("increment_seed: ", default=default_value))
    
    
def enter_seed_base(config):
    default_value = str(config.meta.seed_base)
    config.meta.seed_base = int(myprompt_number("seed_base:", min_value=0, default=default_value, validator=NumberValidator()))


def enter_comment(config):
    default_value = config.meta.comment if config.meta.comment is not None else ''

    out = myprompt("comment:",
                   toolbarmsg="vim mode on, use ESC-d-d to delete complete line",
                   default=default_value,
                   completer=PathCompleter()).strip()

    out = None if out == '' else out

    config.meta.comment = out


def enter_run_name(config):
    default_value = config.meta.run_name if config.meta.run_name is not None else ''

    out = myprompt("run_name:",
                   toolbarmsg="vim mode on, use ESC-d-d to delete complete line",
                   default=default_value).strip()

    if out is not None and out != '':
        config.meta.run_name = out
    else:
        print("Run name must be set.")
        enter_run_name(config)


def enter_venv_cmd(config):
    default_value = config.meta.venv_cmd if config.meta.venv_cmd is not None else ''

    out = myprompt("venv_cmd:",
                   toolbarmsg="command to activate virtualenv; vim mode on, use ESC-d-d to delete complete line",
                   default=default_value,
                   completer=PathCompleter()).strip()

    if out is not None and out != '':
        config.meta.venv_cmd = out


def enter_custom_pre_command(config):
    default_value = config.meta.pre_cmd if config.meta.pre_cmd is not None else ''

    out = myprompt("pre cmd:",
                   toolbarmsg="custom command that is executed before the actual run; vim mode on, use ESC-d-d to delete complete line",
                   default=default_value).strip()

    if out is not None and out != '':
        config.meta.pre_cmd = out
    else:
        config.meta.pre_cmd = None


def enter_custom_pre_script_path(config):
    default_value = config.meta.pre_script_path if config.meta.pre_script_path is not None else ''

    out = myprompt("pre-script path:",
                   toolbarmsg="path to custom script that is executed before the actual run; vim mode on, use ESC-d-d to delete complete line",
                   default=default_value,
                   completer=PathCompleter()).strip()

    if out is not None and out != '':
        config.meta.pre_script_path = out


def enter_number_of_runs(config):
    default_value = str(config.meta.number_of_runs)
    out = int(myprompt_number("number_of_runs:", min_value=1, default=default_value, validator=NumberValidator()))
    config.meta.number_of_runs = out


def enter_python_abspath(config):
    default_value = config.meta.python_abspath if config.meta.python_abspath is not None else ''

    out = myprompt("python_abspath:",
                   toolbarmsg="absolute path to python run file; vim mode on, use ESC-d-d to delete complete line",
                   default=default_value,
                   completer=PathCompleter()).strip()

    if out is not None and out != '':
        config.meta.python_abspath = out


def enter_git_path(config):
    default_value = config.meta.git_path if config.meta.git_path is not None else ''

    out = myprompt("git_path:",
                   toolbarmsg="absolute path to git repo; vim mode on, use ESC-d-d to delete complete line",
                   default=default_value,
                   completer=PathCompleter()).strip()

    if out is not None and out != '':
        config.meta.git_path = out
    else:
        print("Git path must be set.")
        enter_git_path(config)


def enter_git_remote_url(config):
    default_value = config.meta.git_remote_url if config.meta.git_remote_url is not None else ''

    out = myprompt("git remote url:",
            toolbarmsg="git remote repository url (e.g. git@github.com:your_username/my-experiments.git)",
            default=default_value).strip()

    out = None if out == '' else out

    config.meta.git_remote_url = out


def enter_git_tag(config):
    default_value = config.meta.git_tag if config.meta.git_tag is not None else ''

    out = myprompt("git_tag:",
                   toolbarmsg="vim mode on, use ESC-d-d to delete complete line",
                   default=default_value).strip()

    if out is not None and out != '':
        config.meta.git_tag = out
    else:
        print("Git tag must be set.")
        enter_git_tag(config)


def enter_log_dir_argument_name(config):
    default_value = config.meta.log_dir_argument_name if config.meta.log_dir_argument_name is not None else ''

    out = myprompt("log_dir_argument_name:",
                   toolbarmsg="log dir argument name of the python run file",
                   default=default_value)

    if out is not None and out != '':
        config.meta.log_dir_argument_name = out
