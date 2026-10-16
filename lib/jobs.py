import os
import time
import time
import socket
from . import utils
from . import torque
from . import slurm


class Jobs:
    def __init__(self, config):
        self.config = config
        self._torque_jobs = None
        self._local_jobs = None
        self._ssh_jobs = None
        self._slurm_jobs = None

    def _get_torque_jobs(self):
        if self._torque_jobs is None:
            self._torque_jobs = TorqueJobs(self.config)
        return self._torque_jobs

    def _get_local_jobs(self):
        if self._local_jobs is None:
            self._local_jobs = LocalJobs(self.config)
        return self._local_jobs

    def _get_ssh_jobs(self):
        if self._ssh_jobs is None:
            self._ssh_jobs = SSHJobs(self.config)
        return self._ssh_jobs
    
    def _get_slurm_jobs(self):
        if self._slurm_jobs is None:
            self._slurm_jobs = SlurmJobs(self.config)
        return self._slurm_jobs

    def get_queued(self, torque_only=False, local_only=False, ssh_only=False, slurm_only=False, ids_only=False):

        queued = utils.readList(self.config.jobs.queued_file)  # first executed job is first in the list

        if torque_only:
            queued = [j for j in queued if self.is_torque(j[0])]
        if local_only:
            queued = [j for j in queued if self.is_local(j[0])]
        if ssh_only:
            queued = [j for j in queued if self.is_ssh(j[0])]
        if slurm_only:
            queued = [j for j in queued if self.is_slurm(j[0])]

        if ids_only:
            assert torque_only or slurm_only
            queued = [j[1] for j in queued]

        return queued

    def add_to_queue(self, job):
        utils.insert(self.config.jobs.queued_file, job)

    def clear_queued(self):
        open(self.config.jobs.queued_file, 'w')

    def has_current(self, torque_only=False, local_only=False, ssh_only=False, slurm_only=False):
        cur = self.get_current()
        has_cur = (cur != '')
        if not has_cur:
            return False
        else:
            if torque_only:
                return self.is_torque(cur)
            if local_only:
                return self.is_local(cur)
            if ssh_only:
                return self.is_ssh(cur)
            if slurm_only:
                return self.is_slurm(cur)

            return True

    def get_current(self):
        return open(self.config.jobs.current_file, 'rt').readline().strip()

    def clear_current(self):
        open(self.config.jobs.current_file, 'w')

    def is_local(self, string):
        return string.startswith("local")

    def is_torque(self, string):
        return string.startswith("torque")

    def is_ssh(self, string):
        return string.startswith("ssh")
    
    def is_slurm(self, string):
        return string.startswith("slurm")

    def check_run(self):
        if self.config.target.which == "torque":
            # It is okay if we have a current job, which is a torque job, as we can simply queue more jobs after it
            run_ok = not self.has_current() or self.has_current(torque_only=True)
            return run_ok
        elif self.config.target.which == "local":
            run_ok = not self.has_current() and self.check_all_finished()
            return run_ok
        elif self.config.target.which == "ssh":
            run_ok = not self.has_current() and self.check_all_finished()
            return run_ok
        elif self.config.target.which == "slurm":
            # It is okay if we have a current job, which is a slurm job, as we can simply queue more jobs after it
            run_ok = not self.has_current() or self.has_current(slurm_only=True)
            return run_ok

    def print_status(self):
        torque_jobs = self._get_torque_jobs()
        local_jobs = self._get_local_jobs()
        ssh_jobs = self._get_ssh_jobs()
        slurm_jobs = self._get_slurm_jobs()

        for job_idx, job in enumerate(self.get_queued()):
            print("Job #%d (%s):" % (job_idx, job[0] + ":" + job[1]))
            job_type = job[0]
            job_id = job[1]

            if self.is_torque(job_type):
                torque_jobs.print_status(job_id)
            elif self.is_local(job_type):
                local_jobs.print_status(job_id)
            elif self.is_ssh(job_type):
                ssh_jobs.print_status(job_id)
            elif self.is_slurm(job_type):
                slurm_jobs.print_status(job_id)
            else:
                print("\tUnknown job type!")

    def check_all_finished(self):
        if self.has_current():
            return False

        # torque and slurm jobs might not be currently running, but still be in the queue
        return self._get_torque_jobs().check_all_finished() and self._get_slurm_jobs().check_all_finished()

    def run(self):
        if not self.check_run():
            return False

        if self.config.target.which == "torque":
            TorqueJobs(self.config).run()
        elif self.config.target.which == "local":
            LocalJobs(self.config).run()
        elif self.config.target.which == "ssh":
            SSHJobs(self.config).run()
        elif self.config.target.which == "slurm":
            SlurmJobs(self.config).run()

        return True

    def construct_run_script(self, config_path, run_template_path, job_num):
        git_dir = self.config.meta.git_path
        git_tag = self.config.meta.git_tag
        git_remote_url = self.config.meta.git_remote_url if self.config.meta.git_remote_url is not None else ""
        output_file = os.path.join(self.config.meta.run_path, "stdout_stderr.txt")
        current_job_filename = self.config.jobs.current_file
        queue_filename = self.config.jobs.queued_file
        config_out_path = os.path.join(self.config.meta.run_path, 'last_config.pickle')

        # construct pre-run command:
        pre_commands = self.config.get_pre_commands(insert_placeholders=True, delimiter=None, job_num=job_num)

        if len(pre_commands) > 0:
            pre_command = ""
            pre_function_names = []
            for idx, single_command in enumerate(pre_commands):
                pre_command += ("pre_fct_%d() {\n" % idx)
                pre_command += single_command
                pre_command += "\n}\n\n"
                pre_function_names.append("pre_fct_%d" % idx)

            pre_command += ("PRE_FCTS=( " + " ".join(pre_function_names) + " )")

        else:
            pre_command = "PRE_FCTS=( )"

        # construct run command:
        run_commands = self.config.get_run_commands(insert_placeholders=True, delimiter=None, job_num=job_num)

        if len(run_commands) > 0:
            run_command = ""

            run_command_block_template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                           'run_cmd_block_template')

            with open(run_command_block_template_path, 'r') as run_command_block_template_file:
                run_command_block_template = run_command_block_template_file.read()

            for idx, single_command in enumerate(run_commands):
                run_command_block = run_command_block_template.format(single_command)
                run_command += "\n"
                run_command += run_command_block

        else:
            run_command = ""

        with open(run_template_path, 'r') as run_template_file:
            run_template = run_template_file.read()

        run_script = run_template.format(git_dir,
                                         git_tag,
                                         git_remote_url,
                                         output_file,
                                         current_job_filename,
                                         queue_filename,
                                         config_path,
                                         config_out_path,
                                         pre_command,
                                         run_command)

        return run_script

    def kill(self, delay=None):
        torque_jobs = self._get_torque_jobs()
        local_jobs = self._get_local_jobs()
        ssh_jobs = self._get_ssh_jobs()
        slurm_jobs = self._get_slurm_jobs()

        for job_idx, job in enumerate(self.get_queued()):
            print("Job #%d (%s):" % (job_idx, job[0] + ":" + job[1]))
            job_type = job[0]
            job_id = job[1]

            if self.is_torque(job_type):
                torque_jobs.kill(job_id, delay)
            elif self.is_local(job_type):
                local_jobs.kill(job_id)
            elif self.is_ssh(job_type):
                ssh_jobs.kill(job_id)
            elif self.is_slurm(job_type):
                slurm_jobs.kill(job_id)
            else:
                print("\tUnknown job type!")

        if self.has_current(torque_only=True):
            self.clear_current()
            
        if self.has_current(slurm_only=True):
            self.clear_current()


