"""Choose database and client CPUs once and share them with child processes."""
import os


def select_cpus():
    value = os.environ.get('SPECSON_EXPERIMENT_CPUS')
    cpus = tuple(map(int, value.split(','))) if value else tuple(sorted(os.sched_getaffinity(0))[:5])
    if len(cpus) != 5 or len(set(cpus)) != 5 or min(cpus) < 0:
        raise ValueError('The experiment suite requires five available logical CPUs')
    os.environ['SPECSON_EXPERIMENT_CPUS'] = ','.join(map(str, cpus))
    return cpus[:4], cpus[4]


BACKEND_CPUS, CLIENT_CPU = select_cpus()
