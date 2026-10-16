from pexpect import ExceptionPexpect, pxssh
from collections import OrderedDict
from threading import Lock
from .utils import *
from .config import _SLURM_LOGIN_HOST, check_system_config_value


class _Job:
    def __init__(self, user, id, name, state, nodelist, walltime, runtime, dependency):
        self.user = user
        self.id = id
        self.name = name
        self.state = state
        self.nodelist = nodelist
        self.walltime = walltime
        self.runtime = runtime
        self.dependency = dependency

    def depend_after(self):  # returns all the jobs that need to run before this job can run (i.e. this job depends on running after them)
        if 'depend' not in self._attrs: return []
        r = []
        deps = self.dependency.split(',')
        for dep in deps:
            if dep.startswith('after'):
                separator_idx = dep.find(':')
                dep = dep[separator_idx + 1:]
                separator_idx = dep.find('(')
                dep = dep[:separator_idx]
                id = dep.strip()
                if self._job_list is not None:
                    r.append(self._job_list[id] if self._job_list.exists(id) else id)
                else:
                    r.append(id)
        return r

    def dependent(self):
        return len(self.depend_after()) > 0

    def is_head(self):
        return len(self.depend_after()) == 0

    def kill(self, delay=None, user_name=None):
        kill(self.id, delay, user_name)
        self.state = 'CANCELLED'

    def __repr__(self):
        s = 'Job(id=%s, owner=%s, state=%s, nodes=%s, name=%s, walltime=%s, runtime=%s, dependency=%s)' % (
            self.id,
            self.user,
            self.state,
            self.nodelist,
            self.name,
            self.walltime,
            self.runtime,
            self.dependency
        )
        return s


sess = None


def connect_to_slurm(user_name=None):
    global sess
    user_name = os.getenv('USER') if user_name is None else user_name

    check_system_config_value(_SLURM_LOGIN_HOST, 'SLURM login host')

    sess = pxssh.pxssh()
    try:
        sess.login(_SLURM_LOGIN_HOST, user_name, login_timeout=30, sync_multiplier=5)
    #
    # ExceptionPexpect also covers EOF and TIMEOUT, which login() lets through
    # on some paths without closing the session itself.
    #
    except ExceptionPexpect as e:
        if not sess.closed: sess.close(force=True)
        sess = None
        raise RuntimeError("SSH session failed on login") from e


_runcmd_lock = Lock()


def _runcmd(cmd, user_name=None):
    global sess
    global _runcmd_lock

    #
    # The lock is required in case this method is called interleaved from multiple threads
    #
    _runcmd_lock.acquire()
    try:
        if sess is None: connect_to_slurm(user_name=user_name)
        sess.sendline('')
        sess.prompt()
        sess.sendline(cmd)
        sess.prompt()
        lines = sess.before.decode('utf-8').split('\n')
    finally:
        _runcmd_lock.release()

    if len(lines) == 1: return None
    return '\n'.join(lines[1:])


def kill(jobid, delay=None, user_name=None):
    if delay is not None:
        print("Note: delay is available for killing slurm jobs.")
    
    cmd = 'scancel --me %s' % jobid
    notice("killing %s: %s" % (jobid, cmd), '\tslurm')
    _runcmd(cmd, user_name)


class _JobList:
    def __init__(self, jobs):
        self._jobs = jobs

        for job in self._jobs.values():
            job._job_list = self

    def exists(self, job):
        return job in self._jobs

    def is_queued(self, job):
        if not self.exists(job): return False
        return self._jobs[job].state in ['PD', 'PENDING', 'RQ', 'REQUEUED']

    def is_running(self, job):
        if not self.exists(job): return False
        return self._jobs[job].state in ['R', 'RUNNING', 'COMPLETING', 'CG', 'CONFIGURING', 'CF']

    def __getitem__(self, item):
        return self._jobs[item]

    def items(self):
        return self._jobs.items()

    def __iter__(self):
        return self._jobs.__iter__()


