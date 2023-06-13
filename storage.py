import sys
import pickle


class NoSuchVectoriser(Exception):
    def __init__(self):
        pass


def get_vectoriser(cursor, vectoriser_id):
    cursor.execute("select vectoriser_pickle from vectorisers "
                   " where vectoriser_id = ?",
                   [vectoriser_id])
    row = cursor.fetchone()
    if row is None:
        sys.exit("Internal error: no vectoriser #%s" % (vectoriser_id,))
    tfidf = pickle.loads(row[0])
    return tfidf


def get_model(cursor, label, verbose=False):
    label = label.strip().upper()
    cursor.execute("select model_id, vectoriser, model_pickle, when_added "
                   " from model_pickles "
                   " where labelname = ? "
                   " order by when_added desc "
                   " limit 1", [label])
    row = cursor.fetchone()
    if row is None:
        sys.exit("Label %s not found" % (label,))
    [model_id, vectoriser, model_pickle, when_added] = row
    if verbose:
        print("Model #%s (created %s) - predicts %s" %
              (model_id, when_added, label))
    return vectoriser, pickle.loads(model_pickle)


def all_labels(cursor):
    cursor.execute("select distinct labelname from model_pickles")
    return [x[0] for x in cursor]
