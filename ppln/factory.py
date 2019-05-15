import os.path as osp
import torch
import logging

from .utils.misc import object_from_dict, get_dist_info, get_timestamp


def make_model(config, device) -> torch.nn.Module:
    model = object_from_dict(config)
    return model.to(device)


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
    rank, _ = get_dist_info()
    timestamp = get_timestamp()
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    if log_dir and rank == 0:
        log_file = osp.join(log_dir, f'{timestamp}.log')
        make_file_handler(logger, log_file, level=logging.INFO)
    return logger
