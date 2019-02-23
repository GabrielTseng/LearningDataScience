# Miscellaneous files
In this folder, I'll add cool things which don't fit into the other folders

## [PCCF](pccf.py) 
StatsCanada charges ~800 dollars for access to its postal codes conversion file (PCCF), which converts postal codes to their equivalent census tracts. 
However, their website does allow for individual conversions of postal codes to census tracts. I had a large amount of postal codes to convert (~500), so I wrote a method using selenium which submits all of them to the website and extracts the census tract from the 'results' webpages.

Note: for best results, its typically best to send ~50 zip codes at once. More and the website may become buggy. 

## [WARP Loss](warp.py)
A PyTorch 0.3 implementation of WARP loss. For more details, see this
[blog post](https://medium.com/@gabrieltseng/intro-to-warp-loss-automatic-differentiation-and-pytorch-b6aa5083187a)
