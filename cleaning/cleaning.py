import pandas as pd
import re
import string
import warnings
warnings.filterwarnings("ignore")
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
import nltk
nltk.download("stopwords")
from nltk.corpus import stopwords

stemmer = StemmerFactory().create_stemmer()

stopwords_id = set(StopWordRemoverFactory().get_stop_words())
stopwords_en = set(stopwords.words("english"))

NEGATION_WORDS = {"tidak", "bukan", "belum", "tanpa"}
ALL_STOPWORDS = (stopwords_id | stopwords_en) - NEGATION_WORDS

# MEDIA NOISE (KHUSUS MEDIA ONLINE)
MEDIA_NOISE_PATTERNS = [
    r'let gptinline.*?passback',
    r'window\.googletag.*?enableservices',
    r'gptinline',
    r'googletag',
    r'pubads',
    r'defineslot',
    r'enableservices',
    r'collapseemptydivs',
    r'cmdpushfunction',
    r'tirtodesktopinline',
    r'baca juga.*',
    r'advertisement.*',
    r'video bagi tampil.*',
    r'tangkap layar.*'
]

def remove_media_noise(text):
    text = text.lower()
    for p in MEDIA_NOISE_PATTERNS:
        text = re.sub(p, ' ', text, flags=re.DOTALL)
    return text

# TITLE CLEANING (CUSTOM)
TITLE_PREFIX_PATTERN = r'''
^(
    \[?\s*(salah|keliru|hoaks?|hoax|klarifikasi|penipuan|misinformasi)\s*\]? |
    cek\s*fakta[:,]? |
    fakta[:,]? |
    klarifikasi[:,]? |
    hoaks! |
    hoax! |
    keliru! |
    salah! |
    update[:,]? |
    breaking\s*news[:,]?
)+
'''

def clean_title(title):
    title = str(title).lower()

    # remove editorial prefixes
    title = re.sub(
        TITLE_PREFIX_PATTERN,
        '',
        title,
        flags=re.IGNORECASE | re.VERBOSE
    )

    # remove symbols
    title = re.sub(r'[^\w\s]', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()

    return title

# TEXT CLEANING
def clean_text(text):
    text = str(text).lower()

    text = remove_media_noise(text)

    # remove html & url
    text = re.sub(r'<.*?>', ' ', text)
    text = re.sub(r'http\S+|www\S+', ' ', text)

    # fix encoding junk
    text = re.sub(r'[�â€™]', ' ', text)

    # remove numbers & punctuation
    text = re.sub(r'\d+', ' ', text)
    text = text.translate(str.maketrans('', '', string.punctuation))

    # normalize spaces
    text = re.sub(r'\s+', ' ', text).strip()

    return text

def split_stuck_words(token):
    if len(token) < 20:
        return [token]

    parts = []
    buffer = ""

    for ch in token:
        buffer += ch
        if buffer in stopwords_id or buffer in stopwords_en:
            parts.append(buffer)
            buffer = ""

    if buffer:
        parts.append(buffer)

    return parts

def normalize_text(text):
    tokens = text.split()
    final_tokens = []

    for t in tokens:
        if len(t) > 25:  # suspiciously long
            split_tokens = split_stuck_words(t)
        else:
            split_tokens = [t]

        for s in split_tokens:
            if s not in ALL_STOPWORDS and len(s) > 2:
                try:
                    final_tokens.append(stemmer.stem(s))
                except:
                    continue

    return " ".join(final_tokens)

# WEIRD DATA FILTER
def is_weird_row(title, narasi, penjelasan=""):
    if len(title.split()) < 3:
        return True
    if len(narasi.split()) < 10:
        return True
    if penjelasan and len(penjelasan.split()) < 5:
        return True
    return False

# MAIN PREPROCESS
def preprocess_df(df):
    if "title" not in df.columns or "narasi" not in df.columns:
        raise ValueError("CSV harus punya kolom 'title' dan 'narasi'")

    df = df.copy()
    df = df.dropna(subset=["title", "narasi"])

    has_penjelasan = "penjelasan" in df.columns

    df["clean_title"] = df["title"].apply(clean_title)

    df["clean_narasi"] = (
        df["narasi"]
        .astype(str)
        .apply(clean_text)
        .apply(normalize_text)
    )

    if has_penjelasan:
        df["clean_penjelasan"] = (
            df["penjelasan"]
            .astype(str)
            .apply(clean_text)
            .apply(normalize_text)
        )
    else:
        df["clean_penjelasan"] = ""

    df = df[
        ~df.apply(
            lambda x: is_weird_row(
                x["clean_title"],
                x["clean_narasi"],
                x["clean_penjelasan"]
            ),
            axis=1
        )
    ]

    df["final_text"] = (
        df["clean_title"] + " " +
        df["clean_narasi"] + " " +
        df["clean_penjelasan"]
    ).str.strip()

    return df.reset_index(drop=True)

def status_to_label(status):
    return 1 if str(status).strip().lower() == "hoax" else 0

# LOAD & LABEL DATA
paths = [
    "news_turnbackhoax fix.csv",
    "news_antaranews fix.csv",
    "news_kompascom fix.csv",
    "news_tempo fix.csv",
]

dfs = []

for path in paths:
    df = pd.read_csv(path)
    df = preprocess_df(df)

    if "status" not in df.columns:
        raise ValueError(f"Kolom 'status' tidak ada di {path}")

    df["label"] = df["status"].apply(status_to_label)
    dfs.append(df)

final_df = pd.concat(dfs, ignore_index=True)
final_df = final_df.sample(frac=1, random_state=42)

# SAVE TO EXCEL
final_df.to_excel(
    "cleaned_news.xlsx",
    index=False,
    engine="openpyxl"
)

print("CLEANING DONE")
print("Total data:", len(final_df))
print(final_df[["clean_title", "label"]].head())