class LocalJobs(Jobs):
    def __init__(self, config):
        super().__init__(config)

    def print_status(self, job_id):
        print("\tLocal job on machine: %s" % job_id)
        running = self.has_current(local_only=True) and job_id in self.get_current()
        print("\tJob currently running: %s" % running)

    def init_run(self):
        run_script_name = '%s_%s_local.sh' % (self.config.meta.run_id, time.strftime('%Y.%m.%d-%H.%M.%S'))
        run_script_path = os.path.join(self.config.jobs.dir, run_script_name)

        config_path = (run_script_path[:-2] + "pickle")
        job_num = len(self.get_queued())

        run_template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run_local_template.sh')
        run_script = self.construct_run_script(config_path, run_template_path, job_num=job_num)

        with open(run_script_path, 'w') as f:
            f.write(run_script)
        perm = os.stat(run_script_path)
        os.chmod(run_script_path, (perm.st_mode | 0o111))

        return run_script_path

    def run(self):
        run_script_path = self.init_run()
        self.config.write(run_script_path[:-2] + "pickle")
        output_path = run_script_path[:-2] + "out"
        self.add_to_queue("local:" + str(socket.gethostname()))
        utils.run_in_shell_and_print(run_script_path + " | tee -a -i %s" % output_path)

    def kill(self, job_id):
        print("\tLocal job on machine: %s" % job_id)
        running = self.has_current(local_only=True) and job_id in self.get_current()
        if not running:
            print("\tJob already completed.")
        else:
            print("\tCould not kill job because it is running locally.")


