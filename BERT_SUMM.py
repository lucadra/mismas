import os
from pathlib import Path

import pandas as pd
from summarizer.sbert import SBertSummarizer

os.environ["TOKENIZERS_PARALLELISM"] = 'false'


# counter = 4


# for sentence in sentences:
#     sentence_length = len(sentence.split())
#     sentence = [sentence, True, counter, counter+sentence_length] if sentence in result else [sentence, False, counter, counter+sentence_length]
#     counter += sentence_length
#     sentences_new.append(sentence)
#
# for sentence[0] in sentences_new:
#
#     print(sentence)
#     print(words.iloc[sentence[2]:sentence[3]])


def compile_BERT_summary_shot_list(transcript: Path, words_df):
    """
    Compiles a list of shots based on sentences present in the summary
    :param transcript: Complete transcript of the video from Visiion Intelligence API
    :param words_df: Word-level transcription annotations from Vision Intelligence API
    :return:
    """
    video_id = words_df['id'].iat[0]
    body = transcript.read_text()
    model = SBertSummarizer('all-MiniLM-L12-v2')
    summary = model(body, ratio=0.25, return_as_list=True)
    shot_list = []
    for sentence in summary:
        sentence_words = sentence.split()
        possible_indexes = words_df.index[words_df['word'] == sentence_words[0]]
        for idx in possible_indexes:
            if words_df.iloc[idx:idx + len(sentence_words)]['word'].tolist() == sentence_words:
                shot_list.append([sentence, idx, idx + len(sentence_words), words_df.iloc[idx]['start'],
                                  words_df.iloc[idx + len(sentence_words) - 1]['end'], video_id])
                break
    return pd.DataFrame(shot_list, columns=['sentence', 'start_index', 'end_index', 'start', 'end', 'id'])

# print(compile_shot_list(result, words))

# df = compile_shot_list(result, words)
# df.to_csv('BERTshots.csv', index=False)

# extract_shots(df)
# merge_shots('videos/selected_shots')
