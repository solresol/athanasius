#!/usr/bin/env python

import argparse
import hashlib
import sqlite3
import os
import pickle

import sys
import tqdm
from sklearn.feature_extraction.text import TfidfVectorizer
import sklearn.linear_model
import pandas

import getfilecontent
import schemasetup
import storage

parser = argparse.ArgumentParser()
parser.add_argument("--database", help="database file",
                    default="~/.athanasius.datafile")
actions = parser.add_subparsers()
actions.dest = "command"
actions.required = True

add_action = actions.add_parser("add",
                                help="Add a file to the corpus")
add_action.add_argument("--filename",
                        help="What file to add", required=True)
add_action.add_argument("--label",
                        help="What label to have for the file",
                        required=True)

remove_action = actions.add_parser(
    "remove",
    help="Remove a file / label from the corpus (not implemented yet)")
remove_action.add_argument(
    "--filename",
    help="What file to add",
    required=True)
remove_action.add_argument(
    "--label",
    help="What label to have for the file")

train_action = actions.add_parser(
    "train",
    help="Trigger a model retrain")

explain_action = actions.add_parser(
    "explain",
    help="Explain what rules predict a label"
    )
explain_action.add_argument(
    "--label",
    help="Which label to explain",
    required=True
    )
explain_action.add_argument(
    "--display-count",
    help="How many phrases to show (in descending order of significance)",
    default=10,
    type=int
    )

predict_action = actions.add_parser(
    "predict",
    help="Suggest the best label(s)"
)
predict_action.add_argument(
    "--filename",
    help="The file to label")

predict_action.add_argument(
    "--threshold",
    default=80,
    type=float,
    help="Percentage confidence in a label required for it to be displayed")
    

args = parser.parse_args()

db_conn = sqlite3.connect(os.path.expanduser(args.database))
cursor = db_conn.cursor()

schemasetup.create_tables_and_indexes(cursor)

if args.command == 'add':
    f = open(args.filename, 'rb')
    h = hashlib.sha256()
    # it would be smarter to do this next line chunk by chunk. Otherwise
    # large files will cause a problem
    h.update(f.read())
    checksum = h.hexdigest()
    path = os.path.abspath(args.filename)
    label = args.label.strip().upper()
    cursor.execute("update corpus set sha256 = ?, "
                   "last_update = current_timestamp where filename = ?",
                   [checksum, path])
    cursor.execute("update corpus set filename = ?, "
                   "last_update = current_timestamp where sha256 = ?",
                   [path, checksum])
    cursor.execute("select count(*) from corpus "
                   "where filename = ? and sha256 = ? and label = ?",
                   [path, checksum, label])
    if cursor.fetchone()[0] > 0:
        print("Label already present.")
    else:
        cursor.execute("insert into corpus (filename, sha256, label) "
                       "values (?,?,?)",
                       [path, checksum, label])
    db_conn.commit()
elif args.command == 'train':
    filecontents = []
    label_cursor = db_conn.cursor()
    filename_cursor = db_conn.cursor()
    presence_cursor = db_conn.cursor()

    filename_cursor.execute("select distinct filename "
                            "from corpus order by filename")
    progress_meter = tqdm.tqdm(filename_cursor)
    progress_meter.set_description("Vectorising file contents")
    filenames = []
    for filename_row in progress_meter:
        filename = filename_row[0]
        try:
            filecontents.append(getfilecontent.as_plain_text(filename))
            filenames.append(filename)
        except getfilecontent.Unimplemented:
            continue
        except FileNotFoundError:
            print("%s not found" % (filename,))
            continue
    vectoriser = TfidfVectorizer(ngram_range=(1, 3))
    vec = vectoriser.fit_transform(filecontents)
    cursor.execute("insert into vectorisers (vectoriser_pickle) values (?)",
                   [pickle.dumps(vectoriser)])
    db_conn.commit()
    cursor.execute("select vectoriser_id from vectorisers where "
                   "when_added = (select max(when_added) from vectorisers)")
    vectoriser_id = cursor.fetchone()[0]
    print("Stored the vectoriser as id = %s" % (str(vectoriser_id),))

    label_cursor.execute("select distinct label from corpus order by label")
    for label_row in label_cursor:
        label = label_row[0]
        positive_label_count = 0
        negative_label_count = 0
        labels = []
        progress_meter = tqdm.tqdm(filenames)
        for filename in progress_meter:
            presence_cursor.execute("select count(*) from corpus "
                                    "where filename = ? and label = ?",
                                    [filename, label])
            c = presence_cursor.fetchone()[0]
            if c > 0:
                labels.append(True)
                positive_label_count += 1
                progress_meter.set_description(
                    "%s %d/%d" % (label, positive_label_count,
                                  negative_label_count))
            else:
                labels.append(False)
                negative_label_count += 1
                progress_meter.set_description(
                    "%s %d/%d" % (label, positive_label_count,
                                  negative_label_count))
        if positive_label_count < 3 or negative_label_count < 3:
            print("Too few labels")
        lr = sklearn.linear_model.LogisticRegression(solver='lbfgs')
        lr.fit(vec, labels)
        # I should do some kind of model simplification here.
        # Now I need to save it somewhere.
        cursor.execute("insert into model_pickles "
                       " (vectoriser, labelname, model_pickle) "
                       " values (?, ?, ?)",
                       [vectoriser_id,
                        label,
                        pickle.dumps(lr)])
        db_conn.commit()
    db_conn.commit()
elif args.command == 'explain':
    (vectoriser_id, lr) = storage.get_model(cursor, args.label, verbose=True)
    tfidf = storage.get_vectoriser(cursor, vectoriser_id)
    strengths = pandas.DataFrame({
        'phrase': tfidf.get_feature_names(),
        'strength': lr.coef_[0]
        })
    strengths.sort_values('strength', inplace=True, ascending=False)
    interesting_entries = strengths[strengths.strength > 0]
    for idx in interesting_entries.head(args.display_count).index:
        s = interesting_entries.loc[idx].strength
        p = interesting_entries.loc[idx].phrase
        print(" - %0.2f %s" % (s, p))
elif args.command == 'predict':
    all_labels = storage.all_labels(cursor)
    try:
        content = getfilecontent.as_plain_text(args.filename)
    except getfilecontent.Unimplemented:
        sys.exit("Unimplemented")
    except FileNotFoundError:
        sys.exit("File not found")
    tfidf = None
    vectoriser_id = None
    found_a_label = False
    for label in all_labels:
        (this_vectoriser_id, lr) = storage.get_model(cursor, label)
        if this_vectoriser_id != vectoriser_id:
            tfidf = storage.get_vectoriser(cursor, this_vectoriser_id)
            vectoriser_id = this_vectoriser_id
        vec = tfidf.transform([content])
        prob = lr.predict_proba(vec)[0][1]
        if prob * 100 > args.threshold:
            found_a_label = True
            print("%1.f%% %s" % (prob * 100, label))
    if not found_a_label:
        print("No labels above %1.f%% threshold" % (args.threshold,))
    