class SSHJobs(Jobs):
    def __init__(self, config):
        super().__init__(config)

    def print_status(self, job_id):
        print("\tSSH job on machine: %s" % job_id)
        running = self.has_current(ssh_only=True)  # and ":".join(self.get_current().split(":")[1:]) in job_id
        print("\tJob currently running: %s" % running)

    def init_run(self):
        run_script_name = '%s_%s_ssh.sh' % (self.config.meta.run_id, time.strftime('%Y.%m.%d-%H.%M.%S'))
        run_script_path = os.path.join(self.config.jobs.dir, run_script_name)

        config_path = (run_script_path[:-2] + "pickle")
        job_num = len(self.get_queued())

        run_template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run_ssh_template.sh')
        run_script = self.construct_run_script(config_path, run_template_path, job_num=job_num)

        with open(run_script_path, 'w') as f:
            f.write(run_script)
        perm = os.stat(run_script_path)
        os.chmod(run_script_path, (perm.st_mode | 0o111))

        return run_script_path

    def run(self):
        run_script_path = self.init_run()
        self.config.write(run_script_path[:-2] + "pickle")
        connect_string = self.config.target.ssh.connect_string
        output_path = run_script_path[:-2] + "out"
        self.add_to_queue("ssh:" + connect_string)
        utils.run_in_shell_and_print(connect_string + " \"" + run_script_path + " | tee -a -i %s \"" % output_path)

    def kill(self, job_id):
        print("\tSSH job on machine: %s" % job_id)
        running = self.has_current(ssh_only=True) and job_id in self.get_current()
        if not running:
            print("\tJob already completed.")
        else:
            print("\tCould not kill job because it is running via ssh.")


