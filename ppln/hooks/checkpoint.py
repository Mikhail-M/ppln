import os
import os.path as osp
from queue import PriorityQueue

import numpy as np

from ..utils.checkpoint import save_checkpoint
from ..utils.misc import master_only
from .base import BaseHook
from .priority import Priority
from .registry import HOOKS


@HOOKS.register_module
class CheckpointHook(BaseHook):
    def __init__(self, metric_name, mode, num_checkpoints=5, save_optimizer=True, out_dir=None, **kwargs):
        self.mode = mode
        self.save_optimizer = save_optimizer
        self.out_dir = out_dir
        self.meta = kwargs
        self._checkpoints = PriorityQueue(num_checkpoints)
        self._metric_name = metric_name
        self._best_metric = -np.infty

    @property
    def priority(self):
        return Priority.LOWEST

    def before_run(self, runner):
        if not self.out_dir:
            self.out_dir = runner.work_dir

    @staticmethod
    def current_filename(runner):
        return f'epoch_{runner.epoch + 1}.pth'

    def current_filepath(self, runner):
        return osp.join(self.out_dir, self.current_filename(runner))

    @master_only
    def after_val_epoch(self, runner):
        metric = runner.log_buffer.output[self._metric_name]

        if self.mode == 'min':
            metric *= -1

        if self._is_update(metric):
            self._checkpoints.put((metric, self.current_filepath(runner)))
            self._save_checkpoint(runner)
        if self._best_metric < metric:
            self._best_metric = metric
            self._save_link(runner)

    def _is_update(self, metric):
        if not self._checkpoints.full():
            return True

        min_metric, min_filename = self._checkpoints.get()

        if min_metric < metric:
            os.remove(min_filename)
            return True

        self._checkpoints.put((min_metric, min_filename))
        return False

    def _save_link(self, runner):
        linkpath = osp.join(self.out_dir, 'best.pth')
        if os.path.lexists(linkpath):
            os.remove(linkpath)
        os.symlink(self.current_filename(runner), linkpath)

    def _save_checkpoint(self, runner):
        self.meta.update(epoch=runner.epoch + 1, iter=runner.iter)

        optimizers = runner.optimizers if self.save_optimizer else None
        save_checkpoint(runner.model, self.current_filepath(runner), optimizer=optimizers, meta=self.meta)
