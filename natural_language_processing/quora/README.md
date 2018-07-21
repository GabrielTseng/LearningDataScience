# Natural Language Processing with Quora

Tackling Kaggle's [Quora question pairs competition](https://www.kaggle.com/c/quora-question-pairs)

Blog, where I describe my exploration of the dataset :
https://medium.com/@gabrieltseng/natural-language-processing-with-quora-9737b40700c8

## Exploration
[Exploration.ipynb](https://github.com/GabrielTseng/LearningDataScience/blob/master/Natural_Language_Processing/Exploration.ipynb) 

In this file, I test various ways of manipulating the data before inputting it into my neural network, including cleaning and adding leaky features. 

## Training
[Training_Cleaned_NeuralNetwork.ipynb](https://github.com/GabrielTseng/LearningDataScience/blob/master/Natural_Language_Processing/Training_Cleaned_NeuralNetwork.ipynb)

I then train to convergence a neural network (without leaky features). 

## SpaCy
[SpaCy_NLP.ipynb](https://github.com/GabrielTseng/LearningDataScience/blob/master/Natural_Language_Processing/Spacy_NLP.ipynb)

I briefly explore [SpaCy](https://spacy.io/)'s capabilities using this dataset, for potential future use. 

## Further steps I could take

1. Ensembling, particularly if I train a neural network with word2vec instead of GloVe embeddings
2. Identifying 'legal' leaky features (such as question lengths). 
3. Further optimization of hyperparameters. 