class TorqueJobs(Jobs):
    def __init__(self, config):
        super().__init__(config)
        self._cur_torque_jobs = None

    def _get_torque_jobs(self):
        if self._cur_torque_jobs is None:
            self._cur_torque_jobs = torque.list(from_user=None, user_name=self.config.target.torque.user_name)
        return self._cur_torque_jobs

    def reload_torque_jobs(self):
        self._cur_torque_jobs = None

    def job_exists(self, job_id):
        torque_jobs = self._get_torque_jobs()
        return torque_jobs.exists(job_id)

    def job_finished(self, job_id):
        return not self.job_exists(job_id) or (self.get_status(job_id) == "Complete")

    def print_status(self, job_id):
        if not self.job_exists(job_id):
            print("\tJob complete and deleted from torque.")
        else:
            status = self.get_status(job_id)
            name = self.get_name(job_id)
            host = self.get_host(job_id)
            runtime = self.get_runtime(job_id)
            walltime = self.get_walltime(job_id)

            print("\tTorque job on machine: %s" % host)
            print("\tJob name: %s" % name)
            print("\tCurrent state: %s" % status)
            print("\tRuntime: %s / %s" % (runtime, walltime))

    def get_host(self, job_id):
        torque_jobs = self._get_torque_jobs()

        if self.job_exists(job_id):
            return torque_jobs[job_id].host()
        else:
            return "non-existent"

    def get_name(self, job_id):
        torque_jobs = self._get_torque_jobs()

        if self.job_exists(job_id):
            return torque_jobs[job_id].name()
        else:
            return "non-existent"

    def get_runtime(self, job_id):
        torque_jobs = self._get_torque_jobs()

        if self.job_exists(job_id):
            return torque_jobs[job_id].runtime()
        else:
            return -1

    def get_walltime(self, job_id):
        torque_jobs = self._get_torque_jobs()

        if self.job_exists(job_id):
            return torque_jobs[job_id].walltime()
        else:
            return -1

    def get_status(self, job_id):
        torque_jobs = self._get_torque_jobs()

        if torque_jobs.exists(job_id):
            status = torque_jobs[job_id].state()
            if status == 'R':
                status = "Running"
            elif status == 'C':
                status = "Complete"
            elif status == 'H':
                status = "Hold"
            elif status == 'E':
                status = "Exiting"
            elif status == 'Q':
                status = "Queued"
            elif status == 'W':
                status = "Waiting"
        else:
            status = 'non-existent'
        return status

    def check_all_finished(self):
        if self.has_current():
            return False

        for job_id in self.get_queued(torque_only=True, ids_only=True):
            if not self.job_finished(job_id):
                return False

        return True

    def init_jobs(self):
        job_script_paths = []
        run_template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run_torque_template.sh')

        for i in range(self.config.target.torque.job_chain_length):
            job_script_name = '%s_%s_torque_%d.sh' % (self.config.meta.run_id, time.strftime('%Y.%m.%d-%H.%M.%S'), i)
            job_script_path = os.path.join(self.config.jobs.dir, job_script_name)

            config_path = (job_script_path[:-2] + "pickle")
            job_num = len(self.get_queued()) + i
            run_script = self.construct_run_script(config_path, run_template_path, job_num=job_num)

            with open(job_script_path, 'w') as f:
                f.write(run_script)
            perm = os.stat(job_script_path)
            os.chmod(job_script_path, (perm.st_mode | 0o111))

            job_script_paths.append(job_script_path)

        return job_script_paths

    def run(self):
        job_script_paths = self.init_jobs()
        prev_job_id = None

        queue = self.get_queued()
        for job_idx, job in enumerate(queue):
            job_type = job[0]
            job_id = job[1]
            if job_type == "torque":
                if self.job_exists(job_id) and not self.job_finished(job_id):
                    prev_job_id = job_id

        for idx, job_script_path in enumerate(job_script_paths):
            output_path = job_script_path[:-2] + "out"
            self.config.write(job_script_path[:-2] + "pickle")
            job_id = torque.submit(
                name=self.config.jobs.name + "_c" + str(idx).zfill(2),
                job_file=job_script_path,
                path=self.config.jobs.dir,  # actually not important
                node=self.config.target.torque.nodes,
                cpus=self.config.target.torque.ppn,
                gpus=self.config.target.torque.gpus,
                properties=self.config.target.torque.properties,
                mem=self.config.target.torque.mem,
                walltime=self.config.target.torque.walltime,
                queue=self.config.target.torque.queue,
                dependency=prev_job_id,
                hostlist=self.config.target.torque.hostlist,
                output_path=output_path,
                mail_notifications=''.join(self.config.target.torque.mail_notifications) if self.config.target.torque.mail_notifications is not None else None,
                user_name=self.config.target.torque.user_name
            )
            utils.notice('Job submitted: %s' % job_id, '\t\ttorque')
            prev_job_id = job_id
            self.add_to_queue("torque:" + job_id + ": " + job_script_path[:-3])

    def kill(self, job_id, delay=None):
        if not self.job_exists(job_id):
            print("\tJob already complete and deleted from torque.")
        else:
            torque_jobs = self._get_torque_jobs()
            torque_jobs[job_id].kill(delay=delay, user_name=self.config.target.torque.user_name)


