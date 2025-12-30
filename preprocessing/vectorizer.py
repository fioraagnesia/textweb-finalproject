import pandas as pd
import numpy as np
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from nlp_id.postag import PosTag

# =========================
# Load Data
# =========================
df = pd.read_excel("cleaned_news.xlsx")
X_text = df["final_text"].astype(str)
y = df["label"]

# =========================
# TF-IDF
# =========================
vectorizer = TfidfVectorizer(
    ngram_range=(1, 3),
    min_df=3,
    max_df=0.9
)
X_tfidf = vectorizer.fit_transform(X_text)
feature_names = vectorizer.get_feature_names_out()

# =========================
# POS Tagging
# =========================
pos_tagger = PosTag()
noun_tags = {"NN", "NNP", "NP"}

def is_all_noun(ngram):
    """
    Cek apakah semua kata dalam ngram adalah noun
    """
    words = ngram.split()
    try:
        tagged = pos_tagger.get_pos_tag(" ".join(words))
        return all(tag in noun_tags for word, tag in tagged)
    except:
        return False

# =========================
# Filter fitur
# =========================
indices_to_keep = []
filtered_feature_names = []

for i, feat in enumerate(feature_names):
    if is_all_noun(feat):
        continue  # hapus unigram/bigram/trigram yang semuanya noun
    indices_to_keep.append(i)
    filtered_feature_names.append(feat)

X_tfidf_filtered = X_tfidf[:, indices_to_keep]

# =========================
# Simpan hasil
# =========================
# 1. Simpan sparse matrix TF-IDF hasil filter
joblib.dump(X_tfidf_filtered, "preprocessing/X_tfidf_filtered.pkl")
print("TF-IDF filtered tersimpan di X_tfidf_filtered.pkl")

# 2. Simpan daftar fitur tersisa
pd.DataFrame(filtered_feature_names, columns=["feature"]).to_csv("preprocessing/filtered_features.csv", index=False)
print("Daftar fitur tersisa tersimpan di filtered_features.csv")

# 3. Simpan vectorizer (TF-IDF)
joblib.dump(vectorizer, "preprocessing/tfidf_vectorizer.pkl")
print("Vectorizer tersimpan di tfidf_vectorizer.pkl")
