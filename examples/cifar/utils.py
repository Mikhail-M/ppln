from collections import OrderedDict

import torch
import torch.nn.functional as F
from torch.nn import SyncBatchNorm
from torch.nn.parallel import DataParallel, DistributedDataParallel
from torch.utils.data import DataLoader
from torch.utils.data.distributed import DistributedSampler

from cifar.dataset import CustomCIFAR10
from ppln.data.transforms import build_albumentations
from ppln.utils.misc import get_dist_info


def accuracy(output, target, topk=(1, )):
    """Computes the precision@k for the specified values of k"""
    with torch.no_grad():
        maxk = max(topk)
        batch_size = target.size(0)

        _, pred = output.topk(maxk, 1, True, True)
        pred = pred.t()
        correct = pred.eq(target.view(1, -1).expand_as(pred))

        res = []
        for k in topk:
            correct_k = correct[:k].view(-1).float().sum(0, keepdim=True)
            res.append(correct_k.mul_(100.0 / batch_size))
        return res


def batch_processor(model, data, mode):
    img, label = data
    label = label.cuda(non_blocking=True)
    pred = model(img)
    loss = F.cross_entropy(pred, label)
    acc_top1, acc_top5 = accuracy(pred, label, topk=(1, 5))

    values = OrderedDict()
    values['loss'] = loss.item()
    values['acc_top1'] = acc_top1.item()
    values['acc_top5'] = acc_top5.item()
    outputs = dict(loss=loss, values=values, num_samples=img.size(0))
    return outputs


def build_dataset(data_root, transforms, train):
    transform = build_albumentations(transforms)
    return CustomCIFAR10(root=data_root, train=train, transform=transform)


def build_dataloader(dataset, images_per_gpu, workers_per_gpu, num_gpus=1, dist=True, **kwargs):
    if dist:
        rank, world_size = get_dist_info()
        sampler = DistributedSampler(dataset, world_size, rank)
        batch_size = images_per_gpu
        num_workers = workers_per_gpu
        kwargs['shuffle'] = False
    else:
        sampler = None
        batch_size = num_gpus * images_per_gpu
        num_workers = num_gpus * workers_per_gpu

    return DataLoader(
        dataset, batch_size=batch_size, sampler=sampler, num_workers=num_workers, pin_memory=False, **kwargs
    )


def build_sync_bn(model, apex):
    if apex:
        return apex.parallel.convert_syncbn_model(model)
    else:
        return SyncBatchNorm.convert_sync_batchnorm(model)


def build_dataparallel(model, sync_bn=True, dist=True, apex=None):
    if dist:
        if sync_bn:
            model = build_sync_bn(model, apex)

        model = DDP(model.cuda(), delay_allreduce=cfg.delay_allreduce)

        model = DistributedDataParallel(model.cuda(), device_ids=[torch.cuda.current_device()])
    else:
        model = DataParallel(model)

    return model
