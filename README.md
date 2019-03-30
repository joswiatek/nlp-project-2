# NLP-Project-2.

## Overview
This project is for the Information Extraction project of Bruce
Porter's Practical NLP class.  This project parses characters and
their relationships with the other characters in Shakespeare's plays
through named entity recognition and sentiment analysis.

### Installation
In order for coreNLP to function, you must download and unzip the full coreNLP
project in the root directory of the repo. Download
[here](https://stanfordnlp.github.io/CoreNLP/index.html#download), move to the
root directory of the repo, and unzip. Don't change the name of the directory
after extracting (it should be stanford-corenlp-full-2018-10-05, if it's not
then change the value of `CORENLP_HOME` in `main.py` to match).

### Running
Run the code by running `python main.py`. It will read the necessary data from
Postgres and perform all the various tasks needed to produce triples. If you
have neo4j running locally it will upload the triples, and it will always write
the triples to text files.

## Data
Final triple data and neo4j exports can be found [here](https://drive.google.com/drive/folders/1-3G1IvRMhPkRkBF80Nk0xV2Gax1ntGrk?usp=sharing).
