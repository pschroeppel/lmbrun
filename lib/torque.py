from pexpect import ExceptionPexpect, pxssh
from collections import OrderedDict
from string import Template
from threading import Lock
from functools import reduce
from .utils import *
from .config import check_system_config_value, _TORQUE_LOGIN_HOST, _TORQUE_JOB_ID_REGEX, _TORQUE_DEFAULT_GPU_QUEUE, _TORQUE_DEFAULT_CPU_QUEUE


class _Job:
    def __init__(self):
        self._attrs = {}
        self._job_id = None
        self._job_list = None

    def parse(self, lines):
        self._job_id = lines.pop(0).replace('Job Id:', '').replace('[]', '').strip()
        for line in lines:
            parts = line.split('=')
            if len(parts) != 2: continue
            key = parts[0].strip()
            value = parts[1].strip()
            self._attrs[key] = value

    def id(self):
        return self._job_id

    def owner(self):
        if 'Job_Owner' in self._attrs:
            return self._attrs['Job_Owner'].split('@')[0].strip()
        else:
            return None

    def state(self):
        return self._attrs['job_state']

    def runtime(self):
        return self._attrs.get('resources_used.walltime', 0)

    def walltime(self):
        return self._attrs.get('Resource_List.walltime', 0)

    def name(self):
        return self._attrs['Job_Name']

    def host(self):
        if 'exec_host' in self._attrs:
            return self._attrs['exec_host'].split('/')[0].strip()
        else:
            return None

    def interactive(self):
        if 'interactive' in self._attrs:
            return bool(self._attrs['interactive'])
        else:
            return False

    def queue(self):
        return self._attrs['queue']

    def init_path(self):
        return self._attrs['init_work_dir']

    def depend_before(self):
        if 'depend' not in self._attrs: return []
        r = []
        deps = self._attrs['depend'].split(',')
        for dep in deps:
            if dep.startswith('beforeok'):
                id = dep.replace('beforeok:', '').strip()
                if self._job_list is not None:
                    r.append(self._job_list[id] if self._job_list.exists(id) else id)
                else:
                    r.append(id)
        return r

    def depend_after(self):
        if 'depend' not in self._attrs: return []
        r = []
        deps = self._attrs['depend'].split(',')
        for dep in deps:
            if dep.startswith('afterok'):
                id = dep.replace('afterok:', '').strip()
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
        # for job in self.depend_before():
        #     if isinstance(job, _Job):
        #         job.kill()
        #     else:
        #         kill(job)
        kill(self._job_id, delay, user_name)
        self._attrs['job_state'] = 'C'

    def __repr__(self):
        s = 'Job(id=%s, owner=%s, state=%s, name=%s, queue=%s, host=%s, interactive=%s, init_path=%s)' % (
            self.id(),
            self.owner(),
            self.state(),
            self.name(),
            self.queue(),
            self.host(),
            self.interactive(),
            self.init_path()
        )
        return s


sess = None


def connect_to_torque(user_name=None):
    global sess
    user_name = os.getenv('USER') if user_name is None else user_name

    check_system_config_value(_TORQUE_LOGIN_HOST, 'Torque login host')

    sess = pxssh.pxssh()
    try:
        sess.login(_TORQUE_LOGIN_HOST, user_name, login_timeout=30, sync_multiplier=5)
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
        if sess is None: connect_to_torque(user_name=user_name)
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
    if delay is None:
        cmd = 'qdel %s' % jobid
        notice("killing %s: %s" % (jobid, cmd), '\ttorque')
        _runcmd(cmd, user_name)
    else:
        cmd = 'qdel -W %d %s' % (delay, jobid)
        notice("killing %s with a delay of %d: %s" % (jobid, delay, cmd), '\ttorque')
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
        return self._jobs[job].state() in ['Q', 'R']

    def is_running(self, job):
        if not self.exists(job): return False
        return self._jobs[job].state == 'R'

    def __getitem__(self, item):
        return self._jobs[item]

    def items(self):
        return self._jobs.items()

    def __iter__(self):
        return self._jobs.__iter__()


def list(from_user='own', user_name=None):  # Set user_name=None if you want to see all jobs
    if from_user == 'own': from_user = os.getenv('USER')

    text = _runcmd('qstat -f', user_name)

    jobs = OrderedDict()
    current = []

    def add_job():
        nonlocal current
        job = _Job()
        job.parse(current)
        if from_user is None:
            jobs[job.id()] = job
        elif job.owner() == from_user:
            jobs[job.id()] = job
        current = []

    if text is not None:
        for line in text.split('\n'):
            if line.strip() == '': continue
            if line.startswith('Job Id:'):
                if len(current):
                    add_job()
            if line.startswith('\t'):
                current[-1] += line.strip()
            else:
                current.append(line[:-1])

    if len(current):
        add_job()

    return _JobList(jobs)


def list_dependencies(jobs):
    for id in jobs:
        job = jobs[id]
        print('%s(%s): before: %s, after: %s' % (
            job.id(), job.state(), [x.id() for x in job.depend_before()], [x.id() for x in job.depend_after()]))


def submit(
        name,
        job_file,
        path=None,
        node=None,
        cpus=1,
        gpus=0,
        properties=None,
        mem='5000mb',
        walltime='01:00:00',
        queue=None,
        dependency=None,
        hostlist=None,
        output_path=None,
        mail_notifications=None,
        user_name=None,
):
    if node is None:
        node = 1

    if queue is None:
        if gpus > 0 and cpus <= 1:
            queue = _TORQUE_DEFAULT_GPU_QUEUE
        else:
            queue = _TORQUE_DEFAULT_CPU_QUEUE

    if hostlist is not None and len(hostlist) > 0:
        hostlist = "hostlist=^" + reduce((lambda x, y: str(x) + "+" + str(y)), hostlist) + ","
    else:
        hostlist = ''

    if properties is not None and len(properties) > 0:
        properties = ':' + ':'.join(properties)
    else:
        properties = ''

    job_file_path = os.path.abspath(job_file)

    if path is None:
        path = job_file_path.path()

    if output_path is None:
        stream_path = job_file_path.path()
    else:
        stream_path = output_path

    qsub = Template(
        'qsub'
        ' -l ${hostlist}nodes=${nodes}:ppn=${cpus}${gpus}${properties},mem=${mem},walltime=$walltime'
        ' -q $queue'
        ' -d $path'
        ' $job_file'
        ' -N $name'
        ' $mail_notifications'
        ' -j oe'
        ' -o $streampath'
        ' $dependency'
    ).substitute(
        hostlist=hostlist if hostlist is not None else '',
        nodes=node,
        cpus=cpus,
        gpus=":gpus="+str(gpus) if gpus > 0 else '',
        properties=properties if properties is not None else '',
        mem=mem,
        queue=queue,
        walltime=walltime,
        path=path,
        job_file=job_file,
        name=name,
        mail_notifications='-m {0}'.format(mail_notifications) if mail_notifications is not None else '',
        streampath=stream_path,
        dependency='-W depend=afterok:{0}'.format(dependency) if dependency is not None else ''
    )

    notice("running %s" % qsub, '\t\ttorque')

    txt = _runcmd(qsub, user_name).strip()

    if not re.match(_TORQUE_JOB_ID_REGEX, txt):
        raise Exception("qsub failed. output:\n" + txt)

    return txt