class SlurmJobs(Jobs):
    def __init__(self, config):
        super().__init__(config)
        self._cur_slurm_jobs = None

    def _get_slurm_jobs(self):
        if self._cur_slurm_jobs is None:
            self._cur_slurm_jobs = slurm.list(from_user=self.config.target.slurm.user_name)
        return self._cur_slurm_jobs

    def reload_slurm_jobs(self):
        self._cur_slurm_jobs = None

    def job_exists(self, job_id):
        slurm_jobs = self._get_slurm_jobs()
        return slurm_jobs.exists(job_id)

    def job_finished(self, job_id):
        slurm_jobs = self._get_slurm_jobs()
        return not self.job_exists(job_id) or not (slurm_jobs.is_running(job_id) or slurm_jobs.is_queued(job_id))

    def print_status(self, job_id):
        if not self.job_exists(job_id):
            print("\tJob complete and deleted from slurm.")
        else:
            status = self.get_status(job_id)
            name = self.get_name(job_id)
            nodelist = self.get_nodelist(job_id)
            runtime = self.get_runtime(job_id)
            walltime = self.get_walltime(job_id)

            print("\tSlurm job on nodes: %s" % nodelist)
            print("\tJob name: %s" % name)
            print("\tCurrent state: %s" % status)
            print("\tRuntime: %s / %s" % (runtime, walltime))

    def get_nodelist(self, job_id):
        slurm_jobs = self._get_slurm_jobs()

        if self.job_exists(job_id):
            return slurm_jobs[job_id].nodelist
        else:
            return "non-existent"

    def get_name(self, job_id):
        slurm_jobs = self._get_slurm_jobs()

        if self.job_exists(job_id):
            return slurm_jobs[job_id].name
        else:
            return "non-existent"

    def get_runtime(self, job_id):
        slurm_jobs = self._get_slurm_jobs()

        if self.job_exists(job_id):
            return slurm_jobs[job_id].runtime
        else:
            return -1

    def get_walltime(self, job_id):
        slurm_jobs = self._get_slurm_jobs()

        if self.job_exists(job_id):
            return slurm_jobs[job_id].walltime
        else:
            return -1

    def get_status(self, job_id):
        slurm_jobs = self._get_slurm_jobs()

        if slurm_jobs.exists(job_id):
            status = slurm_jobs[job_id].state
        else:
            status = 'non-existent'
        return status

    def check_all_finished(self):
        if self.has_current():
            return False

        for job_id in self.get_queued(slurm_only=True, ids_only=True):
            if not self.job_finished(job_id):
                return False

        return True

    def init_jobs(self):
        job_script_paths = []
        run_template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run_slurm_template.sh')

        for i in range(self.config.target.slurm.job_chain_length):
            job_script_name = '%s_%s_slurm_%d.sh' % (self.config.meta.run_id, time.strftime('%Y.%m.%d-%H.%M.%S'), i)
            job_script_path = os.path.join(self.config.jobs.dir, job_script_name)

            config_path = (job_script_path[:-2] + "pickle")
            job_num = len(self.get_queued()) + i
            run_script = self.construct_run_script(config_path, run_template_path, job_num=job_num)

            with open(job_script_path, 'w') as f:
                f.write(run_script)
            perm = os.stat(job_script_path)
            os.chmod(job_script_path, (perm.st_mode | 0o111))

            job_script_paths.append(job_script_path)

        return job_script_paths

    def run(self):
        job_script_paths = self.init_jobs()
        prev_job_id = None

        queue = self.get_queued()
        for job_idx, job in enumerate(queue):
            job_type = job[0]
            job_id = job[1]
            if job_type == "slurm":
                if self.job_exists(job_id) and not self.job_finished(job_id):
                    prev_job_id = job_id
                    
        num_prev_jobs = len(queue)
        
        # do ls starting from experiments base folder, to trigger filesystem update:
        tmp_job_script_path = job_script_paths[0]
        tmp_job_script_path_folder = os.path.dirname(tmp_job_script_path)
        tmp_job_script_path_folder_folder = os.path.dirname(tmp_job_script_path_folder)
        tmp_job_script_path_folder_folder_folder = os.path.dirname(tmp_job_script_path_folder_folder)
        tmp_job_script_path_folder_folder_folder_folder = os.path.dirname(tmp_job_script_path_folder_folder_folder)
        slurm.ls(tmp_job_script_path_folder_folder_folder_folder)
        slurm.ls(tmp_job_script_path_folder_folder_folder)
        slurm.ls(tmp_job_script_path_folder_folder)
        slurm.ls(tmp_job_script_path_folder)
        time.sleep(1)

        for idx, job_script_path in enumerate(job_script_paths):
            job_idx = num_prev_jobs + idx
            output_path = job_script_path[:-2] + "out"
            self.config.write(job_script_path[:-2] + "pickle")
            job_id = slurm.submit(
                name=self.config.jobs.name + "_c" + str(job_idx).zfill(2),
                job_file=job_script_path,
                partitions=self.config.target.slurm.partitions,
                num_gpus=self.config.target.slurm.num_gpus,
                gpu_type=self.config.target.slurm.gpu_type,
                cpus=self.config.target.slurm.cpus_per_gpu,
                mem=self.config.target.slurm.mem,
                walltime_hrs=self.config.target.slurm.walltime_hrs,
                signal_str=self.config.target.slurm.signal_str,
                additional_gres=self.config.target.slurm.additional_gres,
                nodelist=self.config.target.slurm.nodelist,
                exclude_nodelist=self.config.target.slurm.exclude_nodelist,
                nice=self.config.target.slurm.nice,
                dependencies=prev_job_id,
                output_path=output_path,
                user_name=self.config.target.slurm.user_name
            )
            utils.notice('Job submitted: %s' % job_id, '\t\tslurm')
            prev_job_id = job_id
            self.add_to_queue("slurm:" + job_id + ": " + job_script_path[:-3])

    def kill(self, job_id, delay=None):
        if not self.job_exists(job_id):
            print("\tJob already complete and deleted from slurm.")
        else:
            slurm_jobs = self._get_slurm_jobs()
            slurm_jobs[job_id].kill(delay=delay, user_name=self.config.target.slurm.user_name)
