from argparse import ArgumentParser

from torchvision.models import resnet

from cifar.builder import BuildFactory
from cifar.utils import batch_processor
from ppln.factory import make_optimizer
from ppln.hooks import DistSamplerSeedHook
from ppln.runner import Runner
from ppln.utils.config import Config
from ppln.utils.misc import init_dist


def parse_args():
    parser = ArgumentParser(description='Train CIFAR-10 classification')
    parser.add_argument('config', help='train config file path')
    parser.add_argument('--local_rank', type=int, default=0)
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = Config.fromfile(args.config)
    builder = BuildFactory(cfg)
    # init distributed environment if necessary
    init_dist(**cfg.dist_params)

    # build datasets and dataloaders
    train_loader, val_loader = builder.build_data()

    # build model
    model = getattr(resnet, cfg.model)(pretrained=True).cuda()
    optimizer = make_optimizer(model, cfg.optimizer)

    # apex
    if cfg.apex:
        model, optimizer, optimizer_hook = builder.build_apex(model=model, optimizer=optimizer)
    else:
        optimizer = cfg.optimizer
        optimizer_hook = cfg.optimizer_config
        model = builder.build_default_model(model)

    # build runner and register hooks
    runner = Runner(model, optimizer, batch_processor, cfg.work_dir)
    runner.register_hooks(
        lr_config=cfg.lr_config,
        optimizer_config=optimizer_hook,
        checkpoint_config=cfg.checkpoint_config,
        log_config=cfg.log_config
    )
    runner.register_hook(DistSamplerSeedHook())

    # load param (if necessary) and run
    if cfg.get('resume_from') is not None:
        runner.resume(cfg.resume_from)
    elif cfg.get('load_from') is not None:
        runner.load(cfg.load_from)

    runner.run({'train': train_loader, 'val': val_loader}, cfg.total_epochs)


if __name__ == '__main__':
    main()
