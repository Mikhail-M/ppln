import logging
import os.path as osp
import warnings

import torch
from torch.nn.parallel import DistributedDataParallel

from .utils.misc import get_dist_info, get_timestamp, object_from_dict

try:
    from apex import amp
    from apex.parallel import DistributedDataParallel as ApexDDP
except ImportError as e:
    warnings.warn(
        f"Error \"{e}\" during importing apex library. To use mixed precison"
        ' you should install it from https://github.com/NVIDIA/apex'
    )


def make_model(cfg) -> torch.nn.Module:
    model = object_from_dict(cfg)
    return model.cuda()


def make_ddp(model) -> torch.nn.Module:
    return DistributedDataParallel(model, device_ids=[torch.cuda.current_device()])


def make_apex(cfg, model, optimizer=None):
    if optimizer is None:
        model = amp.initialize(model, **cfg)
        return ApexDDP(model, delay_allreduce=True)
    else:
        model, optimizer = amp.initialize(model, optimizer, **cfg)
        return ApexDDP(model, delay_allreduce=True), optimizer


def make_optimizer(model: torch.nn.Module, config: dict) -> torch.optim.Optimizer:
    optimizer = object_from_dict(config, params=filter(lambda x: x.requires_grad, model.parameters()))
    return optimizer


def make_file_handler(logger, filename=None, mode='w', level=logging.INFO):
    file_handler = logging.FileHandler(filename, mode)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    file_handler.setLevel(level)
    logger.addHandler(file_handler)
    return logger


def make_logger(log_dir):
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
    rank, _ = get_dist_info()
    timestamp = get_timestamp()
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    if log_dir and rank == 0:
        log_file = osp.join(log_dir, f'{timestamp}.log')
        make_file_handler(logger, log_file, level=logging.INFO)
    return logger
