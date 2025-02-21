# flake8: noqa
import argparse

from common import add_arguments, get_contrastive_model, get_loaders
from sklearn.linear_model import LogisticRegression

from torch.optim import Adam

from catalyst import dl
from catalyst.contrib import nn
from catalyst.contrib.losses import NTXentLoss
from catalyst.dl import SelfSupervisedRunner

parser = argparse.ArgumentParser(description="Train BYOL")
add_arguments(parser)


def set_requires_grad(model, val):
    for p in model.parameters():
        p.requires_grad = val


if __name__ == "__main__":
    args = parser.parse_args()
    batch_size = args.batch_size

    # 2. model and optimizer

    model = nn.ModuleDict(
        {
            "online": get_contrastive_model(args.feature_dim),
            "target": get_contrastive_model(args.feature_dim),
        }
    )

    set_requires_grad(model["target"], False)
    optimizer = Adam(model["online"].parameters(), lr=args.learning_rate)

    # 3. criterion
    criterion = NTXentLoss(tau=args.temperature)

    callbacks = [
        dl.CriterionCallback(
            input_key="online_projection_left",
            target_key="target_projection_right",
            metric_key="loss",
        ),
        dl.ControlFlowCallback(
            dl.SoftUpdateCallaback(
                target_model_key="target", source_model_key="online", tau=0.1, scope="on_batch_end"
            ),
            loaders="train",
        ),
        dl.SklearnModelCallback(
            feature_key="embedding_origin",
            target_key="target",
            train_loader="train",
            valid_loaders="valid",
            model_fn=LogisticRegression,
            predict_key="sklearn_predict",
            predict_method="predict_proba",
        ),
        dl.OptimizerCallback(metric_key="loss"),
        dl.ControlFlowCallback(
            dl.AccuracyCallback(
                target_key="target", input_key="sklearn_predict", topk_args=(1, 3)
            ),
            loaders="valid",
        ),
    ]

    runner = SelfSupervisedRunner()

    runner.train(
        model=model,
        criterion=criterion,
        optimizer=optimizer,
        callbacks=callbacks,
        loaders=get_loaders(args.dataset, args.batch_size, args.num_workers),
        verbose=True,
        logdir=args.logdir,
        valid_loader="train",
        valid_metric="loss",
        minimize_valid_metric=True,
        num_epochs=args.epochs,
    )
