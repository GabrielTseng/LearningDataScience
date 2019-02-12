from pathlib import Path

from cyp.data import MODISExporter, DataCleaner, Engineer
from cyp.models import ConvModel, RNNModel

import fire


class RunTask:

    @staticmethod
    def export(export_limit=None, major_states_only=True, check_if_done=True, download_folder=None,
               yield_data_path=Path('data/yield_data.csv')):
        """
        Export all the data necessary to train the models.

        Parameters
        ----------
        export_limit: int or None, default=None
            If not none, how many .tif files to export (*3, for the image, mask and temperature
            files)
        major_states_only: boolean, default=True
            Whether to only use the 11 states responsible for 75 % of national soybean
            production, as is done in the paper
        check_if_done: boolean, default=False
            If true, will check download_folder for any .tif files which have already been
            downloaded, and won't export them again. This effectively allows for
            checkpointing, and prevents all files from having to be downloaded at once.
        download_folder: None or pathlib Path, default=None
            Which folder to check for downloaded files, if check_if_done=True. If None, looks
            in data/folder_name
        yield_data_path: pathlib Path, default=Path('data/yield_data.csv')
            A path to the yield data
        """
        exporter = MODISExporter(locations_filepath=yield_data_path)
        exporter.export_all(export_limit, major_states_only, check_if_done,
                            download_folder)

    @staticmethod
    def process(mask_path=Path('data/crop_yield-data_mask'),
                temperature_path=Path('data/crop_yield-data_temperature'),
                image_path=Path('data/crop_yield-data_image'), yield_data_path=Path('data/yield_data.csv'),
                cleaned_data_path=Path('data/img_output'), multiprocessing=True, processes=4, parallelism=6,
                delete_when_done=True, num_years=14):
        """
        Preprocess the data

        Parameters
        ----------
        mask_path: pathlib Path, default=Path('data/crop_yield-data_mask')
            Path to which the mask tif files have been saved
        temperature_path: pathlib Path, default=Path('data/crop_yield-data_temperature')
            Path to which the temperature tif files have been saved
        image_path: pathlib Path, default=Path('data/crop_yield-data_image')
            Path to which the image tif files have been saved
        yield_data_path: pathlib Path, default=Path('data/yield_data.csv')
            Path to the yield data csv file
        cleaned_data_path: pathlib Path, default=Path('data/img_output')
            Path to save the data to
        multiprocessing: boolean, default=False
            Whether to use multiprocessing
        processes: int, default=4
            Number of processes to use if multiprocessing=True
        parallelism: int, default=6
            Parallelism if multiprocesisng=True
        delete_when_done: boolean, default=False
            Whether or not to delete the original .tif files once the .npy array
            has been generated.
        num_years: int, default=14
            How many years of data to create.
        """
        cleaner = DataCleaner(mask_path, temperature_path, image_path, yield_data_path,
                              savedir=cleaned_data_path, multiprocessing=multiprocessing,
                              processes=processes, parallelism=parallelism)
        cleaner.process(delete_when_done=delete_when_done, num_years=num_years)

    @staticmethod
    def engineer(cleaned_data_path=Path('data/img_output'), yield_data_path=Path('data/yield_data.csv'),
                 county_data_path=Path('data/county_data.csv'), num_bins=32, max_bin_val=4999):
        """
        Take the preprocessed data and generate the input to the models

        Parameters
        ----------
        cleaned_data_path: pathlib Path, default=Path('data/img_output')
            Path to save the data to, and path to which processed data has been saved
        yield_data_path: pathlib Path, default=Path('data/yield_data.csv')
            Path to the yield data csv file
        county_data_path: pathlib Path, default=Path('data/county_data.csv')
            Path to the county data csv file
        num_bins: int, default=32
            If generate=='histogram', the number of bins to generate in the histogram.
        max_bin_val: int, default=4999
            The maximum value of the bins. The default is taken from the original repository;
            note that the maximum pixel values from the MODIS datsets range from 16000 to
            18000 depending on the band
        """
        engineer = Engineer(cleaned_data_path, yield_data_path, county_data_path)
        engineer.process(num_bands=9, generate='histogram', num_bins=num_bins, max_bin_val=max_bin_val,
                         channels_first=True)

    def train_cnn(self, cleaned_data_path=Path('data/img_output'), dropout=0.25, out_channels_list=None,
                  stride_list=None, dense_features=None, savedir=Path('data/models'),
                  times=None, pred_years=None, num_runs=2, train_steps=25000, batch_size=32,
                  starter_learning_rate=1e-3, patience=5, use_gp=True,
                  sigma=1, r_loc=0.5, r_year=1.5, sigma_e=0.01, sigma_b=0.01):
        """
        Train a CNN model

        Parameters
        ----------
        cleaned_data_path: pathlib Path, default=Path('data/img_output')
            Path to which histogram has been saved
        dropout: float, default=0.25
            Default taken from the original repository
        out_channels_list: list or None, default=None
            Out_channels of all the convolutional blocks. If None, default values will be taken
            from the paper. Note the length of the list defines the number of conv blocks used.
        stride_list: list or None, default=None
            Strides of all the convolutional blocks. If None, default values will be taken from the paper
            If not None, must be equal in length to the out_channels_list
        dense_features: list, or None, default=None.
            output feature size of the Linear layers. If None, default values will be taken from the paper.
            The length of the list defines how many linear layers are used.
        savedir: pathlib Path, default=Path('data/models')
            The directory into which the models should be saved.
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
        histogram_path = cleaned_data_path / 'histogram_all_full.npz'

        model = ConvModel(in_channels=9, dropout=dropout, out_channels_list=out_channels_list,
                          stride_list=stride_list, dense_features=dense_features, savedir=savedir,
                          use_gp=use_gp, sigma=sigma, r_loc=r_loc, r_year=r_year, sigma_e=sigma_e,
                          sigma_b=sigma_b)
        model.run(histogram_path, times, pred_years, num_runs, train_steps, batch_size,
                  starter_learning_rate, patience)

    @staticmethod
    def train_rnn(cleaned_data_path=Path('data/img_output'), num_bins=32, hidden_size=128, num_rnn_layers=1,
                  rnn_dropout=0.25, dense_features=None, savedir=Path('data/models'), times=None, pred_years=None,
                  num_runs=2, train_steps=25000, batch_size=32, starter_learning_rate=1e-3, patience=5, use_gp=True,
                  sigma=1, r_loc=0.5, r_year=1.5, sigma_e=0.01, sigma_b=0.01):
        """
        Train an RNN model

        Parameters
        ----------
        cleaned_data_path: pathlib Path, default=Path('data/img_output')
            Path to which histogram has been saved
        num_bins: int, default=32
            Number of bins in the generated histogram
        hidden_size: int, default=128
            The size of the hidden state. Default taken from the original repository
        num_rnn_layers: int, default=1
            Number of recurrent layers. Default taken from the original repository
        rnn_dropout: float, default=0.25
            Default taken from the original repository (note, this is 1 - keep_prob)
        dense_features: list, or None, default=None.
            output feature size of the Linear layers. If None, default values will be taken from the paper.
            The length of the list defines how many linear layers are used.
        savedir: pathlib Path, default=Path('data/models')
            The directory into which the models should be saved.
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
        histogram_path = cleaned_data_path / 'histogram_all_full.npz'

        model = RNNModel(in_channels=9, num_bins=num_bins, hidden_size=hidden_size,
                         num_rnn_layers=num_rnn_layers, rnn_dropout=rnn_dropout, dense_features=dense_features,
                         savedir=savedir, use_gp=use_gp, sigma=sigma, r_loc=r_loc, r_year=r_year,
                         sigma_e=sigma_e, sigma_b=sigma_b)
        model.run(histogram_path, times, pred_years, num_runs, train_steps, batch_size,
                  starter_learning_rate, patience)


if __name__ == '__main__':
    fire.Fire(RunTask)
