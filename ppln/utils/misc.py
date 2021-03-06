import functools
import os
import pydoc
import time
from getpass import getuser
from socket import gethostname

import torch
import torch.distributed as dist
import torch.multiprocessing as mp


def get_host_info():
    return '{}@{}'.format(getuser(), gethostname())


def init_dist(backend='nccl', **kwargs):
    if mp.get_start_method(allow_none=True) is None:
        mp.set_start_method('spawn')
    rank = int(os.environ['RANK'])
    num_gpus = torch.cuda.device_count()
    torch.cuda.set_device(rank % num_gpus)
    torch.distributed.init_process_group(backend=backend, **kwargs)


def get_dist_info():
    initialized = dist.is_initialized()
    if initialized:
        rank = dist.get_rank()
        world_size = dist.get_world_size()
    else:
        rank = 0
        world_size = 1
    return rank, world_size


def master_only(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        rank, _ = get_dist_info()
        if rank == 0:
            return func(*args, **kwargs)

    return wrapper


def get_timestamp():
    return time.strftime('%Y%m%d_%H%M%S', time.localtime())


def object_from_dict(d, parent=None, **default_kwargs):
    assert isinstance(d, dict) and 'type' in d
    kwargs = d.copy()
    object_type = kwargs.pop('type')

    for name, value in default_kwargs.items():
        kwargs.setdefault(name, value)

    if parent is not None:
        return getattr(parent, object_type)(**kwargs)
    else:
        return pydoc.locate(object_type)(**kwargs)
