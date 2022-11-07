from collections import Counter
from pprint import pprint
from typing import List

import pandas as pd
import spacy

# loading the english language small model of spacy
en = spacy.load('en_core_web_sm')
stopwords = en.Defaults.stop_words

transcript_data = pd.read_csv('/home/luca/mismas/BBC News/data/transcription/merged.csv')
# remove all punctuation from the word column
print("Removing punctuation from the word column")
transcript_data['word'] = transcript_data['word'].str.replace('[^\w\s]', '')
transcript_data['word'] = transcript_data['word'].str.lower()
transcript_data = transcript_data.query('word != ""')
# lemmatize the words
print("Lemmatizing words...")
# from tqdm import tqdm
# tqdm.pandas()
# transcript_data['word'] = transcript_data['word'].progress_apply(lambda x: en(x)[0].lemma_)
# remove all stopwords
print("Removing stopwords...")
transcript_data = transcript_data.query('word not in @stopwords')


def find_patterns(df):
    # select the word column
    data = df['word'].tolist()
    # sort the data by frequency and remove duplicates
    unique_words = sorted(set(data), key=data.count, reverse=True)
    # create a list of patterns
    patterns = []
    # for each word in the data, find the next most common word
    for word in unique_words:
        next_word = find_next_most_common_word([word], data)
        if next_word != 0:
            patterns.append([word, next_word])
    # for each pattern, find the next most common word until the next most common word appears only once
    for i in range(len(patterns)):
        while True:
            next_word = find_next_most_common_word(patterns[i], data)
            if next_word != 0:
                patterns[i].append(next_word)
            else:
                break
    patterns = [pattern for pattern in patterns if len(pattern) > 2]
    # sort the patterns by length
    patterns = sorted(patterns, key=len, reverse=True)
    return patterns


def find_next_most_common_word(pattern: List[str], data: list) -> str:
    # if items in pattern appear in the same sequence in data, find the next most common word
    words_following_pattern = []
    for i in range(len(data) - len(pattern)):
        if data[i:i + len(pattern)] == pattern:
            words_following_pattern.append(data[i + len(pattern)])
    # if there are no words following the pattern, or the following word appears only once, return 0
    if len(words_following_pattern) == 0 or words_following_pattern.count(words_following_pattern[0]) < 2:
        print(f"No words following pattern {pattern}")
        return 0
    # otherwise, return the next most common word
    else:
        return Counter(words_following_pattern).most_common()[0][0]


out = find_patterns(transcript_data)
pprint(out)
