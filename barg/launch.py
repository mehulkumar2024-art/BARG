"""Enroll a newly launched bounded workload and immediately drop root."""
import argparse
import os
import platform
import sys
from pathlib import Path
from barg.control import CgroupActuator


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--kind',choices=['cpu','memory','io','anomaly'],default='anomaly')
    p.add_argument('--duration',type=float,default=60)
    p.add_argument('--group',choices=['worker','competitor'],default='worker')
    args=p.parse_args()
    if not .1<=args.duration<=120: p.error('Duration must be 0.1–120 seconds')
    if platform.system() != 'Linux' or os.geteuid()!=0:
        p.error('This launcher requires Linux; use scripts/start.ps1 for the Windows demo')
    import pwd
    uid=int(os.environ.get('SUDO_UID','65534'))
    if uid==0: p.error('Workloads must run as a non-root user')
    gid=pwd.getpwuid(uid).pw_gid
    actuator=CgroupActuator('/sys/fs/cgroup/barg-lab','/run/barg/rollback.json')
    leaf=actuator.path(args.group)
    if (leaf/'cgroup.procs').read_text().strip(): p.error('Workload group is already occupied')
    directory=Path('data/workloads').resolve()
    directory.mkdir(parents=True,exist_ok=True)
    os.chown(directory,uid,gid)
    (leaf/'cgroup.procs').write_text(str(os.getpid()))
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    os.setgroups([])
    os.setgid(gid)
    os.setuid(uid)
    os.execv(sys.executable,[sys.executable,'-m','barg.workload','--kind',args.kind,'--duration',str(args.duration),'--directory',str(directory)])


if __name__=='__main__': main()