def list(from_user='own'):  # Set user_name=None if you want to see all jobs
    if from_user == 'own': from_user = os.getenv('USER')

    if from_user is None:
        raise NotImplementedError('from_user=None is not implemented')
    else:
        text_sacct = _runcmd(f'sacct -X  -o User%400,Jobid%400,Jobname%400,State%400,Nodelist%400,Timelimit%400,Elapsed%400 -u {from_user}')
        text_squeue = _runcmd(f'squeue -O Username:400,Jobid:400,name:400,state:400,nodelist:400,timelimit:400,timeused:400,dependency:400 -u {from_user}')
        
    # parse jobs from sacct:
    sacct_jobs = {}
    for line in text_sacct.split('\n'):
        line = line.strip()
        if line.startswith(from_user):
            entries = [x.strip() for x in line.split('  ') if len(x) > 0]
            user, job_id, job_name, job_state, nodelist, walltime, runtime = entries
            job_state = job_state.split(" ")[0]
            sacct_jobs[job_id] = (user, job_name, job_state, nodelist, walltime, runtime, None)
            
    # parse jobs from squeue:
    squeue_jobs = {}
    for line in text_squeue.split('\n'):
        line = line.strip()
        if line.startswith(from_user):
            entries = [x.strip() for x in line.split('  ') if len(x) > 0]
            if len(entries) == 8:
                user, job_id, job_name, job_state, nodelist, walltime, runtime, dependency = entries
            else:
                user, job_id, job_name, job_state, walltime, runtime, dependency = entries
                nodelist = None
                
            job_state = job_state.split(" ")[0]
            squeue_jobs[job_id] = (user, job_name, job_state, nodelist, walltime, runtime, dependency)
            
    # merge jobs
    # for jobs that are available in both sacct and squeue, we take:
    # - user from squeue
    # - job name from squeue
    # - job state from squeue
    # - nodelist from squeue
    # - walltime from sacct
    # - runtime from sacct
    # - dependency from squeue
    
    merged_jobs = {}
    for job_id in sacct_jobs:
        if job_id in squeue_jobs:
            merged_jobs[job_id] = (squeue_jobs[job_id][0], squeue_jobs[job_id][1], squeue_jobs[job_id][2], squeue_jobs[job_id][3], sacct_jobs[job_id][4], sacct_jobs[job_id][5], squeue_jobs[job_id][6])
        else:
            merged_jobs[job_id] = sacct_jobs[job_id]
    for job_id in squeue_jobs:
        if job_id not in merged_jobs:
            merged_jobs[job_id] = squeue_jobs[job_id]

    jobs = OrderedDict()
    
    for job_id, (user, job_name, job_state, nodelist, walltime, runtime, dependency) in merged_jobs.items():
        dependency = None if dependency == "(null)" else dependency        
        job = _Job(user, job_id, job_name, job_state, nodelist, walltime, runtime, dependency)
        jobs[job.id] = job

    return _JobList(jobs)


def submit(
        name,
        job_file,
        partitions=None,
        num_gpus=0,
        gpu_type=None,
        cpus=1,
        mem='5000mb',
        walltime_hrs='1',
        signal_str=None,
        additional_gres=None,
        nodelist=None,
        exclude_nodelist=None,
        nice=None,
        dependencies=None,
        output_path=None,
        user_name=None,
):
    if partitions is not None and len(partitions) > 0:
        partitions = ",".join(partitions)
    else:
        partitions = None
        
    if additional_gres is not None and len(additional_gres) > 0:
        additional_gres = ",".join(additional_gres)
    else:
        additional_gres = None

    if nodelist is not None and len(nodelist) > 0:
        nodelist = ",".join(nodelist)
    else:
        nodelist = None

    if exclude_nodelist is not None and len(exclude_nodelist) > 0:
        exclude_nodelist = ",".join(exclude_nodelist)
    else:
        exclude_nodelist = None

    partitions_str = f' -p {partitions}' if partitions is not None else ''
    
    if num_gpus > 0:
        if gpu_type is not None:
            gres_str = f' --gres gpu:{gpu_type}:{num_gpus}'
        else:
            gres_str = f' --gres gpu:{num_gpus}'
            
        cpus_str = f' --cpus-per-gpu {cpus}'
    else:
        gres_str = ''
        cpus_str = f' --cpus-per-task {cpus}'
        
    if additional_gres is not None:
        if len(gres_str) > 0:
            gres_str += ','
            gres_str += additional_gres
        else:
            gres_str = f" --gres {additional_gres}"
            
    mem_str = f' --mem {mem}'
    
    walltime_str = f' --time {walltime_hrs}:00:00'
    
    signal_str = f' --signal {signal_str}' if signal_str is not None else ''
    
    name_str = f' --job-name {name}'

    output_str = f' --output {output_path}' if output_path is not None else ''

    nodelist_str = f' --nodelist {nodelist}' if nodelist is not None else ''

    exclude_nodelist_str = f' --exclude {exclude_nodelist}' if exclude_nodelist is not None else ''

    nice_str = f' --nice={nice}' if nice is not None else ''

    if dependencies is not None:        
        if isinstance(dependencies, str):
            dependencies = [dependencies]
        
        for idx, dep in enumerate(dependencies):
            if not dep.startswith('after'):
                dep = 'afterany:' + dep
                dependencies[idx] = dep
                
        dependencies = ','.join(dependencies)
        dependency_str = f' --dependency {dependencies}'
    else:
        dependency_str = ''
            
    job_file_path = os.path.realpath(job_file)

    cmd = f'sbatch{partitions_str}{gres_str}{cpus_str}{mem_str}{walltime_str}{signal_str}{name_str}{output_str}{nodelist_str}{exclude_nodelist_str}{nice_str}{dependency_str} {job_file_path}'

    notice("running %s" % cmd, '\t\tslurm')

    txt = _runcmd(cmd, user_name).strip()

    match = re.search(r'Submitted batch job (\d+)', txt)
    if not match:
        raise Exception("sbatch failed. output:\n" + txt)
    else:
        job_id = match.group(1)

    return job_id


def ls(path):
    return _runcmd('ls %s' % path)
