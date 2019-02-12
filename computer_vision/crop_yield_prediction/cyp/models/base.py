import torch
from torch import nn
from torch.utils.data import TensorDataset, DataLoader

from pathlib import Path
import numpy as np
import pandas as pd
from collections import defaultdict
from tqdm import tqdm
from datetime import datetime

from .gp import GaussianProcess


class ModelBase:
    """
    Base class for all models

    Parameters
    ----------
        use_gp: boolean, default=True
            Whether to use a Gaussian process in addition to the model

        If use_gp=True, the following parameters are also used:

        sigma: float, default=1
            The kernel variance, or the signal variance
        r_loc: float, default=0.5
            The length scale for the location data (latitudes and longitudes)
        r_year: float, default=1.5
            The length scale for the time data (years)
        sigma_e: float, default=0.01
            Noise variance
        sigma_b: float, default=0.01
            Parameter variance; the variance on B
    """
    def __init__(self, model, model_weight, model_bias, model_type, savedir, use_gp=True,
                 sigma=1, r_loc=0.5, r_year=1.5, sigma_e=0.01, sigma_b=0.01):
        self.savedir = savedir / model_type
        self.savedir.mkdir(parents=True, exist_ok=True)

        self.model = model
        self.model_type = model_type
        self.model_weight = model_weight
        self.model_bias = model_bias

        self.gp = None
        if use_gp:
            self.gp = GaussianProcess(sigma, r_loc, r_year, sigma_e, sigma_b)

    def run(self, path_to_histogram=Path('data/img_output/histogram_all_full.npz'),
            times=None, pred_years=None, num_runs=2, train_steps=25000, batch_size=32,
            starter_learning_rate=1e-3, patience=5):
        """
        Train the models. Note that multiple models are trained: as per the paper, a model
        is trained for each year, with all preceding years used as training values. In addition,
        for each year, 2 models are trained to account for random initialization.

        Parameters
        ----------
        path_to_histogram: pathlib Path, default=Path('data/img_output/histogram_all_full.npz')
            The location of the training data
        times: list, or None, default=None
            Which time indices to train the model on. If None, the default values from the paper
            for the full run ([32]) are used.
        pred_years: list or None, default=None
            Which years to build models for. If None, the default values from the paper (range(2009, 2016))
            are used.
        num_runs: int, default=2
            The number of runs to do per year. Default taken from the paper
        train_steps: int, default=25000
            The number of steps for which to train the model. Default taken from the paper.
        batch_size: int, default=32
            Batch size when training. Default taken from the paper
        starter_learning_rate: float, default=1e-3
            Starter learning rate. Note that the learning rate is divided by 10 after 2000 and 4000 training
            steps. Default taken from the paper
        patience: int or None, default=5
            The number of epochs to wait without improvement in the validation loss before terminating training.
            Note that the original repository doesn't use early stopping.
        """

        with np.load(path_to_histogram) as hist:
            images = hist['output_image']
            locations = hist['output_locations']
            yields = hist['output_yield']
            years = hist['output_year']
            indices = hist['output_index']

        # to collect results
        years_list = []
        run_numbers = []
        rmse_list = []
        me_list = []
        times_list = []  # which subset of times the model will be trained on
        if self.gp is not None:
            rmse_gp_list = []
            me_gp_list = []

        if pred_years is None:
            pred_years = range(2009, 2016)
        if times is None:
            times = [32]
            # TODO: doesn't work for convolutions
            # times = range(10, 31, 4)

        for pred_year in pred_years:
            for run_number in range(1, num_runs + 1):
                for time in times:
                    print(f'Training to predict on {pred_year}, Run number {run_number}')
                    results = self._run_1_year(images, yields, years, locations, indices, pred_year, time,
                                               run_number, train_steps, batch_size, starter_learning_rate,
                                               patience)
                    years_list.append(pred_year)
                    run_numbers.append(run_number)
                    times_list.append(time)
                    if self.gp is not None:
                        rmse, me, rmse_gp, me_gp = results
                        rmse_gp_list.append(rmse_gp)
                        me_gp_list.append(me_gp)
                    else:
                        rmse, me = results
                    rmse_list.append(rmse)
                    me_list.append(me)

                print('-----------')
        data = {'year': years_list, 'run_number': run_numbers, 'time_idx': times_list,
                'RMSE': rmse_list, 'ME': me_list}
        if self.gp is not None:
            data['RMSE_GP'] = rmse_gp_list
            data['ME_GP'] = me_gp_list
        results_df = pd.DataFrame(data=data)
        results_df.to_csv(self.savedir / f'{str(datetime.now().date())}.csv', index=False)

    def _run_1_year(self, images, yields, years, locations, indices, predict_year, time, run_number,
                    train_steps, batch_size, starter_learning_rate, patience):
        """
        Train one model on one year of data, and then save the model predictions.
        To be called by run().
        """
        train_idx = np.nonzero(years < predict_year)[0]
        val_idx = np.nonzero(years == predict_year)[0]

        train_images, val_images = self._normalize(images[train_idx], images[val_idx])

        print(f'Train set size: {train_idx.shape[0]}, Val set size: {val_idx.shape[0]}')

        train_images = torch.tensor(train_images[:, :, :time, :]).float()
        train_yields = torch.tensor(yields[train_idx]).float().unsqueeze(1)
        train_locations = torch.tensor(locations[train_idx])
        train_indices = torch.tensor(indices[train_idx])
        train_years = torch.tensor(years[train_idx])

        val_images = torch.tensor(val_images[:, :, :time, :]).float()
        val_yields = torch.tensor(yields[val_idx]).float().unsqueeze(1)
        val_locations = torch.tensor(locations[val_idx])
        val_indices = torch.tensor(indices[val_idx])
        val_years = torch.tensor(years[val_idx])

        # reinitialize the weights, since self.model may be trained multiple
        # times in one call to run()
        self.model.initialize_weights()

        train_scores, val_scores = self._train(train_images, train_yields, val_images,
                                               val_yields, train_steps, batch_size,
                                               starter_learning_rate, patience)
        results = self._predict(train_images, train_yields, train_locations, train_indices,
                                val_images, val_yields, val_locations, val_indices,
                                train_years, val_years, batch_size)

        model_information = {
            'state_dict': self.model.state_dict(),
            'val_loss': val_scores['loss'],
            'train_loss': train_scores['loss'],
        }
        for key in results:
            model_information[key] = results[key]

        # finally, get the relevant weights for the Gaussian Process
        model_information['model_weight'] = self.model.state_dict()[self.model_weight].numpy()
        model_information['model_bias'] = self.model.state_dict()[self.model_bias].numpy()

        if self.gp is not None:
            print("Running Gaussian Process!")
            gp_pred = self.gp.run(model_information['train_feat'], model_information['val_feat'],
                                  model_information['train_loc'], model_information['val_loc'],
                                  model_information['train_years'], model_information['val_years'],
                                  model_information['train_real'], model_information['model_weight'],
                                  model_information['model_bias'])
            model_information['val_pred_gp'] = gp_pred.squeeze(1)

        filename = f'{predict_year}_{run_number}{"_gp" if (self.gp is not None) else ""}.pth.tar'
        torch.save(model_information, self.savedir / filename)
        return self.analyze_results(model_information['val_real'], model_information['val_pred'],
                                    model_information['val_pred_gp'])

    def _train(self, train_images, train_yields, val_images, val_yields, train_steps,
               batch_size, starter_learning_rate, patience):

        train_dataset = TensorDataset(train_images, train_yields)
        val_dataset = TensorDataset(val_images, val_yields)

        train_dataloader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_dataloader = DataLoader(val_dataset, batch_size=batch_size)

        criterion = nn.MSELoss()  # TODO: L1 loss as well?
        optimizer = torch.optim.Adam([pam for pam in self.model.parameters()],
                                      lr=starter_learning_rate)

        num_epochs = int(train_steps / (train_images.shape[0] / batch_size))
        print(f'Training for {num_epochs} epochs')
        step_number = 0

        train_scores = defaultdict(list)
        val_scores = defaultdict(list)

        if patience is not None:
            min_loss = np.inf
            best_state = self.model.state_dict()
            epochs_without_improvement = 0

        for epoch in range(num_epochs):
            self.model.train()

            # running train and val scores are only for printing out
            # information
            running_train_scores = defaultdict(list)

            for train_x, train_y in tqdm(train_dataloader):
                optimizer.zero_grad()
                pred_y = self.model(train_x)
                loss = criterion(pred_y, train_y)
                loss.backward()
                optimizer.step()

                running_train_scores['loss'].append(loss.item())
                train_scores['loss'].append(loss.item())

                step_number += 1
                if (step_number == 4000) or (step_number == 20000):
                    for param_group in optimizer.param_groups:
                        param_group['lr'] /= 10

            train_output_strings = []
            for key, val in running_train_scores.items():
                train_output_strings.append('{}: {}'.format(key, round(np.array(val).mean(), 5)))

            running_val_scores = defaultdict(list)
            self.model.eval()
            with torch.no_grad():
                for val_x, val_y, in tqdm(val_dataloader):
                    val_pred_y = self.model(val_x)
                    val_loss = criterion(val_pred_y, val_y)
                    running_val_scores['loss'].append(val_loss.item())

                    val_scores['loss'].append(val_loss.item())

            val_output_strings = []
            for key, val in running_val_scores.items():
                val_output_strings.append('{}: {}'.format(key, round(np.array(val).mean(), 5)))
            print('TRAINING: {}'.format(*train_output_strings))
            print('VALIDATION: {}'.format(*val_output_strings))

            if patience is not None:
                epoch_val_loss = np.array(running_val_scores['loss']).mean()
                if epoch_val_loss < min_loss:
                    best_state = self.model.state_dict()
                    min_loss = epoch_val_loss
                    epochs_without_improvement = 0
                else:
                    epochs_without_improvement += 1

                    if epochs_without_improvement == patience:
                        # revert to the best state dict
                        self.model.load_state_dict(best_state)
                        print('Early stopping!')
                        break

        return train_scores, val_scores

    def _predict(self, train_images, train_yields, train_locations, train_indices,
                 val_images, val_yields, val_locations, val_indices, train_years, val_years,
                 batch_size):
        """
        Predict on the training and validation data. Optionally, return the last
        feature vector of the model.
        """
        train_dataset = TensorDataset(train_images, train_yields, train_locations, train_indices,
                                      train_years)
        val_dataset = TensorDataset(val_images, val_yields, val_locations, val_indices, val_years)

        train_dataloader = DataLoader(train_dataset, batch_size=1)
        val_dataloader = DataLoader(val_dataset, batch_size=batch_size)

        results = defaultdict(list)

        self.model.eval()
        with torch.no_grad():
            for train_im, train_yield, train_loc, train_idx, train_year in tqdm(train_dataloader):
                model_output = self.model(train_im,
                                          return_last_dense=True if (self.gp is not None) else False)
                if self.gp is not None:
                    pred, feat = model_output
                    results['train_feat'].append(feat.numpy())
                else:
                    pred = model_output
                results['train_pred'].extend(pred.squeeze(1).tolist())
                results['train_real'].extend(train_yield.squeeze(1).tolist())
                results['train_loc'].append(train_loc.numpy())
                results['train_indices'].append(train_idx.numpy())
                results['train_years'].extend(train_year.tolist())

            for val_im, val_yield, val_loc, val_idx, val_year in tqdm(val_dataloader):
                model_output = self.model(val_im,
                                          return_last_dense=True if (self.gp is not None) else False)
                if self.gp is not None:
                    pred, feat = model_output
                    results['val_feat'].append(feat.numpy())
                else:
                    pred = model_output
                results['val_pred'].extend(pred.squeeze(1).tolist())
                results['val_real'].extend(val_yield.squeeze(1).tolist())
                results['val_loc'].append(val_loc.numpy())
                results['val_indices'].append(val_idx.numpy())
                results['val_years'].extend(val_year.tolist())

        for key in results:
            if key in ['train_feat', 'val_feat', 'train_loc',
                       'train_indices', 'val_loc', 'val_indices']:
                results[key] = np.concatenate(results[key], axis=0)
            else:
                results[key] = np.array(results[key])
        return results

    @staticmethod
    def _normalize(train_images, val_images):
        """
        Find the mean values of the bands in the train images. Use these values
        to normalize both the training and validation images.

        A little awkward, since transpositions are necessary to make array broadcasting work
        """
        mean = np.mean(train_images, axis=(0, 2, 3))

        train_images = (train_images.transpose(0, 2, 3, 1) - mean).transpose(0, 3, 1, 2)
        val_images = (val_images.transpose(0, 2, 3, 1) - mean).transpose(0, 3, 1, 2)

        return train_images, val_images

    @staticmethod
    def analyze_results(true, pred, pred_gp):
        """Calculate ME and RMSE
        """
        rmse = np.sqrt(np.mean((true - pred) ** 2))
        me = np.mean(true - pred)

        print(f'Without GP: RMSE: {rmse}, ME: {me}')

        if pred_gp is not None:
            rmse_gp = np.sqrt(np.mean((true - pred_gp) ** 2))
            me_gp = np.mean(true - pred_gp)
            print(f'With GP: RMSE: {rmse_gp}, ME: {me_gp}')
            return rmse, me, rmse_gp, me_gp
        return rmse, me
